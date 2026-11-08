"""Run the complete Phase-1 workflow against a synthetic OD folder and write the report files.

  python scripts/demo_vertical_slice.py OUT_DIR            # deterministic fake AI (no API cost)
  python scripts/demo_vertical_slice.py OUT_DIR --real     # real Claude API (needs ANTHROPIC_API_KEY)
"""
import os
import sys
import tempfile
from pathlib import Path

out = Path(sys.argv[1]).resolve()
real = "--real" in sys.argv
tmp = Path(tempfile.mkdtemp(prefix="bid-demo-"))
os.environ.update({"BID_ENVIRONMENT": "test", "BID_DATABASE_URL": f"sqlite:///{tmp}/demo.db",
                   "BID_STORAGE_DIR": str(tmp / "storage"), "BID_ALLOW_LOCAL_CONNECTOR": "true",
                   "BID_LOCAL_CONNECTOR_ROOT": str(tmp / "folders"), "BID_RUN_WORKER_IN_PROCESS": "false"})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.jobs.queue import drain  # noqa: E402
from app.llm.client import set_llm  # noqa: E402
from app.main import app  # noqa: E402
from tests.synthetic_case import build  # noqa: E402

if not real:
    from tests.fake_llm import FakeLLM
    set_llm(FakeLLM())

build(tmp / "folders" / "OD_demo")
API = "/api/v1"
with TestClient(app) as c:
    t = c.post(f"{API}/auth/register", json={"email": "demo@example.com", "password": "demo-password-1",
                                             "full_name": "Demo Investigator"}).json()
    h = {"Authorization": f"Bearer {t['access_token']}"}
    c.put(f"{API}/auth/me", headers=h, json={"investigator_profile": {
        "name": "Demo Investigator", "firm": "Bharati Investigations (DEMO)", "licence_number": "DEMO-0001"}})
    case = c.post(f"{API}/cases", headers=h, json={
        "insured_name": "R. Venkata Rao", "claim_number": "CLM/OD/2026/7788", "policy_number": "3001/OD/2026/000123",
        "vehicle_registration": "AP 39 AB 1234", "insurer_name": "Demo General Insurance",
        "investigation_reference": "BID/2026/001", "investigation_date": "2026-03-20", "category": "own_damage",
        "source_link": "local://OD_demo", "include_invoice": True,
        "invoice": {"invoice_number": "BI/26/014", "invoice_date": "2026-03-25", "bill_to": "Demo General Insurance",
                    "items": [{"description": "Investigation fee - OD claim", "amount": 6000}], "gst_percent": 18}}).json()
    for step, url, body in [("scan", f"/cases/{case['id']}/scan", None),
                            ("analysis", f"/cases/{case['id']}/analyses", None),
                            ("report", f"/cases/{case['id']}/reports", {})]:
        job = c.post(API + url, headers=h, json=body).json()
        drain()
        job = c.get(f"{API}/jobs/{job['id']}", headers=h).json()
        print(f"{step:9s} -> {job['status']} {job['error'] or job['result']}")
    docs = c.get(f"{API}/cases/{case['id']}/documents", headers=h).json()
    print("\nDocument inventory:")
    for d in docs:
        print(f"  {d['ref']} {d['status']:18s} {d['doc_type']:22s} {(d['source_path'] + '/' if d['source_path'] else '')}{d['original_filename']}")
    rep = c.get(f"{API}/cases/{case['id']}/reports", headers=h).json()[0]
    out.mkdir(parents=True, exist_ok=True)
    for fmt in ("docx", "pdf"):
        r = c.get(f"{API}/reports/{rep['id']}/download?format={fmt}", headers=h)
        if r.status_code == 200:
            (out / f"{rep['filename']}.{fmt}").write_bytes(r.content)
    print(f"\nReport v{rep['version']}: {rep['page_count']} page(s), warnings={rep['warnings']}\nWritten to {out}")
