# Phase 2B Authentication Implementation Checklist

## Entry Gate

- [x] Phase 0, Phase 1, and Phase 2A are explicitly approved.
- [x] Phase 2A passed existing tests, lint, format, typecheck, builds, import, documentation, and Git scope checks.
- [x] Phase 2A is committed as `e3c4999`.
- [x] ADR numbering is continuous through Accepted ADR-006.
- [x] Git author and committer identities resolve to the repository-local GitHub noreply identity.

## Decisions

- [x] Select SQLAlchemy 2.x + Alembic + psycopg 3; reject SQLModel and parallel ORMs.
- [x] Select synchronous PostgreSQL access for the existing synchronous FastAPI baseline.
- [x] Select PostgreSQL-backed opaque Web sessions; do not add Redis.
- [x] Select PyJWT crypto validation + existing httpx2 for API OIDC boundaries.
- [x] Select oauth4webapi for trusted Extension OAuth/PKCE logic.
- [x] Separate provider Identity rows from business User rows while preserving `(issuer, subject) -> User.id`.
- [x] Keep advanced distributed/KMS/enterprise controls as future documented design, not Phase 2B over-engineering.
- [x] Freeze Web scopes to `openid profile email`; do not request/store a Web refresh grant and discard provider tokens after callback validation.
- [x] Implement `PATCH /auth/me` and `revoke-all`; explicitly defer the full account-deletion endpoint rather than ship an unsafe ledger-less variant.

## Dependency and Database Foundation

- [x] Lock only approved runtime/development dependencies and document their purposes.
- [x] Extend `.env.example` with non-secret database/Auth0/session/Web/Extension configuration.
- [ ] Create exact User/Identity columns, nullability, constraints, and the first Alembic migration.
- [ ] Add WebSession/LoginTransaction only in the later Web-session migration.
- [ ] Prove clean upgrade -> downgrade -> upgrade against real PostgreSQL.
- [ ] Prove User persistence, identity uniqueness, email conflict, and duplicate-race protection.

## FastAPI Boundary

- [ ] Define provider-neutral `VerifiedProviderIdentity` and `AuthenticatedUser` types.
- [ ] Keep JWT/OIDC/provider code inside infrastructure/auth.
- [ ] Implement deterministic fixed-issuer/JWKS validation with mature crypto.
- [ ] Implement idempotent Identity -> User mapping in an application service.
- [ ] Implement `POST /api/v1/auth/session` for Extension provisioning.
- [ ] Implement `GET /api/v1/auth/me` without provider/session leakage.
- [ ] Implement `PATCH /api/v1/auth/me` for display name, locale, and time zone.
- [ ] Reject missing, malformed, expired, wrong-issuer, wrong-audience, wrong-signature/algorithm/`azp`, future-`nbf`, wrong-token-type, ID-token-as-bearer, query-token, and unverified-email credentials.
- [ ] Bound unknown-`kid` refresh to the fixed issuer/JWKS without advanced distributed caching.
- [ ] Reject cookie+bearer ambiguity, unknown identity on normal endpoints, and deletion-pending reprovision.
- [ ] Keep routers free of JWT parsing, provider calls, and User creation logic.

## Web Authentication

- [ ] Implement bounded browser login transactions and exact relative `returnTo` validation.
- [ ] Implement authorize/callback with state, nonce, PKCE, and safe provider-error mapping.
- [ ] Clean login transaction state on success, cancellation, timeout, mismatch, and provider error.
- [ ] Store only an opaque HttpOnly session cookie in the browser.
- [ ] Implement session restore through `/api/v1/auth/me`.
- [ ] Implement session-bound CSRF plus exact Origin/Fetch Metadata checks.
- [ ] Implement idempotent local logout and exact cookie deletion.
- [ ] Prove session fixation rotation, idle/absolute expiry, missing/expired-session logout Origin gate, and store-outage behavior.
- [ ] Implement recent-authenticated revoke-all with truthful provider failure semantics.
- [ ] Render only signed-out/signed-in User state and logout in React.
- [ ] Prove expiry behavior and that React never stores provider tokens.

## Extension Authentication

- [ ] Add only `identity`, `storage`, and exact API/Auth0 host permissions needed for auth.
- [ ] Build a trusted MV3 service worker; popup sends typed intents only.
- [ ] Implement Authorization Code + PKCE/state/nonce with no client secret.
- [ ] Validate the signed Extension ID token issuer/audience/signature/nonce and discard it immediately.
- [ ] Clean Extension login transaction state on every terminal path.
- [ ] Apply `TRUSTED_CONTEXTS` before secret storage.
- [ ] Keep access token in memory/session storage and versioned rotating refresh state in local storage.
- [ ] Fail closed on `refresh_in_progress`, worker restart, or ambiguous refresh outcome.
- [ ] Refresh expired access tokens on demand with current-worker single-flight and no retry loop after failure.
- [ ] Call `/auth/session` and `/auth/me` through bearer transport.
- [ ] Clear local credentials on logout and distinguish remote revoke failure.
- [ ] Render only minimal signed-out/signed-in popup state.
- [ ] Prove popup `/me` behavior and token-expiry transition.

## Integration, Authorization, and Security

- [ ] Prove Web session and Extension bearer for the same identity return the same JobPilot User ID.
- [ ] Prove different subjects map to different User IDs.
- [ ] Prove a test-only repository/temporary-table fixture uses both resource ID and authenticated User ID; add no production Job-like schema or router.
- [ ] Prove production CORS never permits `*` and only exact configured origins.
- [ ] Prove production cookie flags and development loopback exception.
- [ ] Fail production startup when Web/API are not HTTPS schemeful same-site; test the rejection path.
- [ ] Prove unauthorized responses and provider failures reveal no user/credential/provider internals.
- [ ] Scan tracked files and captured logs for secrets/tokens.
- [ ] Confirm no Phase 3 Job/Application/Resume/AI/RAG implementation entered the diff.
- [ ] Build/test Extension with deterministic `.invalid` configuration, require real production values at runtime/build, and never claim that fake config is live Auth0 verification.

## Review and Acceptance

- [ ] Run `code-review-and-quality` across correctness, readability, architecture, security, performance, and dependency health.
- [ ] Resolve every Critical and Required finding.
- [ ] Run `code-simplification` on changed code and remove only proven unnecessary complexity.
- [ ] Synchronize README, auth/overall architecture, API contract, data model, roadmap, ADR index if needed, and tasks.
- [ ] Run frozen pnpm install and locked uv sync.
- [ ] Run all TypeScript tests, ESLint, Prettier, typecheck, Web build, and Extension build.
- [ ] Run all Pytest, Ruff lint/format, migration, import, and startup checks.
- [ ] Run PostgreSQL clean upgrade -> downgrade -> upgrade.
- [ ] Run `git diff --check`, secret scan, and final `git status`.
- [ ] Report real Auth0 verification truthfully as PASS, BLOCKED, or NOT ATTEMPTED.
- [ ] Stop before Phase 3 and wait for explicit project-owner approval.
