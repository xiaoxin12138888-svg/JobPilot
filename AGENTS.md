# JobPilot Agent Rules

## Current phase

Phase 2B — Authentication Implementation & User Boundary. Phase 0, Phase 1, and Phase 2A are approved; the Phase 0–1 baseline is commit `c8821a7e2ea966ebfd96f55dcec5d195c451fd57`. Task 8 real-provider configuration and integration are paused at the ADR-007 Architecture Change Gate. Work on `phase/2-authentication`; do not enter Phase 3 or implement Job, Application, Resume, recruitment-site parsing, AI, RAG, uploads, analytics, or product dashboards.

## Canonical context

Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ENGINEERING_PRINCIPLES.md`, `docs/AUTH_ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `docs/ROADMAP.md`, and relevant ADRs before changing public behavior or boundaries. ADR-006 remains the Accepted record for the implemented provider-neutral boundaries. ADR-007 is Proposed; while it awaits approval, its active Gate pauses real Auth0/Logto configuration, provider migration, Task 8, and Phase 3.

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
- The current Phase 2B Extension has only `identity`/`storage`, a service worker, and exact JobPilot/fake-provider host permissions. Do not add Auth0, Logto, recruitment-site, tab, or content-script permissions during the ADR-007 Gate.
- FastAPI may retain the current PostgreSQL auth routes, migrations, User/Identity/session persistence, and Auth0 adapter. Domain/Application code must remain provider-neutral; routers remain thin. Do not modify authentication business code or delete the Auth0 adapter during this Gate.
- Do not create or guess real Auth0 or Logto tenants/applications, IDs, origins, redirects, Management API scopes, connectors, or secrets. Deterministic tests continue to use a fake issuer/JWKS until a separately approved provider-verification slice.
- Active auth invariants: Web opaque HttpOnly session; Extension Authorization Code + PKCE; `(issuer, subject) -> User.id`; `/auth/session` and `/auth/me` remain provider-neutral; every private resource query uses both resource ID and authenticated local user ID.
- Production hard constraint: **Core JobPilot workflow must operate without VPN/proxy in Mainland China.** No provider can be approved without ordinary-network Web, Extension, recovery, and dependency verification.
- Treat API responses and browser data as untrusted at their boundaries.
- Write a failing behavior test before implementing logic, then make the smallest change that passes.
- Run the affected test/build/lint/typecheck after each increment. Do not defer failures to the end.
