# JobPilot Agent Rules

## Current phase

Phase 2.5 Local Runtime Foundation Finalization is active on `phase/2.5-local-runtime`. The original `phase/2-authentication` branch and recovery checkpoint `pre-local-first-cleanup` remain untouched. Phase 3 is not started. Do not implement Job, Application, ResumeVersion, recruitment-site adapters, content scripts, AI, RAG, uploads, analytics or dashboards without separate approval.

## Canonical context

Read ADR-008, `tasks/plan.md`, `tasks/todo.md`, README, PRODUCT_SPEC, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ROADMAP and ENGINEERING_PRINCIPLES. Historical remote-identity experiments exist only at `pre-local-first-cleanup` and are not current design input.

## Toolchains

- TypeScript: pnpm; tests: Vitest.
- Python: uv; tests: Pytest; lint/format: Ruff.
- Do not create npm/Yarn locks, Poetry/Pipenv workflows, Black or isort configuration.

## Commands

- Web: `pnpm run dev:web`, `pnpm run build:web`, `pnpm run test:web`.
- Extension: `pnpm run dev:extension`, `pnpm run build:extension`, `pnpm run test:extension`.
- TypeScript gates: `pnpm run test`, `pnpm run lint`, `pnpm run format:check`, `pnpm run typecheck`.
- API: `pnpm run api:dev`, `pnpm run api:test`, `pnpm run api:lint`, `pnpm run api:format:check`, `pnpm run api:import:check`.

## Boundaries

- One installation is one local workspace. There is no account, login, session, User or multi-user ownership boundary.
- Current API surface is only `GET /health`; the request does not query the database or call a remote service. The supported launcher initializes local SQLite before starting Uvicorn.
- Web and Extension connections to the JobPilot API and the API bind are loopback-only. Never document or default the JobPilot service to `0.0.0.0`, LAN or public hosts. Future Extension access to recruitment pages is a separate, user-triggered exact-host permission governed below.
- CORS uses exact reviewed loopback Web origins, GET-only and no credentials; never use wildcard or regex. The Extension's direct loopback fetch is authorized by its exact manifest host permission and does not require its ID in API CORS.
- Current database metadata is empty. Preserve the SQLite/SQLAlchemy/Alembic foundation; never delete or replace `runtime-data/jobpilot.db`, and do not create `LocalProfile` without a real requirement.
- Installed core must work in Mainland China without VPN, proxy or special DNS and without remote identity, CDN, fonts/scripts, telemetry, update APIs or mandatory foreign AI.
- Extension bundles all code, never modifies proxies, and currently has no background/content script/recruitment host. Future capture requires exact hosts, user gesture, current rendered DOM and per-Adapter no-proxy acceptance.
- Treat API responses, DOM, pasted text, URLs and files as untrusted at their boundaries.
- Write a failing behavior test before logic, implement the smallest GREEN, and run affected gates after each increment.
- Keep docs synchronized, remove dead abstractions, and stop before Phase 3 until the project owner explicitly approves it.
