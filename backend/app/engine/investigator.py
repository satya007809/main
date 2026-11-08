"""Central investigation engine: per-document digests -> case synthesis -> validation (+ one repair pass)."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
from collections.abc import Callable

from PIL import Image
from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm.client import get_llm
from ..models import AnalysisRun, Case, CaseNote, Document, DocumentDigest
from ..playbooks.store import compose_for_case
from ..storage import get_storage
from .prompts import DIGEST_SYSTEM, analysis_system, fence_json
from .schema import ANALYSIS_SCHEMA, DIGEST_SCHEMA
from .validation import EvidenceIndex, validate_analysis

log = logging.getLogger(__name__)
DIGEST_VERSION = "digest-v1"
USABLE = ("processed", "partial")
UNUSABLE = ("unreadable", "password_protected", "corrupted", "unsupported", "error")
MAX_PHOTOS = 24

Progress = Callable[[float, str], None]


def page_text(p) -> str:
    if p.user_corrected_text:
        return p.user_corrected_text
    parts = []
    if p.text_english and p.text_english.strip() != p.text_original.strip():
        parts.append(p.text_english)
        if p.text_original.strip():
            parts.append(f"[Original-language text]\n{p.text_original}")
    else:
        parts.append(p.text_original)
    if p.visual_description:
        parts.append(f"[Visual description] {p.visual_description}")
    if not p.legible:
        parts.append("[Page marked illegible by OCR]")
    return "\n".join(x for x in parts if x)


def document_text(doc: Document) -> str:
    return "\n\n".join(f"[Page {p.page_no}{' - ' + p.label if p.label else ''}]\n{page_text(p)}" for p in doc.pages)


def _doc_header(doc: Document) -> dict:
    return {"ref": doc.ref, "filename": doc.original_filename, "folder": doc.source_path, "type": doc.doc_type,
            "pages": doc.page_count, "status": doc.status, "status_detail": doc.status_detail,
            "source_modified": doc.source_modified_at,
            "metadata": {k: v for k, v in (doc.metadata_json or {}).items() if k in ("exif", "pdf_info", "exported_as")}}


def get_digest(db: Session, doc: Document) -> dict:
    corrections = "|".join(p.user_corrected_text for p in doc.pages if p.user_corrected_text)
    key = hashlib.sha256(f"{DIGEST_VERSION}:{doc.sha256}:{doc.doc_type}:{corrections}".encode()).hexdigest()
    cached = db.query(DocumentDigest).filter_by(document_id=doc.id, cache_key=key).one_or_none()
    if cached:
        return cached.digest
    s = get_settings()
    content = [{"type": "text", "text": (
        f"Document {doc.ref}: {doc.original_filename} (folder: {doc.source_path or '/'}; "
        f"pre-classified as {doc.doc_type}; {doc.page_count} page(s))\n"
        f"<document ref=\"{doc.ref}\">\n{document_text(doc)}\n</document>\nReturn the digest JSON.")}]
    res = get_llm().structured(purpose=f"digest {doc.ref}", system=DIGEST_SYSTEM, content=content,
                               schema=DIGEST_SCHEMA, model=s.ai_digest_model, max_tokens=16000)
    db.add(DocumentDigest(document_id=doc.id, cache_key=key, model=res.model, digest=res.data))
    if not doc.doc_type_corrected and res.data.get("doc_type") and doc.doc_type in ("unknown", "photograph") \
            and res.data["doc_type"] not in ("unknown", ""):
        doc.doc_type = res.data["doc_type"]
    db.commit()
    return res.data


def _photo_block(data: bytes) -> dict | None:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.standard_b64encode(buf.getvalue()).decode()}}


def case_particulars(case: Case) -> dict:
    return {"insured_name": case.insured_name, "claim_number": case.claim_number, "policy_number": case.policy_number,
            "vehicle_registration": case.vehicle_registration, "insurer": case.insurer_name,
            "investigation_reference": case.investigation_reference, "category": case.category,
            "additional_aspects": case.additional_aspects, "investigation_date": case.investigation_date}


def build_evidence(db: Session, case: Case, digests: dict[str, dict]) -> tuple[list[dict], EvidenceIndex, list[str]]:
    docs = sorted(case.documents, key=lambda d: d.ref)
    notes = db.query(CaseNote).filter_by(case_id=case.id).order_by(CaseNote.ref).all()
    idx = EvidenceIndex(
        docs={d.ref: d.page_count for d in docs if d.status in USABLE or d.status == "duplicate"},
        notes={n.ref: n.kind for n in notes},
        unusable_docs=[d.ref for d in docs if d.status in UNUSABLE])
    inventory = [_doc_header(d) | ({"duplicate_of": next((x.ref for x in docs if x.id == d.duplicate_of_id), "")}
                                   if d.status == "duplicate" else {}) for d in docs]
    note_list = [{"ref": n.ref, "kind": n.kind, "title": n.title, "body": n.body, "verified_by": n.verified_by,
                  "verified_on": n.verified_on, "target": n.target} for n in notes]
    text = [
        "## CASE PARTICULARS (entered by investigator)\n" + json.dumps(case_particulars(case), ensure_ascii=False),
        "## DOCUMENT INVENTORY (every file found in the linked folder, including problems)\n"
        + fence_json("case_documents", inventory),
        "## INVESTIGATOR NOTES, FIELD OBSERVATIONS, VERIFICATION RESULTS AND CORRECTIONS\n"
        "(Corrections override the documents' extracted text where they conflict.)\n"
        + fence_json("investigator_notes", note_list),
        "## PER-DOCUMENT DIGESTS\n" + "\n".join(
            f"<digest ref=\"{r}\">{json.dumps(d, ensure_ascii=False)}</digest>" for r, d in digests.items()),
    ]
    budget = get_settings().ai_max_case_chars
    full = []
    usable = [d for d in docs if d.status in USABLE]
    # prioritise documents with more pages of text-bearing types (policy, FIR, PM, statements) before photos
    usable.sort(key=lambda d: (d.doc_type == "photograph", d.ref))
    omitted = []
    for d in usable:
        t = document_text(d)
        if len(t) > budget:
            omitted.append(d.ref)
            continue
        budget -= len(t)
        full.append(f"<document ref=\"{d.ref}\" filename=\"{d.original_filename}\">\n{t}\n</document>")
    text.append("## FULL EXTRACTED TEXT\n" + "\n".join(full))
    if omitted:
        text.append(f"(Full text omitted for size; rely on digests: {', '.join(omitted)})")
    content: list[dict] = [{"type": "text", "text": "\n\n".join(text)}]
    photos = [d for d in usable if d.doc_type == "photograph" and d.storage_key][:MAX_PHOTOS]
    for d in photos:
        try:
            blk = _photo_block(get_storage().get(d.storage_key))
        except Exception:
            blk = None
        if blk:
            content.append({"type": "text", "text": f"Photograph {d.ref} ({d.original_filename}), "
                                                    f"EXIF: {json.dumps((d.metadata_json or {}).get('exif', {}))}"})
            content.append(blk)
    return content, idx, [d.ref for d in photos]


def run_analysis(db: Session, run: AnalysisRun, progress: Progress) -> None:
    case = db.get(Case, run.case_id)
    glob, books, used = compose_for_case(db, case.category, case.additional_aspects or [])
    run.playbooks_used = used
    usable = [d for d in sorted(case.documents, key=lambda d: d.ref) if d.status in USABLE]
    digests: dict[str, dict] = {}
    for i, d in enumerate(usable):
        progress(0.05 + 0.55 * i / max(len(usable), 1), f"Reading {d.ref} {d.original_filename}")
        digests[d.ref] = get_digest(db, d)
    progress(0.62, "Building evidence pack")
    content, idx, _photos = build_evidence(db, case, digests)
    run.document_refs = sorted(idx.docs)
    run.note_refs = sorted(idx.notes)
    system = analysis_system(glob, books)
    required = [c["id"] for pb in books[:1] for c in pb.get("document_checklist", []) if c.get("required")]
    content.append({"type": "text", "text": "Produce the complete investigation analysis JSON for this case."})
    progress(0.65, "Running investigation analysis")
    res = get_llm().structured(purpose="analysis", system=system, content=content, schema=ANALYSIS_SCHEMA,
                               max_tokens=64000)
    usage = dict(res.usage)
    val = validate_analysis(res.data, idx, required)
    if val.errors:
        progress(0.85, "Correcting unsupported references")
        repair = content + [{"type": "text", "text": (
            "Your previous analysis failed validation:\n- " + "\n- ".join(val.errors) +
            "\n\nPrevious output:\n" + json.dumps(res.data, ensure_ascii=False) +
            "\n\nReturn the complete corrected analysis JSON. Remove or re-source any claim you cannot support; "
            "never invent references.")}]
        res = get_llm().structured(purpose="analysis-repair", system=system, content=repair,
                                   schema=ANALYSIS_SCHEMA, max_tokens=64000)
        usage = {k: usage.get(k, 0) + res.usage.get(k, 0) for k in set(usage) | set(res.usage)}
        val = validate_analysis(res.data, idx, required)
    run.result = res.data
    run.validation = val.as_dict()
    run.model = res.model
    run.usage = usage
    run.status = "completed"
    pending = [p for p in res.data.get("pending_verifications", []) if p["impact"] == "could_change_opinion"]
    case.status = "pending_verification" if pending else "analysed"
    db.commit()
    progress(1.0, "Analysis complete")
