# JobPilot Agent Rules

## Current phase

Phase 5 Nowcoder Adapter & Shared Capture Contract is complete on `phase/5-nowcoder-adapter`; BOSS and Nowcoder are both `SUPPORTED — V1`. The original branches, Phase 3/4 commits and recovery checkpoint `pre-local-first-cleanup` remain untouched. Stop before Phase 6 until explicit project-owner approval. Do not implement another recruitment platform, persistent content scripts, background capture, AI, RAG, uploads, recommendations, automatic submission, cloud sync, analytics or dashboards.

## Canonical context

Read ADR-008, ADR-009, ADR-010, ADR-011, ADR-012, `tasks/plan.md`, `tasks/todo.md`, README, PRODUCT_SPEC, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ROADMAP, ENGINEERING_PRINCIPLES and `docs/technical/JOB_CAPTURE_ADAPTER.md`. Historical remote-identity experiments exist only at `pre-local-first-cleanup` and are not current design input.

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
- The API exposes `GET /health` plus the Phase 3 `/api/v1/jobs` and `/api/v1/applications` contracts. BOSS and Nowcoder capture both reuse `POST /api/v1/jobs` and the same bounded duplicate metadata. The supported launcher upgrades local SQLite before starting Uvicorn.
- Web and Extension connections to the JobPilot API and the API bind are loopback-only. Never document or default the JobPilot service to `0.0.0.0`, LAN or public hosts. Future Extension access to recruitment pages is a separate, user-triggered exact-host permission governed below.
- CORS uses exact reviewed loopback Web origins and no credentials; never use wildcard or regex. Writes additionally enforce loopback Host, safe browser origin/fetch metadata and JSON content. The Extension Origin is not in API CORS; its mutations require the exact stable JobPilot Extension Origin derived from the manifest public key plus `Sec-Fetch-Site: none`, never an arbitrary valid Extension ID.
- Preserve SQLite/SQLAlchemy/Alembic and the `jobs`/`applications` schema; never delete or replace `runtime-data/jobpilot.db`, and do not create other business tables.
- Installed core must work in Mainland China without VPN, proxy or special DNS and without remote identity, CDN, fonts/scripts, telemetry, update APIs or mandatory foreign AI.
- Extension bundles all code, never modifies proxies, and uses only `activeTab`, `scripting` and the exact loopback host. BOSS and Nowcoder capture require a user gesture, current rendered DOM and separate real no-proxy acceptance; there is no background/content script or recruitment-site host permission.
- Treat API responses, DOM, pasted text, URLs and files as untrusted at their boundaries.
- Write a failing behavior test before logic, implement the smallest GREEN, and run affected gates after each increment.
- Keep docs synchronized, remove dead abstractions, and stop after Phase 5 until the project owner explicitly approves Phase 6.
