"""Sessão demo explícita e validação criptográfica dos headers do IAP."""

import hashlib
import secrets
import time
from functools import lru_cache
from typing import cast

from fastapi import Request

from .config import Settings
from .domain import AppError, Principal, Role
from .repository import Repository

COOKIE = "otm_session"
PROFILES: dict[str, tuple[str, Role]] = {
    "operator": ("Analista de operações", "operator"),
    "viewer": ("Gestão e diretoria", "viewer"),
    "auditor": ("Auditoria técnica", "auditor"),
    "admin": ("Administração demo", "admin"),
}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def demo_login(repo: Repository, settings: Settings, profile: str) -> tuple[str, Principal]:
    if settings.environment == "gcp":
        raise AppError(404, "NOT_FOUND", "Recurso indisponível neste ambiente.")
    name, role = PROFILES[profile]
    principal = Principal(f"demo:{profile}", name, role, secrets.token_urlsafe(32))
    token = secrets.token_urlsafe(32)
    repo.save_session(token_hash(token), principal, time.time() + settings.session_seconds)
    return token, principal


@lru_cache(maxsize=128)
def _verify_iap(token: str, audience: str) -> dict:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    class BoundedRequest(GoogleRequest):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 5
            return super().__call__(*args, **kwargs)

    return dict(
        id_token.verify_token(
            token,
            BoundedRequest(),
            audience=audience,
            certs_url="https://www.gstatic.com/iap/verify/public_key",
            clock_skew_in_seconds=30,
        )
    )


def iap_principal(token: str, settings: Settings) -> Principal:
    try:
        claims = _verify_iap(token, settings.iap_audience)
        now = time.time()
        if (
            claims.get("iss") != "https://cloud.google.com/iap"
            or claims.get("aud") != settings.iap_audience
            or claims["exp"] < now - 30
            or claims["iat"] > now + 30
            or claims["exp"] - claims["iat"] > 660
        ):
            raise ValueError("claims")
        email, subject = claims["email"], claims["sub"]
    except Exception:
        raise AppError(401, "INVALID_IDENTITY", "Identidade ausente, expirada ou inválida.") from None
    role = settings.identities.get(email)
    if role not in {"operator", "viewer", "auditor", "admin"}:
        raise AppError(
            403, "IDENTITY_NOT_AUTHORIZED", "Identidade autenticada sem papel autorizado na aplicação."
        )
    return Principal(subject, "Conta corporativa", cast(Role, role))


def authenticate(request: Request, repo: Repository, settings: Settings) -> Principal:
    if settings.environment == "gcp":
        token = request.headers.get("x-goog-iap-jwt-assertion", "")
        if not token:
            raise AppError(401, "AUTHENTICATION_REQUIRED", "Acesse pela entrada autenticada do IAP.")
        return iap_principal(token, settings)
    token = request.cookies.get(COOKIE, "")
    row = repo.session(token_hash(token)) if token else None
    if not row:
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Abra uma sessão demonstrativa para continuar.")
    return Principal(row["subject"], row["name"], row["role"], row["csrf"])


def check_origin(request: Request, settings: Settings):
    origin = request.headers.get("origin")
    allowed = {settings.public_origin}
    if settings.environment != "gcp":
        allowed.add(str(request.base_url).rstrip("/"))
    if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin not in allowed):
        raise AppError(403, "ORIGIN_REJECTED", "Solicitação de outra origem recusada.")


def authorize_mutation(request: Request, principal: Principal, settings: Settings):
    check_origin(request, settings)
    if principal.role not in {"operator", "admin"}:
        raise AppError(
            403, "ROLE_NOT_ALLOWED", "Seu perfil permite consulta. Use um perfil operacional para executar."
        )
    if settings.environment != "gcp" and not secrets.compare_digest(
        request.headers.get("x-csrf-token", ""), principal.csrf
    ):
        raise AppError(403, "CSRF_REJECTED", "Sessão desatualizada. Atualize a página antes de executar.")
