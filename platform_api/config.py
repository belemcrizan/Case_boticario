"""Configuração explícita: demo local e GCP têm contratos distintos."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    environment: str = "demo"
    data_dir: Path = ROOT / ".runtime"
    database_url: str = ""
    frontend_dir: Path = ROOT / "frontend/dist"
    public_origin: str = "http://localhost:8000"
    max_upload_bytes: int = 64 * 1024 * 1024
    max_request_bytes: int = 128 * 1024 * 1024
    max_active_jobs: int = 4
    workers: int = 2
    lease_seconds: int = 1800
    session_seconds: int = 8 * 3600
    iap_audience: str = ""
    identities: dict = field(default_factory=dict)
    bucket: str = ""
    project: str = ""
    region: str = "southamerica-east1"
    job_name: str = ""
    sql_instance: str = ""
    sql_user: str = ""
    sql_database: str = "otm_guard"
    initialize_schema: bool = True
    seed_demo: bool = True

    def __post_init__(self):
        if self.environment not in {"demo", "gcp", "test"}:
            raise ValueError("OTM_ENV deve ser demo, test ou gcp")
        if self.environment == "gcp":
            if not all(
                (
                    self.iap_audience,
                    self.identities,
                    self.bucket,
                    self.project,
                    self.job_name,
                    self.sql_instance,
                    self.sql_user,
                )
            ):
                raise ValueError("GCP exige IAP, identidades autorizadas, bucket, job e Cloud SQL")
            if not self.public_origin.startswith("https://"):
                raise ValueError("GCP exige origem HTTPS explícita")
            if self.initialize_schema or self.seed_demo:
                raise ValueError("GCP não cria schema nem semeia dados de demonstração automaticamente")

    @classmethod
    def from_env(cls):
        cloud = os.getenv("OTM_ENV", "demo") == "gcp"
        return cls(
            environment=os.getenv("OTM_ENV", "demo"),
            data_dir=Path(os.getenv("OTM_DATA_DIR", str(ROOT / ".runtime"))),
            database_url=os.getenv("OTM_DATABASE_URL", ""),
            frontend_dir=Path(os.getenv("OTM_FRONTEND_DIR", str(ROOT / "frontend/dist"))),
            public_origin=os.getenv("OTM_PUBLIC_ORIGIN", "http://localhost:8000"),
            iap_audience=os.getenv("OTM_IAP_AUDIENCE", ""),
            identities=json.loads(os.getenv("OTM_IDENTITIES_JSON", "{}")),
            bucket=os.getenv("OTM_BUCKET", ""),
            project=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            region=os.getenv("OTM_REGION", "southamerica-east1"),
            job_name=os.getenv("OTM_JOB_NAME", ""),
            sql_instance=os.getenv("OTM_SQL_INSTANCE", ""),
            sql_user=os.getenv("OTM_SQL_USER", ""),
            sql_database=os.getenv("OTM_SQL_DATABASE", "otm_guard"),
            initialize_schema=not cloud,
            seed_demo=not cloud,
        )
