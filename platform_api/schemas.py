"""Schemas públicos documentados pelo OpenAPI."""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .domain import Mode, Role


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoSession(StrictModel):
    profile: Role = "operator"


class UserView(BaseModel):
    name: str
    role: Role
    csrf_token: str
    environment: str


class SimulationRequest(StrictModel):
    policy: Mode


class ExampleRequest(StrictModel):
    policy: Mode = "strict"


class RunView(BaseModel):
    id: str
    label: str
    policy: Mode
    state: str
    kind: str
    parent_id: str | None = None
    created_at: float
    updated_at: float
    attempt: int
    summary: dict[str, Any] | None = None
    failure: dict[str, Any] | None = None
    timings: dict[str, float] | None = None
    snapshot: str | None = None


class DecisionView(BaseModel):
    poi_id: str
    pedido_id: str
    cd_origem: str
    cod_franqueado: str
    sku: str
    qtd_pedida: int = Field(ge=0)
    qtd_sugerida_otm: int | None
    qtd_final: int = Field(ge=0)
    status: Literal["MANTIDO", "AJUSTADO", "ZERADO", "REVISAO"]
    combo_id: str
    reasons: list[str]
    explanation: str
    next_action: str
    constraints: dict[str, Any]
    input_references: list[dict[str, str]]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    detail: str
    correlation_id: str
