"""Report generation: draft narrative from a validated analysis -> DOCX -> page check -> optional PDF.

Two entry points share the same checks and rendering:
  * generate_report()  – API mode: the server drafts the text with the Claude API (with condense loop);
  * submit_draft()     – Claude Code mode: the draft comes from the user's Claude Code session and is
                         accepted only if it passes the same verification-claim and page-limit checks.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
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
                "corrupted": "Corrupted", "duplicate": "Duplicate", "error": "Not processed",
                "awaiting_reading": "Not read"}
Progress = Callable[[float, str], None]


class DraftRejected(ReportBuildError):
    def __init__(self, message: str, details: dict):
        super().__init__(message)
        self.details = details


@dataclass
class ReportContext:
    case: Case
    run: AnalysisRun
    glob: dict
    books: list
    template: dict
    investigator: dict
    invoice: dict | None
    reference: ReferenceTemplate | None
    reference_docx: bytes | None
    inventory: list[dict]
    page_limit: int
    warnings: list[str] = field(default_factory=list)

    @property
    def analysis(self) -> dict:
        return self.run.result

    def word_budget(self, page_limit: int | None = None) -> int:
        pl = page_limit or self.page_limit
        return max(350, pl * get_settings().words_per_page - _fixed_overhead_words(self.analysis, self.inventory))


def _inventory(case: Case) -> list[dict]:
    return [{"ref": d.ref, "filename": d.original_filename, "type": d.doc_type,
             "status_label": STATUS_LABEL.get(d.status, d.status)}
            for d in sorted(case.documents, key=lambda d: d.ref) if d.status not in ("container",)]


def _fixed_overhead_words(analysis: dict, inventory: list[dict]) -> int:
    rows = len(analysis.get("chronology", [])) + 2 * len(analysis.get("discrepancies", [])) \
        + len(analysis.get("pending_verifications", [])) + len(inventory) * 0.6
    return int(160 + rows * 22)


def _word_count(draft: dict) -> int:
    return sum(len(p.split()) for s in draft.get("sections", []) for p in s.get("paragraphs", []))


def prepare_context(db: Session, case: Case, run: AnalysisRun | None, page_limit: int | None) -> ReportContext:
    if run is None or run.status != "completed":
        raise ReportBuildError("Analysis is not complete")
    if run.validation.get("errors"):
        raise ReportBuildError("Analysis has validation errors; rerun the analysis before generating a report")
    owner = db.get(User, case.owner_id)
    invoice = None
    if case.include_invoice:
        missing = validate_invoice(case.invoice or {})
        if missing:
            raise ReportBuildError("Invoice details missing: " + ", ".join(missing))
        invoice = case.invoice
    glob, books, _ = compose_for_case(db, case.category, case.additional_aspects or [])
    ref = (db.query(ReferenceTemplate).filter_by(category=case.category, active=True)
           .order_by(ReferenceTemplate.created_at.desc()).first()
           or db.query(ReferenceTemplate).filter_by(category="default", active=True)
           .order_by(ReferenceTemplate.created_at.desc()).first())
    return ReportContext(
        case=case, run=run, glob=glob, books=books, template=load_template(case.category),
        investigator=owner.investigator_profile or {}, invoice=invoice, reference=ref,
        reference_docx=get_storage().get(ref.storage_key) if ref else None, inventory=_inventory(case),
        page_limit=max(1, min(page_limit or case.page_limit or 7, 10)))


def check_draft(ctx: ReportContext, draft: dict) -> list[str]:
    """Structural + factual checks on a draft (both modes)."""
    problems = []
    keys = [s["key"] for s in ctx.template["sections"] if s.get("drafted", True)]
    got = {s.get("key") for s in draft.get("sections", [])}
    for k in keys:
        if k not in got:
            problems.append(f"Missing section '{k}'")
    for s in draft.get("sections", []):
        if s.get("key") not in keys:
            problems.append(f"Unknown section '{s.get('key')}' (allowed: {keys})")
        if not isinstance(s.get("paragraphs"), list) or not all(isinstance(p, str) for p in s.get("paragraphs", [])):
            problems.append(f"Section '{s.get('key')}' needs a list of paragraph strings")
    if problems:
        return problems
    text = "\n".join(p for sec in draft["sections"] for p in sec["paragraphs"])
    problems += unsupported_verification_claims(text, ctx.analysis)
    if re.search(r"\b[DN]\d{3}\b", text):
        problems.append("Refer to documents by description, not internal codes like D003/N001")
    return problems


def render(ctx: ReportContext, draft: dict) -> tuple[bytes, bytes | None, int, int]:
    """Return (docx, pdf, total_pages, report_pages_excluding_invoice)."""
    s = get_settings()
    docx = build_report(
        template=ctx.template, analysis=ctx.analysis, draft=draft, inventory=ctx.inventory,
        investigator=ctx.investigator, opinion_labels=ctx.glob.get("opinion_labels", {}), invoice=ctx.invoice,
        reference_docx=ctx.reference_docx,
        case=case_particulars(ctx.case) | {"report_date": date.today().isoformat()})
    pdf = docx_to_pdf(docx)
    if pdf is None:
        words = _word_count(draft) + _fixed_overhead_words(ctx.analysis, ctx.inventory)
        pages = -(-words // s.words_per_page) + (1 if ctx.invoice else 0)
        if "Page count estimated (LibreOffice not installed on server)" not in ctx.warnings:
            ctx.warnings.append("Page count estimated (LibreOffice not installed on server)")
    else:
        pages = count_pdf_pages(pdf)
    return docx, pdf, pages, pages - (1 if ctx.invoice else 0)


def _save(db: Session, ctx: ReportContext, rv: ReportVersion, draft: dict, docx: bytes, pdf: bytes | None,
          pages: int) -> None:
    case = ctx.case
    rv.draft = draft
    rv.page_count = pages
    rv.page_limit = ctx.page_limit
    rv.warnings = ctx.warnings
    rv.template_key = ctx.template["key"]
    rv.reference_template_id = ctx.reference.id if ctx.reference else None
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{case.claim_number or case.insured_name or 'case'}")[:60]
    rv.filename = f"Investigation_Report_{safe}_v{rv.version}"
    rv.docx_key = get_storage().put(docx, f"cases/{case.id}/reports")
    if pdf:
        rv.pdf_key = get_storage().put(pdf, f"cases/{case.id}/reports")
    rv.status = "completed"
    case.status = "report_ready"
    db.commit()


# ------------------------------------------------------------------ API mode
def _draft(ctx: ReportContext, budget_words: int, feedback: str = "") -> dict:
    content = [{"type": "text", "text": "\n\n".join([
        "## CASE PARTICULARS\n" + json.dumps(case_particulars(ctx.case), ensure_ascii=False),
        "## VALIDATED INVESTIGATION ANALYSIS\n" + fence_json("analysis", ctx.analysis),
        f"## WORD BUDGET\nAll drafted sections together must not exceed {budget_words} words.",
        feedback,
        "Return the report sections JSON.",
    ])}]
    res = get_llm().structured(purpose="report-draft", system=draft_system(ctx.glob, ctx.books, ctx.template),
                               content=content, schema=DRAFT_SCHEMA, max_tokens=32000)
    return res.data


def generate_report(db: Session, rv: ReportVersion, progress: Progress) -> None:
    case = db.get(Case, rv.case_id)
    ctx = prepare_context(db, case, db.get(AnalysisRun, rv.analysis_run_id), rv.page_limit)
    budget = ctx.word_budget()
    feedback = ""
    for attempt in range(3):
        progress(0.1 + attempt * 0.28, "Drafting report text" if attempt == 0 else "Condensing report to page limit")
        draft = _draft(ctx, budget, feedback)
        claims = check_draft(ctx, draft)
        if claims and attempt < 2:
            feedback = ("Your previous draft had these problems; fix them (rephrase unverified checks as "
                        "pending):\n- " + "\n- ".join(claims))
            continue
        ctx.warnings = list(claims)
        docx, pdf, pages, report_pages = render(ctx, draft)
        if report_pages <= ctx.page_limit:
            break
        budget = int(_word_count(draft) * ctx.page_limit / report_pages * 0.9)
        feedback = (f"The previous draft produced {report_pages} pages; the limit is {ctx.page_limit}. "
                    f"Condense to at most {budget} words without dropping decisive evidence.")
    else:
        ctx.warnings.append(f"Report is {pages} pages, above the {ctx.page_limit}-page limit after condensing")
    _save(db, ctx, rv, draft, docx, pdf, pages)
    progress(1.0, "Report ready")


# ------------------------------------------------------------------ Claude Code mode
def submit_draft(db: Session, rv: ReportVersion, draft: dict) -> None:
    """Accept a draft written in Claude Code. Raises DraftRejected with actionable details."""
    case = db.get(Case, rv.case_id)
    ctx = prepare_context(db, case, db.get(AnalysisRun, rv.analysis_run_id), rv.page_limit)
    problems = check_draft(ctx, draft)
    if problems:
        raise DraftRejected("Draft failed checks", {"problems": problems})
    docx, pdf, pages, report_pages = render(ctx, draft)
    if report_pages > ctx.page_limit:
        target = int(_word_count(draft) * ctx.page_limit / report_pages * 0.9)
        raise DraftRejected("Report is over the page limit", {
            "pages": report_pages, "page_limit": ctx.page_limit, "current_words": _word_count(draft),
            "target_words": target})
    _save(db, ctx, rv, draft, docx, pdf, pages)
