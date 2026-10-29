"""Identidade, erros públicos e políticas autorizadas da aplicação."""

from dataclasses import dataclass
from typing import Literal

Mode = Literal["strict", "complete-kits"]
Role = Literal["operator", "viewer", "auditor", "admin"]


@dataclass(frozen=True)
class Principal:
    subject: str
    name: str
    role: Role
    csrf: str = ""


class AppError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


POLICIES = [
    {
        "id": "strict",
        "label": "Conservadora",
        "version": "1.0.0",
        "default": True,
        "description": "Zera o lote incompleto quando a regra comercial exige integridade do lote.",
        "homologation": "Premissa do demonstrador. Requer confirmação comercial.",
        "example": "50 perfumes e 35 loções: proposta 0 e 0.",
    },
    {
        "id": "complete-kits",
        "label": "Preservar kits completos",
        "version": "1.0.0",
        "default": False,
        "description": "Preserva a maior quantidade viável de kits completos também nos lotes incompletos.",
        "homologation": "Cenário alternativo não homologado.",
        "example": "50 perfumes e 35 loções: proposta 35 e 35.",
    },
]
