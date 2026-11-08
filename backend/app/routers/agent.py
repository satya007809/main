"""Endpoints used by the investigator's own Claude Code session (Max-plan mode).

Flow (driven by tools/bid_agent.py + .claude/skills/investigate-case):
  1. GET  /cases/{id}/analysis-package        instructions (global rules + playbooks), schema, evidence
  2. GET  /documents/{id}/pages/{n}/image     scanned page / photo to read
     PUT  /documents/{id}/pages/{n}/reading   transcription + English translation + visual description
  3. POST /cases/{id}/analyses/import         analysis JSON -> schema check + deterministic validation
  4. POST /cases/{id}/reports/draft           report text -> claim checks, page limit, DOCX/PDF
The server applies exactly the same validation as the automatic (API) mode; nothing is accepted on trust.
"""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from PIL import Image
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..db import get_db
from ..deps import current_user, owned_case
from ..engine.investigator import case_particulars, evidence_index, page_text
from ..engine.prompts import analysis_system, draft_system
from ..engine.schema import ANALYSIS_SCHEMA, DRAFT_SCHEMA
from ..engine.schema_check import check
from ..engine.validation import validate_analysis
from ..extraction.classifier import classify
from ..extraction.ocr import OCR_SCHEMA, OCR_SYSTEM
from ..models import AnalysisRun, Case, CaseNote, Document, DocumentPage, ReportVersion, User
from ..playbooks.store import compose_for_case
from ..reports.builder import ReportBuildError
from ..reports.generator import DraftRejected, prepare_context, submit_draft
from ..storage import get_storage

router = APIRouter(tags=["claude-code"])
SUBSCRIPTION_MODEL = "Claude Code (Claude subscription)"


@router.get("/config")
def config(user: User = Depends(current_user)):
    return {"ai_mode": get_settings().ai_mode}


def _pending_pages(case: Case) -> list[dict]:
    return [{"document_id": d.id, "ref": d.ref, "filename": d.original_filename, "page_no": p.page_no}
            for d in sorted(case.documents, key=lambda d: d.ref) if d.status == "awaiting_reading"
            for p in d.pages if p.method == "pending_ocr"]


