"""API HTTP e entrega do frontend sob a mesma origem."""

import logging
import re
import tempfile
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException

from otm_guard.ingest import SCHEMAS

from . import VERSION
from .auth import COOKIE, authenticate, authorize_mutation, check_origin, demo_login, token_hash
from .config import ROOT, Settings
from .domain import POLICIES, AppError, Principal
from .observability import configure_tracing, event, latency, registry, requests_total
from .repository import Repository, make_engine
from .schemas import (
    ArtifactList,
    DecisionView,
    DemoSession,
    ErrorDetail,
    ExampleRequest,
    InventoryView,
    Page,
    RunView,
    SimulationRequest,
    SummaryView,
    UserView,
    ValidationView,
)
from .service import Service
from .storage import LocalStorage, Storage, verified_stream

ID = r"^[a-z0-9-]{8,64}$"
Key = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9:_-]+$")
]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=1_000_000)]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    repo = Repository(make_engine(settings))
    storage: Storage
    if settings.environment == "gcp":
        from .cloud import GCSStorage

        storage = GCSStorage(settings.bucket)
    else:
        storage = LocalStorage(settings.data_dir / "objects")
    service = Service(settings, repo, storage)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_tracing()
        service.seed()
        yield
        service.close()
        repo.engine.dispose()

    app = FastAPI(
        title="OTM Guard API",
        version=VERSION,
        lifespan=lifespan,
        description="Propostas auditáveis pós-OTM. Nenhuma rota reserva estoque ou autoriza faturamento.",
        responses={
            401: {"model": ErrorDetail},
            403: {"model": ErrorDetail},
            404: {"model": ErrorDetail},
            409: {"model": ErrorDetail},
            413: {"model": ErrorDetail},
            422: {"model": ErrorDetail},
        },
    )
    app.state.service, app.state.repository, app.state.settings = service, repo, settings

    def error_response(request: Request, status: int, code: str, detail: str):
        return JSONResponse(
            status_code=status,
            content={
                "code": code,
                "detail": detail,
                "correlation_id": getattr(request.state, "correlation_id", "unknown"),
            },
        )

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return error_response(request, exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = ", ".join(".".join(map(str, e["loc"])) for e in exc.errors()[:5])
        return error_response(
            request,
            422,
            "REQUEST_SCHEMA_REJECTED",
            f"Parâmetros inválidos: {fields}. Consulte o contrato OpenAPI.",
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.detail == "UPLOAD_TOTAL_TOO_LARGE":
            return error_response(request, 413, "UPLOAD_TOO_LARGE", "Envio excede 128 MiB.")
        return error_response(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.middleware("http")
    async def controls(request: Request, call_next):
        started = time.perf_counter()
        supplied = request.headers.get("x-correlation-id", "")
        correlation = supplied if re.fullmatch(r"[a-zA-Z0-9_-]{8,64}", supplied) else uuid.uuid4().hex
        request.state.correlation_id = correlation
        try:
            length = request.headers.get("content-length")
            if length and (not length.isdecimal() or int(length) > settings.max_request_bytes):
                raise AppError(413, "UPLOAD_TOO_LARGE", "Upload excede o limite total de 128 MiB.")
            if request.url.path.startswith("/api/") and request.url.path != "/api/v1/auth/demo-session":
                request.state.principal = authenticate(request, repo, settings)
            response = await call_next(request)
        except AppError as exc:
            response = error_response(request, exc.status, exc.code, exc.detail)
        except Exception as exc:
            event("http_failure", correlation_id=correlation, error_type=type(exc).__name__)
            response = error_response(
                request, 500, "INTERNAL_ERROR", "Falha interna. Informe o identificador de correlação."
            )
        response.headers.update(
            {
                "X-Correlation-ID": correlation,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Cache-Control": "no-store",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            }
        )
        if request.url.path in {"/docs", "/redoc"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com"
            )
        if settings.environment == "gcp":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        duration = time.perf_counter() - started
        requests_total.labels(request.method, str(response.status_code)).inc()
        latency.labels(request.method).observe(duration)
        event(
            "http_request",
            correlation_id=correlation,
            method=request.method,
            status=response.status_code,
            duration_seconds=round(duration, 6),
        )
        return response

    def principal(request: Request) -> Principal:
        return request.state.principal

    def mutation(request: Request) -> Principal:
        p = principal(request)
        authorize_mutation(request, p, settings)
        return p

    User = Annotated[Principal, Depends(principal)]
    Operator = Annotated[Principal, Depends(mutation)]

    def ready_run(run_id: str, p: Principal):
        if not re.fullmatch(ID, run_id):
            raise AppError(404, "RUN_NOT_FOUND", "Lote não encontrado.")
        return service.require_completed(run_id, p)

    @asynccontextmanager
    async def upload_directory(request: Request):
        seen = set()
        total = 0
        received = 0
        original_receive = request._receive

        async def limited_receive():
            nonlocal received
            message = await original_receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > settings.max_request_bytes:
                    # MultipartException também fecha temporários abertos pelo parser.
                    raise MultiPartException("UPLOAD_TOTAL_TOO_LARGE")
            return message

        # Conta bytes reais, inclusive quando Content-Length não existe ou diverge.
        request._receive = limited_receive
        with tempfile.TemporaryDirectory(prefix="otm-upload-") as folder:
            root = Path(folder)
            async with request.form(
                max_files=5, max_fields=3, max_part_size=settings.max_upload_bytes
            ) as form:
                for field, item in form.multi_items():
                    if not isinstance(item, UploadFile) or field != "files":
                        raise AppError(
                            422, "UPLOAD_SCHEMA_REJECTED", "Envie somente cinco arquivos no campo files."
                        )
                    name = item.filename or ""
                    if name not in SCHEMAS or name in seen:
                        raise AppError(
                            422,
                            "UPLOAD_FILENAME_REJECTED",
                            "Nomes devem corresponder aos cinco CSVs, sem duplicatas ou caminhos.",
                        )
                    seen.add(name)
                    size = 0
                    with (root / name).open("xb") as out:
                        while chunk := await item.read(1024 * 1024):
                            size += len(chunk)
                            total += len(chunk)
                            if size > settings.max_upload_bytes or total > settings.max_request_bytes:
                                raise AppError(
                                    413, "UPLOAD_TOO_LARGE", "Limite: 64 MiB por CSV e 128 MiB por envio."
                                )
                            out.write(chunk)
                if seen != set(SCHEMAS):
                    raise AppError(422, "UPLOAD_FILES_MISSING", "Selecione os cinco CSVs exigidos pelo case.")
                yield root

    @app.get("/healthz", tags=["Saúde"])
    def healthz():
        return {"status": "ok", "version": VERSION}

    @app.get("/readyz", tags=["Saúde"])
    def readyz():
        try:
            repo.ready()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    @app.post("/api/v1/auth/demo-session", response_model=UserView, tags=["Identidade"])
    def login(body: DemoSession, request: Request, response: Response):
        check_origin(request, settings)
        token, p = demo_login(repo, settings, body.profile)
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            samesite="strict",
            max_age=settings.session_seconds,
            secure=settings.environment == "gcp",
        )
        return {"name": p.name, "role": p.role, "csrf_token": p.csrf, "environment": settings.environment}

    @app.get("/api/v1/me", response_model=UserView, tags=["Identidade"])
    def me(p: User):
        return {"name": p.name, "role": p.role, "csrf_token": p.csrf, "environment": settings.environment}

    @app.post("/api/v1/auth/logout", status_code=204, tags=["Identidade"])
    def logout(request: Request, response: Response, p: User):
        check_origin(request, settings)
        if settings.environment != "gcp":
            if request.headers.get("x-csrf-token") != p.csrf:
                raise AppError(403, "CSRF_REJECTED", "Sessão desatualizada.")
            repo.delete_session(token_hash(request.cookies.get(COOKIE, "")))
        response.delete_cookie(COOKIE)

    @app.get("/api/v1/policies", tags=["Políticas"])
    def policies(p: User):
        return {"items": POLICIES, "default": "strict", "homologated": False}

    @app.post(
        "/api/v1/validations",
        response_model=ValidationView,
        tags=["Importação"],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
                            },
                            "required": ["files"],
                        }
                    }
                },
            }
        },
    )
    async def validate_upload(request: Request, p: Operator):
        async with upload_directory(request) as directory:
            return service.validate(directory)

    @app.post(
        "/api/v1/reconciliations",
        response_model=RunView,
        status_code=202,
        tags=["Conciliação"],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
                            },
                            "required": ["files"],
                        }
                    }
                },
            }
        },
    )
    async def create(
        request: Request,
        p: Operator,
        idempotency_key: Key,
        policy: Literal["strict", "complete-kits"] = "strict",
    ):
        async with upload_directory(request) as directory:
            result, _ = service.create(directory, policy, p, idempotency_key)
            return result

    @app.post("/api/v1/examples", response_model=RunView, status_code=202, tags=["Demonstração"])
    def example(body: ExampleRequest, p: Operator, idempotency_key: Key):
        result, _ = service.create(
            ROOT / "data/input", body.policy, p, idempotency_key, "Case original · nova execução"
        )
        return result

    @app.get("/api/v1/reconciliations", response_model=Page[RunView], tags=["Conciliação"])
    def list_runs(p: User, limit: Limit = 20, offset: Offset = 0):
        return repo.list_runs(p, limit, offset)

    @app.get("/api/v1/reconciliations/{run_id}", response_model=RunView, tags=["Conciliação"])
    def get_run(run_id: str, p: User):
        return repo.public(repo.get(run_id, p))

    @app.get("/api/v1/reconciliations/{run_id}/summary", response_model=SummaryView, tags=["Resultados"])
    def summary(run_id: str, p: User):
        return ready_run(run_id, p)["summary"]

    @app.get(
        "/api/v1/reconciliations/{run_id}/decisions", response_model=Page[DecisionView], tags=["Resultados"]
    )
    def list_decisions(
        run_id: str,
        p: User,
        limit: Limit = 20,
        offset: Offset = 0,
        search: Annotated[str, Query(max_length=128)] = "",
        status: Literal["", "MANTIDO", "AJUSTADO", "ZERADO", "REVISAO"] = "",
        cd: Annotated[str, Query(max_length=128)] = "",
        sort: Literal["poi_id", "sku", "cd_origem", "qtd_final", "pedido_id"] = "poi_id",
        descending: bool = False,
    ):
        ready_run(run_id, p)
        return repo.page("decisions", run_id, limit, offset, search, status, cd, sort, descending)

    @app.get(
        "/api/v1/reconciliations/{run_id}/decisions/{poi_id}",
        response_model=DecisionView,
        tags=["Resultados"],
    )
    def decision(run_id: str, poi_id: str, p: User):
        ready_run(run_id, p)
        return repo.detail(run_id, poi_id)

    @app.get(
        "/api/v1/reconciliations/{run_id}/exceptions", response_model=Page[DecisionView], tags=["Resultados"]
    )
    def exceptions(run_id: str, p: User, limit: Limit = 20, offset: Offset = 0):
        ready_run(run_id, p)
        return repo.page("decisions", run_id, limit, offset, status="REVISAO")

    @app.get(
        "/api/v1/reconciliations/{run_id}/inventory", response_model=Page[InventoryView], tags=["Resultados"]
    )
    def list_inventory(
        run_id: str,
        p: User,
        limit: Limit = 20,
        offset: Offset = 0,
        search: Annotated[str, Query(max_length=128)] = "",
        cd: str = "",
    ):
        ready_run(run_id, p)
        return repo.page("inventory", run_id, limit, offset, search=search, cd=cd, sort="sku")

    @app.get("/api/v1/reconciliations/{run_id}/artifacts", response_model=ArtifactList, tags=["Auditoria"])
    def files(run_id: str, p: User):
        ready_run(run_id, p)
        return {"items": [{k: f[k] for k in ("name", "sha256", "size")} for f in repo.files(run_id)]}

    @app.get("/api/v1/reconciliations/{run_id}/artifacts/{name}", tags=["Auditoria"])
    def download(run_id: str, name: str, p: User):
        ready_run(run_id, p)
        item = next((f for f in repo.files(run_id) if f["name"] == name), None)
        if not item:
            raise AppError(404, "ARTIFACT_NOT_FOUND", "Artefato não encontrado.")
        # Validação antes de responder 200. O objeto permanece imutável entre as leituras.
        context = verified_stream(storage, item["key"], item["sha256"])
        stream = context.__enter__()

        def chunks():
            try:
                yield from iter(lambda: stream.read(64 * 1024), b"")
            finally:
                context.__exit__(None, None, None)

        repo.event(run_id, p.subject, "ARTIFACT_DOWNLOADED", {"name": name})
        return StreamingResponse(
            chunks(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{name}"', "ETag": f'"{item["sha256"]}"'},
        )

    @app.get("/api/v1/reconciliations/{run_id}/audit", tags=["Auditoria"])
    def audit_events(run_id: str, p: User):
        repo.get(run_id, p)
        return {"items": repo.events(run_id)}

    @app.post("/api/v1/reconciliations/{run_id}/integrity", tags=["Auditoria"])
    def integrity(run_id: str, request: Request, p: User):
        check_origin(request, settings)
        if settings.environment != "gcp" and request.headers.get("x-csrf-token") != p.csrf:
            raise AppError(403, "CSRF_REJECTED", "Sessão desatualizada.")
        return service.integrity(run_id, p)

    @app.post(
        "/api/v1/reconciliations/{run_id}/simulations",
        response_model=RunView,
        status_code=202,
        tags=["Políticas"],
    )
    def simulate(run_id: str, body: SimulationRequest, p: Operator, idempotency_key: Key):
        return service.simulation(run_id, body.policy, p, idempotency_key)[0]

    @app.get("/api/v1/reconciliations/{run_id}/comparison/{other_id}", tags=["Políticas"])
    def compare(run_id: str, other_id: str, p: User):
        source = ready_run(run_id, p)["summary"]
        target = ready_run(other_id, p)["summary"]
        if source["inputs_sha256"] != target["inputs_sha256"]:
            raise AppError(
                422, "COMPARISON_INPUTS_MISMATCH", "Compare somente execuções das mesmas cinco entradas."
            )
        before = source["metrics"]["unidades_finais"]
        after = target["metrics"]["unidades_finais"]
        return {
            "source_id": run_id,
            "target_id": other_id,
            "delta_units": after - before,
            "delta_percent": round(100 * (after - before) / before, 2) if before else None,
            **repo.compare(run_id, other_id),
            "notice": "Simulação não homologada. Nenhuma proposta foi alterada.",
        }

    @app.post(
        "/api/v1/reconciliations/{run_id}/retry",
        response_model=RunView,
        status_code=202,
        tags=["Conciliação"],
    )
    def retry(run_id: str, p: Operator):
        repo.get(run_id, p)
        repo.requeue(run_id)
        repo.event(run_id, p.subject, "RETRY_REQUESTED")
        service.dispatch(run_id)
        return repo.public(repo.get(run_id))

    @app.get("/api/v1/metrics", tags=["Observabilidade"])
    def metrics(p: User):
        if p.role not in {"admin", "auditor"}:
            raise AppError(403, "ROLE_NOT_ALLOWED", "Métricas técnicas exigem perfil de auditoria.")
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = (settings.frontend_dir / path).resolve()
        root = settings.frontend_dir.resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        index = root / "index.html"
        if index.exists() and not path.startswith(("api/", "assets/")):
            return FileResponse(index)
        return JSONResponse(
            status_code=404,
            content={"detail": "Frontend não construído. Execute npm run build em frontend/."},
        )

    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
            {
                "DemoSession": {"type": "apiKey", "in": "cookie", "name": COOKIE},
                "IAPAssertion": {"type": "apiKey", "in": "header", "name": "X-Goog-IAP-JWT-Assertion"},
            }
        )
        for path, methods in schema["paths"].items():
            if path.startswith("/api/") and path != "/api/v1/auth/demo-session":
                for operation in methods.values():
                    if isinstance(operation, dict):
                        operation["security"] = [{"DemoSession": []}, {"IAPAssertion": []}]
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app


def serve():
    import os

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(
        create_app(),
        host=os.getenv("OTM_BIND", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
        access_log=False,
        forwarded_allow_ips="127.0.0.1",
    )


if __name__ == "__main__":
    serve()
