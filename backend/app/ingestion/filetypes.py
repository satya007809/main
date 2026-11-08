"""File-type sniffing by magic bytes (never trust extension alone)."""
from __future__ import annotations

import zipfile
import io

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
TEXT_EXT = {".txt", ".csv", ".log", ".md", ".json", ".xml", ".html", ".htm", ".eml", ".vcf"}
MEDIA_EXT = {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".mp3", ".m4a", ".wav", ".opus", ".ogg", ".aac", ".amr"}


def sniff(data: bytes, filename: str) -> str:
    """Return a coarse kind: pdf, docx, xlsx, pptx, zip, image, text, doc_legacy, xls_legacy, rar, 7z, media, unknown."""
    head = data[:16]
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return "corrupted_zip"
        if "word/document.xml" in names:
            return "docx"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "ppt/presentation.xml" in names:
            return "pptx"
        return "zip"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls_legacy" if ext in (".xls",) else "doc_legacy"
    if head.startswith(b"Rar!"):
        return "rar"
    if head.startswith(b"7z\xbc\xaf"):
        return "7z"
    if (head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG") or head[:4] in (b"GIF8",)
            or head.startswith(b"BM") or head[:4] in (b"II*\x00", b"MM\x00*")
            or (head[:4] == b"RIFF" and data[8:12] == b"WEBP") or data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1")):
        return "image"
    if ext in MEDIA_EXT or data[4:8] == b"ftyp":
        return "media"
    if ext in TEXT_EXT or _looks_text(data):
        return "text"
    if ext in IMAGE_EXT:
        return "image"  # extension says image but magic unknown -> extractor will report corruption
    return "unknown"


def _looks_text(data: bytes) -> bool:
    sample = data[:4096]
    if not sample or b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
