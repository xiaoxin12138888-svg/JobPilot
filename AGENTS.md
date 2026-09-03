# JobPilot Agent Rules

## Current phase

Phase 4 BOSS Direct Job Capture is active on `phase/4-boss-job-capture` after explicit project-owner approval. The original branches, Phase 3 commits and recovery checkpoint `pre-local-first-cleanup` remain untouched. Implement only one BOSS 直聘 Adapter, explicit current-tab capture, editable Popup preview, save through the existing Job API/service, and the minimum source/Web support. Do not implement another recruitment platform, persistent content scripts, background capture, AI, RAG, uploads, recommendations, automatic submission, cloud sync, analytics or dashboards.

## Canonical context

Read ADR-008, ADR-009, ADR-010, ADR-011, `tasks/plan.md`, `tasks/todo.md`, README, PRODUCT_SPEC, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ROADMAP and ENGINEERING_PRINCIPLES. Historical remote-identity experiments exist only at `pre-local-first-cleanup` and are not current design input.

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
- The API exposes `GET /health` plus the Phase 3 `/api/v1/jobs` and `/api/v1/applications` contracts. Phase 4 reuses `POST /api/v1/jobs` for BOSS capture and may add only bounded duplicate metadata. The supported launcher upgrades local SQLite before starting Uvicorn.
- Web and Extension connections to the JobPilot API and the API bind are loopback-only. Never document or default the JobPilot service to `0.0.0.0`, LAN or public hosts. Future Extension access to recruitment pages is a separate, user-triggered exact-host permission governed below.
- CORS uses exact reviewed loopback Web origins and no credentials; never use wildcard or regex. Writes additionally enforce loopback Host, safe browser origin/fetch metadata and JSON content. The Extension remains health-only and does not require its ID in API CORS.
- Preserve SQLite/SQLAlchemy/Alembic and the `jobs`/`applications` schema; never delete or replace `runtime-data/jobpilot.db`, and do not create other business tables.
- Installed core must work in Mainland China without VPN, proxy or special DNS and without remote identity, CDN, fonts/scripts, telemetry, update APIs or mandatory foreign AI.
- Extension bundles all code, never modifies proxies, and uses only `activeTab`, `scripting` and the exact loopback host. BOSS capture requires a user gesture, current rendered DOM and real no-proxy acceptance; it has no background/content script or BOSS host permission.
- Treat API responses, DOM, pasted text, URLs and files as untrusted at their boundaries.
- Write a failing behavior test before logic, implement the smallest GREEN, and run affected gates after each increment.
- Keep docs synchronized, remove dead abstractions, and stop after Phase 4 until the project owner explicitly approves Phase 5.
