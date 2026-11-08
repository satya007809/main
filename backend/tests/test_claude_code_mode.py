"""Claude-plan mode: the server makes no AI calls; a Claude Code session drives tools/bid_agent.py.

Starts a real uvicorn server and runs the CLI as a subprocess, exactly as Claude Code would.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import docx
import io
import pytest
import uvicorn

from app.config import get_settings
from app.jobs.queue import drain
from app.llm.client import set_llm
from tests.synthetic_case import build

API = "/api/v1"
CLI = str(Path(__file__).resolve().parents[2] / "tools" / "bid_agent.py")


class NoAI:
    def structured(self, **kw):
        raise AssertionError(f"server must not call the AI in claude_code mode ({kw.get('purpose')})")


@pytest.fixture
def claude_code_mode():
    s = get_settings()
    s.ai_mode = "claude_code"
    set_llm(NoAI())
    yield
    s.ai_mode = "api"
    set_llm(None)


@pytest.fixture(scope="module")
def live_server(client):
    from app.main import app

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


def cli(server, token, *args, cwd=None):
    env = {**os.environ, "BID_SERVER_URL": server, "BID_AGENT_TOKEN": token}
    p = subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, env=env, cwd=cwd, timeout=120)
    return p.returncode, p.stdout + p.stderr


def test_claude_code_workflow(client, auth_headers, tmp_root, tmp_path, claude_code_mode, live_server):
    h = auth_headers
    assert client.get(f"{API}/config", headers=h).json() == {"ai_mode": "claude_code"}
    build(tmp_root / "folders" / "cc_case")
    case = client.post(f"{API}/cases", headers=h, json={
        "category": "own_damage", "claim_number": "CLM/CC/1", "insured_name": "R. Venkata Rao",
        "vehicle_registration": "AP 39 AB 1234", "source_link": "local://cc_case", "page_limit": 7}).json()
    client.post(f"{API}/cases/{case['id']}/scan", headers=h)
    drain()
    docs = {d["original_filename"]: d for d in client.get(f"{API}/cases/{case['id']}/documents", headers=h).json()}
    assert docs["DL_scan.pdf"]["status"] == "awaiting_reading"     # scanned page left for Claude Code
    assert docs["FIR_telugu.png"]["status"] == "awaiting_reading"
    assert docs["policy_schedule.pdf"]["status"] == "processed"     # text layer needs no AI
    # automatic endpoints are disabled in this mode
    assert client.post(f"{API}/cases/{case['id']}/analyses", headers=h).status_code == 409

    tok = client.post(f"{API}/auth/agent-tokens", headers=h, json={"name": "test"}).json()["token"]
    assert client.post(f"{API}/auth/agent-tokens", headers={"Authorization": f"Bearer {tok}"},
                       json={}).status_code == 403
    assert cli(live_server, "bid_at_wrong", "find", "CC")[0] == 1

    code, out = cli(live_server, tok, "find", "CLM/CC/1")
    assert code == 0 and case["id"] in out
    work = tmp_path / "work"
    code, out = cli(live_server, tok, "package", case["id"], "--out", str(work))
    assert code == 0, out
    pkg = json.loads((work / "case.json").read_text())
    assert "GLOBAL RULES" in (work / "1_analysis_instructions.md").read_text()
    assert "Motor Own Damage" in (work / "1_analysis_instructions.md").read_text()
    pending = pkg["pending_pages"]
    assert {p["filename"] for p in pending} >= {"DL_scan.pdf", "FIR_telugu.png"}

    # analysis is refused while pages are unread
    (work / "analysis.json").write_text("{}")
    assert cli(live_server, tok, "submit-analysis", case["id"], str(work / "analysis.json"))[0] == 2

    for p in pending:
        img = work / f"{p['ref']}_{p['page_no']}.jpg"
        assert cli(live_server, tok, "page-image", p["document_id"], str(p["page_no"]), str(img))[0] == 0
        assert img.read_bytes()[:3] == b"\xff\xd8\xff"
        photo = p["filename"].endswith(".jpg")
        reading = {"languages": [] if photo else ["te"],
                   "text_original": "" if photo else "ప్రథమ సమాచార నివేదిక 45/2026",
                   "text_english": "" if photo else "First Information Report No. 45/2026, Gannavaram PS",
                   "is_photograph": photo, "visual_description": "Front bumper damaged" if photo else "",
                   "legible": True, "legibility_notes": ""}
        rf = work / f"{p['ref']}_{p['page_no']}.json"
        rf.write_text(json.dumps(reading, ensure_ascii=False))
        assert cli(live_server, tok, "read-page", p["document_id"], str(p["page_no"]), str(rf))[0] == 0
    docs = {d["original_filename"]: d for d in client.get(f"{API}/cases/{case['id']}/documents", headers=h).json()}
    assert docs["FIR_telugu.png"]["status"] == "processed" and docs["FIR_telugu.png"]["doc_type"] == "fir"
    assert docs["damage_front.jpg"]["doc_type"] == "photograph"

    cli(live_server, tok, "package", case["id"], "--out", str(work))
    pkg = json.loads((work / "case.json").read_text())
    assert pkg["pending_pages"] == []
    inv = {d["filename"]: d["ref"] for d in pkg["inventory"]}
    pol, claim, stmt = inv["policy_schedule.pdf"], inv["claim_form.docx"], inv["driver_statement.docx"]

    analysis = {
        "case_summary": "OD claim", "detected_aspects": [],
        "findings": [{"id": "F1", "category": "documentary_evidence", "statement": "Policy period 02.03.2026 onwards",
                      "sources": [{"ref": pol, "page": 1}], "significance": "material"},
                     {"id": "F2", "category": "verified_fact", "statement": "Hospital confirmed",
                      "sources": [{"ref": "D999", "page": 1}], "significance": "material"}],
        "chronology": [{"date": "14.03.2026", "time": "22:30", "event": "Accident (claim form)",
                        "sources": [{"ref": claim, "page": 1}], "certainty": "stated"}],
        "discrepancies": [{"id": "X1", "point": "Time", "version_a": "22:30 hrs", "sources_a": [{"ref": claim, "page": 1}],
                           "version_b": "23:15 hrs", "sources_b": [{"ref": stmt, "page": 1}],
                           "significance": "material", "resolution": ""}],
        "checklist": [], "question_answers": [], "photo_observations": [],
        "external_checks": [{"source": "fastag", "status": "pending", "basis_refs": [], "remarks": ""}],
        "pending_verifications": [{"item": "FASTag statement", "reason": "Not supplied", "impact": "could_change_opinion"}],
        "policy_analysis": {"wording_available": False, "clauses": [], "coverage_position": "Provisional"},
        "anomalies": [],
        "opinion": {"verdict": "insufficient_evidence", "summary": "Time discrepancy unresolved.",
                    "decisive_evidence": [{"point": "Time discrepancy", "sources": [{"ref": claim, "page": 1}]}],
                    "limitations": ["Bank statement password protected"]}}
    af = work / "analysis.json"
    af.write_text(json.dumps({**analysis, "extra": 1}))
    code, out = cli(live_server, tok, "submit-analysis", case["id"], str(af))
    assert code == 2 and "unexpected field 'extra'" in out
    af.write_text(json.dumps(analysis))
    code, out = cli(live_server, tok, "submit-analysis", case["id"], str(af))
    assert code == 2 and "D999" in out                                    # invented reference rejected
    analysis["findings"].pop()
    af.write_text(json.dumps(analysis))
    code, out = cli(live_server, tok, "submit-analysis", case["id"], str(af))
    assert code == 0, out
    run_id = json.loads(out)["run_id"]
    runs = client.get(f"{API}/cases/{case['id']}/analyses", headers=h).json()
    assert runs[0]["model"] == "Claude Code (Claude subscription)"

    cli(live_server, tok, "package", case["id"], "--out", str(work))
    budget = json.loads((work / "case.json").read_text())["report_word_budget"]
    sections = [s for s in json.loads(json.dumps(__import__("yaml").safe_load(
        (Path(__file__).resolve().parents[1] / "app/reports/templates/own_damage.yaml").read_text())["sections"]))
        if s.get("drafted", True)]
    para = "The investigation examined the claim documents and photographs in detail. "

    def draft(words_each, extra=""):
        return {"sections": [{"key": s["key"], "heading": s["heading"],
                              "paragraphs": [(para * (words_each // 10 + 1))[: words_each * 7] + extra]}
                             for s in sections]}
    rf = work / "report.json"
    rf.write_text(json.dumps(draft(40, " FASTag records were verified with the toll operator.")))
    code, out = cli(live_server, tok, "submit-report", case["id"], str(rf), "--run", run_id)
    assert code == 2 and "fastag" in out.lower()
    rf.write_text(json.dumps(draft(1200)))
    code, out = cli(live_server, tok, "submit-report", case["id"], str(rf), "--run", run_id)
    assert code == 2 and "target_words" in out                            # over page limit
    rf.write_text(json.dumps(draft(budget // len(sections))))
    code, out = cli(live_server, tok, "submit-report", case["id"], str(rf), "--run", run_id)
    assert code == 0, out
    res = json.loads(out)
    assert res["accepted"] and res["pages"] <= 7
    out_docx = work / "r.docx"
    assert cli(live_server, tok, "download-report", res["report_id"], str(out_docx))[0] == 0
    d = docx.Document(io.BytesIO(out_docx.read_bytes()))
    assert "insufficient to reach a reliable conclusion" in "\n".join(p.text for p in d.paragraphs)
    actions = {a["action"] for a in client.get(f"{API}/cases/{case['id']}/audit", headers=h).json()}
    assert {"agent.package_downloaded", "agent.page_read", "analysis.completed", "report.generated"} <= actions
