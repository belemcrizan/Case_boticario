import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from sqlalchemy import update

from otm_guard.engine import reconcile
from otm_guard.ingest import load_dataset
from platform_api.config import ROOT, Settings
from platform_api.domain import AppError, Principal
from platform_api.publish import enriched_rows, publish
from platform_api.repository import Repository, make_engine, runs
from platform_api.service import Service
from platform_api.storage import LocalStorage, digest, verified_stream


@pytest.fixture
def service(tmp_path):
    settings = Settings(environment="test", data_dir=tmp_path, seed_demo=False)
    repo = Repository(make_engine(settings))
    service = Service(settings, repo, LocalStorage(tmp_path / "objects"))
    yield service
    service.close()
    repo.engine.dispose()


P = Principal("user-a", "Analista", "operator")


def create(service, key="request-1", **kwargs):
    return service.create(ROOT / "data/input", "strict", P, key, dispatch=False, **kwargs)[0]


def test_concurrent_idempotency_one_record_and_one_claim(service):
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: create(service), range(4)))
    assert len({r["id"] for r in records}) == 1
    rid = records[0]["id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: service.repo.claim(rid, 60), range(4)))
    assert sum(claims) == 1


def test_quota_does_not_break_idempotent_replay(service):
    first = create(service)
    for i in range(1, 4):
        create(service, f"request-{i + 1}")
    assert create(service)["id"] == first["id"]
    with pytest.raises(AppError) as exc:
        create(service, "request-five")
    assert exc.value.status == 429


def test_global_capacity_serializes_different_owners(service):
    def attempt(index):
        principal = Principal(f"independent-{index}", "Operador", "operator")
        try:
            service.create(ROOT / "data/input", "strict", principal, f"request-{index}", dispatch=False)
            return 202
        except AppError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(attempt, range(5)))
    assert statuses.count(202) == 4 and statuses.count(429) == 1


def test_missing_inputs_and_failed_dispatch_are_not_published(service):
    with patch.object(service.storage, "put", side_effect=OSError("secret-dsn")):
        with pytest.raises(OSError):
            create(service)
    record = service.repo.by_key(P.subject, "request-1")
    assert record["state"] == "FAILED" and "secret-dsn" not in record["failure"]["detail"]
    assert service.repo.files(record["id"]) == []


def test_changed_input_is_detected_before_engine(service):
    record = create(service)
    path = service.storage.path(f"runs/{record['id']}/inputs/pedidos_oms.csv")
    path.write_bytes(path.read_bytes().replace(b",50\n", b",49\n", 1))
    service.execute(record["id"])
    row = service.repo.get(record["id"])
    assert row["state"] == "FAILED" and row["failure"]["code"] == "INPUT_INTEGRITY_FAILURE"


def test_unexpected_failure_is_redacted_and_retry_recovers(service):
    record = create(service)
    with patch("platform_api.service.reconcile", side_effect=RuntimeError("password=secret")):
        service.execute(record["id"])
    assert service.repo.get(record["id"])["failure"]["code"] == "PROCESSING_FAILED"
    assert "secret" not in str(service.repo.get(record["id"])["failure"])
    service.repo.requeue(record["id"])
    service.execute(record["id"])
    row = service.repo.get(record["id"])
    assert row["state"] == "COMPLETED" and row["attempt"] == 2
    service.execute(record["id"])
    assert service.repo.get(record["id"])["attempt"] == 2


def test_stale_worker_fenced_from_new_attempt(service):
    record = create(service)
    rid = record["id"]
    assert service.repo.claim(rid, 30)
    with service.repo.engine.begin() as db:
        db.execute(update(runs).where(runs.c.id == rid).values(lease_until=time.time() - 1))
    service.repo.requeue(rid)
    assert service.repo.claim(rid, 60)
    with pytest.raises(AppError, match="Outra tentativa"):
        service.repo.complete(rid, [], [], {}, {}, [], attempt=1)
    service.repo.fail(rid, "STALE", "wrong", attempt=1)
    assert service.repo.get(rid)["state"] == "RUNNING" and service.repo.get(rid)["attempt"] == 2


def test_retry_limits_and_active_lease(service):
    record = create(service)
    rid = record["id"]
    assert service.repo.claim(rid, 60)
    with pytest.raises(AppError):
        service.repo.requeue(rid)
    for attempt in range(1, 4):
        service.repo.fail(rid, "ERROR", "test", attempt)
        if attempt < 3:
            service.repo.requeue(rid)
            assert service.repo.claim(rid, 60)
    with pytest.raises(AppError):
        service.repo.requeue(rid)


def test_not_ready_cannot_be_read_or_simulated(service):
    record = create(service)
    with pytest.raises(AppError) as exc:
        service.require_completed(record["id"], P)
    assert exc.value.status == 409
    with pytest.raises(AppError):
        service.simulation(record["id"], "complete-kits", P, "sim")


def test_local_storage_immutable_and_paths(service, tmp_path):
    source = tmp_path / "source"
    source.write_text("original")
    store = service.storage
    store.put("safe/file.csv", source)
    store.put("safe/file.csv", source)
    source.write_text("changed")
    with pytest.raises(AppError):
        store.put("safe/file.csv", source)
    for key in ("../escape", "/root/escape", "safe/../../escape"):
        with pytest.raises(AppError):
            store.path(key)
    with pytest.raises(AppError):
        with verified_stream(store, "safe/file.csv", "wrong"):
            pass
    with verified_stream(store, "safe/file.csv", hashlib.sha256(b"original").hexdigest()) as stream:
        assert stream.read() == b"original"


def test_large_report_is_bounded_and_csv_complete(tmp_path):
    from scripts.benchmark import generate

    data = generate(600, 42)
    result = reconcile(data)
    out = tmp_path / "large"
    publish(data, result, out)
    report = (out / "relatorio.html").read_text()
    assert report.count("<tr data-status=") == 200
    assert f"200 de {len(data.orders)} POIs" in report
    import csv
    import json

    with (out / "proposta_conciliada.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == len(data.orders)
    manifest = json.loads((out / "manifest.json").read_text())
    for name, checksum in manifest["artifacts_sha256"].items():
        assert digest(out / name) == checksum


def test_deterministic_explanation_fractionation_and_missing_data():
    data = load_dataset(ROOT / "data/input")
    rows = {r["poi_id"]: r for r in enriched_rows(data, reconcile(data))}
    assert "3 kits completos" in rows["POI-1004"]["explanation"]
    assert rows["POI-1011"]["constraints"]["initial_stock"] is None
    assert "origem" in rows["POI-1011"]["next_action"]


def test_comparison_requires_identical_inputs(client, input_files):
    from .conftest import completed

    changed = []
    for field, (name, raw, typ) in input_files:
        if name == "pedidos_oms.csv":
            raw = raw.replace(b",50\n", b",49\n", 1)
        changed.append((field, (name, raw, typ)))
    result = client.post(
        "/api/v1/reconciliations", files=changed, headers={"Idempotency-Key": "changed-dataset"}
    ).json()
    completed(client, result["id"])
    assert client.get(f"/api/v1/reconciliations/demo-strict/comparison/{result['id']}").status_code == 422
