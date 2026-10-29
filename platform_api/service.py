"""Casos de uso: validar, executar, simular e recuperar com efeitos limitados."""

import hashlib
import tempfile
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

from otm_guard import __version__
from otm_guard.engine import reconcile
from otm_guard.ingest import SCHEMAS, load_dataset
from otm_guard.models import ContractError, InvariantError, Policy
from otm_guard.report import canonical_json

from . import VERSION
from .config import ROOT, Settings
from .domain import AppError, Principal
from .observability import event, jobs_total, stage
from .publish import enriched_rows, publish, stock_rows
from .repository import Repository
from .storage import Storage, digest


class Service:
    def __init__(self, settings: Settings, repo: Repository, storage: Storage):
        self.settings, self.repo, self.storage = settings, repo, storage
        self.pool = (
            ThreadPoolExecutor(max_workers=settings.workers) if settings.environment != "gcp" else None
        )

    def close(self):
        if self.pool:
            self.pool.shutdown(wait=True)

    def validate(self, directory: Path) -> dict:
        try:
            data = load_dataset(directory)
        except ContractError as exc:
            raise AppError(422, "INPUT_CONTRACT_REJECTED", str(exc)) from exc
        return {
            "valid": True,
            "orders": len(data.orders),
            "files": data.input_hashes,
            "issues": [asdict(i) for i in data.issues],
            "preview": [asdict(o) for o in list(data.orders.values())[:5]],
            "snapshot_timestamp": None,
            "notice": "Validação estrutural aprovada. Data da foto e política comercial ainda exigem conferência.",
        }

    def create(
        self,
        directory: Path,
        policy: str,
        principal: Principal,
        key: str,
        label: str = "Lote importado",
        parent_id: str | None = None,
        run_id: str | None = None,
        visibility: str = "private",
        dispatch: bool = True,
    ) -> tuple[dict, bool]:
        validation = self.validate(directory)
        fingerprint = hashlib.sha256(
            canonical_json({"inputs": validation["files"], "policy": policy}).encode()
        ).hexdigest()
        previous = self.repo.by_key(principal.subject, key)
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise AppError(
                    409, "IDEMPOTENCY_CONFLICT", "A chave já identifica outras entradas ou política."
                )
            return self.repo.public(previous), False
        if self.repo.active_count(principal.subject) >= self.settings.max_active_jobs:
            raise AppError(
                429, "QUEUE_CAPACITY", "Há execuções em andamento. Aguarde antes de enviar outro lote."
            )
        now = time.time()
        record: dict[str, Any] = {
            "id": run_id or uuid.uuid4().hex,
            "owner": principal.subject,
            "label": label,
            "policy": policy,
            "state": "UPLOADING",
            "kind": "SIMULATION" if parent_id else "PROPOSAL",
            "visibility": visibility,
            "fingerprint": fingerprint,
            "idempotency_key": key,
            "parent_id": parent_id,
            "created_at": now,
            "updated_at": now,
            "attempt": 0,
            "summary": None,
            "failure": None,
            "timings": None,
            "snapshot": None,
        }
        existing, created = self.repo.create(record, self.settings.max_active_jobs)
        if not created:
            return self.repo.public(existing), False
        try:
            for name in SCHEMAS:
                self.storage.put(f"runs/{record['id']}/inputs/{name}", directory / name)
            self.repo.queued(record["id"])
            self.repo.event(
                record["id"], principal.subject, "CREATED", {"policy": policy, "kind": record["kind"]}
            )
            if dispatch:
                self.dispatch(record["id"])
        except Exception:
            self.repo.fail(
                record["id"],
                "DISPATCH_OR_STORAGE_FAILED",
                "Falha ao armazenar ou agendar. É seguro consultar o lote e tentar novamente.",
            )
            raise
        return self.repo.public(self.repo.get(record["id"])), True

    def dispatch(self, run_id: str):
        if self.settings.environment == "gcp":
            from .cloud import dispatch_job

            dispatch_job(self.settings, run_id)
        elif self.pool:
            self.pool.submit(self.execute, run_id)

    def execute(self, run_id: str):
        if not self.repo.claim(run_id, self.settings.lease_seconds):
            return
        record = self.repo.get(run_id)
        attempt = record["attempt"]
        timings: dict[str, float] = {}
        started = time.perf_counter()
        self.repo.event(run_id, "worker", "STARTED", {"attempt": attempt})
        jobs_total.labels("started").inc()
        try:
            with tempfile.TemporaryDirectory(prefix="otm-job-") as folder:
                root = Path(folder)
                inputs = root / "inputs"
                inputs.mkdir()
                with stage(timings, "ingestion"):
                    for name in SCHEMAS:
                        self.storage.get(f"runs/{run_id}/inputs/{name}", inputs / name)
                    data = load_dataset(inputs)
                    observed = hashlib.sha256(
                        canonical_json({"inputs": data.input_hashes, "policy": record["policy"]}).encode()
                    ).hexdigest()
                    if observed != record["fingerprint"]:
                        raise AppError(
                            409,
                            "INPUT_INTEGRITY_FAILURE",
                            "Entradas divergem do lote validado. Não processar.",
                        )
                with stage(timings, "reconcile_and_verify"):
                    result = reconcile(data, Policy(record["policy"]))
                with stage(timings, "publication"):
                    output = root / "output"
                    engine_id = publish(data, result, output)
                    files = []
                    for path in sorted(output.iterdir()):
                        key = f"runs/{run_id}/attempt-{attempt}/{path.name}"
                        self.storage.put(key, path)
                        files.append(
                            {
                                "name": path.name,
                                "key": key,
                                "sha256": digest(path),
                                "size": path.stat().st_size,
                            }
                        )
                reasons = Counter(
                    code for row in result.decisions for code in row.reasons if code != "SEM_AJUSTE"
                )
                summary = {
                    "engine_run_id": engine_id,
                    "engine_version": __version__,
                    "platform_version": VERSION,
                    "metrics": result.metrics,
                    "checks": result.checks,
                    "policy": asdict(result.policy),
                    "requires_review": bool(result.metrics["linhas_revisao"]),
                    "review_state": "PENDING_HUMAN_REVIEW",
                    "snapshot_timestamp": None,
                    "reasons": [{"code": code, "count": count} for code, count in reasons.most_common()],
                    "quality_issues": [asdict(i) for i in data.issues],
                    "inputs_sha256": data.input_hashes,
                    "cds": sorted({o.cd_origem for o in data.orders.values()}),
                    "report_scope": {
                        "displayed_rows": min(len(result.decisions), 200)
                        if len(result.decisions) > 500
                        else len(result.decisions),
                        "total_rows": len(result.decisions),
                    },
                    "notice": "Proposta para conferência. Não há reserva ou envio ao OMS.",
                }
                with stage(timings, "persistence"):
                    timings["total_before_persistence"] = round(time.perf_counter() - started, 6)
                    self.repo.complete(
                        run_id,
                        enriched_rows(data, result, include_references=False),
                        stock_rows(data, result),
                        summary,
                        timings,
                        files,
                        attempt,
                    )
                timings["total"] = round(time.perf_counter() - started, 6)
                self.repo.save_timings(run_id, attempt, timings)
                self.repo.event(
                    run_id, "worker", "COMPLETED", {"all_invariants_passed": True, "attempt": attempt}
                )
                jobs_total.labels("completed").inc()
                event("run_completed", run_id=run_id, attempt=attempt, timings=timings)
        except (ContractError, InvariantError, AppError) as exc:
            code = exc.code if isinstance(exc, AppError) else type(exc).__name__
            self.repo.fail(run_id, code, str(exc), attempt)
            self.repo.event(run_id, "worker", "FAILED", {"code": code, "attempt": attempt})
            jobs_total.labels("failed").inc()
        except Exception as exc:
            # Não registrar texto de exceção de infraestrutura: pode conter DSN ou dados.
            self.repo.fail(
                run_id,
                "PROCESSING_FAILED",
                "Falha de processamento. Consulte a correlação e a trilha de auditoria.",
                attempt,
            )
            self.repo.event(run_id, "worker", "FAILED", {"code": type(exc).__name__, "attempt": attempt})
            jobs_total.labels("failed").inc()
            event("run_failed", run_id=run_id, error_type=type(exc).__name__)

    def simulation(self, parent_id: str, policy: str, principal: Principal, key: str) -> tuple[dict, bool]:
        parent = self.require_completed(parent_id, principal)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in SCHEMAS:
                self.storage.get(f"runs/{parent_id}/inputs/{name}", root / name)
            return self.create(root, policy, principal, key, f"Simulação de {parent['label']}", parent_id)

    def require_completed(self, run_id: str, principal: Principal) -> dict:
        record = self.repo.get(run_id, principal)
        if record["state"] != "COMPLETED":
            raise AppError(409, "RESULTS_NOT_READY", "O lote ainda não possui resultados publicados.")
        return record

    def seed(self):
        if not self.settings.seed_demo:
            return
        principal = Principal("system:demo", "Dados do case", "admin")
        for mode in ("strict", "complete-kits"):
            run_id = f"demo-{mode}"
            try:
                existing = self.repo.get(run_id)
                if existing["state"] == "COMPLETED":
                    continue
            except AppError:
                existing = None
            if existing is None:
                self.create(
                    ROOT / "data/input",
                    mode,
                    principal,
                    f"seed-{mode}",
                    f"Case original · {'Conservadora' if mode == 'strict' else 'Kits completos'}",
                    run_id=run_id,
                    visibility="demo",
                    dispatch=False,
                )
            self.execute(run_id)

    def integrity(self, run_id: str, principal: Principal) -> dict:
        self.require_completed(run_id, principal)
        checks = []
        for artifact in self.repo.files(run_id):
            checksum = hashlib.sha256()
            with self.storage.open(artifact["key"]) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    checksum.update(chunk)
            checks.append({"name": artifact["name"], "valid": checksum.hexdigest() == artifact["sha256"]})
        self.repo.event(
            run_id, principal.subject, "INTEGRITY_CHECKED", {"valid": all(c["valid"] for c in checks)}
        )
        return {"valid": all(c["valid"] for c in checks), "artifacts": checks}
