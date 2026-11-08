"""Recursive case-folder ingestion: download -> store encrypted -> expand ZIPs -> dedupe -> extract -> classify.

Idempotent and resumable: files already processed for the case (same provider file id) are skipped, so a
scan interrupted by a crash or network drop simply continues when the job is retried.
"""
from __future__ import annotations

import hashlib
import io
import logging
import mimetypes
import zipfile
from collections.abc import Callable
from pathlib import PurePosixPath

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..connectors.base import CloudConnector, ConnectorError
from ..extraction.classifier import classify
from ..extraction.extractors import extract
from ..models import Case, Document, DocumentPage
from ..storage import get_storage
from .filetypes import sniff

log = logging.getLogger(__name__)
FINAL_STATES = {"processed", "partial", "unreadable", "password_protected", "unsupported", "corrupted",
                "duplicate", "container", "awaiting_reading"}

Progress = Callable[[float, str], None]


def next_ref(db: Session, case_id: str, prefix: str = "D") -> str:
    n = db.query(func.count(Document.id)).filter(Document.case_id == case_id).scalar() or 0
    return f"{prefix}{n + 1:03d}"


def scan_case(db: Session, case: Case, connector: CloudConnector, progress: Progress) -> dict:
    progress(0.01, "Listing folder contents")
    try:
        files = list(connector.walk(case.source_folder_id))
    except ConnectorError:
        raise
    total = max(len(files), 1)
    stats = {"listed": len(files), "new": 0, "skipped": 0}
    for i, rf in enumerate(files):
        existing = (db.query(Document)
                    .filter(Document.case_id == case.id, Document.source_file_id == rf.id, Document.parent_id.is_(None))
                    .one_or_none())
        if existing and existing.status in FINAL_STATES:
            stats["skipped"] += 1
            continue
        progress(0.02 + 0.96 * i / total, f"Processing {rf.full_path}")
        doc = existing or Document(case_id=case.id, ref=next_ref(db, case.id), origin=connector.provider,
                                   source_file_id=rf.id, source_path=rf.path, original_filename=rf.name,
                                   mime_type=rf.mime_type, size_bytes=rf.size, source_modified_at=rf.modified_time)
        if not existing:
            db.add(doc)
            db.commit()
        if rf.size and rf.size > get_settings().max_file_mb * 1024 * 1024:
            _set(db, doc, "unsupported", f"File larger than {get_settings().max_file_mb} MB was not downloaded")
            continue
        try:
            data, eff_name = connector.download(rf)
        except ConnectorError as e:
            _set(db, doc, "error", f"Download failed: {e}")
            continue
        if eff_name != doc.original_filename:
            doc.metadata_json = {**(doc.metadata_json or {}), "exported_as": eff_name}
        ingest_bytes(db, case, doc, data, eff_name)
        stats["new"] += 1
    progress(1.0, "Scan complete")
    return stats


def _set(db: Session, doc: Document, status: str, detail: str = "") -> None:
    doc.status, doc.status_detail = status, detail
    db.commit()


def ingest_bytes(db: Session, case: Case, doc: Document, data: bytes, filename: str, depth: int = 0) -> None:
    """Store, dedupe, expand and extract one file (already registered as `doc`)."""
    doc.sha256 = hashlib.sha256(data).hexdigest()
    doc.size_bytes = len(data)
    if not doc.storage_key:
        doc.storage_key = get_storage().put(data, f"cases/{case.id}/docs")
    doc.status = "processing"
    db.commit()

    kind = sniff(data, filename)
    if not doc.mime_type:
        doc.mime_type = mimetypes.guess_type(filename)[0] or ""
    if kind == "zip":
        _expand_zip(db, case, doc, data, depth)
        return

    dup = (db.query(Document)
           .filter(Document.case_id == case.id, Document.sha256 == doc.sha256, Document.id != doc.id,
                   Document.status.in_(["processed", "partial", "unreadable", "password_protected",
                                        "unsupported", "corrupted", "awaiting_reading"]))
           .order_by(Document.ref).first())
    if dup:
        doc.duplicate_of_id = dup.id
        doc.doc_type = dup.doc_type
        _set(db, doc, "duplicate", f"Identical content to {dup.ref} ({dup.original_filename})")
        return

    try:
        ex = extract(kind, data, filename, ref=doc.ref)
    except Exception as e:  # never silently skip
        log.exception("extraction crashed for %s", doc.ref)
        _set(db, doc, "error", f"Extraction failed: {e}")
        return
    db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()
    for p in ex.pages:
        db.add(DocumentPage(document_id=doc.id, page_no=p.page_no, label=p.label, method=p.method,
                            language=p.language, text_original=p.text_original, text_english=p.text_english,
                            visual_description=p.visual_description, legible=p.legible))
    doc.page_count = len(ex.pages)
    doc.metadata_json = {**(doc.metadata_json or {}), **ex.metadata, "kind": kind}
    doc.languages = sorted({l for p in ex.pages for l in (p.language or "").split(",") if l})
    if not doc.doc_type_corrected:
        doc.doc_type, doc.doc_type_confidence = classify(filename, ex.text, ex.is_photo)
    _set(db, doc, ex.status, ex.detail)


def _expand_zip(db: Session, case: Case, parent: Document, data: bytes, depth: int) -> None:
    s = get_settings()
    if depth >= s.max_zip_depth:
        _set(db, parent, "unsupported", f"ZIP nesting deeper than {s.max_zip_depth} levels")
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
    except zipfile.BadZipFile as e:
        _set(db, parent, "corrupted", f"ZIP archive is damaged: {e}")
        return
    if len(infos) > s.max_zip_members:
        _set(db, parent, "unsupported", f"ZIP has {len(infos)} files (limit {s.max_zip_members})")
        return
    if sum(i.file_size for i in infos) > s.max_file_mb * 1024 * 1024 * 5:
        _set(db, parent, "unsupported", "ZIP expands to an unsafe size (possible zip bomb)")
        return
    base_path = f"{parent.source_path}/{parent.original_filename}!".lstrip("/")
    encrypted = 0
    for info in infos:
        name = _zip_name(info)
        pp = PurePosixPath(name)
        child = (db.query(Document)
                 .filter(Document.parent_id == parent.id, Document.source_file_id == f"{parent.source_file_id}!{name}")
                 .one_or_none())
        if child and child.status in FINAL_STATES:
            continue
        if child is None:
            child = Document(case_id=case.id, ref=next_ref(db, case.id), parent_id=parent.id, origin="zip_member",
                             source_file_id=f"{parent.source_file_id}!{name}",
                             source_path=f"{base_path}/{pp.parent}".rstrip("/.").rstrip("/"),
                             original_filename=pp.name, size_bytes=info.file_size,
                             source_modified_at="%04d-%02d-%02dT%02d:%02d:%02d" % info.date_time)
            db.add(child)
            db.commit()
        if info.flag_bits & 0x1:
            encrypted += 1
            _set(db, child, "password_protected", "File inside ZIP is password protected")
            continue
        try:
            member = zf.read(info)
        except (zipfile.BadZipFile, RuntimeError, OSError, Exception) as e:  # CRC errors etc.
            _set(db, child, "corrupted", f"Could not extract from ZIP: {e}")
            continue
        ingest_bytes(db, case, child, member, pp.name, depth + 1)
    detail = f"ZIP archive with {len(infos)} file(s)" + (f"; {encrypted} password protected" if encrypted else "")
    _set(db, parent, "container", detail)


def _zip_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not info.flag_bits & 0x800:  # not flagged UTF-8: try to recover Indian-language names encoded as UTF-8
        try:
            name = name.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name
