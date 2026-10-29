import hashlib
import secrets
import time

import pytest
from fastapi.testclient import TestClient

from platform_api.auth import COOKIE, token_hash
from platform_api.domain import Principal
from platform_api.storage import LocalStorage

from .conftest import completed


def test_health_readiness_and_openapi(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["status"] == "ready"
    schema = client.get("/openapi.json").json()
    assert "DecisionView" in schema["components"]["schemas"]
    assert schema["paths"]["/api/v1/reconciliations"]["post"]["security"]
    assert (
        "multipart/form-data" in schema["paths"]["/api/v1/reconciliations"]["post"]["requestBody"]["content"]
    )


def test_baseline_and_summary_exact(client):
    rows = client.get("/api/v1/reconciliations").json()
    assert rows["total"] == 2
    a = client.get("/api/v1/reconciliations/demo-strict/summary").json()
    b = client.get("/api/v1/reconciliations/demo-complete-kits/summary").json()
    assert a["metrics"]["unidades_finais"] == 199
    assert b["metrics"]["unidades_finais"] == 269
    assert len(a["checks"]) == 10 and all(a["checks"].values())
    assert a["snapshot_timestamp"] is None
    assert a["engine_run_id"] == "eaef0c553f967363efbab1577af379dbfa688b22a79931a66be4cdf884f6cf4e"


def test_requires_authentication_and_expired_session(app):
    with TestClient(app) as c:
        assert c.get("/api/v1/reconciliations").status_code == 401
        app.state.repository.save_session(
            token_hash("expired"), Principal("u", "U", "operator", "csrf"), time.time() - 1
        )
        c.cookies.set(COOKIE, "expired")
        assert c.get("/api/v1/me").status_code == 401


def test_session_cookie_and_logout(client):
    r = client.post("/api/v1/auth/demo-session", json={"profile": "viewer"})
    assert "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers["set-cookie"]
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert client.get("/api/v1/me").json()["role"] == "viewer"
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401


@pytest.mark.parametrize("profile", ["viewer", "auditor"])
def test_readonly_profiles_cannot_execute(client, profile):
    r = client.post("/api/v1/auth/demo-session", json={"profile": profile})
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert (
        client.post("/api/v1/examples", json={}, headers={"Idempotency-Key": "readonly-key"}).status_code
        == 403
    )
    assert client.get("/api/v1/reconciliations/demo-strict/decisions").status_code == 200


def test_csrf_and_origin(client):
    assert (
        client.post(
            "/api/v1/examples", json={}, headers={"Idempotency-Key": "csrf-test", "X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/demo-session", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/examples",
            json={},
            headers={"Idempotency-Key": "origin-test", "Sec-Fetch-Site": "cross-site"},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403


def test_create_idempotency_and_policy_conflict(client):
    headers = {"Idempotency-Key": "same-request-key"}
    a = client.post("/api/v1/examples", json={"policy": "strict"}, headers=headers)
    assert a.status_code == 202
    run = completed(client, a.json()["id"])
    assert run["summary"]["metrics"]["unidades_finais"] == 199
    b = client.post("/api/v1/examples", json={"policy": "strict"}, headers=headers)
    assert b.json()["id"] == run["id"]
    c = client.post("/api/v1/examples", json={"policy": "complete-kits"}, headers=headers)
    assert c.status_code == 409 and c.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert run["timings"]["total"] >= run["timings"]["ingestion"]


def test_idor_all_resource_routes(client, app):
    run = client.post("/api/v1/examples", json={}, headers={"Idempotency-Key": "private-resource"}).json()
    completed(client, run["id"])
    token = secrets.token_urlsafe(32)
    p = Principal("another-subject", "Outro usuário", "operator", "other-csrf")
    app.state.repository.save_session(token_hash(token), p, time.time() + 60)
    client.cookies.clear()
    client.cookies.set(COOKIE, token)
    client.headers["X-CSRF-Token"] = p.csrf
    for suffix in (
        "",
        "/summary",
        "/decisions",
        "/decisions/POI-1001",
        "/exceptions",
        "/inventory",
        "/artifacts",
        "/artifacts/manifest.json",
        "/audit",
        "/comparison/demo-strict",
    ):
        assert client.get(f"/api/v1/reconciliations/{run['id']}{suffix}").status_code == 404, suffix
    assert (
        client.post(
            f"/api/v1/reconciliations/{run['id']}/simulations",
            json={"policy": "complete-kits"},
            headers={"Idempotency-Key": "unauthorized-sim"},
        ).status_code
        == 404
    )
    assert client.post(f"/api/v1/reconciliations/{run['id']}/retry").status_code == 404
    assert client.post(f"/api/v1/reconciliations/{run['id']}/integrity").status_code == 404
    assert all(r["id"] != run["id"] for r in client.get("/api/v1/reconciliations").json()["items"])


def test_admin_authorization_is_server_side(client):
    login = client.post("/api/v1/auth/demo-session", json={"profile": "admin"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.get("/api/v1/metrics").status_code == 200
    assert client.get("/api/v1/me").json()["role"] == "admin"


def test_filters_sorting_pagination_and_literal_wildcards(client):
    url = "/api/v1/reconciliations/demo-strict/decisions"
    a = client.get(url + "?limit=2&sort=qtd_final&descending=true").json()
    assert a["total"] == 12 and len(a["items"]) == 2 and a["items"][0]["qtd_final"] == 108
    b = client.get(url + "?limit=2&offset=2&sort=qtd_final&descending=true").json()
    assert not {r["poi_id"] for r in a["items"]} & {r["poi_id"] for r in b["items"]}
    assert client.get(url + "?status=REVISAO").json()["total"] == 1
    assert client.get(url + "?cd=CD_PR").json()["total"] == 2
    assert client.get(url + "?search=SKU-X1").json()["items"][0]["qtd_final"] == 12
    assert client.get(url + "?search=%25").json()["total"] == 0
    assert client.get(url + "?search=' OR 1=1 --").json()["total"] == 0
    assert client.get(url + "?sort=DROP_TABLE").status_code == 422
    assert client.get(url + "?limit=101").status_code == 422
    assert client.get(url + "?offset=-1").status_code == 422


def test_detail_exceptions_inventory_and_policies(client):
    root = "/api/v1/reconciliations/demo-strict"
    d = client.get(root + "/decisions/POI-1007").json()
    assert "18 caixas" in d["explanation"] and len(d["input_references"]) == 5
    assert client.get(root + "/decisions/UNKNOWN").status_code == 404
    assert client.get(root + "/exceptions").json()["items"][0]["sku"] == "SKU-GHOST"
    assert client.get(root + "/inventory?search=SKU-A2&cd=CD_SP").json()["items"][0]["saldo_simulado"] == 35
    assert client.get("/api/v1/policies").json()["default"] == "strict"


def test_real_simulation_and_comparison(client):
    result = client.post(
        "/api/v1/reconciliations/demo-strict/simulations",
        json={"policy": "complete-kits"},
        headers={"Idempotency-Key": "simulation-key"},
    )
    assert result.status_code == 202
    alternative = completed(client, result.json()["id"])
    assert alternative["parent_id"] == "demo-strict" and alternative["kind"] == "SIMULATION"
    r = client.get(f"/api/v1/reconciliations/demo-strict/comparison/{alternative['id']}").json()
    assert r["delta_units"] == 70 and r["affected_count"] == 2
    assert (
        client.get("/api/v1/reconciliations/demo-strict/summary").json()["metrics"]["unidades_finais"] == 199
    )


def test_artifact_download_integrity_and_audit(client, app):
    root = "/api/v1/reconciliations/demo-strict"
    files = client.get(root + "/artifacts").json()["items"]
    assert len(files) == 7
    f = next(f for f in files if f["name"] == "manifest.json")
    response = client.get(root + "/artifacts/manifest.json")
    assert response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == f["sha256"]
    assert "attachment" in response.headers["content-disposition"]
    assert client.get(root + "/artifacts/missing.csv").status_code == 404
    assert client.post(root + "/integrity").json()["valid"] is True
    service = app.state.service
    artifact = next(f for f in service.repo.files("demo-strict") if f["name"] == "manifest.json")
    assert isinstance(service.storage, LocalStorage)
    service.storage.path(artifact["key"]).write_text("tampered")
    assert client.get(root + "/artifacts/manifest.json").status_code == 409
    assert client.post(root + "/integrity").json()["valid"] is False
    assert any(e["action"] == "ARTIFACT_DOWNLOADED" for e in client.get(root + "/audit").json()["items"])


def test_upload_validation_and_execution(client, input_files):
    response = client.post("/api/v1/validations", files=input_files)
    assert response.status_code == 200 and response.json()["orders"] == 12
    assert len(response.json()["preview"]) == 5
    r = client.post(
        "/api/v1/reconciliations?policy=complete-kits",
        files=input_files,
        headers={"Idempotency-Key": "upload-request"},
    )
    assert r.status_code == 202
    assert completed(client, r.json()["id"])["summary"]["metrics"]["unidades_finais"] == 269


def test_upload_bad_names_missing_files_malformed_and_sizes(client, input_files, app):
    assert client.post("/api/v1/validations", files=input_files[:4]).status_code == 422
    evil = input_files.copy()
    evil[0] = ("files", ("../pedidos_oms.csv", b"a,b", "text/csv"))
    assert client.post("/api/v1/validations", files=evil).status_code == 422
    assert client.post("/api/v1/validations", files=[input_files[0]] * 5).status_code == 422
    malformed = [(field, (name, b"wrong,header\n", typ)) for field, (name, _, typ) in input_files]
    assert client.post("/api/v1/validations", files=malformed).status_code == 422
    assert client.post("/api/v1/validations", data={"unexpected": "field"}).status_code == 422
    assert (
        client.post(
            "/api/v1/validations", content=b"", headers={"Content-Length": str(129 * 1024 * 1024)}
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/v1/examples", json={"policy": "invented"}, headers={"Idempotency-Key": "bad-policy"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/examples",
            json={"policy": "strict", "role": "admin"},
            headers={"Idempotency-Key": "extra-fields"},
        ).status_code
        == 422
    )


def test_error_correlation_security_headers_no_pii(client):
    r = client.get("/api/v1/reconciliations/unknown-run", headers={"X-Correlation-ID": "valid-correlation"})
    assert r.status_code == 404 and r.json()["correlation_id"] == "valid-correlation"
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert "owner" not in client.get("/api/v1/reconciliations/demo-strict").json()
    assert client.get("/api/v1/metrics").status_code == 403


def test_completed_cannot_retry(client):
    assert client.post("/api/v1/reconciliations/demo-strict/retry").status_code == 409


def test_frontend_static_path_fallback_and_missing_build(client, app, tmp_path):
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/api/nonexistent").status_code == 404
    assert client.get("/").status_code in {200, 404}
