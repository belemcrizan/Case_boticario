"""Adaptadores GCP. Carregados somente no ambiente gcp; nenhuma credencial estática."""

from pathlib import Path

from sqlalchemy import create_engine, event

from .config import Settings
from .domain import AppError
from .storage import digest


class GCSStorage:
    def __init__(self, bucket: str):
        from google.cloud.storage import Client

        self.bucket = Client().bucket(bucket)

    def put(self, key: str, path: Path) -> None:
        from google.api_core.exceptions import PreconditionFailed

        blob = self.bucket.blob(key)
        checksum = digest(path)
        blob.metadata = {"sha256": checksum}
        try:
            blob.upload_from_filename(str(path), if_generation_match=0, timeout=120, checksum="crc32c")
        except PreconditionFailed:
            current = self.bucket.get_blob(key)
            if current is None or (current.metadata or {}).get("sha256") != checksum:
                raise AppError(409, "IMMUTABLE_OBJECT", "Objeto GCS existente diverge do artefato.") from None

    def get(self, key: str, path: Path) -> None:
        blob = self.bucket.get_blob(key)
        if blob is None:
            raise FileNotFoundError("Objeto não disponível")
        blob.download_to_filename(
            str(path), if_generation_match=blob.generation, timeout=120, checksum="crc32c"
        )

    def open(self, key: str):
        blob = self.bucket.get_blob(key)
        if blob is None:
            raise FileNotFoundError("Objeto não disponível")
        return blob.open("rb", chunk_size=1024 * 1024, if_generation_match=blob.generation)


def cloud_sql_engine(settings: Settings):
    from google.cloud.sql.connector import Connector

    connector = Connector(refresh_strategy="LAZY")

    def creator():
        return connector.connect(
            settings.sql_instance,
            "pg8000",
            user=settings.sql_user,
            db=settings.sql_database,
            enable_iam_auth=True,
            ip_type="PUBLIC",
        )

    engine = create_engine(
        "postgresql+pg8000://",
        creator=creator,
        pool_size=2,
        max_overflow=1,
        pool_pre_ping=True,
        pool_recycle=1500,
    )
    # Mantém o conector vivo durante o pool. Encerrado junto ao processo Cloud Run.
    event.listen(engine, "engine_disposed", lambda unused: connector.close())
    return engine


def dispatch_job(settings: Settings, run_id: str):
    from google.cloud import run_v2

    client = run_v2.JobsClient()
    request = run_v2.RunJobRequest(
        name=f"projects/{settings.project}/locations/{settings.region}/jobs/{settings.job_name}",
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(args=["-m", "platform_api.worker", run_id])
            ]
        ),
    )
    client.run_job(request=request, timeout=30)
