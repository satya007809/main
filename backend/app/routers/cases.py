from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..connectors.base import ConnectorError
from ..connectors.registry import detect_provider, get_connector
from ..db import get_db
from ..deps import client_ip, current_user, owned_case
from ..ingestion.scanner import next_ref
from ..jobs.queue import enqueue
from ..models import AnalysisRun, AuditLog, Case, CaseNote, Document, DocumentPage, Job, User
from ..schemas import (AnalysisOut, AnalysisSummary, CaseIn, CaseOut, CasePatch, DocumentDetail, DocumentOut,
                       DocumentPatch, JobOut, NoteIn, NoteOut)
from ..storage import get_storage

router = APIRouter(tags=["cases"])
DASHBOARD_GROUPS = {
    "new": ["new", "scanned", "failed"],
    "processing": ["scanning", "analysing"],
    "reports_ready": ["report_ready"],
    "pending_verification": ["pending_verification", "analysed"],
    "completed": ["completed"],
}


def _out(db: Session, case: Case) -> CaseOut:
    n = db.query(func.count(Document.id)).filter(Document.case_id == case.id).scalar()
    return CaseOut.model_validate(case).model_copy(update={"document_count": n})


def _resolve_link(db: Session, user: User, case: Case, link: str) -> None:
    if not link:
        case.source_link, case.source_provider, case.source_folder_id = "", "", ""
        return
    try:
        provider = detect_provider(link)
        conn = get_connector(db, user.id, provider)
        case.source_folder_id = conn.parse_link(link)
    except ConnectorError as e:
        raise HTTPException(400, str(e))
    case.source_link, case.source_provider = link, provider


# ------------------------------------------------------------------ dashboard & cases
@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Case.status, func.count(Case.id)).filter(Case.owner_id == user.id).group_by(Case.status).all()
    by_status = dict(rows)
    return {"groups": {g: sum(by_status.get(s, 0) for s in sts) for g, sts in DASHBOARD_GROUPS.items()},
            "by_status": by_status}


@router.get("/cases", response_model=list[CaseOut])
def list_cases(group: str | None = None, q: str | None = None, date_from: str | None = None,
               date_to: str | None = None, limit: int = Query(100, le=500),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    qry = db.query(Case).filter(Case.owner_id == user.id)
    if group:
        qry = qry.filter(Case.status.in_(DASHBOARD_GROUPS.get(group, [group])))
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(Case.claim_number.ilike(like), Case.vehicle_registration.ilike(like),
                             Case.insured_name.ilike(like), Case.insurer_name.ilike(like),
                             Case.policy_number.ilike(like), Case.investigation_reference.ilike(like)))
    if date_from:
        qry = qry.filter(Case.investigation_date >= date_from)
    if date_to:
        qry = qry.filter(Case.investigation_date <= date_to)
    return [_out(db, c) for c in qry.order_by(Case.updated_at.desc()).limit(limit)]


@router.post("/cases", response_model=CaseOut, status_code=201)
def create_case(body: CaseIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"source_link", "retention_days"})
    case = Case(owner_id=user.id, retention_days=body.retention_days or get_settings().default_retention_days, **data)
    _resolve_link(db, user, case, body.source_link)
    db.add(case)
    db.commit()
    audit(db, "case.created", user.id, case.id, ip=client_ip(request), category=case.category)
    db.commit()
    return _out(db, case)


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(db, owned_case(case_id, user, db))


