import pytest

from app.connectors.base import ConnectorError
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.local import LocalFolderConnector
from app.connectors.registry import detect_provider
from app.engine.validation import EvidenceIndex, unsupported_verification_claims, validate_analysis
from app.extraction.classifier import classify
from app.ingestion.filetypes import sniff
from app.playbooks.store import DEFAULTS_DIR, PlaybookValidationError, parse_and_validate


def _analysis(**over):
    a = {"findings": [], "chronology": [], "discrepancies": [], "checklist": [], "question_answers": [],
         "photo_observations": [], "external_checks": [], "pending_verifications": [],
         "policy_analysis": {"wording_available": True, "clauses": [], "coverage_position": ""},
         "anomalies": [], "opinion": {"verdict": "insufficient_evidence", "summary": "", "decisive_evidence": [],
                                      "limitations": []}}
    a.update(over)
    return a


IDX = EvidenceIndex(docs={"D001": 2, "D002": 1}, notes={"N001": "hospital_verification", "N002": "instruction"})


def test_unknown_ref_and_page_out_of_range():
    a = _analysis(findings=[{"id": "F1", "category": "documentary_evidence", "statement": "x",
                             "sources": [{"ref": "D009", "page": 1}, {"ref": "D001", "page": 5}],
                             "significance": "minor"}])
    errs = validate_analysis(a, IDX).errors
    assert any("unknown source 'D009'" in e for e in errs)
    assert any("page 5" in e for e in errs)


def test_verified_fact_needs_document_or_verification_note():
    a = _analysis(findings=[{"id": "F1", "category": "verified_fact", "statement": "x",
                             "sources": [{"ref": "N002", "page": 0}], "significance": "material"}])
    assert any("not backed" in e for e in validate_analysis(a, IDX).errors)
    a["findings"][0]["sources"] = [{"ref": "N001", "page": 0}]
    assert not validate_analysis(a, IDX).errors


def test_external_check_cannot_be_verified_without_record():
    a = _analysis(external_checks=[{"source": "fastag", "status": "verified_from_supplied_record",
                                    "basis_refs": [], "remarks": ""}])
    assert any("fastag" in e for e in validate_analysis(a, IDX).errors)


def test_definite_opinion_requires_sourced_evidence():
    a = _analysis(opinion={"verdict": "not_genuine_or_breach_established", "summary": "", "decisive_evidence":
                           [{"point": "suspicion", "sources": []}], "limitations": []})
    errs = validate_analysis(a, IDX).errors
    assert any("decisive evidence" in e for e in errs)
    assert any("Repudiation-type" in e for e in errs)


def test_genuine_with_open_material_discrepancy_warns():
    a = _analysis(discrepancies=[{"id": "X1", "point": "time", "version_a": "a", "sources_a": [{"ref": "D001", "page": 1}],
                                  "version_b": "b", "sources_b": [{"ref": "D002", "page": 1}],
                                  "significance": "material", "resolution": ""}],
                  opinion={"verdict": "genuine_admissible", "summary": "", "limitations": [],
                           "decisive_evidence": [{"point": "p", "sources": [{"ref": "D001", "page": 1}]}]})
    res = validate_analysis(a, IDX)
    assert not res.errors and any("unresolved" in w for w in res.warnings)


def test_unsupported_verification_language():
    a = _analysis(external_checks=[{"source": "hospital", "status": "verified_from_supplied_record",
                                    "basis_refs": ["N001"], "remarks": ""}])
    text = ("Admission was confirmed with the hospital. FASTag records were verified. "
            "Google Timeline is yet to be verified. Police records were not verified.")
    issues = unsupported_verification_claims(text, a)
    assert len(issues) == 1 and "fastag" in issues[0]


def test_all_default_playbooks_valid():
    keys = set()
    for p in DEFAULTS_DIR.glob("*.yaml"):
        keys.add(parse_and_validate(p.read_text())["key"])
    assert {"global_rules", "own_damage", "pa_injury", "pa_death", "theft", "fire", "road_accident",
            "hire_and_reward", "close_proximity", "vehicle_modification", "policy_breach", "general"} <= keys


def test_playbook_validation_errors():
    with pytest.raises(PlaybookValidationError):
        parse_and_validate("key: own_damage\nname: x\nkind: category\n")  # no objective
    with pytest.raises(PlaybookValidationError):
        parse_and_validate("key: x\nname: x\nkind: category\nobjective: o\n", expected_key="own_damage")
    with pytest.raises(PlaybookValidationError):
        parse_and_validate(": : bad yaml [")


def test_drive_link_parsing():
    c = GoogleDriveConnector(lambda: "t")
    assert c.parse_link("https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp?usp=sharing") == "1AbCdEfGhIjKlMnOp"
    assert c.parse_link("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOp") == "1AbCdEfGhIjKlMnOp"
    with pytest.raises(ConnectorError):
        c.parse_link("https://example.com/x")
    assert detect_provider("https://drive.google.com/drive/u/0/folders/abc") == "google_drive"
    assert detect_provider("https://1drv.ms/f/s!abc") == "onedrive"


def test_local_connector_blocks_traversal(tmp_path):
    (tmp_path / "root").mkdir()
    c = LocalFolderConnector(str(tmp_path / "root"))
    with pytest.raises(ConnectorError):
        c.parse_link("local://../")


def test_sniff_and_classify():
    assert sniff(b"%PDF-1.4 ...", "x.bin") == "pdf"
    assert sniff(b"\x89PNG\r\n\x1a\n....", "a") == "image"
    assert sniff("तारीख".encode(), "a.txt") == "text"
    assert classify("FIR_45.pdf", "FIRST INFORMATION REPORT under section 279 Police Station")[0] == "fir"
    assert classify("x.pdf", "POST MORTEM report cause of death: head injury")[0] == "postmortem_report"
    assert classify("IMG_001.jpg", "", is_photo=True)[0] == "photograph"
