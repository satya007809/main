"""Vertical slice: create case -> link folder -> recursive scan -> OD playbook analysis -> DOCX report."""
import io

import docx
from docx.shared import Pt

from app.jobs.queue import drain
from tests.synthetic_case import build

API = "/api/v1"


def test_full_od_workflow(client, auth_headers, fake_llm, tmp_root):
    build(tmp_root / "folders" / "OD_case_1")
    h = auth_headers
    r = client.post(f"{API}/cases", headers=h, json={
        "insured_name": "R. Venkata Rao", "claim_number": "CLM/OD/2026/7788", "policy_number": "3001/OD/2026/000123",
        "vehicle_registration": "AP 39 AB 1234", "insurer_name": "Demo General Insurance",
        "investigation_reference": "BID/2026/001", "investigation_date": "2026-03-20", "category": "own_damage",
        "source_link": "local://OD_case_1", "page_limit": 7, "include_invoice": True,
        "invoice": {"invoice_number": "BI/26/014", "invoice_date": "2026-03-25", "bill_to": "Demo General Insurance",
                    "items": [{"description": "Investigation fee - OD claim", "amount": 6000}], "gst_percent": 18}})
    assert r.status_code == 201, r.text
    case = r.json()
    assert case["source_provider"] == "local"

    # --- scan
    job = client.post(f"{API}/cases/{case['id']}/scan", headers=h).json()
    assert drain() >= 1
    job = client.get(f"{API}/jobs/{job['id']}", headers=h).json()
    assert job["status"] == "done", job
    docs = client.get(f"{API}/cases/{case['id']}/documents", headers=h).json()
    by_name = {d["original_filename"]: d for d in docs}

    assert by_name["damage_front_copy.jpg"]["status"] == "duplicate"
    assert by_name["bank_statement_protected.pdf"]["status"] == "password_protected"
    assert by_name["survey_report_corrupted.pdf"]["status"] == "corrupted"
    assert by_name["spot_video.mp4"]["status"] == "unsupported"
    assert by_name["secret_estimate.pdf"]["status"] == "password_protected"
    assert by_name["additional_documents.zip"]["status"] == "container"
    assert by_name["inner_docs.zip"]["status"] == "container"
    # nested zip members preserve their path
    tow = by_name["towing_bill.txt"]
    assert tow["status"] == "processed" and tow["source_path"].endswith("inner_docs.zip!/Towing")
    assert by_name["FIR_telugu.png"]["status"] == "processed"
    assert by_name["policy_schedule.pdf"]["doc_type"] == "policy_schedule"
    assert by_name["policy_schedule.pdf"]["source_path"] == "Policy"
    assert by_name["DL_scan.pdf"]["status"] == "processed"  # scanned page -> OCR
    # EXIF retained for photos
    assert by_name["damage_left.jpg"]["metadata_json"]["exif"]["DateTimeOriginal"] == "2026:02:20 18:05:00"
    assert by_name["damage_front.jpg"]["metadata_json"]["exif"]["GPSLatitude"] > 16
    # multilingual: Telugu original preserved alongside English
    fir = client.get(f"{API}/documents/{by_name['FIR_telugu.png']['id']}", headers=h).json()
    assert "ప్రథమ" in fir["pages"][0]["text_original"] and "First Information Report" in fir["pages"][0]["text_english"]
    inv = client.get(f"{API}/cases/{case['id']}/inventory", headers=h).json()
    assert inv["unreadable"] == 4 and inv["duplicates"] == 1 and inv["pending"] == 0

    # rescanning is idempotent (resume semantics): nothing re-processed
    client.post(f"{API}/cases/{case['id']}/scan", headers=h)
    drain()
    assert len(client.get(f"{API}/cases/{case['id']}/documents", headers=h).json()) == len(docs)

    # --- investigator adds a hospital verification note and a correction
    note = client.post(f"{API}/cases/{case['id']}/notes", headers=h, json={
        "kind": "hospital_verification", "title": "Hospital check", "body": "No hospital visit involved.",
        "verified_by": "Investigator", "verified_on": "2026-03-21", "client_uuid": "abc-1"}).json()
    again = client.post(f"{API}/cases/{case['id']}/notes", headers=h, json={
        "kind": "hospital_verification", "body": "dup", "client_uuid": "abc-1"}).json()
    assert again["id"] == note["id"]  # offline sync idempotency

    # --- analysis (first fake output cites a non-existent doc -> repaired)
    job = client.post(f"{API}/cases/{case['id']}/analyses", headers=h).json()
    drain()
    assert client.get(f"{API}/jobs/{job['id']}", headers=h).json()["status"] == "done"
    runs = client.get(f"{API}/cases/{case['id']}/analyses", headers=h).json()
    run = client.get(f"{API}/analyses/{runs[0]['id']}", headers=h).json()
    assert "analysis-repair" in fake_llm.calls
    assert run["validation"]["ok"] is True
    assert {"key": "own_damage", "version": 1} in run["playbooks_used"]
    assert {"key": "global_rules", "version": 1} in run["playbooks_used"]
    assert any("Policy wording not supplied" in w for w in run["validation"]["warnings"])
    assert any(c["source"] == "hospital" and c["status"] == "verified_from_supplied_record"
               for c in run["result"]["external_checks"])
    # injection text reached the model only inside the fenced evidence block
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in fake_llm.last_analysis_content.split("<document ", 1)[1]
    assert client.get(f"{API}/cases/{case['id']}", headers=h).json()["status"] == "pending_verification"

    # --- report
    job = client.post(f"{API}/cases/{case['id']}/reports", headers=h, json={}).json()
    drain()
    jr = client.get(f"{API}/jobs/{job['id']}", headers=h).json()
    assert jr["status"] == "done", jr
    reports = client.get(f"{API}/cases/{case['id']}/reports", headers=h).json()
    rep = reports[0]
    assert rep["version"] == 1 and rep["status"] == "completed"
    assert fake_llm.calls.count("report-draft") >= 2  # unsupported FASTag claim forced a redraft
    r = client.get(f"{API}/reports/{rep['id']}/download?format=docx", headers=h)
    assert r.status_code == 200
    d = docx.Document(io.BytesIO(r.content))
    normal = d.styles["Normal"]
    assert normal.font.name == "Times New Roman" and normal.font.size == Pt(13)
    assert normal.paragraph_format.line_spacing == 1.5
    full = "\n".join(p.text for p in d.paragraphs)
    assert "INVESTIGATION REPORT – MOTOR OWN DAMAGE CLAIM" in full
    assert "9. Conclusion and Opinion" in full
    assert "insufficient to reach a reliable conclusion" in full
    assert "verified with the toll operator" not in full
    assert "INVOICE" in full
    tables_text = "\n".join(c.text for t in d.tables for row in t.rows for c in row.cells)
    assert "CLM/OD/2026/7788" in tables_text and "7,080.00" in tables_text  # 6000 + 18% GST
    assert "22:30 hrs (claim form)" in tables_text  # discrepancy table
    assert "Test Investigator" in full
    if rep["has_pdf"]:
        assert rep["page_count"] - 1 <= 7

    # report versioning after new evidence
    client.post(f"{API}/cases/{case['id']}/analyses", headers=h)
    drain()
    client.post(f"{API}/cases/{case['id']}/reports", headers=h, json={"page_limit": 10})
    drain()
    versions = [x["version"] for x in client.get(f"{API}/cases/{case['id']}/reports", headers=h).json()]
    assert versions == [2, 1]

    audit = client.get(f"{API}/cases/{case['id']}/audit", headers=h).json()
    actions = {a["action"] for a in audit}
    assert {"case.created", "case.scanned", "analysis.completed", "report.generated", "report.downloaded"} <= actions

    dash = client.get(f"{API}/dashboard", headers=h).json()
    assert dash["groups"]["reports_ready"] >= 1
    assert client.get(f"{API}/cases?q=AP 39", headers=h).json()[0]["id"] == case["id"]


