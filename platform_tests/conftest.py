import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_api.api import create_app
from platform_api.config import Settings


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(environment="test", data_dir=tmp_path))


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/demo-session", json={"profile": "operator"})
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        yield client


@pytest.fixture
def input_files():
    root = Path(__file__).resolve().parents[1] / "data/input"
    return [("files", (p.name, p.read_bytes(), "text/csv")) for p in sorted(root.glob("*.csv"))]


def completed(client, run_id):
    for _ in range(200):
        response = client.get(f"/api/v1/reconciliations/{run_id}")
        assert response.status_code == 200
        row = response.json()
        if row["state"] in {"COMPLETED", "FAILED"}:
            assert row["state"] == "COMPLETED", row
            return row
        time.sleep(0.01)
    raise AssertionError("Worker não concluiu no prazo do teste")
