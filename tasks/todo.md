# Local-first Single-user Cleanup Checklist

## Safety and decision

- [x] Confirm clean `phase/2-authentication` at `9a3e79a7e134142d800bf94a78ecafcad0cf9302`.
- [x] Create annotated checkpoint tag `pre-local-first-cleanup` without rewriting history.
- [x] Add ADR-008 and synchronize the active agent/task boundaries.
- [ ] Keep Phase 3 and all Job/Application/Resume/Adapter/content-script/AI/RAG work out of scope.

## API and persistence cleanup

- [x] Write RED tests for `/health`-only OpenAPI, loopback-only launcher and exact credential-free CORS.
- [x] Delete Auth0/OIDC/JWT/JWKS/Web auth/session/identity API, application, domain and infrastructure code.
- [x] Delete User/Identity/WebSession/LoginTransaction models, repositories and auth-only Alembic revisions.
- [x] Delete auth-only API tests; keep generic health/error/log/CORS/database/migration infrastructure coverage.
- [x] Reduce `ApiSettings` to current local settings and reject every non-loopback bind host.
- [x] Keep `/health` startup database-free and reject non-loopback PostgreSQL URLs in retained engine/migration tooling.
- [x] Add the supported loopback Uvicorn launcher and route `pnpm api:dev` through it.
- [x] Remove PyJWT/crypto/auth-only dependencies; keep `httpx2` only as a test dependency if required by TestClient.

## Shared client and Web cleanup

- [x] Write RED health/client/Web tests for loopback-only pending/ready/unavailable/retry behavior.
- [x] Add credential-free loopback `GET /health` with untrusted-response validation while temporarily retaining Extension-consumed auth exports.
- [x] Delete `use-auth-session.ts` and every login/logout/account/auth-error UI path.
- [x] Make Web start directly in the local workspace shell and bind its dev server to loopback.
- [x] Prove Web builds without provider configuration and contains no remote runtime dependency.

## Extension cleanup

- [x] Write RED manifest/config/Popup tests for exact `127.0.0.1` health-only behavior.
- [x] Delete the entire Extension auth directory, OAuth background worker/messages and credential lifecycle tests.
- [x] Remove `chrome.identity`, `storage`, background, provider hosts and `oauth4webapi`.
- [x] Atomically delete the last UserView/CSRF/session/login/logout/Extension bearer exports and tests after Extension no longer consumes them.
- [x] Implement a bundled Popup with checking/available/unavailable/retry states using only local `/health`.
- [x] Freeze manifest to exact loopback host/CSP with no content script, proxy, telemetry or remote executable code.
- [x] Prove build output has no provider/auth/token/CDN/remote-script/background artifacts.

## Documentation and repository cleanup

- [ ] Delete Logto verification infrastructure/evidence/summary and `docs/AUTH_ARCHITECTURE.md`.
- [ ] Remove hosted-auth ADR-006/ADR-007 from the working tree; history remains at `pre-local-first-cleanup`.
- [ ] Rewrite README, architecture, API contract, data model, product spec, roadmap and engineering principles for local-first single-user use.
- [ ] Record the P0 no-proxy runtime and per-adapter future acceptance gate.
- [ ] Remove all provider/auth environment variables and test fixtures.
- [ ] Expand `.gitignore` for current caches, logs, local secrets and a scoped local runtime-data directory.
- [ ] Audit tracked files for generated builds, caches, logs, screenshots and obsolete evidence.
- [ ] Document that pre-release databases containing removed auth revisions must be recreated; no in-place migration is supported.

## Rebuild and validation

- [ ] Remove local `node_modules`, builds, coverage, caches, bytecode, temporary logs/browser artifacts and rebuildable `.venv` after implementation tests.
- [ ] Run `pnpm install --frozen-lockfile` and `uv sync --project apps/api --locked` from the cleaned state.
- [ ] Run all TypeScript tests, ESLint, Prettier, strict typecheck, Web build and Extension build.
- [ ] Run all Pytest, Ruff lint/format, API import/startup and `/health` checks.
- [ ] Run lock/dependency, secret, remote-runtime, proxy, manifest/CSP, loopback/CORS, tracked-artifact and `git diff --check` scans.
- [ ] Use Chrome DevTools MCP for Web and Extension runtime verification, or report the tool as BLOCKED without substituting a fake PASS.

## Mandatory review

- [ ] Run `code-review-and-quality`; resolve every Critical and Required finding.
- [ ] Run `code-simplification`; remove every confirmed dead wrapper/interface/DTO/helper/comment/TODO.
- [ ] Re-run affected gates after every review fix or simplification.
- [ ] Commit coherent increments and finish with a clean worktree.
- [ ] Stop before Phase 3 and wait for explicit project-owner approval.
