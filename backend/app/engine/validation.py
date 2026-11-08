"""Deterministic validation of AI output before it can be used in a report.

Errors block report generation; warnings are shown to the investigator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

VERIFICATION_NOTE_KINDS = {"hospital_verification", "police_verification", "rto_verification", "fastag_verification",
                           "gps_verification", "other_verification", "field_observation"}
SOURCE_REQUIRED = {"verified_fact", "documentary_evidence", "technical_observation", "field_verification",
                   "claimant_statement", "third_party_statement"}
EXTERNAL_WORDS = {
    "google_timeline": r"(google )?timeline|location history",
    "gps": r"\bgps\b",
    "fastag": r"fastag|toll",
    "weather": r"weather|rainfall|meteorolog",
    "hospital": r"hospital",
    "police": r"police|station house|\bsho\b",
    "rto": r"\brto\b|\brta\b|vahan|parivahan|transport authority",
}
_VERIFY_VERB = r"(independently |duly |physically )?(verified|confirmed|cross[- ]checked|ascertained from|checked with|visited)"


@dataclass
class EvidenceIndex:
    docs: dict[str, int]  # ref -> page_count (0 means unpaged, allow page 0/1)
    notes: dict[str, str]  # ref -> kind
    unusable_docs: list[str] = field(default_factory=list)  # refs that were unreadable/password/corrupt


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"errors": self.errors, "warnings": self.warnings, "ok": not self.errors}


def _check_sources(srcs: list[dict], idx: EvidenceIndex, where: str, res: ValidationResult) -> None:
    for s in srcs:
        ref, page = s.get("ref", ""), s.get("page", 0)
        if ref in idx.notes:
            continue
        if ref not in idx.docs:
            res.errors.append(f"{where}: cites unknown source '{ref}'")
            continue
        pc = idx.docs[ref]
        if page < 0 or (pc and page > pc):
            res.errors.append(f"{where}: {ref} has {pc} page(s) but page {page} was cited")


def validate_analysis(a: dict, idx: EvidenceIndex, required_checklist: list[str] | None = None) -> ValidationResult:
    res = ValidationResult()
    for f in a.get("findings", []):
        where = f"Finding {f.get('id')}"
        _check_sources(f.get("sources", []), idx, where, res)
        if f["category"] in SOURCE_REQUIRED and not f.get("sources"):
            res.errors.append(f"{where} ({f['category']}) has no source reference")
        if f["category"] == "field_verification":
            if not any(s["ref"] in idx.notes for s in f.get("sources", [])):
                res.errors.append(f"{where}: field verification must cite an investigator note (N###)")
        if f["category"] == "verified_fact":
            doc_srcs = [s for s in f.get("sources", []) if s["ref"] in idx.docs or
                        idx.notes.get(s["ref"]) in VERIFICATION_NOTE_KINDS]
            if not doc_srcs:
                res.errors.append(f"{where}: verified fact is not backed by a document or verification note")
    for i, c in enumerate(a.get("chronology", []), 1):
        _check_sources(c.get("sources", []), idx, f"Chronology #{i}", res)
        if c["certainty"] != "inferred" and not c.get("sources"):
            res.errors.append(f"Chronology #{i} ({c['event'][:40]}) has no source")
    for d in a.get("discrepancies", []):
        _check_sources(d.get("sources_a", []) + d.get("sources_b", []), idx, f"Discrepancy {d.get('id')}", res)
        if not d.get("sources_a") or not d.get("sources_b"):
            res.errors.append(f"Discrepancy {d.get('id')} must cite sources for both versions")
    for q in a.get("question_answers", []):
        _check_sources(q.get("sources", []), idx, "Question answer", res)
    for c in a.get("checklist", []):
        for r in c.get("refs", []):
            if r not in idx.docs and r not in idx.notes:
                res.errors.append(f"Checklist '{c['item_id']}' cites unknown ref {r}")
    if required_checklist:
        status = {c["item_id"]: c["status"] for c in a.get("checklist", [])}
        for item in required_checklist:
            if status.get(item) in (None, "missing"):
                res.warnings.append(f"Required document not available: {item}")
    for p in a.get("photo_observations", []):
        if p["ref"] not in idx.docs:
            res.errors.append(f"Photo observation cites unknown ref {p['ref']}")
    for e in a.get("external_checks", []):
        if e["status"] == "verified_from_supplied_record":
            basis = [r for r in e.get("basis_refs", []) if r in idx.docs or r in idx.notes]
            if not basis:
                res.errors.append(f"External check '{e['source']}' marked verified without a supplied record or note")
    pol = a.get("policy_analysis", {})
    for c in pol.get("clauses", []):
        _check_sources(c.get("sources", []), idx, f"Policy clause {c.get('clause_ref')}", res)
        if c.get("quoted_text") and not c.get("sources"):
            res.errors.append(f"Policy clause {c.get('clause_ref')} is quoted without a source document")
    op = a.get("opinion", {})
    for d in op.get("decisive_evidence", []):
        _check_sources(d.get("sources", []), idx, "Opinion evidence", res)
    if op.get("verdict") in ("genuine_admissible", "not_genuine_or_breach_established"):
        if not any(d.get("sources") for d in op.get("decisive_evidence", [])):
            res.errors.append("A definite opinion must cite decisive evidence with sources")
    if op.get("verdict") == "not_genuine_or_breach_established" and not pol.get("clauses") \
            and not any(f["category"] in ("verified_fact", "documentary_evidence", "field_verification")
                        for f in a.get("findings", []) if f["significance"] == "material"):
        res.errors.append("Repudiation-type opinion without established material facts or policy clause")
    if op.get("verdict") == "genuine_admissible":
        open_material = [d["id"] for d in a.get("discrepancies", [])
                         if d["significance"] == "material" and not d.get("resolution", "").strip()]
        if open_material:
            res.warnings.append(f"Opinion is 'genuine' but material discrepancies are unresolved: {', '.join(open_material)}")
    if idx.unusable_docs and not op.get("limitations"):
        res.warnings.append("Some documents were unreadable/protected but the opinion lists no limitations")
    if not pol.get("wording_available"):
        res.warnings.append("Policy wording not supplied: coverage position is provisional")
    for an in a.get("anomalies", []):
        res.warnings.append(f"Anomaly reported by engine: {an}")
    return res


def unsupported_verification_claims(text: str, analysis: dict) -> list[str]:
    """Find narrative sentences claiming verification of an external source that the analysis has not verified."""
    verified = {e["source"] for e in analysis.get("external_checks", [])
                if e["status"] == "verified_from_supplied_record"}
    issues = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        s = sentence.lower()
        if not re.search(_VERIFY_VERB, s) or re.search(r"\b(not|pending|could not|yet to|awaited|unable)\b", s):
            continue
        for src, pat in EXTERNAL_WORDS.items():
            if src not in verified and re.search(pat, s):
                issues.append(f"Unsupported verification claim ({src}): \"{sentence.strip()[:160]}\"")
    return issues