def test_upload_additional_evidence(client, auth_headers, fake_llm, tmp_root):
    h = auth_headers
    build(tmp_root / "folders" / "OD_case_2")
    case = client.post(f"{API}/cases", headers=h, json={"category": "own_damage", "claim_number": "C2",
                                                         "source_link": "local://OD_case_2"}).json()
    files = {"file": ("spot_note.txt", b"Spot visit: median damage marks visible near km 12.", "text/plain")}
    d = client.post(f"{API}/cases/{case['id']}/documents", headers=h, files=files, data={"client_uuid": "u-1"}).json()
    d2 = client.post(f"{API}/cases/{case['id']}/documents", headers=h, files=files, data={"client_uuid": "u-1"}).json()
    assert d["id"] == d2["id"] and d["status"] == "pending"
    drain()
    doc = client.get(f"{API}/documents/{d['id']}", headers=h).json()
    assert doc["status"] == "processed" and doc["origin"] == "upload"
    r = client.patch(f"{API}/documents/{d['id']}", headers=h, json={"doc_type": "witness_statement",
                                                                   "page_corrections": {"1": "Corrected text"}}).json()
    assert r["doc_type_corrected"] and r["pages"][0]["user_corrected_text"] == "Corrected text"


def test_report_blocked_without_invoice_details(client, auth_headers, fake_llm, tmp_root):
    h = auth_headers
    build(tmp_root / "folders" / "OD_case_3")
    case = client.post(f"{API}/cases", headers=h, json={"category": "own_damage", "claim_number": "C3",
                                                         "source_link": "local://OD_case_3",
                                                         "include_invoice": True, "invoice": {}}).json()
    client.post(f"{API}/cases/{case['id']}/scan", headers=h)
    drain()
    client.post(f"{API}/cases/{case['id']}/analyses", headers=h)
    drain()
    job = client.post(f"{API}/cases/{case['id']}/reports", headers=h, json={}).json()
    drain()
    j = client.get(f"{API}/jobs/{job['id']}", headers=h).json()
    assert j["status"] == "failed" and "Invoice details missing" in j["error"]
