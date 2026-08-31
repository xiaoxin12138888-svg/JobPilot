# JobPilot Agent Rules

## Current phase

Local-first Single-user Repository Simplification is complete and awaiting project-owner acceptance. Work on `phase/2-authentication`; recovery checkpoint is `pre-local-first-cleanup`. Phase 3 is not started. Do not implement Job, Application, ResumeVersion, recruitment-site adapters, content scripts, AI, RAG, uploads, analytics or dashboards without separate approval.

## Canonical context

Read ADR-008, `tasks/plan.md`, `tasks/todo.md`, README, PRODUCT_SPEC, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ROADMAP and ENGINEERING_PRINCIPLES. Historical remote-identity experiments exist only at `pre-local-first-cleanup` and are not current design input.

## Toolchains

- TypeScript: pnpm; tests: Vitest.
- Python: uv; tests: Pytest; lint/format: Ruff.
- Do not create npm/Yarn locks, Poetry/Pipenv workflows, Black or isort configuration.

## Commands

- Web: `pnpm dev:web`, `pnpm build:web`, `pnpm test:web`.
- Extension: `pnpm dev:extension`, `pnpm build:extension`, `pnpm test:extension`.
- TypeScript gates: `pnpm test`, `pnpm lint`, `pnpm format:check`, `pnpm typecheck`.
- API: `pnpm api:dev`, `pnpm api:test`, `pnpm api:lint`, `pnpm api:format:check`, `pnpm api:import:check`.

## Boundaries

- One installation is one local workspace. There is no account, login, session, User or multi-user ownership boundary.
- Current API surface is only `GET /health`; it does not create a database engine or call a remote service.
- Web and Extension connections to the JobPilot API, the API bind, and PostgreSQL tooling are loopback-only. Never document or default the JobPilot service to `0.0.0.0`, LAN or public hosts. Future Extension access to recruitment pages is a separate, user-triggered exact-host permission governed below.
- CORS uses exact reviewed Web/Extension origins, GET-only and no credentials; never use wildcard or regex.
- Current database metadata is empty. Preserve PostgreSQL/SQLAlchemy/Alembic scaffolding; do not create `LocalProfile` without a real requirement.
- Installed core must work in Mainland China without VPN, proxy or special DNS and without remote identity, CDN, fonts/scripts, telemetry, update APIs or mandatory foreign AI.
- Extension bundles all code, never modifies proxies, and currently has no background/content script/recruitment host. Future capture requires exact hosts, user gesture, current rendered DOM and per-Adapter no-proxy acceptance.
- Treat API responses, DOM, pasted text, URLs and files as untrusted at their boundaries.
- Write a failing behavior test before logic, implement the smallest GREEN, and run affected gates after each increment.
- Keep docs synchronized, remove dead abstractions, and stop before Phase 3 until the project owner explicitly approves it.
