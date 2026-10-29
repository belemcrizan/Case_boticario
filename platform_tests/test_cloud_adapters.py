"""Contratos dos SDKs com mocks: não equivalem a testes no GCP."""

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import PreconditionFailed

from platform_api.cloud import GCSStorage, cloud_sql_engine, dispatch_job
from platform_api.config import Settings
from platform_api.domain import AppError


@pytest.fixture
def storage():
    with patch("google.cloud.storage.Client") as client:
        store = GCSStorage("private-artifacts")
        yield store, client.return_value.bucket.return_value


def test_gcs_upload_conditional_immutable_with_checksum(storage, tmp_path):
    store, bucket = storage
    source = tmp_path / "input.csv"
    source.write_bytes(b"verified")
    store.put("runs/id/input.csv", source)
    blob = bucket.blob.return_value
    assert blob.metadata == {"sha256": hashlib.sha256(b"verified").hexdigest()}
    blob.upload_from_filename.assert_called_once_with(
        str(source), if_generation_match=0, timeout=120, checksum="crc32c"
    )


def test_gcs_replay_requires_same_digest(storage, tmp_path):
    store, bucket = storage
    source = tmp_path / "input.csv"
    source.write_bytes(b"verified")
    bucket.blob.return_value.upload_from_filename.side_effect = PreconditionFailed("exists")
    bucket.get_blob.return_value.metadata = {"sha256": hashlib.sha256(b"verified").hexdigest()}
    store.put("key", source)
    bucket.get_blob.return_value.metadata = {"sha256": "different"}
    with pytest.raises(AppError) as error:
        store.put("key", source)
    assert error.value.code == "IMMUTABLE_OBJECT"


def test_gcs_download_is_generation_bound(storage, tmp_path):
    store, bucket = storage
    bucket.get_blob.return_value.generation = 42
    target = tmp_path / "output.csv"
    store.get("key", target)
    bucket.get_blob.return_value.download_to_filename.assert_called_once_with(
        str(target), if_generation_match=42, timeout=120, checksum="crc32c"
    )
    store.open("key")
    bucket.get_blob.return_value.open.assert_called_once_with(
        "rb", chunk_size=1024 * 1024, if_generation_match=42
    )


@pytest.mark.parametrize("operation", ["get", "open"])
def test_gcs_missing_object_fails_closed(storage, tmp_path, operation):
    store, bucket = storage
    bucket.get_blob.return_value = None
    with pytest.raises(FileNotFoundError):
        if operation == "get":
            store.get("missing", tmp_path / "target")
        else:
            store.open("missing")


def test_cloud_sql_iam_and_connector_lifecycle():
    settings = Settings(sql_instance="project:region:instance", sql_user="service@project.iam")
    with (
        patch("google.cloud.sql.connector.Connector") as connector,
        patch("platform_api.cloud.create_engine", return_value=MagicMock()) as factory,
        patch("platform_api.cloud.event.listen") as listener,
    ):
        cloud_sql_engine(settings)
        creator = factory.call_args.kwargs["creator"]
        creator()
        connector.return_value.connect.assert_called_once_with(
            settings.sql_instance,
            "pg8000",
            user=settings.sql_user,
            db=settings.sql_database,
            enable_iam_auth=True,
            ip_type="PUBLIC",
        )
        listener.call_args.args[2](SimpleNamespace())
        connector.return_value.close.assert_called_once()


def test_job_dispatch_has_explicit_execution_override():
    with patch("google.cloud.run_v2.JobsClient") as client:
        dispatch_job(Settings(project="project", region="region", job_name="worker"), "run-123456")
        kwargs = client.return_value.run_job.call_args.kwargs
        assert kwargs["timeout"] == 30
        request = kwargs["request"]
        assert request.name == "projects/project/locations/region/jobs/worker"
        assert list(request.overrides.container_overrides[0].args) == [
            "-m",
            "platform_api.worker",
            "run-123456",
        ]
