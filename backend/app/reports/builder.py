"""DOCX report rendering with python-docx.

Defaults: Times New Roman 13 pt, 1.5 line spacing, A4. When the investigator has uploaded a reference report
(e.g. OD_report.docx) for the category, it is used as the base document so its header, footer, letterhead,
margins and styles are preserved; the body is replaced with the new report.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import yaml
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from ..config import get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"
CATEGORY_TEMPLATE = {"own_damage": "own_damage", "pa_death": "pa_death", "pa_injury": "pa_injury",
                     "theft": "theft", "fire": "fire"}
INVOICE_REQUIRED = ["invoice_number", "invoice_date", "bill_to", "items"]


class ReportBuildError(ValueError):
    pass


def load_template(category: str) -> dict:
    key = CATEGORY_TEMPLATE.get(category, "general")
    return yaml.safe_load((TEMPLATES_DIR / f"{key}.yaml").read_text(encoding="utf-8"))


def fmt_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except Exception:
        return iso


def _set_font(run_or_style, name: str, size: float | None = None, bold: bool | None = None):
    font = run_or_style.font
    font.name = name
    if size:
        font.size = Pt(size)
    if bold is not None:
        font.bold = bold
    el = run_or_style.element if hasattr(run_or_style, "element") else run_or_style._element
    rpr = el.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), name)


def _base_document(reference_docx: bytes | None) -> Document:
    if reference_docx:
        doc = Document(io.BytesIO(reference_docx))
        body = doc.element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)
        return doc
    doc = Document()
    for s in doc.sections:
        s.page_height, s.page_width = Cm(29.7), Cm(21.0)
        s.top_margin = s.bottom_margin = Cm(2.2)
        s.left_margin, s.right_margin = Cm(2.5), Cm(2.2)
    return doc


def _apply_format(doc: Document, fmt: dict) -> None:
    name, size, spacing = fmt.get("font", "Times New Roman"), fmt.get("size", 13), fmt.get("line_spacing", 1.5)
    for style_name in ("Normal", "Table Grid", "List Bullet"):
        try:
            st = doc.styles[style_name]
        except KeyError:
            continue
        _set_font(st, name, size)
        pf = st.paragraph_format
        pf.line_spacing = spacing if style_name != "Table Grid" else 1.0
        pf.space_after = Pt(4)
        pf.space_before = Pt(0)


class ReportWriter:
    def __init__(self, fmt: dict, reference_docx: bytes | None = None):
        self.fmt = {"font": "Times New Roman", "size": 13, "line_spacing": 1.5, **(fmt or {})}
        self.doc = _base_document(reference_docx)
        _apply_format(self.doc, self.fmt)

    # ---------------------------------------------------------------- primitives
    def para(self, text: str = "", bold: bool = False, align=None, size: float | None = None, italic=False,
             space_after: float | None = None):
        p = self.doc.add_paragraph()
        p.paragraph_format.line_spacing = self.fmt["line_spacing"]
        if align is not None:
            p.alignment = align
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if space_after is not None:
            p.paragraph_format.space_after = Pt(space_after)
        if text:
            r = p.add_run(text)
            _set_font(r, self.fmt["font"], size or self.fmt["size"], bold)
            r.italic = italic
        return p

    def heading(self, text: str):
        p = self.para(text, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=2)
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(6)
        return p

    def table(self, headers: list[str], rows: list[list[str]], widths_cm: list[float] | None = None):
        t = self.doc.add_table(rows=1, cols=len(headers))
        try:
            t.style = self.doc.styles["Table Grid"]
        except KeyError:
            pass
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        size = self.fmt["size"] - 2
        trpr = t.rows[0]._tr.get_or_add_trPr()
        hdr = OxmlElement("w:tblHeader")  # repeat header row on each page
        hdr.set(qn("w:val"), "true")
        trpr.append(hdr)
        for i, h in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = ""
            r = cell.paragraphs[0].add_run(h)
            _set_font(r, self.fmt["font"], size, True)
        for row in rows:
            cells = t.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = ""
                r = cells[i].paragraphs[0].add_run(str(val))
                _set_font(r, self.fmt["font"], size)
                cells[i].paragraphs[0].paragraph_format.line_spacing = 1.0
        if widths_cm:
            t.autofit = False
            for i, wd in enumerate(widths_cm):
                t.columns[i].width = Cm(wd)
            for row in t.rows:
                for i, w in enumerate(widths_cm):
                    row.cells[i].width = Cm(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(0)
        return t

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def to_bytes(self) -> bytes:
        buf = io.BytesIO()
        self.doc.save(buf)
        return buf.getvalue()


def build_report(*, template: dict, case: dict, analysis: dict, draft: dict, inventory: list[dict],
                 investigator: dict, opinion_labels: dict, invoice: dict | None,
                 reference_docx: bytes | None = None) -> bytes:
    w = ReportWriter(template.get("format", {}), reference_docx)
    w.para(template["title"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=w.fmt["size"] + 1)
    w.para(f"Date: {fmt_date(case.get('report_date') or date.today().isoformat())}", align=WD_ALIGN_PARAGRAPH.RIGHT)
    particulars = [
        ("Insurer", case.get("insurer")), ("Claim No.", case.get("claim_number")),
        ("Policy No.", case.get("policy_number")), ("Insured", case.get("insured_name")),
        ("Vehicle Regn. No.", case.get("vehicle_registration")),
        ("Investigation Ref.", case.get("investigation_reference")),
        ("Date of Investigation", fmt_date(case.get("investigation_date") or "")),
    ]
    w.table(["Particular", "Details"], [[k, v] for k, v in particulars if v], [5.5, 10.5])

    drafted = {s["key"]: s for s in draft.get("sections", [])}
    for sec in template["sections"]:
        table = sec.get("table")
        if table == "chronology":
            rows = [[c["date"], c["time"], c["event"]] for c in analysis.get("chronology", [])]
            if not rows:
                continue
            w.heading(sec["heading"])
            w.table(["Date", "Time", "Event"], rows, [3.0, 2.2, 10.8])
        elif table == "discrepancies":
            rows = [[d["point"], d["version_a"], d["version_b"], d["significance"].title()]
                    for d in analysis.get("discrepancies", [])]
            w.heading(sec["heading"])
            if rows:
                w.table(["Point", "Version / Record A", "Version / Record B", "Significance"], rows, [3.2, 5.2, 5.2, 2.4])
            else:
                w.para("No material discrepancy was observed in the documents examined.")
        elif table == "pending":
            items = analysis.get("pending_verifications", [])
            if not items:
                continue
            w.heading(sec["heading"])
            for i, p in enumerate(items, 1):
                w.para(f"{i}. {p['item']} – {p['reason']}", space_after=1)
        elif table == "documents":
            rows = [[d["filename"], d["type"].replace("_", " ").title(), d["status_label"]] for d in inventory]
            w.page_break() if len(rows) > 25 else None
            w.heading(sec["heading"])
            w.table(["Document", "Type", "Status"], rows, [8.5, 4.5, 3.0])
        else:
            body = drafted.get(sec["key"])
            if sec.get("opinion"):
                w.heading(sec["heading"])
                label = opinion_labels.get(analysis["opinion"]["verdict"], "")
                if label:
                    w.para(label, bold=True)
                for ptxt in (body or {}).get("paragraphs", []):
                    w.para(ptxt)
                _signature(w, investigator)
                continue
            if not body or not body.get("paragraphs"):
                continue
            w.heading(sec["heading"])
            for ptxt in body["paragraphs"]:
                w.para(ptxt)

    if invoice is not None:
        _invoice(w, invoice, case, investigator)
    return w.to_bytes()


def _signature(w: ReportWriter, investigator: dict) -> None:
    """Signature block using only details stored in the investigator profile (never generated)."""
    lines = [investigator.get(k) for k in ("name", "designation", "licence_number", "address", "phone", "email")]
    lines = [x for x in lines if x]
    if not lines and not investigator.get("firm"):
        return
    block = []
    if investigator.get("firm"):
        block.append(w.para("For " + investigator["firm"], align=WD_ALIGN_PARAGRAPH.LEFT, space_after=0))
    block.append(w.para("", align=WD_ALIGN_PARAGRAPH.LEFT))  # space for signature / seal
    for line in lines:
        block.append(w.para(line, align=WD_ALIGN_PARAGRAPH.LEFT, space_after=0))
    for p in block[:-1]:
        p.paragraph_format.keep_with_next = True
    block[0].paragraph_format.space_before = Pt(12)


def validate_invoice(invoice: dict) -> list[str]:
    missing = [f for f in INVOICE_REQUIRED if not invoice.get(f)]
    for i, item in enumerate(invoice.get("items") or [], 1):
        if not item.get("description") or item.get("amount") in (None, ""):
            missing.append(f"items[{i}] description/amount")
    return missing


def _invoice(w: ReportWriter, inv: dict, case: dict, investigator: dict) -> None:
    w.page_break()
    w.para("INVOICE", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=w.fmt["size"] + 1)
    header = [("Invoice No.", inv["invoice_number"]), ("Invoice Date", fmt_date(inv["invoice_date"])),
              ("Bill To", inv["bill_to"]), ("Claim No.", case.get("claim_number")),
              ("Insured", case.get("insured_name")), ("Vehicle", case.get("vehicle_registration"))]
    if investigator.get("gstin"):
        header.append(("Investigator GSTIN", investigator["gstin"]))
    if inv.get("bill_to_gstin"):
        header.append(("Insurer GSTIN", inv["bill_to_gstin"]))
    w.table(["Particular", "Details"], [[k, v] for k, v in header if v], [5.5, 10.5])
    rows, subtotal = [], 0.0
    for i, item in enumerate(inv["items"], 1):
        amt = float(item["amount"])
        subtotal += amt
        rows.append([str(i), item["description"], f"{amt:,.2f}"])
    total = subtotal
    if inv.get("gst_percent"):
        gst = round(subtotal * float(inv["gst_percent"]) / 100, 2)
        rows.append(["", f"GST @ {inv['gst_percent']}%", f"{gst:,.2f}"])
        total += gst
    rows.append(["", "TOTAL (INR)", f"{total:,.2f}"])
    w.table(["S.No.", "Description", "Amount (INR)"], rows, [1.6, 10.4, 4.0])
    bank = investigator.get("bank_details") or inv.get("bank_details")
    if bank:
        w.para("Bank details: " + bank, align=WD_ALIGN_PARAGRAPH.LEFT)
    if investigator.get("name"):
        w.para("")
        w.para(investigator["name"], align=WD_ALIGN_PARAGRAPH.LEFT)


def docx_to_pdf(docx_bytes: bytes) -> bytes | None:
    soffice = shutil.which(get_settings().soffice_path)
    if not soffice:
        return None
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "report.docx"
        src.write_bytes(docx_bytes)
        subprocess.run([soffice, "--headless", f"-env:UserInstallation=file://{td}/lo", "--convert-to", "pdf",
                        "--outdir", td, str(src)], capture_output=True, timeout=240)
        out = Path(td) / "report.pdf"
        return out.read_bytes() if out.exists() else None


def count_pdf_pages(pdf: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(pdf)).pages)
