from __future__ import annotations

import re

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# auth
def _email(v: str) -> str:
    v = v.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
        raise ValueError("invalid email")
    return v


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=10)
    full_name: str = ""

    _v = field_validator("email")(classmethod(lambda cls, v: _email(v)))


class LoginIn(BaseModel):
    email: str
    password: str
    device: str = ""


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    is_admin: bool
    investigator_profile: dict


class ProfileIn(BaseModel):
    full_name: str | None = None
    investigator_profile: dict[str, str] | None = None


# cases
CATEGORIES = ["own_damage", "pa_injury", "pa_death", "theft", "fire", "road_accident", "general"]


class CaseIn(BaseModel):
    insured_name: str = ""
    claim_number: str = ""
    policy_number: str = ""
    vehicle_registration: str = ""
    insurer_name: str = ""
    investigation_reference: str = ""
    investigation_date: str = ""
    category: str
    additional_aspects: list[str] = []
    source_link: str = ""
    page_limit: int = 7
    include_invoice: bool = False
    invoice: dict[str, Any] = {}
    retention_days: int | None = None
    notes: str = ""

    @field_validator("page_limit")
    @classmethod
    def _pl(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("page_limit must be between 1 and 10")
        return v

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v


class CasePatch(BaseModel):
    insured_name: str | None = None
    claim_number: str | None = None
    policy_number: str | None = None
    vehicle_registration: str | None = None
    insurer_name: str | None = None
    investigation_reference: str | None = None
    investigation_date: str | None = None
    category: str | None = None
    additional_aspects: list[str] | None = None
    source_link: str | None = None
    page_limit: int | None = Field(default=None, ge=1, le=10)
    include_invoice: bool | None = None
    invoice: dict[str, Any] | None = None
    retention_days: int | None = None
    status: str | None = None
    notes: str | None = None


class CaseOut(ORM):
    id: str
    insured_name: str
    claim_number: str
    policy_number: str
    vehicle_registration: str
    insurer_name: str
    investigation_reference: str
    investigation_date: str
    category: str
    additional_aspects: list[str]
    source_provider: str
    source_link: str
    status: str
    page_limit: int
    include_invoice: bool
    invoice: dict
    retention_days: int
    notes: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0


class PageOut(ORM):
    page_no: int
    label: str
    method: str
    language: str
    text_original: str
    text_english: str
    visual_description: str
    legible: bool
    user_corrected_text: str


class DocumentOut(ORM):
    id: str
    ref: str
    parent_id: str | None
    origin: str
    source_path: str
    original_filename: str
    mime_type: str
    size_bytes: int
    source_modified_at: str
    status: str
    status_detail: str
    duplicate_of_id: str | None
    doc_type: str
    doc_type_confidence: float
    doc_type_corrected: bool
    languages: list[str]
    page_count: int
    metadata_json: dict


class DocumentDetail(DocumentOut):
    pages: list[PageOut]


class DocumentPatch(BaseModel):
    doc_type: str | None = None
    page_corrections: dict[int, str] | None = None  # page_no -> corrected text


class NoteIn(BaseModel):
    kind: str
    title: str = ""
    body: str
    verified_by: str = ""
    verified_on: str = ""
    target: str = ""
    client_uuid: str = ""

    @field_validator("kind")
    @classmethod
    def _k(cls, v: str) -> str:
        allowed = {"field_observation", "hospital_verification", "police_verification", "rto_verification",
                   "fastag_verification", "gps_verification", "other_verification", "correction", "instruction"}
        if v not in allowed:
            raise ValueError(f"kind must be one of {sorted(allowed)}")
        return v


class NoteOut(ORM):
    id: str
    ref: str
    kind: str
    title: str
    body: str
    verified_by: str
    verified_on: str
    target: str
    client_uuid: str
    created_at: datetime


class JobOut(ORM):
    id: str
    case_id: str | None
    kind: str
    status: str
    progress: float
    message: str
    error: str
    attempts: int
    result: dict
    created_at: datetime
    updated_at: datetime


class AnalysisOut(ORM):
    id: str
    run_no: int
    status: str
    model: str
    playbooks_used: list
    document_refs: list
    note_refs: list
    result: dict
    validation: dict
    error: str
    created_at: datetime


class AnalysisSummary(ORM):
    id: str
    run_no: int
    status: str
    model: str
    playbooks_used: list
    validation: dict
    error: str
    created_at: datetime


class ReportIn(BaseModel):
    analysis_run_id: str | None = None
    page_limit: int | None = Field(default=None, ge=1, le=10)


class ReportOut(ORM):
    id: str
    analysis_run_id: str
    version: int
    status: str
    filename: str
    page_count: int
    page_limit: int
    template_key: str
    warnings: list
    has_pdf: bool = False
    drive_file_id: str
    error: str
    created_at: datetime


class PlaybookOut(ORM):
    key: str
    name: str
    kind: str
    active_version: int


class PlaybookVersionOut(ORM):
    version: int
    content_yaml: str
    change_note: str
    created_at: datetime


class PlaybookVersionIn(BaseModel):
    content_yaml: str
    change_note: str = ""
    activate: bool = True


class ConnectorOut(BaseModel):
    provider: str
    connected: bool
    account_email: str = ""
    configured: bool = False
