"""Report generation: draft narrative from a validated analysis -> DOCX -> page check -> optional PDF."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date

from sqlalchemy.orm import Session

from ..config import get_settings
from ..engine.investigator import case_particulars
from ..engine.prompts import draft_system, fence_json
from ..engine.schema import DRAFT_SCHEMA
from ..engine.validation import unsupported_verification_claims
from ..llm.client import get_llm
from ..models import AnalysisRun, Case, ReferenceTemplate, ReportVersion, User
from ..playbooks.store import compose_for_case
from ..storage import get_storage
from .builder import (ReportBuildError, build_report, count_pdf_pages, docx_to_pdf, load_template,
                      validate_invoice)

STATUS_LABEL = {"processed": "Examined", "partial": "Partly legible", "unreadable": "Unreadable",
                "password_protected": "Password protected", "unsupported": "Not analysable",
                "corrupted": "Corrupted", "duplicate": "Duplicate", "error": "Not processed"}
Progress = Callable[[float, str], None]


def _inventory(case: Case) -> list[dict]:
    return [{"ref": d.ref, "filename": d.original_filename, "type": d.doc_type,
             "status_label": STATUS_LABEL.get(d.status, d.status)}
            for d in sorted(case.documents, key=lambda d: d.ref) if d.status not in ("container",)]


def _fixed_overhead_words(analysis: dict, inventory: list[dict]) -> int:
    rows = len(analysis.get("chronology", [])) + 2 * len(analysis.get("discrepancies", [])) \
        + len(analysis.get("pending_verifications", [])) + len(inventory) * 0.6
    return int(160 + rows * 22)


def _draft(glob, books, template, case: Case, analysis: dict, budget_words: int, feedback: str = "") -> dict:
    content = [{"type": "text", "text": "\n\n".join([
        "## CASE PARTICULARS\n" + json.dumps(case_particulars(case), ensure_ascii=False),
        "## VALIDATED INVESTIGATION ANALYSIS\n" + fence_json("analysis", analysis),
        f"## WORD BUDGET\nAll drafted sections together must not exceed {budget_words} words.",
        feedback,
        "Return the report sections JSON.",
    ])}]
    res = get_llm().structured(purpose="report-draft", system=draft_system(glob, books, template),
                               content=content, schema=DRAFT_SCHEMA, max_tokens=32000)
    return res.data


def _word_count(draft: dict) -> int:
    return sum(len(p.split()) for s in draft.get("sections", []) for p in s.get("paragraphs", []))


def generate_report(db: Session, rv: ReportVersion, progress: Progress) -> None:
    s = get_settings()
    case = db.get(Case, rv.case_id)
    run = db.get(AnalysisRun, rv.analysis_run_id)
    if run is None or run.status != "completed":
        raise ReportBuildError("Analysis is not complete")
    if run.validation.get("errors"):
        raise ReportBuildError("Analysis has validation errors; rerun the analysis before generating a report")
    owner = db.get(User, case.owner_id)
    investigator = owner.investigator_profile or {}
    invoice = None
    if case.include_invoice:
        missing = validate_invoice(case.invoice or {})
        if missing:
            raise ReportBuildError("Invoice details missing: " + ", ".join(missing))
        invoice = case.invoice
    glob, books, _ = compose_for_case(db, case.category, case.additional_aspects or [])
    template = load_template(case.category)
    ref = (db.query(ReferenceTemplate).filter_by(category=case.category, active=True)
           .order_by(ReferenceTemplate.created_at.desc()).first()
           or db.query(ReferenceTemplate).filter_by(category="default", active=True)
           .order_by(ReferenceTemplate.created_at.desc()).first())
    reference_docx = get_storage().get(ref.storage_key) if ref else None
    rv.reference_template_id = ref.id if ref else None
    rv.template_key = template["key"]
    analysis = run.result
    inventory = _inventory(case)
    page_limit = max(1, min(rv.page_limit or 7, 10))
    budget = max(350, page_limit * s.words_per_page - _fixed_overhead_words(analysis, inventory))
    warnings: list[str] = []
    feedback = ""
    docx = pdf = None
    pages = 0
    for attempt in range(3):
        progress(0.1 + attempt * 0.28, "Drafting report text" if attempt == 0 else "Condensing report to page limit")
        draft = _draft(glob, books, template, case, analysis, budget, feedback)
        text = "\n".join(p for sec in draft["sections"] for p in sec["paragraphs"])
        claims = unsupported_verification_claims(text, analysis)
        if claims and attempt < 2:
            feedback = ("Your previous draft contained verification claims not supported by the analysis. "
                        "Remove or rephrase them as pending:\n- " + "\n- ".join(claims))
            continue
        warnings = [c for c in claims]
        docx = build_report(
            template=template, analysis=analysis, draft=draft, inventory=inventory, investigator=investigator,
            opinion_labels=glob.get("opinion_labels", {}), invoice=invoice, reference_docx=reference_docx,
            case=case_particulars(case) | {"report_date": date.today().isoformat()})
        pdf = docx_to_pdf(docx)
        if pdf is None:
            words = _word_count(draft) + _fixed_overhead_words(analysis, inventory)
            pages = -(-words // s.words_per_page) + (1 if invoice else 0)
            warnings.append("Page count estimated (LibreOffice not installed on server)")
        else:
            pages = count_pdf_pages(pdf)
        report_pages = pages - (1 if invoice else 0)
        if report_pages <= page_limit:
            break
        budget = int(_word_count(draft) * page_limit / report_pages * 0.9)
        feedback = (f"The previous draft produced {report_pages} pages; the limit is {page_limit}. "
                    f"Condense to at most {budget} words without dropping decisive evidence.")
    else:
        warnings.append(f"Report is {pages} pages, above the {page_limit}-page limit after condensing")
    rv.draft = draft
    rv.page_count = pages
    rv.warnings = warnings
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{case.claim_number or case.insured_name or 'case'}")[:60]
    rv.filename = f"Investigation_Report_{safe}_v{rv.version}"
    rv.docx_key = get_storage().put(docx, f"cases/{case.id}/reports")
    if pdf:
        rv.pdf_key = get_storage().put(pdf, f"cases/{case.id}/reports")
    rv.status = "completed"
    case.status = "report_ready"
    db.commit()
    progress(1.0, "Report ready")
