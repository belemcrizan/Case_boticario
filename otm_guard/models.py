"""Contratos imutáveis do domínio. Quantidades são sempre inteiros em peças."""

from dataclasses import dataclass, field
from typing import Literal


class ContractError(ValueError):
    """Entrada estruturalmente inválida: nenhum lote deve ser publicado."""


class InvariantError(RuntimeError):
    """Resultado inconsistente: interromper antes de gerar os artefatos."""


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    source: str
    line: int
    key: str
    detail: str


@dataclass(frozen=True)
class Order:
    poi_id: str
    pedido_id: str
    cd_origem: str
    cod_franqueado: str
    sku: str
    qtd_pedida: int

    @property
    def scope(self) -> tuple[str, str, str]:
        return self.pedido_id, self.cd_origem, self.cod_franqueado


@dataclass(frozen=True)
class Suggestion:
    poi_id: str
    sku: str
    quantity: int
    status: str


@dataclass(frozen=True)
class Packaging:
    sku: str
    brand: str
    multiple: int
    fractionation: bool

    @property
    def step(self) -> int:
        return 1 if self.fractionation else self.multiple


@dataclass(frozen=True)
class Combo:
    combo_id: str
    description: str
    rule: str
    components: dict[str, int]


STRICT_RULE = "Zerar se incompleto"
MAX_RULE = "Ajustar para maior combo completo"


@dataclass(frozen=True)
class Policy:
    incomplete_policy: Literal["strict", "complete-kits"] = "strict"
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if self.incomplete_policy not in {"strict", "complete-kits"}:
            raise ValueError("Política de combo desconhecida")


@dataclass
class Dataset:
    orders: dict[str, Order]
    suggestions: dict[str, Suggestion]
    stock: dict[tuple[str, str], int]
    packaging: dict[str, Packaging]
    combos: dict[str, Combo]
    membership: dict[str, str]
    input_hashes: dict[str, str] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    poi_id: str
    pedido_id: str
    cd_origem: str
    cod_franqueado: str
    sku: str
    qtd_pedida: int
    qtd_sugerida_otm: int | None
    qtd_final: int
    status: str
    combo_id: str
    reasons: tuple[str, ...]


@dataclass
class Result:
    decisions: list[Decision]
    remaining_stock: dict[tuple[str, str], int]
    policy: Policy
    checks: dict[str, bool]
    metrics: dict[str, int | float | None]
