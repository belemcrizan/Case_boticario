# ADR 002 — API, frontend e persistência

Status: implementada e testada; integração GCP não homologada.

Motor/CLI continuam sem dependências. FastAPI, Pydantic e SQLAlchemy Core compõem a camada externa. React, TypeScript, TanStack Query/Table e Zod compartilham origem com a API. CSS nativo, SVG para gráfico e dialog nativo reduzem dependências. SSR/Next.js não são necessários para este painel autenticado.

SQLite atende o demo. PostgreSQL/Cloud SQL oferece transações, claims, filtros e comparação de decisões. Firestore exigiria outra modelagem para essas consultas e para publicação transacional. SQL persiste propostas, sem reservar estoque.

O adapter de publicação limita HTML grande e preserva CSV completo, fora dos sete fontes originais. Precisa de regressão própria. O schema inicial tem bootstrap explícito; create_all não substitui migrações versionadas futuras.