@router.patch("/cases/{case_id}", response_model=CaseOut)
def patch_case(case_id: str, body: CasePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    data = body.model_dump(exclude_unset=True)
    if "source_link" in data:
        _resolve_link(db, user, case, data.pop("source_link") or "")
    if "category" in data:
        CaseIn.model_validate({"category": data["category"]})
    if data.get("status") and data["status"] not in ("completed", "pending_verification", "report_ready"):
        raise HTTPException(400, "Only completed / pending_verification / report_ready can be set manually")
    for k, v in data.items():
        setattr(case, k, v)
    audit(db, "case.updated", user.id, case.id, fields=sorted(data))
    db.commit()
    return _out(db, case)


@router.delete("/cases/{case_id}")
def delete_case(case_id: str, confirm: str = Query(..., description="Must equal the claim number or 'DELETE'"),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    if confirm not in ("DELETE", case.claim_number) or not confirm:
        raise HTTPException(400, "Confirmation text does not match")
    get_storage().delete_prefix(f"cases/{case.id}")
    audit(db, "case.deleted", user.id, case.id, claim=case.claim_number)
    db.delete(case)
    db.commit()
    return {"ok": True}


@router.post("/cases/{case_id}/purge-copies")
def purge_copies(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Delete stored copies of source documents (extracted text, analyses and reports are kept)."""
    case = owned_case(case_id, user, db)
    get_storage().delete_prefix(f"cases/{case.id}/docs")
    for d in case.documents:
        d.storage_key = ""
    audit(db, "case.copies_purged", user.id, case.id)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ scanning & jobs
@router.post("/cases/{case_id}/scan", response_model=JobOut, status_code=202)
def scan(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    if not case.source_folder_id:
        raise HTTPException(400, "Add a folder link to the case first")
    active = db.query(Job).filter(Job.case_id == case.id, Job.kind == "scan", Job.status.in_(["queued", "running"])).first()
    if active:
        return active
    job = enqueue(db, "scan", user.id, case.id)
    audit(db, "case.scan_requested", user.id, case.id, provider=case.source_provider)
    db.commit()
    return job


@router.get("/cases/{case_id}/jobs", response_model=list[JobOut])
def case_jobs(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    return db.query(Job).filter_by(case_id=case_id).order_by(Job.created_at.desc()).limit(50).all()


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    return job


# ------------------------------------------------------------------ documents
@router.get("/cases/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    return db.query(Document).filter_by(case_id=case_id).order_by(Document.ref).all()


@router.get("/cases/{case_id}/inventory")
def inventory_summary(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    rows = db.query(Document.status, func.count(Document.id)).filter_by(case_id=case_id).group_by(Document.status).all()
    counts = dict(rows)
    run = db.query(AnalysisRun).filter_by(case_id=case_id, status="completed").order_by(AnalysisRun.run_no.desc()).first()
    missing = [c for c in (run.result.get("checklist", []) if run else []) if c["status"] == "missing"]
    return {
        "processed": counts.get("processed", 0) + counts.get("partial", 0),
        "unreadable": sum(counts.get(s, 0) for s in ("unreadable", "password_protected", "corrupted", "unsupported", "error")),
        "pending": counts.get("pending", 0) + counts.get("processing", 0),
        "duplicates": counts.get("duplicate", 0),
        "containers": counts.get("container", 0),
        "by_status": counts,
        "missing_documents": missing,
    }


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    owned_case(doc.case_id, user, db)
    return doc


@router.get("/documents/{doc_id}/content")
def document_content(doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    owned_case(doc.case_id, user, db)
    if not doc.storage_key:
        raise HTTPException(410, "Stored copy was deleted")
    audit(db, "document.downloaded", user.id, doc.case_id, ref=doc.ref)
    db.commit()
    return Response(get_storage().get(doc.storage_key), media_type=doc.mime_type or "application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{doc.ref}_{doc.original_filename}"'})


@router.patch("/documents/{doc_id}", response_model=DocumentDetail)
def patch_document(doc_id: str, body: DocumentPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    owned_case(doc.case_id, user, db)
    if body.doc_type:
        doc.doc_type, doc.doc_type_corrected, doc.doc_type_confidence = body.doc_type, True, 1.0
    for page_no, text in (body.page_corrections or {}).items():
        page = db.query(DocumentPage).filter_by(document_id=doc.id, page_no=page_no).one_or_none()
        if not page:
            raise HTTPException(400, f"Page {page_no} not found")
        page.user_corrected_text = text
    audit(db, "document.corrected", user.id, doc.case_id, ref=doc.ref, doc_type=body.doc_type,
          pages=sorted((body.page_corrections or {}).keys()))
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/cases/{case_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(case_id: str, file: UploadFile = File(...), client_uuid: str = Form(""),
                          folder: str = Form("Uploaded from iPhone"),
                          user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    if client_uuid:
        existing = db.query(Document).filter_by(case_id=case.id, source_file_id=f"upload:{client_uuid}").first()
        if existing:
            return existing
    data = await file.read()
    if len(data) > get_settings().max_file_mb * 1024 * 1024:
        raise HTTPException(413, "File too large")
    doc = Document(case_id=case.id, ref=next_ref(db, case.id), origin="upload",
                   source_file_id=f"upload:{client_uuid or datetime.now(timezone.utc).timestamp()}",
                   source_path=folder, original_filename=file.filename or "upload.bin",
                   mime_type=file.content_type or "", size_bytes=len(data),
                   source_modified_at=datetime.now(timezone.utc).isoformat(),
                   storage_key=get_storage().put(data, f"cases/{case.id}/docs"))
    db.add(doc)
    db.commit()
    enqueue(db, "extract", user.id, case.id, document_id=doc.id)
    audit(db, "document.uploaded", user.id, case.id, ref=doc.ref, filename=doc.original_filename)
    db.commit()
    return doc


# ------------------------------------------------------------------ notes / verification results / corrections
@router.get("/cases/{case_id}/notes", response_model=list[NoteOut])
def list_notes(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    return db.query(CaseNote).filter_by(case_id=case_id).order_by(CaseNote.ref).all()


@router.post("/cases/{case_id}/notes", response_model=NoteOut, status_code=201)
def add_note(case_id: str, body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    if body.client_uuid:
        existing = db.query(CaseNote).filter_by(case_id=case.id, client_uuid=body.client_uuid).first()
        if existing:
            return existing
    n = db.query(func.count(CaseNote.id)).filter_by(case_id=case.id).scalar() or 0
    note = CaseNote(case_id=case.id, ref=f"N{n + 1:03d}", author_id=user.id, **body.model_dump())
    db.add(note)
    audit(db, "note.added", user.id, case.id, ref=note.ref, kind=note.kind)
    db.commit()
    return note


@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: str, body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = db.get(CaseNote, note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    owned_case(note.case_id, user, db)
    for k, v in body.model_dump(exclude={"client_uuid"}).items():
        setattr(note, k, v)
    audit(db, "note.updated", user.id, note.case_id, ref=note.ref)
    db.commit()
    return note


@router.delete("/notes/{note_id}")
def delete_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = db.get(CaseNote, note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    owned_case(note.case_id, user, db)
    audit(db, "note.deleted", user.id, note.case_id, ref=note.ref)
    db.delete(note)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ analysis
@router.post("/cases/{case_id}/analyses", response_model=JobOut, status_code=202)
def start_analysis(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    if get_settings().ai_mode == "claude_code":
        raise HTTPException(409, "This server runs investigations in Claude Code (your Claude plan). "
                                 "Open Claude Code and ask it to investigate this case.")
    pending = db.query(Document).filter(Document.case_id == case.id,
                                        Document.status.in_(["pending", "processing"])).count()
    if pending:
        raise HTTPException(409, f"{pending} document(s) are still being processed")
    if not db.query(Document).filter(Document.case_id == case.id, Document.status.in_(["processed", "partial"])).count():
        raise HTTPException(400, "No readable documents in this case yet")
    busy = db.query(Job).filter(Job.case_id == case.id, Job.kind == "analyze",
                                Job.status.in_(["queued", "running"])).first()
    if busy:
        return busy
    n = db.query(func.count(AnalysisRun.id)).filter_by(case_id=case.id).scalar() or 0
    run = AnalysisRun(case_id=case.id, run_no=n + 1, status="queued")
    db.add(run)
    db.commit()
    job = enqueue(db, "analyze", user.id, case.id, run_id=run.id)
    audit(db, "analysis.requested", user.id, case.id, run_no=run.run_no)
    db.commit()
    return job


@router.get("/cases/{case_id}/analyses", response_model=list[AnalysisSummary])
def list_analyses(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    return db.query(AnalysisRun).filter_by(case_id=case_id).order_by(AnalysisRun.run_no.desc()).all()


@router.get("/analyses/{run_id}", response_model=AnalysisOut)
def get_analysis(run_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    run = db.get(AnalysisRun, run_id)
    if not run:
        raise HTTPException(404, "Analysis not found")
    owned_case(run.case_id, user, db)
    return run


# ------------------------------------------------------------------ audit & retention
@router.get("/cases/{case_id}/audit")
def case_audit(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    rows = db.query(AuditLog).filter_by(case_id=case_id).order_by(AuditLog.at.desc()).limit(500).all()
    return [{"at": r.at, "action": r.action, "detail": r.detail} for r in rows]


def purge_expired(db: Session) -> int:
    """Delete cases whose retention period (from last update) has elapsed. Run daily via CLI/cron."""
    now = datetime.now(timezone.utc)
    n = 0
    for case in db.query(Case).all():
        upd = case.updated_at if case.updated_at.tzinfo else case.updated_at.replace(tzinfo=timezone.utc)
        if case.retention_days and upd + timedelta(days=case.retention_days) < now:
            get_storage().delete_prefix(f"cases/{case.id}")
            audit(db, "case.retention_purged", None, case.id, claim=case.claim_number)
            db.delete(case)
            n += 1
    db.commit()
    return n
