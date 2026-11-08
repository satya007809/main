"""Per-format text extraction. Every page/sheet/image is kept separately so findings can cite it."""
from __future__ import annotations

import email
import io
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from email import policy
from pathlib import Path

from PIL import ExifTags, Image, UnidentifiedImageError

from ..config import get_settings
from .ocr import ocr_image

log = logging.getLogger(__name__)
MIN_TEXT_LAYER_CHARS = 40  # below this a PDF page is treated as scanned and OCR'd
_INDIC = re.compile(r"[ऀ-෿]")  # Devanagari .. Sinhala blocks (covers Telugu, Kannada, Tamil, ...)

try:  # optional HEIC support (iPhone photos)
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
except Exception:  # pragma: no cover
    pass


@dataclass
class PageOut:
    page_no: int
    text_original: str = ""
    text_english: str = ""
    method: str = "native"
    language: str = ""
    visual_description: str = ""
    legible: bool = True
    label: str = ""


@dataclass
class Extraction:
    status: str = "processed"  # processed | partial | unreadable | password_protected | unsupported | corrupted
    detail: str = ""
    pages: list[PageOut] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    is_photo: bool = False

    @property
    def text(self) -> str:
        return "\n".join((p.text_english or p.text_original) + "\n" + p.visual_description for p in self.pages)


def _finalise(ex: Extraction) -> Extraction:
    if ex.status != "processed":
        return ex
    if not ex.pages:
        ex.status, ex.detail = "unreadable", "No readable content found"
        return ex
    illegible = [p.page_no for p in ex.pages if not p.legible]
    if illegible and len(illegible) == len(ex.pages):
        ex.status, ex.detail = "unreadable", "All pages illegible"
    elif illegible:
        ex.status, ex.detail = "partial", f"Unreadable pages: {', '.join(map(str, illegible))}"
    return ex


def _mark_lang(p: PageOut) -> PageOut:
    if not p.language:
        p.language = "indic" if _INDIC.search(p.text_original or "") else ("en" if p.text_original.strip() else "")
    return p


# ------------------------------------------------------------------ PDF
def extract_pdf(data: bytes, ref: str) -> Extraction:
    from pypdf import PdfReader
    from pypdf.errors import FileNotDecryptedError, PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    return Extraction("password_protected", "PDF is password protected")
            except Exception:
                return Extraction("password_protected", "PDF is password protected")
        n = len(reader.pages)
    except FileNotDecryptedError:
        return Extraction("password_protected", "PDF is password protected")
    except (PdfReadError, ValueError, KeyError, OSError) as e:
        return Extraction("corrupted", f"PDF could not be opened: {e}")
    ex = Extraction(metadata={"pdf_info": {k: str(v) for k, v in (reader.metadata or {}).items()}})
    pdfium_doc = None
    for i in range(n):
        try:
            txt = reader.pages[i].extract_text() or ""
        except Exception as e:  # damaged page
            log.warning("pdf page %s failed: %s", i + 1, e)
            txt = ""
        if len(txt.strip()) >= MIN_TEXT_LAYER_CHARS:
            ex.pages.append(_mark_lang(PageOut(i + 1, text_original=txt, method="text_layer")))
            continue
        # scanned page -> render and OCR
        try:
            if pdfium_doc is None:
                import pypdfium2 as pdfium
                pdfium_doc = pdfium.PdfDocument(data)
            img = pdfium_doc[i].render(scale=200 / 72).to_pil()
            o = ocr_image(img, context=f"{ref} page {i + 1}")
            ex.pages.append(PageOut(i + 1, o.text_original, o.text_english, o.method, ",".join(o.languages),
                                    o.visual_description, o.legible))
        except Exception as e:
            log.warning("ocr failed for %s p%s: %s", ref, i + 1, e)
            ex.pages.append(PageOut(i + 1, text_original=txt, method="failed", legible=False))
    return _finalise(ex)


# ------------------------------------------------------------------ Office
def extract_docx(data: bytes) -> Extraction:
    import docx

    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as e:
        return Extraction("corrupted", f"Word file could not be opened: {e}")
    lines = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells]
            lines.append(" | ".join(cells))
    text = "\n".join(lines)
    ex = Extraction(pages=[_mark_lang(PageOut(1, text_original=text, method="native", label="document"))])
    if not text.strip():
        ex.status, ex.detail = "unreadable", "Word file contains no text (may contain only images)"
    return ex


def extract_xlsx(data: bytes) -> Extraction:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:
        msg = str(e).lower()
        if "encrypt" in msg or "password" in msg:
            return Extraction("password_protected", "Excel file is password protected")
        return Extraction("corrupted", f"Excel file could not be opened: {e}")
    ex = Extraction()
    for idx, ws in enumerate(wb.worksheets, start=1):
        rows = []
        for row in ws.iter_rows(values_only=True):
            if any(v not in (None, "") for v in row):
                rows.append(" | ".join("" if v is None else str(v) for v in row))
            if len(rows) > 5000:
                rows.append("[... sheet truncated at 5000 rows for analysis ...]")
                break
        ex.pages.append(_mark_lang(PageOut(idx, text_original="\n".join(rows), method="native", label=ws.title)))
    return _finalise(ex)


