"""Durable database-backed job queue with heartbeats.

Jobs survive API restarts: a job whose worker died (stale heartbeat) is re-queued and, because every task is
idempotent, resumes where it stopped. Run workers in-process (single server) or as `python -m app.worker`.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..connectors.base import ConnectorError
from ..db import SessionLocal
from ..llm.client import LLMError
from ..models import AnalysisRun, Case, Document, Job, ReportVersion
from ..reports.builder import ReportBuildError

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
PERMANENT_ERRORS = (ConnectorError, ReportBuildError, KeyError)


def enqueue(db: Session, kind: str, user_id: str, case_id: str | None = None, **payload) -> Job:
    job = Job(kind=kind, user_id=user_id, case_id=case_id, payload=payload)
    db.add(job)
    db.commit()
    return job


def _now() -> datetime:
    return datetime.now(timezone.utc)


def recover_stale(db: Session) -> int:
    cutoff = _now() - timedelta(seconds=get_settings().job_stale_seconds)
    n = 0
    for job in db.query(Job).filter(Job.status == "running").all():
        hb = job.heartbeat_at
        if hb is not None and hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        if hb is None or hb < cutoff:
            job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
            job.message = "Resuming after interruption" if job.status == "queued" else job.message
            n += 1
    db.commit()
    return n


def claim_next(db: Session) -> Job | None:
    stmt = select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1)
    if db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        return None
    job.status, job.attempts, job.heartbeat_at = "running", job.attempts + 1, _now()
    db.commit()
    return job


def run_job(job_id: str) -> None:
    from . import tasks

    db = SessionLocal()
    job = db.get(Job, job_id)

    def progress(frac: float, msg: str) -> None:
        job.progress, job.message, job.heartbeat_at = round(frac, 3), msg[:500], _now()
        db.commit()

    try:
        handler = getattr(tasks, f"task_{job.kind}")
        job.result = handler(db, job, progress) or {}
        job.status, job.progress = "done", 1.0
        audit(db, f"job.{job.kind}.done", job.user_id, job.case_id, job_id=job.id)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, job_id)
        permanent = isinstance(e, PERMANENT_ERRORS) or job.attempts >= MAX_ATTEMPTS
        log.warning("job %s (%s) failed: %s", job.id, job.kind, e)
        job.error = str(e)[:2000]
        job.status = "failed" if permanent else "queued"
        job.message = ("Failed: " if permanent else "Will retry: ") + str(e)[:300]
        if permanent:
            _mark_failed(db, job, str(e))
            audit(db, f"job.{job.kind}.failed", job.user_id, job.case_id, job_id=job.id, error=str(e)[:500],
                  trace=traceback.format_exc()[-1500:] if not isinstance(e, PERMANENT_ERRORS + (LLMError,)) else "")
        db.commit()
    finally:
        db.close()


def _mark_failed(db: Session, job: Job, err: str) -> None:
    p = job.payload or {}
    if job.kind == "analyze" and (run := db.get(AnalysisRun, p.get("run_id", ""))):
        run.status, run.error = "failed", err[:2000]
    if job.kind == "report" and (rv := db.get(ReportVersion, p.get("report_id", ""))):
        rv.status, rv.error = "failed", err[:2000]
    if job.kind == "extract" and (doc := db.get(Document, p.get("document_id", ""))):
        doc.status, doc.status_detail = "error", err[:500]
    if job.kind == "scan" and (case := db.get(Case, job.case_id)):
        case.status = "failed"


def work_once() -> bool:
    db = SessionLocal()
    try:
        job = claim_next(db)
        job_id = job.id if job else None
    finally:
        db.close()
    if job_id:
        run_job(job_id)
        return True
    return False


def drain(max_jobs: int = 100) -> int:
    """Run queued jobs synchronously (tests / CLI)."""
    n = 0
    while n < max_jobs and work_once():
        n += 1
    return n


class WorkerThread(threading.Thread):
    def __init__(self, poll: float = 1.5):
        super().__init__(daemon=True, name="bid-worker")
        self.poll = poll
        self.stop_event = threading.Event()

    def run(self) -> None:
        db = SessionLocal()
        try:
            recover_stale(db)
        finally:
            db.close()
        last_recover = time.monotonic()
        while not self.stop_event.is_set():
            try:
                if not work_once():
                    self.stop_event.wait(self.poll)
                if time.monotonic() - last_recover > 60:
                    db = SessionLocal()
                    try:
                        recover_stale(db)
                    finally:
                        db.close()
                    last_recover = time.monotonic()
            except Exception:  # pragma: no cover
                log.exception("worker loop error")
                self.stop_event.wait(5)
