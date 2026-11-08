from app.connectors.base import ConnectorError
from app.connectors.local import LocalFolderConnector
from app.db import SessionLocal
from app.ingestion.scanner import scan_case
from app.jobs.queue import drain, recover_stale
from app.models import Case, Document, Job
from tests.synthetic_case import build

API = "/api/v1"


def _second_user(client):
    r = client.post(f"{API}/auth/register", json={"email": "other@example.com", "password": "another-pass-9"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["refresh_token"]


def test_auth_required_and_case_isolation(client, auth_headers, tmp_root):
    assert client.get(f"{API}/cases").status_code == 401
    assert client.get(f"{API}/cases", headers={"Authorization": "Bearer garbage"}).status_code == 401
    case = client.post(f"{API}/cases", headers=auth_headers, json={"category": "theft", "claim_number": "T1"}).json()
    other, _ = _second_user(client)
    assert client.get(f"{API}/cases/{case['id']}", headers=other).status_code == 404
    assert client.get(f"{API}/cases", headers=other).json() == []
    # second user is not admin -> cannot edit playbooks
    r = client.post(f"{API}/playbooks/theft/versions", headers=other, json={"content_yaml": "x"})
    assert r.status_code == 403


def test_refresh_token_rotation(client):
    r = client.post(f"{API}/auth/login", json={"email": "investigator@example.com", "password": "correct-horse-1"})
    rt = r.json()["refresh_token"]
    r2 = client.post(f"{API}/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 200
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": rt}).status_code == 401  # single use
    assert client.post(f"{API}/auth/login", json={"email": "investigator@example.com",
                                                  "password": "wrong-password"}).status_code == 401


def test_stored_files_are_encrypted(client, auth_headers, fake_llm, tmp_root):
    build(tmp_root / "folders" / "enc_case")
    case = client.post(f"{API}/cases", headers=auth_headers,
                       json={"category": "own_damage", "source_link": "local://enc_case"}).json()
    client.post(f"{API}/cases/{case['id']}/scan", headers=auth_headers)
    drain()
    blobs = list((tmp_root / "storage" / "cases" / case["id"]).rglob("*.bin"))
    assert blobs
    for b in blobs:
        raw = b.read_bytes()
        assert not raw.startswith(b"%PDF") and b"Venkata" not in raw
    # purge copies keeps metadata but removes files
    client.post(f"{API}/cases/{case['id']}/purge-copies", headers=auth_headers)
    assert not list((tmp_root / "storage" / "cases" / case["id"] / "docs").rglob("*.bin"))
    # controlled deletion requires confirmation
    assert client.delete(f"{API}/cases/{case['id']}?confirm=nope", headers=auth_headers).status_code == 400
    assert client.delete(f"{API}/cases/{case['id']}?confirm=DELETE", headers=auth_headers).status_code == 200


class FlakyConnector(LocalFolderConnector):
    """Simulates a network drop after N downloads."""
    def __init__(self, root, fail_after):
        super().__init__(root)
        self.left = fail_after

    def download(self, f):
        if self.left == 0:
            raise RuntimeError("connection reset")
        self.left -= 1
        return super().download(f)


def test_interrupted_scan_resumes(client, auth_headers, fake_llm, tmp_root):
    build(tmp_root / "folders" / "resume_case")
    case_json = client.post(f"{API}/cases", headers=auth_headers,
                            json={"category": "own_damage", "source_link": "local://resume_case"}).json()
    db = SessionLocal()
    case = db.get(Case, case_json["id"])
    try:
        scan_case(db, case, FlakyConnector(str(tmp_root / "folders"), 4), lambda *_: None)
    except RuntimeError:
        pass
    done_before = db.query(Document).filter(Document.case_id == case.id, Document.status != "pending").count()
    assert 0 < done_before
    stats = scan_case(db, case, LocalFolderConnector(str(tmp_root / "folders")), lambda *_: None)
    assert stats["skipped"] >= 4  # already-processed files were not downloaded again
    assert db.query(Document).filter(Document.case_id == case.id, Document.status.in_(["pending", "processing"])).count() == 0
    db.close()


def test_stale_running_job_is_requeued(client):
    db = SessionLocal()
    job = Job(kind="scan", user_id="u", status="running", attempts=1, heartbeat_at=None)
    db.add(job)
    db.commit()
    assert recover_stale(db) >= 1
    db.refresh(job)
    assert job.status == "queued"
    db.delete(job)
    db.commit()
    db.close()


def test_playbook_admin_versioning(client, auth_headers):
    h = auth_headers
    vers = client.get(f"{API}/playbooks/theft/versions", headers=h).json()
    text = vers[0]["content_yaml"] + "\n# added check\n"
    text = text.replace("investigation_questions:", "investigation_questions:\n  - Were all original keys produced?")
    r = client.post(f"{API}/playbooks/theft/versions", headers=h, json={"content_yaml": text, "change_note": "keys"})
    assert r.status_code == 201 and r.json()["version"] == 2
    bad = client.post(f"{API}/playbooks/theft/versions", headers=h, json={"content_yaml": "key: theft\nname: x\nkind: category"})
    assert bad.status_code == 422
    assert client.post(f"{API}/playbooks/theft/activate/1", headers=h).json()["active_version"] == 1
