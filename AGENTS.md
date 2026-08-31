# JobPilot Agent Rules

## Current phase

Authentication & Repository Simplification for the accepted local-first, single-user product scope. Work on `phase/2-authentication` from checkpoint tag `pre-local-first-cleanup` (`9a3e79a`). Remove the hosted authentication stack and re-establish a minimal local health baseline. Do not enter Phase 3 or implement Job, Application, Resume, recruitment-site adapters, content scripts, AI, RAG, uploads, analytics or dashboards.

## Canonical context

Read [ADR-008](docs/DECISIONS/ADR-008-local-first-single-user-no-authentication.md), `tasks/plan.md`, `tasks/todo.md`, `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/ENGINEERING_PRINCIPLES.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md` and `docs/ROADMAP.md`. ADR-008 supersedes the active hosted-auth direction and controls whenever still-stale auth text conflicts during this cleanup. Historical Auth0/Logto/OAuth material is recoverable from Git history and `pre-local-first-cleanup`; do not preserve dead working-tree abstractions for hypothetical SaaS use.

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

- Runtime architecture is Web / Extension -> loopback FastAPI -> local PostgreSQL. One installation is one local workspace; there is no authentication User or multi-user ownership boundary. The current `/health`-only baseline does not create a database engine or connect at API startup; retained PostgreSQL/Alembic tooling must reject remote database hosts when used.
- Default API origin is `http://127.0.0.1:8000`. The supported launcher must reject non-loopback bind addresses before starting Uvicorn. Do not use `0.0.0.0` in local-first defaults or documented commands.
- CORS uses exact reviewed origins only, never `*`, wildcard regex or credential allowance. Treat every API response and browser/DOM value as untrusted at its boundary.
- Extension runtime code is fully bundled and may connect only to the exact local API origin plus, in a future separately approved Phase, the current user-opened page on exact recruitment-site hosts. Do not add `identity`, `storage`, proxy, telemetry, remote scripts, service workers, content scripts or recruitment-site permissions during this cleanup.
- Remove Auth0, Logto, OAuth/OIDC/PKCE/JWT/session code, configuration, dependencies, tests, infrastructure and documents. Do not leave commented-out code, compatibility shims, empty wrappers or speculative `LocalProfile`/pairing systems.
- Preserve the Web, Extension, FastAPI, shared packages, PostgreSQL engine, SQLAlchemy/Alembic scaffolding, toolchains and Git history.
- P0 runtime constraint: installed core use must work on ordinary Mainland China networks with VPN/proxy/special DNS disabled and without Auth0, Logto Cloud, Google, Cloudflare, GitHub runtime APIs/raw content, public CDNs, remote fonts/scripts, foreign AI, telemetry or update APIs.
- Development mirrors/package registries are dependency acquisition, not runtime. Build artifacts must contain no remote executable code or mandatory external origin.
- Write a failing behavior test before implementing logic, then make the smallest change that passes.
- Run the affected test/build/lint/typecheck after each increment. Do not defer failures to the end.
