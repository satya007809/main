"""Rule-based document-type classifier.

Deterministic first pass using filename + extracted English/original text. The AI digest step can refine
the type later, and the investigator can always correct it in the app.
"""
from __future__ import annotations

import re

DOC_TYPES: dict[str, list[str]] = {
    "policy_schedule": [r"policy schedule", r"certificate of insurance", r"\bidv\b", r"insured declared value",
                        r"period of insurance", r"policy no", r"premium"],
    "policy_wording": [r"policy wording", r"general exclusions", r"terms and conditions", r"section i\b", r"definitions"],
    "previous_policy": [r"previous policy", r"prev(ious)? insurer", r"expiring policy"],
    "claim_form": [r"claim form", r"claim intimation", r"motor claim form", r"cause of loss"],
    "fir": [r"first information report", r"\bf\.?i\.?r\b", r"under section", r"police station", r"प्रथम सूचना"],
    "police_report": [r"panchnama", r"spot panchanama", r"final report", r"police report", r"inquest", r"charge ?sheet"],
    "mvi_report": [r"motor vehicle inspector", r"\bmvi\b", r"mechanical inspection"],
    "postmortem_report": [r"post[- ]?mortem", r"autopsy", r"cause of death", r"pm report"],
    "death_certificate": [r"death certificate", r"certificate of death", r"registrar of births and deaths"],
    "mlc": [r"medico[- ]?legal", r"\bmlc\b"],
    "discharge_summary": [r"discharge summary", r"date of discharge", r"date of admission", r"diagnosis"],
    "medical_record": [r"case sheet", r"prescription", r"investigation report", r"radiology", r"x-?ray", r"ct scan",
                       r"hospital", r"\bopd\b", r"\bipd\b"],
    "driving_licence": [r"driving licen[cs]e", r"\bdl no\b", r"licensing authority", r"\bcov\b"],
    "registration_certificate": [r"registration certificate", r"\brc\b", r"chassis no", r"engine no", r"registering authority"],
    "permit": [r"\bpermit\b", r"contract carriage", r"goods carriage permit", r"all india tourist"],
    "fitness_certificate": [r"fitness certificate", r"certificate of fitness"],
    "fastag_statement": [r"fastag", r"toll plaza", r"\bnetc\b"],
    "google_timeline": [r"google timeline", r"location history", r"semanticsegments", r"timelineobjects"],
    "bank_statement": [r"bank statement", r"account statement", r"opening balance", r"closing balance", r"\bifsc\b"],
    "salary_slip": [r"salary slip", r"pay ?slip", r"basic pay", r"gross salary", r"net pay"],
    "attendance_record": [r"attendance", r"muster roll", r"in time", r"out time"],
    "invoice": [r"tax invoice", r"\bgstin\b", r"invoice no", r"bill no"],
    "towing_bill": [r"towing", r"crane charges", r"recovery van"],
    "garage_job_card": [r"job card", r"repair order", r"estimate", r"workshop", r"service advisor"],
    "survey_report": [r"survey report", r"surveyor", r"assessment of loss"],
    "fire_report": [r"fire station", r"fire brigade", r"fire and emergency", r"fire report"],
    "whatsapp_export": [r"\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}.{0,6} - [^:]+:", r"messages and calls are end-to-end encrypted"],
    "witness_statement": [r"statement of", r"witness", r"i,? the undersigned", r"do hereby state", r"declaration"],
    "identity_document": [r"aadhaar", r"\bpan\b", r"income tax department", r"voter id", r"passport"],
    "cctv_record": [r"cctv", r"footage"],
}

FILENAME_HINTS = {
    "fir": "fir", "pm": "postmortem_report", "postmortem": "postmortem_report", "dl": "driving_licence",
    "rc": "registration_certificate", "policy": "policy_schedule", "claim": "claim_form", "fastag": "fastag_statement",
    "jobcard": "garage_job_card", "job_card": "garage_job_card", "estimate": "garage_job_card", "tow": "towing_bill",
    "discharge": "discharge_summary", "death": "death_certificate", "mlc": "mlc", "permit": "permit",
    "fitness": "fitness_certificate", "statement": "witness_statement", "timeline": "google_timeline",
    "salary": "salary_slip", "attendance": "attendance_record", "invoice": "invoice", "whatsapp": "whatsapp_export",
    "panchnama": "police_report", "mvi": "mvi_report",
}

_COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in DOC_TYPES.items()}


def classify(filename: str, text: str, is_photo: bool = False) -> tuple[str, float]:
    if is_photo and len(text.strip()) < 40:
        return "photograph", 0.8
    scores: dict[str, float] = {}
    sample = text[:20000]
    for dtype, pats in _COMPILED.items():
        hits = sum(1 for p in pats if p.search(sample))
        if hits:
            scores[dtype] = hits / len(pats) + 0.15 * hits
    stem = re.sub(r"[^a-z_]", " ", filename.lower())
    for token in stem.split():
        if token in FILENAME_HINTS:
            dt = FILENAME_HINTS[token]
            scores[dt] = scores.get(dt, 0) + 0.6
    if not scores:
        return ("photograph", 0.5) if is_photo else ("unknown", 0.0)
    best = max(scores, key=scores.get)
    return best, round(min(0.95, scores[best]), 2)
