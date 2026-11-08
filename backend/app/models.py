"""Database schema (SQLAlchemy 2.0). Portable across PostgreSQL (production) and SQLite (tests)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --------------------------------------------------------------------------- users & auth
class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Investigator particulars printed on reports / invoices. Never invented by the AI.
    investigator_profile: Mapped[dict] = mapped_column(JSON, default=dict)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    device: Mapped[str] = mapped_column(String(255), default="")


class ConnectorAccount(TimestampMixin, Base):
    """OAuth connection to a cloud provider. Tokens are Fernet-encrypted at rest."""
    __tablename__ = "connector_accounts"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))  # google_drive | onedrive
    account_email: Mapped[str] = mapped_column(String(255), default="")
    refresh_token_enc: Mapped[str] = mapped_column(Text, default="")
    access_token_enc: Mapped[str] = mapped_column(Text, default="")
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, default="")


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    code_verifier: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- cases
class Case(TimestampMixin, Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    insured_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    claim_number: Mapped[str] = mapped_column(String(128), default="", index=True)
    policy_number: Mapped[str] = mapped_column(String(128), default="")
    vehicle_registration: Mapped[str] = mapped_column(String(64), default="", index=True)
    insurer_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    investigation_reference: Mapped[str] = mapped_column(String(128), default="")
    investigation_date: Mapped[str] = mapped_column(String(32), default="")  # ISO date
    category: Mapped[str] = mapped_column(String(64))  # playbook key, e.g. own_damage
    additional_aspects: Mapped[list] = mapped_column(JSON, default=list)  # extra playbook keys
    source_provider: Mapped[str] = mapped_column(String(32), default="")
    source_link: Mapped[str] = mapped_column(Text, default="")
    source_folder_id: Mapped[str] = mapped_column(String(255), default="")
    # new | scanning | scanned | analysing | analysed | report_ready | pending_verification | completed | failed
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    page_limit: Mapped[int] = mapped_column(Integer, default=7)
    include_invoice: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice: Mapped[dict] = mapped_column(JSON, default=dict)
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    notes: Mapped[str] = mapped_column(Text, default="")

    documents: Mapped[list[Document]] = relationship(back_populates="case", cascade="all, delete-orphan",
                                                     passive_deletes=True)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_doc_case_source", "case_id", "source_file_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(16))  # short citation id, e.g. D007 (stable per case)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    origin: Mapped[str] = mapped_column(String(32), default="drive")  # drive | onedrive | zip_member | upload | local
    source_file_id: Mapped[str] = mapped_column(String(512), default="")
    source_path: Mapped[str] = mapped_column(Text, default="")  # folder path incl. zip path
    original_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(255), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    source_modified_at: Mapped[str] = mapped_column(String(64), default="")
    storage_key: Mapped[str] = mapped_column(String(255), default="")
    # pending | processing | processed | partial | unreadable | password_protected | unsupported
    # | corrupted | duplicate | container | error
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    status_detail: Mapped[str] = mapped_column(Text, default="")
    duplicate_of_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(64), default="unknown")
    doc_type_confidence: Mapped[float] = mapped_column(default=0.0)
    doc_type_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)  # EXIF, PDF info, etc.

    case: Mapped[Case] = relationship(back_populates="documents")
    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_no",
        passive_deletes=True)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)  # 1-based; sheet index for spreadsheets; 1 for images
    label: Mapped[str] = mapped_column(String(255), default="")  # e.g. sheet name
    method: Mapped[str] = mapped_column(String(32), default="")  # text_layer | ocr_vision | ocr_tesseract | native
    language: Mapped[str] = mapped_column(String(64), default="")
    text_original: Mapped[str] = mapped_column(Text, default="")
    text_english: Mapped[str] = mapped_column(Text, default="")
    visual_description: Mapped[str] = mapped_column(Text, default="")
    legible: Mapped[bool] = mapped_column(Boolean, default=True)
    user_corrected_text: Mapped[str] = mapped_column(Text, default="")

    document: Mapped[Document] = relationship(back_populates="pages")


class DocumentDigest(Base):
    """Cached per-document AI digest; keyed by content hash + prompt version so reruns are cheap."""
    __tablename__ = "document_digests"
    __table_args__ = (UniqueConstraint("document_id", "cache_key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    cache_key: Mapped[str] = mapped_column(String(128))
    model: Mapped[str] = mapped_column(String(64))
    digest: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseNote(TimestampMixin, Base):
    """Investigator input: field observations, verification results and corrections.

    These are the ONLY source of external verification the engine may rely on.
    """
    __tablename__ = "case_notes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    ref: Mapped[str] = mapped_column(String(16))  # N001...
    client_uuid: Mapped[str] = mapped_column(String(64), default="", index=True)  # offline-sync idempotency
    # field_observation | hospital_verification | police_verification | rto_verification
    # | fastag_verification | gps_verification | other_verification | correction | instruction
    kind: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text)
    verified_by: Mapped[str] = mapped_column(String(255), default="")
    verified_on: Mapped[str] = mapped_column(String(32), default="")
    target: Mapped[str] = mapped_column(String(255), default="")  # e.g. "D004 p2" for corrections
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))


# --------------------------------------------------------------------------- playbooks
class Playbook(TimestampMixin, Base):
    __tablename__ = "playbooks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), unique=True)  # global_rules, own_damage, ...
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16), default="category")  # global | category | aspect
    active_version: Mapped[int] = mapped_column(Integer, default=1)
    versions: Mapped[list[PlaybookVersion]] = relationship(
        back_populates="playbook", cascade="all, delete-orphan", order_by="PlaybookVersion.version"
    )


class PlaybookVersion(Base):
    __tablename__ = "playbook_versions"
    __table_args__ = (UniqueConstraint("playbook_id", "version"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    playbook_id: Mapped[str] = mapped_column(ForeignKey("playbooks.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content_yaml: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    playbook: Mapped[Playbook] = relationship(back_populates="versions")


class ReferenceTemplate(Base):
    """User-supplied reference DOCX (e.g. OD_report.docx) used as the style/header base for a category."""
    __tablename__ = "reference_templates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- analysis & reports
class AnalysisRun(TimestampMixin, Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|running|completed|failed
    model: Mapped[str] = mapped_column(String(64), default="")
    playbooks_used: Mapped[list] = mapped_column(JSON, default=list)  # [{key, version}]
    document_refs: Mapped[list] = mapped_column(JSON, default=list)
    note_refs: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)  # {errors:[], warnings:[]}
    error: Mapped[str] = mapped_column(Text, default="")
    usage: Mapped[dict] = mapped_column(JSON, default=dict)


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("case_id", "version"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    docx_key: Mapped[str] = mapped_column(String(255), default="")
    pdf_key: Mapped[str] = mapped_column(String(255), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    page_limit: Mapped[int] = mapped_column(Integer, default=7)
    template_key: Mapped[str] = mapped_column(String(64), default="")
    reference_template_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)  # report text produced by the drafting step
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    drive_file_id: Mapped[str] = mapped_column(String(255), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- jobs & audit
class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))  # scan | extract | analyze | report
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)  # queued|running|done|failed
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[float] = mapped_column(default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
