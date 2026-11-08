from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..connectors.base import ConnectorError
from ..connectors.registry import get_connector
from ..db import get_db
from ..deps import admin_user, current_user, owned_case
from ..ingestion.filetypes import sniff
from ..jobs.queue import enqueue
from ..models import AnalysisRun, Playbook, PlaybookVersion, ReferenceTemplate, ReportVersion, User
from ..playbooks.store import PlaybookValidationError, add_version, available_aspects
from ..schemas import (JobOut, PlaybookOut, PlaybookVersionIn, PlaybookVersionOut, ReportIn, ReportOut)
from ..storage import get_storage

router = APIRouter(tags=["reports"])
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _rout(rv: ReportVersion) -> ReportOut:
    return ReportOut.model_validate(rv).model_copy(update={"has_pdf": bool(rv.pdf_key)})


@router.post("/cases/{case_id}/reports", response_model=JobOut, status_code=202)
def create_report(case_id: str, body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = owned_case(case_id, user, db)
    if get_settings().ai_mode == "claude_code":
        raise HTTPException(409, "Reports are drafted in Claude Code on this server. Ask Claude Code to "
                                 "write the report for this case.")
    q = db.query(AnalysisRun).filter_by(case_id=case.id, status="completed")
    run = q.filter_by(id=body.analysis_run_id).first() if body.analysis_run_id else \
        q.order_by(AnalysisRun.run_no.desc()).first()
    if not run:
        raise HTTPException(400, "Run a completed investigation analysis first")
    if run.validation.get("errors"):
        raise HTTPException(409, "The analysis failed validation: " + "; ".join(run.validation["errors"][:5]))
    n = db.query(func.count(ReportVersion.id)).filter_by(case_id=case.id).scalar() or 0
    rv = ReportVersion(case_id=case.id, analysis_run_id=run.id, version=n + 1,
                       page_limit=body.page_limit or case.page_limit)
    db.add(rv)
    db.commit()
    job = enqueue(db, "report", user.id, case.id, report_id=rv.id)
    audit(db, "report.requested", user.id, case.id, version=rv.version, analysis_run=run.run_no)
    db.commit()
    return job


@router.get("/cases/{case_id}/reports", response_model=list[ReportOut])
def list_reports(case_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_case(case_id, user, db)
    return [_rout(r) for r in db.query(ReportVersion).filter_by(case_id=case_id).order_by(ReportVersion.version.desc())]


def _owned_report(report_id: str, user: User, db: Session) -> ReportVersion:
    rv = db.get(ReportVersion, report_id)
    if not rv:
        raise HTTPException(404, "Report not found")
    owned_case(rv.case_id, user, db)
    return rv


@router.get("/reports/{report_id}/download")
def download(report_id: str, format: str = Query("docx", pattern="^(docx|pdf)$"),
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    rv = _owned_report(report_id, user, db)
    key = rv.docx_key if format == "docx" else rv.pdf_key
    if not key:
        raise HTTPException(404, f"No {format.upper()} available for this report")
    audit(db, "report.downloaded", user.id, rv.case_id, version=rv.version, format=format)
    db.commit()
    mime = DOCX_MIME if format == "docx" else "application/pdf"
    return Response(get_storage().get(key), media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{rv.filename}.{format}"'})


@router.post("/reports/{report_id}/upload-to-drive")
def upload_to_drive(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rv = _owned_report(report_id, user, db)
    case = owned_case(rv.case_id, user, db)
    if not case.source_folder_id:
        raise HTTPException(400, "Case has no linked folder")
    try:
        conn = get_connector(db, user.id, case.source_provider)
        rv.drive_file_id = conn.upload(case.source_folder_id, f"{rv.filename}.docx",
                                       get_storage().get(rv.docx_key), DOCX_MIME)
    except ConnectorError as e:
        raise HTTPException(400, str(e))
    audit(db, "report.uploaded_to_drive", user.id, case.id, version=rv.version, provider=case.source_provider)
    db.commit()
    return {"ok": True, "file_id": rv.drive_file_id}


# ------------------------------------------------------------------ playbooks (admin)
@router.get("/playbooks", response_model=list[PlaybookOut])
def list_playbooks(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.query(Playbook).order_by(Playbook.kind.desc(), Playbook.name).all()


@router.get("/playbooks/aspects")
def aspects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return available_aspects(db)


@router.get("/playbooks/{key}/versions", response_model=list[PlaybookVersionOut])
def versions(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    pb = db.query(Playbook).filter_by(key=key).one_or_none()
    if not pb:
        raise HTTPException(404, "Playbook not found")
    return sorted(pb.versions, key=lambda v: -v.version)


@router.post("/playbooks/{key}/versions", response_model=PlaybookVersionOut, status_code=201)
def new_version(key: str, body: PlaybookVersionIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    try:
        ver = add_version(db, key, body.content_yaml, body.change_note, user.id, body.activate)
    except PlaybookValidationError as e:
        raise HTTPException(422, str(e))
    audit(db, "playbook.version_created", user.id, key=key, version=ver.version, activated=body.activate)
    db.commit()
    return ver


@router.post("/playbooks/{key}/activate/{version}", response_model=PlaybookOut)
def activate(key: str, version: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    pb = db.query(Playbook).filter_by(key=key).one_or_none()
    if not pb or not db.query(PlaybookVersion).filter_by(playbook_id=pb.id, version=version).first():
        raise HTTPException(404, "Version not found")
    pb.active_version = version
    audit(db, "playbook.activated", user.id, key=key, version=version)
    db.commit()
    return pb


# ------------------------------------------------------------------ reference report templates (admin)
@router.get("/templates")
def list_templates(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": t.id, "category": t.category, "filename": t.filename, "active": t.active, "created_at": t.created_at}
            for t in db.query(ReferenceTemplate).order_by(ReferenceTemplate.created_at.desc())]


@router.post("/templates/{category}", status_code=201)
async def upload_template(category: str, file: UploadFile = File(...), user: User = Depends(admin_user),
                          db: Session = Depends(get_db)):
    data = await file.read()
    if sniff(data, file.filename or "") != "docx":
        raise HTTPException(400, "Upload a .docx reference report")
    for t in db.query(ReferenceTemplate).filter_by(category=category, active=True):
        t.active = False
    t = ReferenceTemplate(category=category, filename=file.filename or "reference.docx", uploaded_by=user.id,
                          storage_key=get_storage().put(data, "templates"))
    db.add(t)
    audit(db, "template.uploaded", user.id, category=category, filename=t.filename)
    db.commit()
    return {"id": t.id, "category": category}
