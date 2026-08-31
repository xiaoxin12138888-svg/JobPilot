# Implementation Plan: Local-first Single-user Cleanup

## Objective

Rescope JobPilot to a local-first, single-user, self-hosted desktop companion. One installation is one local workspace. Remove the hosted authentication stack and its dead code, tests, dependencies, infrastructure and documentation while preserving the Web, Chrome Extension, FastAPI, PostgreSQL/Alembic, shared packages and engineering toolchains.

The cleanup starts from clean branch `phase/2-authentication` at `9a3e79a7e134142d800bf94a78ecafcad0cf9302`. Annotated tag `pre-local-first-cleanup` is the recovery checkpoint. Do not rewrite history, force push, start Phase 3, or implement Job, Application, Resume, recruitment-site adapters, content scripts, AI or RAG.

## Accepted Runtime Contract

- JobPilot has no account, login, identity provider, OAuth/OIDC/PKCE, JWT, session, refresh token, recovery or multi-user authorization.
- Web and Extension communicate only with the local JobPilot API. The default API origin is `http://127.0.0.1:8000`.
- The supported API launcher binds only an IP-literal loopback address and rejects `0.0.0.0`, `::`, LAN addresses and hostnames before Uvicorn starts.
- Current public API surface is only `GET /health`. CORS uses exact configured origins, never wildcard or regex, and sends no credential allowance.
- Extension code is fully bundled. The Popup performs only a credential-free local `/health` check. No service worker, `identity`, `storage`, proxy, telemetry, remote script or provider host is needed.
- GitHub, package registries and mirrors are development/download channels only. Installed runtime must not depend on GitHub, CDNs, remote fonts/scripts, foreign telemetry, remote IdP or foreign AI APIs.
- PostgreSQL/Alembic infrastructure remains, but current auth-only tables and revisions are removed. A future `LocalProfile` requires a separate product need; no placeholder User model remains.
- Future recruitment-site access stays in the user's browser. A future content script must be user-triggered, current-page-only and limited to separately approved exact host permissions.

## Incremental Slices

### Slice 0 — Decision, checkpoint and executable cleanup plan

**Status:** Complete.

**Acceptance:** ADR-008 records the local-first decision; the checkpoint tag resolves to the clean pre-cleanup HEAD; AGENTS and task files constrain all subsequent work.

**Verification:** `git show pre-local-first-cleanup`; Markdown format/link checks; `git diff --check`.

### Slice 1 — Remove API authentication and enforce loopback runtime

**Status:** Complete.

**Acceptance:** delete provider/auth/User/Identity/session/transaction code, routes, revisions and tests; OpenAPI contains only `/health`; retain generic request IDs/errors/query redaction, PostgreSQL engine, empty SQLAlchemy metadata and Alembic scaffolding. `/health` startup creates no database connection. Add a tested launcher that rejects non-loopback bind hosts before calling Uvicorn, and restrict supported PostgreSQL URLs to loopback hosts. CORS is exact, GET-only and credential-free. Pre-release development/test databases containing removed auth revisions must be recreated; no in-place compatibility is claimed.

**TDD:** first change tests to require `/health`-only OpenAPI, loopback launcher rejection and exact credential-free CORS; confirm targeted RED; then make the smallest API/config/main changes and delete obsolete tests/files.

**Dependencies:** Slice 0.

### Slice 2 — Reduce shared contracts and Web to local health

**Status:** Complete.

**Acceptance:** add a loopback-only health client and migrate Web to it; Web has no login/logout/account/auth-error state and directly renders local API `checking / ready / unavailable` with retry as an unavailable-state action. Temporarily retain only the auth exports still consumed by the not-yet-migrated Extension so this increment remains buildable. Web dev server binds loopback and build needs no provider config.

**TDD:** replace auth tests with health pending/success/failure/retry/stale-result and loopback URL tests; confirm RED before implementation.

**Dependencies:** Slice 1 contract.

### Slice 3 — Replace Extension OAuth lifecycle with local health Popup

**Status:** Complete.

**Acceptance:** delete OAuth/PKCE/token/storage/background/message code and tests; remove `oauth4webapi`; Popup directly uses the bundled local health client. In the same atomic increment, delete the now-last auth exports (`UserView`, CSRF, Web session/login/logout and Extension bearer contracts/tests) from shared-types/api-client. Manifest has no permissions, background, content script, remote host, telemetry or proxy capability; its only host permission and `connect-src` are the exact loopback API origin.

**TDD:** first rewrite manifest/config/Popup tests for local-only behavior and confirm RED; then implement `checking / available / unavailable` with retry as an unavailable-state action and rebuild. Inspect unpacked artifacts for no provider/auth/remote executable code.

**Dependencies:** Slice 2 health client.

### Slice 4 — Remove obsolete provider infrastructure and rebaseline documentation

**Status:** Complete.

**Acceptance:** delete `infra/logto`, Logto summary, AUTH_ARCHITECTURE and hosted-auth ADRs; rewrite README, product/architecture/API/data/roadmap/principles around local-first single-user operation and P0 no-proxy runtime. `.env.example` and `.gitignore` contain only current local settings and rebuildable/runtime exclusions.

**Dependencies:** Slices 1–3.

### Slice 5 — Repository cleanup, clean install and complete validation

**Status:** Complete.

**Acceptance:** remove generated caches/builds/logs and any tracked generated artifact; regenerate pnpm/uv locks after dependency removal; perform frozen/locked installs and the complete new test/build/lint/typecheck/import/startup/health/security suite. Run real browser verification when Chrome DevTools MCP is available.

**Dependencies:** Slices 1–4.

### Slice 6 — Mandatory review and simplification

**Status:** Complete — Critical 0 / Required 0.

**Acceptance:** `code-review-and-quality` reports Critical 0 / Required 0 across correctness, readability, architecture, security, performance and dependencies. `code-simplification` removes orphan interfaces, empty wrappers, dead DTOs/helpers/comments/TODOs and duplicate local-mode checks without adding speculative abstractions.

**Dependencies:** Slice 5.

## Commit Strategy

Use a small number of meaningful, buildable commits:

1. `docs: adopt local-first single-user architecture`
2. `refactor(auth): remove hosted authentication stack`
3. `refactor(extension): replace oauth with local health check`
4. `chore: remove dead auth dependencies and generated caches`

Adjust boundaries only when needed to keep each commit coherent and verified. Do not collapse everything into one unexplained commit or mechanically create dozens of commits.

## Final Gate

- Auth0 runtime dependency: 0
- Logto runtime dependency: 0
- OAuth/OIDC/PKCE/JWT/session runtime code: 0
- Remote executable script/CDN/font/telemetry/update dependency: 0
- Extension proxy manipulation: 0
- API default bind: loopback; supported non-loopback config fails before start
- Extension and Web builds: PASS without provider configuration
- OpenAPI: only `/health`
- Full automated and browser/runtime checks: PASS or truthfully BLOCKED with evidence
- Working tree: clean
- Phase 3: not started; requires separate project-owner approval
