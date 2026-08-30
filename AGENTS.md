# JobPilot Agent Rules

## Current phase

Phase 1 — Engineering Skeleton. Phase 0 is approved. Do not implement authentication, persistence, business entities, recruitment-site parsing, AI, RAG, uploads, analytics, or product dashboards.

## Canonical context

Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ENGINEERING_PRINCIPLES.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `docs/ROADMAP.md`, and relevant ADRs before changing public behavior or boundaries.

## Toolchains

- TypeScript: pnpm only. Do not create npm or Yarn lock files.
- Python: uv only. Do not add Poetry, Pipenv, or repository-level pip workflows.
- Python formatting and linting: Ruff only. Do not add Black or isort.
- TypeScript tests: Vitest. Python tests: Pytest.

## Commands

- Install TypeScript dependencies: `pnpm install --frozen-lockfile`
- Start Web: `pnpm dev:web`
- Build Web: `pnpm build:web`
- Build/watch Extension: `pnpm dev:extension`
- Build Extension: `pnpm build:extension`
- Start API: `pnpm api:dev`
- API import check: `pnpm api:import:check`
- TypeScript tests: `pnpm test`
- API tests: `pnpm api:test`
- TypeScript lint/typecheck: `pnpm lint`, `pnpm typecheck`
- Python lint/format checks: `pnpm api:lint`, `pnpm api:format:check`

## Boundaries

- React components and Extension popup code never contain an API URL literal. Compose the shared API client from validated environment configuration.
- The Extension uses `activeTab` only after the user opens the popup. Add no recruitment-site host permission, content script, or service worker in Phase 1.
- FastAPI exposes only `GET /health` in Phase 1. It does not connect to PostgreSQL or create router/service/repository layers for future use.
- Treat API responses and browser data as untrusted at their boundaries.
- Write a failing behavior test before implementing logic, then make the smallest change that passes.
- Run the affected test/build/lint/typecheck after each increment. Do not defer failures to the end.