@router.get("/cases/{case_id}/analysis-package")
def analysis_package(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    glob, books, used = compose_for_case(db, case.category, case.additional_aspects or [])
    docs = sorted(case.documents, key=lambda d: d.ref)
    notes = db.query(CaseNote).filter_by(case_id=case.id).order_by(CaseNote.ref).all()
    latest = (db.query(AnalysisRun).filter_by(case_id=case.id, status="completed")
              .order_by(AnalysisRun.run_no.desc()).first())
    from ..reports.builder import load_template
    template = load_template(case.category)
    budget = None
    if latest and not latest.validation.get("errors"):
        try:
            budget = prepare_context(db, case, latest, None).word_budget()
        except ReportBuildError:
            budget = None
    audit(db, "agent.package_downloaded", user.id, case.id)
    db.commit()
    return {
        "case_id": case.id,
        "case": case_particulars(case),
        "page_limit": case.page_limit,
        "include_invoice": case.include_invoice,
        "playbooks_used": used,
        "instructions": {
            "analysis_system_prompt": analysis_system(glob, books),
            "analysis_schema": ANALYSIS_SCHEMA,
            "required_checklist": [c["id"] for pb in books[:1] for c in pb.get("document_checklist", [])
                                   if c.get("required")],
            "page_reading_prompt": OCR_SYSTEM,
            "page_reading_schema": OCR_SCHEMA,
            "report_draft_prompt": draft_system(glob, books, template),
            "report_draft_schema": DRAFT_SCHEMA,
            "report_word_budget": budget,
        },
        "inventory": [{"ref": d.ref, "document_id": d.id, "filename": d.original_filename, "folder": d.source_path,
                       "type": d.doc_type, "status": d.status, "status_detail": d.status_detail,
                       "pages": d.page_count, "source_modified": d.source_modified_at,
                       "metadata": {k: v for k, v in (d.metadata_json or {}).items() if k in ("exif", "pdf_info")}}
                      for d in docs],
        "investigator_notes": [{"ref": n.ref, "kind": n.kind, "title": n.title, "body": n.body,
                                "verified_by": n.verified_by, "verified_on": n.verified_on, "target": n.target}
                               for n in notes],
        "documents": [{"ref": d.ref, "document_id": d.id, "filename": d.original_filename, "type": d.doc_type,
                       "pages": [{"page_no": p.page_no, "label": p.label, "method": p.method,
                                  "needs_reading": p.method == "pending_ocr", "text": page_text(p)}
                                 for p in d.pages]}
                      for d in docs if d.status in ("processed", "partial", "awaiting_reading")],
        "photos": [{"ref": d.ref, "document_id": d.id, "filename": d.original_filename}
                   for d in docs if d.status in ("processed", "partial", "awaiting_reading")
                   and (d.metadata_json or {}).get("kind") == "image"],
        "pending_pages": _pending_pages(case),
        "latest_analysis": {"run_id": latest.id, "run_no": latest.run_no, "validation": latest.validation}
        if latest else None,
    }


def _doc(doc_id: str, user: User, db: Session) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    owned_case(doc.case_id, user, db)
    return doc


@router.get("/documents/{doc_id}/pages/{page_no}/image")
def page_image(doc_id: str, page_no: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(doc_id, user, db)
    if not doc.storage_key:
        raise HTTPException(410, "Stored copy was deleted")
    data = get_storage().get(doc.storage_key)
    kind = (doc.metadata_json or {}).get("kind")
    try:
        if kind == "pdf":
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(data)
            if not 1 <= page_no <= len(pdf):
                raise HTTPException(404, "Page not found")
            img = pdf[page_no - 1].render(scale=200 / 72).to_pil()
        elif kind == "image":
            img = Image.open(io.BytesIO(data))
        else:
            raise HTTPException(400, "This document has no page images; use its extracted text")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Could not render page: {e}")
    img = img.convert("RGB")
    img.thumbnail((2000, 2000))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return Response(buf.getvalue(), media_type="image/jpeg")


@router.put("/documents/{doc_id}/pages/{page_no}/reading")
def page_reading(doc_id: str, page_no: int, body: dict, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    doc = _doc(doc_id, user, db)
    errors = check(body, OCR_SCHEMA)
    if errors:
        raise HTTPException(422, {"errors": errors})
    page = db.query(DocumentPage).filter_by(document_id=doc.id, page_no=page_no).one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    page.text_original, page.text_english = body["text_original"], body["text_english"]
    page.visual_description = body["visual_description"]
    page.language = ",".join(body["languages"])
    page.legible = body["legible"] or body["is_photograph"]
    page.method = "claude_code_vision"
    db.flush()
    pages = db.query(DocumentPage).filter_by(document_id=doc.id).all()
    if not any(p.method == "pending_ocr" for p in pages):
        bad = [p.page_no for p in pages if not p.legible]
        if bad and len(bad) == len(pages):
            doc.status, doc.status_detail = "unreadable", body.get("legibility_notes") or "All pages illegible"
        elif bad:
            doc.status, doc.status_detail = "partial", f"Unreadable pages: {', '.join(map(str, bad))}"
        else:
            doc.status, doc.status_detail = "processed", ""
        doc.languages = sorted({l for p in pages for l in (p.language or "").split(",") if l})
        if not doc.doc_type_corrected:
            text = "\n".join((p.text_english or p.text_original) + "\n" + p.visual_description for p in pages)
            doc.doc_type, doc.doc_type_confidence = classify(doc.original_filename, text,
                                                             is_photo=body["is_photograph"] and len(pages) == 1)
    audit(db, "agent.page_read", user.id, doc.case_id, ref=doc.ref, page=page_no)
    db.commit()
    return {"ref": doc.ref, "page_no": page_no, "document_status": doc.status, "doc_type": doc.doc_type,
            "remaining_pages": len(_pending_pages(db.get(Case, doc.case_id)))}


@router.post("/cases/{case_id}/analyses/import")
def import_analysis(case_id: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    pending = _pending_pages(case)
    if pending:
        raise HTTPException(409, {"message": "Read the pending scanned pages/photos first", "pending_pages": pending})
    analysis = body.get("analysis")
    if not isinstance(analysis, dict):
        raise HTTPException(422, {"errors": ["Body must be {\"analysis\": {...}}"]})
    schema_errors = check(analysis, ANALYSIS_SCHEMA)
    if schema_errors:
        return JSONResponse({"accepted": False, "schema_errors": schema_errors}, status_code=422)
    _, books, used = compose_for_case(db, case.category, case.additional_aspects or [])
    required = [c["id"] for pb in books[:1] for c in pb.get("document_checklist", []) if c.get("required")]
    idx = evidence_index(db, case)
    val = validate_analysis(analysis, idx, required)
    n = db.query(func.count(AnalysisRun.id)).filter_by(case_id=case.id).scalar() or 0
    run = AnalysisRun(case_id=case.id, run_no=n + 1, status="completed", model=SUBSCRIPTION_MODEL,
                      playbooks_used=used, document_refs=sorted(idx.docs), note_refs=sorted(idx.notes),
                      result=analysis, validation=val.as_dict(), usage={})
    db.add(run)
    if not val.errors:
        could_change = [p for p in analysis.get("pending_verifications", []) if p["impact"] == "could_change_opinion"]
        case.status = "pending_verification" if could_change else "analysed"
    audit(db, "analysis.completed", user.id, case.id, run_no=run.run_no, model=SUBSCRIPTION_MODEL,
          playbooks=used, documents=run.document_refs, validation_ok=not val.errors)
    db.commit()
    return {"accepted": not val.errors, "run_id": run.id, "run_no": run.run_no, "validation": val.as_dict()}


@router.post("/cases/{case_id}/reports/draft")
def import_report_draft(case_id: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    q = db.query(AnalysisRun).filter_by(case_id=case.id, status="completed")
    run = q.filter_by(id=body["analysis_run_id"]).first() if body.get("analysis_run_id") else \
        q.order_by(AnalysisRun.run_no.desc()).first()
    if not run:
        raise HTTPException(400, "Submit an accepted analysis first")
    draft = {"sections": body.get("sections")}
    errors = check(draft, DRAFT_SCHEMA)
    if errors:
        return JSONResponse({"accepted": False, "problems": errors}, status_code=422)
    page_limit = body.get("page_limit") or case.page_limit
    if not isinstance(page_limit, int) or not 1 <= page_limit <= 10:
        raise HTTPException(422, "page_limit must be 1-10")
    n = db.query(func.count(ReportVersion.id)).filter_by(case_id=case.id).scalar() or 0
    rv = ReportVersion(case_id=case.id, analysis_run_id=run.id, version=n + 1, page_limit=page_limit, status="running")
    db.add(rv)
    db.flush()
    try:
        submit_draft(db, rv, draft)
    except DraftRejected as e:
        db.rollback()
        return JSONResponse({"accepted": False, "message": str(e), **e.details}, status_code=422)
    except ReportBuildError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    audit(db, "report.generated", user.id, case.id, version=rv.version, analysis_run=run.run_no,
          pages=rv.page_count, template=rv.template_key, source="claude_code")
    db.commit()
    return {"accepted": True, "report_id": rv.id, "version": rv.version, "pages": rv.page_count,
            "warnings": rv.warnings, "filename": rv.filename}
