# JobPilot Agent Rules

## Current phase

Phase 2B — Authentication Implementation & User Boundary. Phase 0, Phase 1, and Phase 2A are approved; the Phase 0–1 baseline is commit `c8821a7e2ea966ebfd96f55dcec5d195c451fd57`. Work on `phase/2-authentication` and implement only the minimal Web/Extension/FastAPI/PostgreSQL authentication closure. Do not enter Phase 3 or implement Job, Application, Resume, recruitment-site parsing, AI, RAG, uploads, analytics, or product dashboards.

## Canonical context

Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ENGINEERING_PRINCIPLES.md`, `docs/AUTH_ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, `docs/ROADMAP.md`, and relevant ADRs before changing public behavior or boundaries. ADR-006 is Accepted and governs Phase 2B.

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
- Phase 2B may add only the Extension `identity`/`storage` permissions, service worker, and exact JobPilot/Auth0 host permissions required by the accepted auth flow. It must not add recruitment-site capture permissions or behavior.
- FastAPI may connect PostgreSQL and add the minimum auth routes, migrations, User/Identity/session persistence, and authentication adapters. Domain/Application code must not import Auth0-specific SDKs; routers remain thin.
- Phase 2B may add the reviewed ORM, migration, JWT/OIDC, and HTTP dependencies. Do not create or guess a real Auth0 tenant/application, IDs, origins, redirects, Management API scopes, or secrets; deterministic tests use a fake issuer/JWKS.
- Accepted auth invariants: Auth0 managed OIDC; Web opaque HttpOnly session; Extension Authorization Code + PKCE; `(issuer, subject) -> User.id`; every private resource query uses both resource ID and authenticated local user ID.
- Treat API responses and browser data as untrusted at their boundaries.
- Write a failing behavior test before implementing logic, then make the smallest change that passes.
- Run the affected test/build/lint/typecheck after each increment. Do not defer failures to the end.
