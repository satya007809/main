"""Background task implementations. Each task is idempotent so retries resume safely."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..audit import audit
from ..connectors.registry import get_connector
from ..engine.investigator import run_analysis
from ..ingestion.scanner import ingest_bytes, scan_case
from ..models import AnalysisRun, Case, Document, Job, ReportVersion
from ..reports.generator import generate_report
from ..storage import get_storage


def task_scan(db: Session, job: Job, progress) -> dict:
    case = db.get(Case, job.case_id)
    case.status = "scanning"
    db.commit()
    connector = get_connector(db, job.user_id, case.source_provider)
    stats = scan_case(db, case, connector, progress)
    case.status = "scanned"
    counts: dict[str, int] = {}
    for d in case.documents:
        counts[d.status] = counts.get(d.status, 0) + 1
    audit(db, "case.scanned", job.user_id, case.id, **stats, statuses=counts)
    db.commit()
    return {**stats, "statuses": counts}


def task_extract(db: Session, job: Job, progress) -> dict:
    doc = db.get(Document, job.payload["document_id"])
    case = db.get(Case, doc.case_id)
    progress(0.1, f"Reading {doc.original_filename}")
    data = get_storage().get(doc.storage_key)
    ingest_bytes(db, case, doc, data, doc.original_filename)
    audit(db, "document.processed", job.user_id, case.id, ref=doc.ref, status=doc.status)
    db.commit()
    return {"status": doc.status}


def task_analyze(db: Session, job: Job, progress) -> dict:
    run = db.get(AnalysisRun, job.payload["run_id"])
    case = db.get(Case, run.case_id)
    run.status = "running"
    case.status = "analysing"
    db.commit()
    run_analysis(db, run, progress)
    audit(db, "analysis.completed", job.user_id, case.id, run_no=run.run_no, model=run.model,
          playbooks=run.playbooks_used, documents=run.document_refs, validation_ok=run.validation.get("ok"))
    db.commit()
    return {"run_id": run.id, "verdict": run.result.get("opinion", {}).get("verdict")}


def task_report(db: Session, job: Job, progress) -> dict:
    rv = db.get(ReportVersion, job.payload["report_id"])
    rv.status = "running"
    db.commit()
    generate_report(db, rv, progress)
    audit(db, "report.generated", job.user_id, rv.case_id, version=rv.version, analysis_run=rv.analysis_run_id,
          pages=rv.page_count, template=rv.template_key)
    db.commit()
    return {"report_id": rv.id, "pages": rv.page_count}
