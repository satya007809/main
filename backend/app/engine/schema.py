"""JSON schemas for every AI stage (enforced with Claude structured outputs, then re-validated in code)."""

FINDING_CATEGORIES = ["verified_fact", "documentary_evidence", "claimant_statement", "third_party_statement",
                      "technical_observation", "field_verification", "ai_inference"]
VERDICTS = ["genuine_admissible", "not_genuine_or_breach_established", "insufficient_evidence"]
EXTERNAL_SOURCES = ["google_timeline", "gps", "fastag", "weather", "hospital", "police", "rto", "garage",
                    "employer", "bank", "cctv", "other"]


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}
SOURCE = _obj({"ref": S, "page": I})
SOURCES = {"type": "array", "items": SOURCE}


def arr(item: dict) -> dict:
    return {"type": "array", "items": item}


def enum(values: list[str]) -> dict:
    return {"type": "string", "enum": values}


DIGEST_SCHEMA = _obj({
    "doc_type": S,
    "title": S,
    "summary": S,
    "key_facts": arr(_obj({"fact": S, "page": I, "kind": enum(
        ["recorded_fact", "statement", "opinion", "measurement", "identifier", "date_time", "amount"])})),
    "dates_times": arr(_obj({"date": S, "time": S, "event": S, "page": I})),
    "persons": arr(_obj({"name": S, "role": S, "page": I})),
    "vehicles": arr(_obj({"registration": S, "details": S, "page": I})),
    "identifiers": arr(_obj({"label": S, "value": S, "page": I})),
    "anomalies": arr(_obj({"description": S, "page": I})),
})

ANALYSIS_SCHEMA = _obj({
    "case_summary": S,
    "detected_aspects": arr(_obj({"key": S, "reason": S})),
    "findings": arr(_obj({
        "id": S, "category": enum(FINDING_CATEGORIES), "statement": S, "sources": SOURCES,
        "significance": enum(["material", "supporting", "minor"])})),
    "chronology": arr(_obj({"date": S, "time": S, "event": S, "sources": SOURCES,
                            "certainty": enum(["documented", "stated", "inferred"])})),
    "discrepancies": arr(_obj({
        "id": S, "point": S, "version_a": S, "sources_a": SOURCES, "version_b": S, "sources_b": SOURCES,
        "significance": enum(["material", "minor"]), "resolution": S})),
    "checklist": arr(_obj({"item_id": S, "label": S,
                           "status": enum(["available", "partial", "missing", "not_applicable"]),
                           "refs": arr(S), "remarks": S})),
    "question_answers": arr(_obj({"question": S, "answer": S, "sources": SOURCES,
                                  "basis": enum(["established", "partly_established", "not_established", "pending"])})),
    "photo_observations": arr(_obj({"ref": S, "observation": S, "metadata_note": S})),
    "external_checks": arr(_obj({"source": enum(EXTERNAL_SOURCES),
                                 "status": enum(["verified_from_supplied_record", "pending", "not_required"]),
                                 "basis_refs": arr(S), "remarks": S})),
    "pending_verifications": arr(_obj({"item": S, "reason": S, "impact": enum(["could_change_opinion", "supporting"])})),
    "policy_analysis": _obj({
        "wording_available": B,
        "clauses": arr(_obj({"clause_ref": S, "quoted_text": S, "sources": SOURCES, "application": S})),
        "coverage_position": S}),
    "anomalies": arr(S),
    "opinion": _obj({"verdict": enum(VERDICTS), "summary": S,
                     "decisive_evidence": arr(_obj({"point": S, "sources": SOURCES})),
                     "limitations": arr(S)}),
})

DRAFT_SCHEMA = _obj({
    "sections": arr(_obj({"key": S, "heading": S, "paragraphs": arr(S)})),
})
