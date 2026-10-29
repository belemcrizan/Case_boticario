"""Persistência SQL com autorização aplicada antes das consultas de dados."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    create_engine,
    delete,
    func,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .config import Settings
from .domain import AppError, Principal

metadata = MetaData()
capacity = Table(
    "capacity_lock",
    metadata,
    Column("id", String(16), primary_key=True),
    Column("version", Integer, nullable=False),
)
runs = Table(
    "runs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("owner", String(256), nullable=False),
    Column("label", String(160), nullable=False),
    Column("policy", String(32), nullable=False),
    Column("state", String(24), nullable=False),
    Column("kind", String(24), nullable=False),
    Column("visibility", String(16), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column("parent_id", String(64)),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    Column("lease_until", Float),
    Column("attempt", Integer, nullable=False, default=0),
    Column("summary", JSON),
    Column("failure", JSON),
    Column("timings", JSON),
    Column("snapshot", String(64)),
    UniqueConstraint("owner", "idempotency_key"),
)
decisions = Table(
    "decisions",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("poi_id", String(128), primary_key=True),
    Column("pedido_id", String(128), nullable=False),
    Column("sku", String(128), nullable=False),
    Column("cd_origem", String(128), nullable=False),
    Column("status", String(24), nullable=False),
    Column("qtd_final", BigInteger, nullable=False),
    Column("payload", JSON, nullable=False),
)
Index("ix_decisions_filter", decisions.c.run_id, decisions.c.status, decisions.c.cd_origem)
inventory = Table(
    "inventory",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("cd_origem", String(128), primary_key=True),
    Column("sku", String(128), primary_key=True),
    Column("payload", JSON, nullable=False),
)
audit = Table(
    "audit_events",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("at", Float, nullable=False),
    Column("actor_hash", String(64), nullable=False),
    Column("action", String(64), nullable=False),
    Column("detail", JSON, nullable=False),
)
artifacts = Table(
    "artifacts",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("name", String(128), primary_key=True),
    Column("key", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("size", BigInteger, nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("subject", String(256), nullable=False),
    Column("name", String(160), nullable=False),
    Column("role", String(24), nullable=False),
    Column("csrf", String(128), nullable=False),
    Column("expires_at", Float, nullable=False),
)


def make_engine(settings: Settings) -> Engine:
    if settings.environment == "gcp":
        from .cloud import cloud_sql_engine

        return cloud_sql_engine(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = settings.database_url or f"sqlite:///{settings.data_dir / 'platform.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, pool_pre_ping=True)
    if settings.initialize_schema:
        metadata.create_all(engine)
        with engine.begin() as db:
            if not db.scalar(select(capacity.c.id).where(capacity.c.id == "global")):
                db.execute(insert(capacity).values(id="global", version=0))
    return engine


class Repository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def ready(self) -> bool:
        with self.engine.connect() as db:
            db.execute(select(runs.c.id).limit(1))
        return True

    def get(self, run_id: str, principal: Principal | None = None) -> dict:
        with self.engine.connect() as db:
            row = db.execute(select(runs).where(runs.c.id == run_id)).mappings().first()
        if row is None or (
            principal
            and principal.role != "admin"
            and row["owner"] != principal.subject
            and row["visibility"] != "demo"
        ):
            raise AppError(404, "RUN_NOT_FOUND", "Lote não encontrado ou sem permissão de acesso.")
        return dict(row)

    def list_runs(self, principal: Principal, limit: int, offset: int) -> dict:
        query = select(runs)
        if principal.role != "admin":
            query = query.where(or_(runs.c.owner == principal.subject, runs.c.visibility == "demo"))
        with self.engine.connect() as db:
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            items = db.execute(
                query.order_by(runs.c.created_at.desc(), runs.c.id).limit(limit).offset(offset)
            ).mappings()
            return {
                "items": [self.public(dict(x)) for x in items],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    @staticmethod
    def public(row: dict) -> dict:
        return {
            k: row[k]
            for k in (
                "id",
                "label",
                "policy",
                "state",
                "kind",
                "parent_id",
                "created_at",
                "updated_at",
                "attempt",
                "summary",
                "failure",
                "timings",
                "snapshot",
            )
        }

    def create(self, record: dict, max_active: int = 4) -> tuple[dict, bool]:
        try:
            with self.engine.begin() as db:
                # UPDATE adquire o mesmo lock em SQLite e PostgreSQL, serializando
                # admissão global sem depender do número de instâncias da API.
                lock = db.execute(
                    update(capacity).where(capacity.c.id == "global").values(version=capacity.c.version + 1)
                )
                if lock.rowcount != 1:
                    raise AppError(
                        503,
                        "SCHEMA_NOT_INITIALIZED",
                        "Inicialize o schema e o lock global antes de aceitar lotes.",
                    )
                previous = (
                    db.execute(
                        select(runs).where(
                            and_(
                                runs.c.owner == record["owner"],
                                runs.c.idempotency_key == record["idempotency_key"],
                            )
                        )
                    )
                    .mappings()
                    .first()
                )
                if previous:
                    if previous["fingerprint"] != record["fingerprint"]:
                        raise AppError(
                            409, "IDEMPOTENCY_CONFLICT", "A chave já identifica outras entradas ou política."
                        )
                    return dict(previous), False
                active = (
                    db.scalar(
                        select(func.count())
                        .select_from(runs)
                        .where(runs.c.state.in_(["UPLOADING", "QUEUED", "RUNNING"]))
                    )
                    or 0
                )
                if active >= max_active:
                    raise AppError(
                        429,
                        "QUEUE_CAPACITY",
                        "Limite global de execuções ativas atingido. Aguarde um lote concluir.",
                    )
                db.execute(insert(runs).values(**record))
            return record, True
        except IntegrityError:
            with self.engine.connect() as db:
                row = (
                    db.execute(
                        select(runs).where(
                            and_(
                                runs.c.owner == record["owner"],
                                runs.c.idempotency_key == record["idempotency_key"],
                            )
                        )
                    )
                    .mappings()
                    .first()
                )
            if row is None:
                raise
            if row["fingerprint"] != record["fingerprint"]:
                raise AppError(
                    409, "IDEMPOTENCY_CONFLICT", "A chave já identifica outras entradas ou política."
                ) from None
            return dict(row), False

    def active_count(self, subject: str) -> int:
        with self.engine.connect() as db:
            return int(
                db.scalar(
                    select(func.count())
                    .select_from(runs)
                    .where(
                        and_(runs.c.owner == subject, runs.c.state.in_(["UPLOADING", "QUEUED", "RUNNING"]))
                    )
                )
                or 0
            )

    def by_key(self, owner: str, key: str) -> dict | None:
        with self.engine.connect() as db:
            row = (
                db.execute(select(runs).where(and_(runs.c.owner == owner, runs.c.idempotency_key == key)))
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def save_timings(self, run_id: str, attempt: int, timings: dict):
        with self.engine.begin() as db:
            db.execute(
                update(runs)
                .where(and_(runs.c.id == run_id, runs.c.attempt == attempt, runs.c.state == "COMPLETED"))
                .values(timings=timings)
            )

    def claim(self, run_id: str, lease_seconds: int) -> bool:
        now = time.time()
        with self.engine.begin() as db:
            result = db.execute(
                update(runs)
                .where(and_(runs.c.id == run_id, runs.c.state == "QUEUED"))
                .values(
                    state="RUNNING",
                    updated_at=now,
                    lease_until=now + lease_seconds,
                    attempt=runs.c.attempt + 1,
                )
            )
        return result.rowcount == 1

    def queued(self, run_id: str):
        with self.engine.begin() as db:
            db.execute(update(runs).where(runs.c.id == run_id).values(state="QUEUED", updated_at=time.time()))

    def event(self, run_id: str, actor: str, action: str, detail: dict | None = None):
        import uuid

        with self.engine.begin() as db:
            db.execute(
                insert(audit).values(
                    id=uuid.uuid4().hex,
                    run_id=run_id,
                    at=time.time(),
                    actor_hash=hashlib.sha256(actor.encode()).hexdigest(),
                    action=action,
                    detail=detail or {},
                )
            )

    def fail(self, run_id: str, code: str, detail: str, attempt: int | None = None):
        with self.engine.begin() as db:
            predicate = runs.c.id == run_id
            if attempt is not None:
                predicate = and_(predicate, runs.c.attempt == attempt, runs.c.state == "RUNNING")
            db.execute(
                update(runs)
                .where(predicate)
                .values(
                    state="FAILED",
                    updated_at=time.time(),
                    lease_until=None,
                    failure={"code": code, "detail": detail},
                )
            )

    def requeue(self, run_id: str):
        now = time.time()
        with self.engine.begin() as db:
            result = db.execute(
                update(runs)
                .where(
                    and_(
                        runs.c.id == run_id,
                        runs.c.attempt < 3,
                        or_(
                            runs.c.state == "FAILED",
                            and_(runs.c.state == "RUNNING", runs.c.lease_until < now),
                        ),
                    )
                )
                .values(state="QUEUED", updated_at=now, failure=None)
            )
        if result.rowcount != 1:
            raise AppError(
                409, "RETRY_NOT_ALLOWED", "Retry exige falha ou lease expirado e no máximo três tentativas."
            )

    def complete(
        self,
        run_id: str,
        rows: Iterable[dict],
        stock_rows: Iterable[dict],
        summary: dict,
        timings: dict,
        files: list[dict],
        attempt: int,
    ):
        # Dados visíveis somente com estado COMPLETED, na mesma transação SQL.
        with self.engine.begin() as db:
            fence = db.execute(
                update(runs)
                .where(and_(runs.c.id == run_id, runs.c.state == "RUNNING", runs.c.attempt == attempt))
                .values(updated_at=time.time())
            )
            if fence.rowcount != 1:
                raise AppError(409, "LEASE_LOST", "Outra tentativa assumiu esta execução.")
            for table in (decisions, inventory, artifacts):
                db.execute(delete(table).where(table.c.run_id == run_id))
            batch = []
            for row in rows:
                batch.append(
                    {
                        "run_id": run_id,
                        "poi_id": row["poi_id"],
                        "pedido_id": row["pedido_id"],
                        "sku": row["sku"],
                        "cd_origem": row["cd_origem"],
                        "status": row["status"],
                        "qtd_final": row["qtd_final"],
                        "payload": row,
                    }
                )
                if len(batch) == 1000:
                    db.execute(insert(decisions), batch)
                    batch = []
            if batch:
                db.execute(insert(decisions), batch)
            stock = [
                {"run_id": run_id, "cd_origem": r["cd_origem"], "sku": r["sku"], "payload": r}
                for r in stock_rows
            ]
            if stock:
                db.execute(insert(inventory), stock)
            db.execute(insert(artifacts), [{"run_id": run_id, **f} for f in files])
            db.execute(
                update(runs)
                .where(runs.c.id == run_id)
                .values(
                    state="COMPLETED",
                    summary=summary,
                    timings=timings,
                    updated_at=time.time(),
                    lease_until=None,
                    failure=None,
                )
            )

    def page(
        self,
        table_name: str,
        run_id: str,
        limit: int,
        offset: int,
        search: str = "",
        status: str = "",
        cd: str = "",
        sort: str = "poi_id",
        descending: bool = False,
    ) -> dict:
        table = {"decisions": decisions, "inventory": inventory}[table_name]
        query = select(table.c.payload).where(table.c.run_id == run_id)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            fields = [table.c.sku, table.c.cd_origem]
            if table_name == "decisions":
                fields += [table.c.poi_id, table.c.pedido_id]
            query = query.where(or_(*(c.ilike(f"%{escaped}%", escape="\\") for c in fields)))
        if cd:
            query = query.where(table.c.cd_origem == cd)
        if status and table_name == "decisions":
            query = query.where(table.c.status == status)
        allowed = {"poi_id", "sku", "cd_origem", "qtd_final", "pedido_id"}
        column = table.c[sort if sort in allowed and sort in table.c else "sku"]
        with self.engine.connect() as db:
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            tie = table.c.poi_id if table_name == "decisions" else table.c.cd_origem
            items: list[dict] = list(
                db.execute(
                    query.order_by(column.desc() if descending else column.asc(), table.c.sku, tie)
                    .limit(limit)
                    .offset(offset)
                )
                .scalars()
                .all()
            )
        if table_name == "decisions":
            hashes = self.get(run_id)["summary"]["inputs_sha256"]
            items = [self.hydrate(item, hashes) for item in items]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @staticmethod
    def hydrate(row: dict, hashes: dict) -> dict:
        if "input_references" not in row:
            row = {
                **row,
                "input_references": [
                    {
                        "file": name,
                        "sha256": checksum,
                        "key": row["poi_id"]
                        if name in {"pedidos_oms.csv", "saidas_otm.csv"}
                        else f"{row['cd_origem']}/{row['sku']}"
                        if name.startswith("foto_")
                        else row["sku"],
                    }
                    for name, checksum in sorted(hashes.items())
                ],
            }
        return row

    def detail(self, run_id: str, poi_id: str) -> dict:
        with self.engine.connect() as db:
            row = db.scalar(
                select(decisions.c.payload).where(
                    and_(decisions.c.run_id == run_id, decisions.c.poi_id == poi_id)
                )
            )
        if row is None:
            raise AppError(404, "POI_NOT_FOUND", "Item não encontrado neste lote.")
        return self.hydrate(row, self.get(run_id)["summary"]["inputs_sha256"])

    def compare(self, source_id: str, target_id: str) -> dict:
        before, after = decisions.alias("before"), decisions.alias("after")
        query = (
            select(before.c.payload.label("before"), after.c.payload.label("after"))
            .select_from(before.join(after, before.c.poi_id == after.c.poi_id))
            .where(
                and_(
                    before.c.run_id == source_id,
                    after.c.run_id == target_id,
                    before.c.qtd_final != after.c.qtd_final,
                )
            )
        )
        with self.engine.connect() as db:
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            rows = db.execute(query.order_by(before.c.poi_id).limit(100)).mappings()
            items = [
                {
                    "poi_id": r["before"]["poi_id"],
                    "sku": r["before"]["sku"],
                    "before": r["before"]["qtd_final"],
                    "after": r["after"]["qtd_final"],
                    "combo_id": r["before"]["combo_id"],
                }
                for r in rows
            ]
        return {"affected_count": total, "items": items, "limit": 100}

    def files(self, run_id: str) -> list[dict]:
        with self.engine.connect() as db:
            return [
                dict(r) for r in db.execute(select(artifacts).where(artifacts.c.run_id == run_id)).mappings()
            ]

    def events(self, run_id: str) -> list[dict]:
        with self.engine.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    select(audit).where(audit.c.run_id == run_id).order_by(audit.c.at.desc()).limit(100)
                ).mappings()
            ]

    def save_session(self, token_hash: str, principal: Principal, expires_at: float):
        with self.engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.expires_at < time.time()))
            db.execute(
                insert(sessions).values(
                    token_hash=token_hash,
                    subject=principal.subject,
                    name=principal.name,
                    role=principal.role,
                    csrf=principal.csrf,
                    expires_at=expires_at,
                )
            )

    def session(self, token_hash: str) -> dict[str, Any] | None:
        with self.engine.connect() as db:
            row = (
                db.execute(
                    select(sessions).where(
                        and_(sessions.c.token_hash == token_hash, sessions.c.expires_at > time.time())
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def delete_session(self, token_hash: str):
        with self.engine.begin() as db:
            db.execute(delete(sessions).where(sessions.c.token_hash == token_hash))
