import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="bid-tests-"))
os.environ.update({
    "BID_ENVIRONMENT": "test",
    "BID_DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "BID_STORAGE_DIR": str(_TMP / "storage"),
    "BID_ALLOW_LOCAL_CONNECTOR": "true",
    "BID_LOCAL_CONNECTOR_ROOT": str(_TMP / "folders"),
    "BID_RUN_WORKER_IN_PROCESS": "false",
    "BID_JWT_SECRET": "test-secret-0123456789-abcdefghijklmnop",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.llm.client import set_llm  # noqa: E402
from tests.fake_llm import FakeLLM  # noqa: E402


@pytest.fixture
def tmp_root() -> Path:
    return _TMP


@pytest.fixture
def fake_llm():
    llm = FakeLLM()
    set_llm(llm)
    yield llm
    set_llm(None)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    r = client.post("/api/v1/auth/register", json={"email": "investigator@example.com",
                                                    "password": "correct-horse-1", "full_name": "Test Investigator"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    client.put("/api/v1/auth/me", headers=h, json={"investigator_profile": {
        "name": "Test Investigator", "firm": "Bharati Investigations", "licence_number": "TEST-LIC-1",
        "bank_details": "Test Bank A/c 000"}})
    return h