def convert_legacy_office(data: bytes, suffix: str, target: str) -> bytes | None:
    """Convert .doc/.xls using LibreOffice if present on the server."""
    soffice = shutil.which(get_settings().soffice_path)
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"in{suffix}"
        src.write_bytes(data)
        subprocess.run([soffice, "--headless", "--convert-to", target, "--outdir", td, str(src)],
                       capture_output=True, timeout=180)
        out = Path(td) / f"in.{target}"
        return out.read_bytes() if out.exists() else None


# ------------------------------------------------------------------ images
def _exif(img: Image.Image) -> dict:
    out: dict = {}
    try:
        raw = img.getexif()
    except Exception:
        return out
    if not raw:
        return out
    tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in raw.items()}
    for k in ("DateTime", "Make", "Model", "Software"):
        if k in tags:
            out[k] = str(tags[k])
    try:
        sub = raw.get_ifd(0x8769)  # Exif IFD
        for k, v in sub.items():
            name = ExifTags.TAGS.get(k, str(k))
            if name in ("DateTimeOriginal", "DateTimeDigitized", "OffsetTimeOriginal"):
                out[name] = str(v)
        gps = raw.get_ifd(0x8825)
        if gps:
            g = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in gps.items()}

            def deg(vals, ref):
                d, m, s = (float(x) for x in vals)
                val = d + m / 60 + s / 3600
                return -val if ref in ("S", "W") else val

            if "GPSLatitude" in g and "GPSLongitude" in g:
                out["GPSLatitude"] = round(deg(g["GPSLatitude"], g.get("GPSLatitudeRef", "N")), 6)
                out["GPSLongitude"] = round(deg(g["GPSLongitude"], g.get("GPSLongitudeRef", "E")), 6)
            if "GPSDateStamp" in g:
                out["GPSDateStamp"] = str(g["GPSDateStamp"])
    except Exception:
        pass
    return out


def extract_image(data: bytes, ref: str) -> Extraction:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as e:
        return Extraction("corrupted", f"Image could not be decoded: {e}")
    meta = {"exif": _exif(img), "width": img.width, "height": img.height, "format": img.format}
    try:
        o = ocr_image(img, context=ref)
    except Exception as e:
        log.warning("image ocr failed %s: %s", ref, e)
        return Extraction("error", f"Image analysis failed: {e}", metadata=meta)
    ex = Extraction(metadata=meta, is_photo=o.is_photograph,
                    pages=[PageOut(1, o.text_original, o.text_english, o.method, ",".join(o.languages),
                                   o.visual_description, o.legible or o.is_photograph, label="image")])
    if not o.legible and not o.is_photograph:
        ex.status, ex.detail = "unreadable", o.notes or "Image text not legible"
    return ex


# ------------------------------------------------------------------ text / email
def extract_text(data: bytes, filename: str) -> Extraction:
    if filename.lower().endswith(".eml"):
        msg = email.message_from_bytes(data, policy=policy.default)
        body = msg.get_body(preferencelist=("plain", "html"))
        text = (f"From: {msg['from']}\nTo: {msg['to']}\nDate: {msg['date']}\nSubject: {msg['subject']}\n\n"
                + (body.get_content() if body else ""))
    else:
        for enc in ("utf-8-sig", "utf-16", "cp1252"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = data.decode("utf-8", "replace")
    return _finalise(Extraction(pages=[_mark_lang(PageOut(1, text_original=text, method="native"))]))


def extract(kind: str, data: bytes, filename: str, ref: str) -> Extraction:
    if kind == "pdf":
        return extract_pdf(data, ref)
    if kind == "docx":
        return extract_docx(data)
    if kind == "xlsx":
        return extract_xlsx(data)
    if kind == "image":
        return extract_image(data, ref)
    if kind == "text":
        return extract_text(data, filename)
    if kind in ("doc_legacy", "xls_legacy", "pptx"):
        target = {"doc_legacy": "docx", "xls_legacy": "xlsx", "pptx": "pdf"}[kind]
        converted = convert_legacy_office(data, Path(filename).suffix or ".bin", target)
        if converted is None:
            return Extraction("unsupported", f"{kind} needs LibreOffice on the server for conversion")
        return extract({"docx": "docx", "xlsx": "xlsx", "pdf": "pdf"}[target], converted, filename, ref)
    if kind in ("rar", "7z"):
        return Extraction("unsupported", f"{kind.upper()} archives are not supported; please re-upload as ZIP")
    if kind == "media":
        return Extraction("unsupported", "Audio/video files are listed but not analysed; add a note with key content")
    if kind == "corrupted_zip":
        return Extraction("corrupted", "ZIP archive is damaged")
    return Extraction("unsupported", "Unrecognised file format")
