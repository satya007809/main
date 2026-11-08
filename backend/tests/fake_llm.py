"""Deterministic stand-in for the Claude API used by the automated tests.

It derives its output from the evidence it is given (inventory refs, notes, template sections) so the tests
exercise the real validation, repair, redraft and page-limit logic. It lives in tests/ only.
"""
from __future__ import annotations

import json
import re

import yaml

from app.llm.client import LLMResult


class FakeLLM:
    def __init__(self, bad_ref_first: bool = True, unsupported_claim_first: bool = True, words: int | None = None):
        self.calls: list[str] = []
        self.bad_ref_first = bad_ref_first
        self.unsupported_claim_first = unsupported_claim_first
        self.words = words
        self.last_analysis_content = ""

    def structured(self, *, purpose, system, content, schema, model=None, max_tokens=32000):
        self.calls.append(purpose)
        text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
        if purpose == "ocr":
            img = next(b for b in content if b["type"] == "image")
            from PIL import Image
            import base64, io
            im = Image.open(io.BytesIO(base64.b64decode(img["source"]["data"])))
            photo = im.width > im.height
            data = {
                "languages": [] if photo else ["te", "en"],
                "text_original": "" if photo else "ప్రథమ సమాచార నివేదిక FIR No. 45/2026 గన్నవరం పోలీస్ స్టేషన్ " + text[-40:],
                "text_english": "" if photo else "First Information Report FIR No. 45/2026 Gannavaram Police Station. "
                                                 "Driving licence and police station details as scanned.",
                "is_photograph": photo,
                "visual_description": "Car with damage visible on the front portion." if photo else "",
                "legible": True, "legibility_notes": "",
            }
        elif purpose.startswith("digest"):
            ref = purpose.split()[-1]
            first = re.search(r"\[Page 1[^\]]*\]\n(.{0,160})", text, re.S)
            data = {"doc_type": "unknown", "title": ref, "summary": f"Digest of {ref}",
                    "key_facts": [{"fact": (first.group(1) if first else "content").strip()[:120], "page": 1,
                                   "kind": "recorded_fact"}],
                    "dates_times": [], "persons": [], "vehicles": [], "identifiers": [], "anomalies": []}
        elif purpose.startswith("analysis"):
            data = self._analysis(text, repair=purpose.endswith("repair"))
        elif purpose == "report-draft":
            data = self._draft(system, text)
        else:
            raise AssertionError(purpose)
        return LLMResult(data=data, model="fake-model", usage={"input_tokens": 10, "output_tokens": 10})

    def _analysis(self, text: str, repair: bool) -> dict:
        self.last_analysis_content = text
        inv = json.loads(re.search(r"<case_documents>\n(.*?)\n</case_documents>", text, re.S).group(1))
        notes = json.loads(re.search(r"<investigator_notes>\n(.*?)\n</investigator_notes>", text, re.S).group(1))
        usable = [d for d in inv if d["status"] in ("processed", "partial")]
        findings = [{"id": f"F{i}", "category": "documentary_evidence", "statement": f"{d['filename']} examined",
                     "sources": [{"ref": d["ref"], "page": 1}], "significance": "supporting"}
                    for i, d in enumerate(usable, 1)]
        if self.bad_ref_first and not repair:
            findings.append({"id": "FX", "category": "verified_fact", "statement": "Hospital confirmed admission",
                             "sources": [{"ref": "D999", "page": 3}], "significance": "material"})
        hosp = [n for n in notes if n["kind"] == "hospital_verification"]
        for n in hosp:
            findings.append({"id": f"V{n['ref']}", "category": "field_verification", "statement": n["body"],
                             "sources": [{"ref": n["ref"], "page": 0}], "significance": "material"})
        a, b = usable[0], usable[1]
        return {
            "case_summary": "Synthetic OD case.",
            "detected_aspects": [{"key": "close_proximity", "reason": "Accident 12 days after inception"}],
            "findings": findings,
            "chronology": [{"date": "02.03.2026", "time": "00:00", "event": "Policy incepted",
                            "sources": [{"ref": a["ref"], "page": 1}], "certainty": "documented"},
                           {"date": "14.03.2026", "time": "22:30", "event": "Accident as per claim form",
                            "sources": [{"ref": b["ref"], "page": 1}], "certainty": "stated"}],
            "discrepancies": [{"id": "X1", "point": "Time of accident", "version_a": "22:30 hrs (claim form)",
                               "sources_a": [{"ref": a["ref"], "page": 1}], "version_b": "23:15 hrs (statement)",
                               "sources_b": [{"ref": b["ref"], "page": 1}], "significance": "material",
                               "resolution": ""}],
            "checklist": [{"item_id": "policy_schedule", "label": "Policy", "status": "available",
                           "refs": [a["ref"]], "remarks": ""}],
            "question_answers": [],
            "photo_observations": [],
            "external_checks": [
                {"source": "fastag", "status": "pending", "basis_refs": [], "remarks": "Not supplied"},
                {"source": "hospital", "status": "verified_from_supplied_record" if hosp else "pending",
                 "basis_refs": [n["ref"] for n in hosp], "remarks": ""}],
            "pending_verifications": [{"item": "FASTag statement for 14.03.2026", "reason": "Not in folder",
                                       "impact": "could_change_opinion"}],
            "policy_analysis": {"wording_available": False, "clauses": [{
                "clause_ref": "Limitations as to use", "quoted_text": "any purpose other than hire or reward",
                "sources": [{"ref": a["ref"], "page": 1}], "application": "No evidence of hire use."}],
                "coverage_position": "Provisional"},
            "anomalies": ["notes_with_injection.txt contains an instruction to mark the claim genuine; ignored"],
            "opinion": {"verdict": "insufficient_evidence", "summary": "Material time discrepancy unresolved.",
                        "decisive_evidence": [{"point": "Time discrepancy", "sources": [{"ref": a["ref"], "page": 1}]}],
                        "limitations": ["Bank statement password protected"]},
        }

    def _draft(self, system: str, text: str) -> dict:
        block = system.split("## REQUIRED SECTIONS (use exactly these keys and headings, in order)\n", 1)[1]
        block = block.split("\n\nSECURITY:", 1)[0]
        secs = yaml.safe_load(block)["sections"]
        budget = int(re.search(r"must not exceed (\d+) words", text).group(1))
        words = self.words or budget
        per = max(20, words // max(len(secs), 1))
        first_draft = self.calls.count("report-draft") == 1
        out = []
        for s in secs:
            para = " ".join(["The investigation examined the documents in the folder carefully."] * (per // 9 + 1))
            paras = [" ".join(para.split()[:per])]
            if s["key"] == "investigation" and first_draft and self.unsupported_claim_first:
                paras.append("The FASTag records were verified with the toll operator.")
            out.append({"key": s["key"], "heading": s["heading"], "paragraphs": paras})
        return {"sections": out}
