# Phase 2B Authentication Implementation Checklist

## Entry Gate

- [x] Phase 0, Phase 1, and Phase 2A are explicitly approved.
- [x] Phase 2A passed existing tests, lint, format, typecheck, builds, import, documentation, and Git scope checks.
- [x] Phase 2A is committed as `e3c4999`.
- [x] ADR numbering is continuous through Accepted ADR-006.
- [x] Git author and committer identities resolve to the repository-local GitHub noreply identity.
- [x] Task 6 is approved at `ff8593c`; Task 7 is explicitly authorized from a clean `phase/2-authentication` worktree.

## Decisions

- [x] Select SQLAlchemy 2.x + Alembic + psycopg 3; reject SQLModel and parallel ORMs.
- [x] Select synchronous PostgreSQL access for the existing synchronous FastAPI baseline.
- [x] Select PostgreSQL-backed opaque Web sessions; do not add Redis.
- [x] Select PyJWT crypto validation + existing httpx2 for API OIDC boundaries.
- [x] Select oauth4webapi for trusted Extension OAuth/PKCE logic.
- [x] Separate provider Identity rows from business User rows while preserving `(issuer, subject) -> User.id`.
- [x] Keep advanced distributed/KMS/enterprise controls as future documented design, not Phase 2B over-engineering.
- [x] Freeze Web scopes to `openid profile email`; do not request/store a Web refresh grant and discard provider tokens after callback validation.
- [x] Implement `PATCH /auth/me`; explicitly defer recent reauthentication, `revoke-all`, and the full account-deletion endpoint rather than ship unsafe partial variants.

## Dependency and Database Foundation

- [x] Lock only approved runtime/development dependencies and document their purposes.
- [x] Extend `.env.example` with non-secret database/Auth0/session/Web/Extension configuration.
- [x] Create exact User/Identity columns, nullability, constraints, and the first Alembic migration.
- [x] Freeze the minimal hash-only WebSession/LoginTransaction model before migration.
- [x] Add WebSession/LoginTransaction in a new migration without rewriting migration `0001`.
- [x] Prove clean upgrade -> downgrade -> upgrade against real PostgreSQL.
- [x] Prove User persistence, identity uniqueness, email conflict, and duplicate-race protection.

## FastAPI Boundary

- [x] Define the provider-neutral `VerifiedProviderIdentity` type.
- [x] Define the provider-neutral `AuthenticatedUser` type.
- [x] Keep JWT/OIDC/provider code inside infrastructure/auth.
- [x] Implement deterministic fixed-issuer/JWKS validation with mature crypto.
- [x] Implement idempotent Identity -> User mapping in an application service.
- [x] Implement `POST /api/v1/auth/session` for Extension provisioning.
- [x] Implement `GET /api/v1/auth/me` without provider/session leakage.
- [x] Implement `PATCH /api/v1/auth/me` for display name, locale, and time zone.
- [x] Reject missing, malformed, expired, wrong-issuer, wrong-audience, wrong-signature/algorithm/`azp`, future-`nbf`, wrong-token-type, ID-token-as-bearer, query-token, and unverified-email credentials.
- [x] Bound unknown-`kid` refresh to the fixed issuer/JWKS without advanced distributed caching.
- [x] Before exposing bearer routes, construct one process-scoped validator and HTTP client in the application lifespan and prove requests reuse the JWKS cache.
- [x] Reject cookie+bearer ambiguity, unknown identity on normal endpoints, and deletion-pending reprovision.
- [x] Keep routers free of JWT parsing, provider calls, and User creation logic.

## Web Authentication

- [x] Implement bounded `login|signup` browser transactions and exact relative `returnTo` validation.
- [x] Implement authorize/callback with state, nonce, PKCE, and safe provider-error mapping.
- [x] Clean login transaction state on success, cancellation, timeout, mismatch, and provider error.
- [x] Store only an opaque HttpOnly session cookie in the browser.
- [x] Implement session restore through `/api/v1/auth/me`.
- [x] Implement session-bound CSRF plus exact Origin/Fetch Metadata checks.
- [x] Implement idempotent local logout and exact cookie deletion.
- [x] Prove session fixation rotation, idle/absolute expiry, missing/expired-session logout Origin gate, and store-outage behavior.
- [x] Keep recent reauthentication/revoke-all absent from OpenAPI until its later contract and provider capability gate are approved.
- [x] Render only signed-out/signed-in User state and logout in React.
- [x] Prove expiry behavior and that React never stores provider tokens.

## Task 6 Review and Acceptance

- [x] Run independent correctness, readability, architecture, security, performance, and dependency review.
- [x] Resolve every Task 6 Critical and Required finding; final result is Critical 0 / Required 0.
- [x] Run `code-simplification`; remove the unused shared response type and completed TDD reflection scaffolding.
- [x] Pass 452 Pytest and 41 TypeScript tests, with no skipped Task 6 database coverage.
- [x] Pass Ruff, ESLint, Prettier, typecheck, Web build, Extension regression build, API import/startup, and exact OpenAPI surface checks.
- [x] Pass PostgreSQL upgrade -> downgrade -> upgrade, frozen pnpm install, locked uv sync, dependency audit, secret/token/storage/layer/scope/bundle scans, and Git diff checks.
- [x] Keep real Auth0 Web verification marked `BLOCKED / USER ACTION REQUIRED` until the project owner supplies exact tenant/application values.
- [x] Stop after Task 6; do not start Task 7 or Phase 3 without explicit project-owner approval.

## Extension Authentication

- [ ] Validate every public Extension auth/API/Web endpoint, audience, and client-ID input; no client-secret input exists.
- [ ] Add only `identity`, `storage`, exact API/Auth0 host permissions, a module service worker, and strict MV3 CSP needed for auth.
- [ ] Generate a secure RFC 7636 verifier, S256 challenge, unpredictable state/nonce, and runtime redirect from `chrome.identity.getRedirectURL()`.
- [ ] Persist one bounded, versioned login attempt in trusted session state and reject missing, mismatched, stale, reused, or malformed callbacks.
- [ ] Keep `chrome.identity.launchWebAuthFlow` behind a user-initiated worker boundary and map cancellation/provider failure without leaking callback data.
- [ ] Exchange the code as a public client through `oauth4webapi` with no client secret.
- [ ] Validate token-response shape and signed Extension ID token issuer/audience/RS256 signature/times/nonce, then discard the ID token.
- [ ] Require a bounded short-lived bearer access token and rotating refresh-token replacement.
- [ ] Await `TRUSTED_CONTEXTS` for local and session storage before every secret read/write or token exchange.
- [ ] Keep access token in worker memory/session storage and versioned rotating refresh state in local storage.
- [ ] Persist each new refresh record before access state; `refresh_in_progress` contains no old refresh token.
- [ ] Restore a valid `ready` record after normal worker restart; fail closed only on corrupt, in-progress, unacknowledged, or ambiguous state.
- [ ] Cover termination before refresh request, during unknown network outcome, after response, before ready-write acknowledgement, and before access-write acknowledgement; never replay the old token.
- [ ] Refresh locally expired/near-expiry access at most once with current-worker single-flight; an arbitrary API 401 clears state instead of triggering a speculative refresh loop.
- [ ] On first login call `/auth/session` then `/auth/me`; on normal restore call `/auth/me` directly through the shared bearer boundary with `credentials: omit`.
- [ ] Clear local credentials on logout and distinguish confirmed from unconfirmed remote revoke.
- [ ] Validate typed popup/worker intents and reject untrusted or malformed messages.
- [ ] Render minimal signed-out, authenticating, signed-in, error, and logout-result popup states; no OAuth/token/storage logic enters the popup.
- [ ] Prove popup `/me`, token-expiry, logout, open-Web, and accessible-control behavior.
- [ ] Remove the obsolete current-tab diagnostic and `activeTab` permission because Task 7 does not read page/tab content.
- [ ] Re-run the existing Web/Extension same-identity integration test and confirm identical local `User.id`.
- [ ] Inspect the built manifest/CSP/bundle and attempt isolated load-unpacked verification where the environment permits it.

## Task 7 Review and Acceptance

- [ ] Run `code-review-and-quality` across correctness, readability, architecture, security, performance, and dependency health.
- [ ] Resolve every Task 7 Critical and Required finding.
- [ ] Run `code-simplification` on Task 7 changes without altering behavior.
- [ ] Synchronize README, auth/overall architecture, API contract, roadmap, `.env.example`, and tasks with the Extension implementation.
- [ ] Run frozen pnpm install, locked uv sync, all tests, lint, format, typecheck, both builds, API import/startup, and dependency audit.
- [ ] Run secret/token/storage/manifest/CSP/layer/scope scans, `git diff --check`, and final `git status`.
- [ ] Report Chrome load-unpacked and real Auth0 verification truthfully as PASS, BLOCKED, or NOT VERIFIED.
- [ ] Stop before Task 8 and Phase 3; wait for explicit project-owner approval.

## Integration, Authorization, and Security

- [x] Prove Web session and Extension bearer for the same identity return the same JobPilot User ID.
- [x] Prove different subjects map to different User IDs.
- [ ] Prove a test-only repository/temporary-table fixture uses both resource ID and authenticated User ID; add no production Job-like schema or router.
- [x] Prove production CORS never permits `*` and only exact configured origins.
- [x] Prove production cookie flags and development loopback exception.
- [x] Fail production startup when Web/API are not HTTPS schemeful same-site; test the rejection path.
- [x] Prove unauthorized responses and provider failures reveal no user/credential/provider internals.
- [x] Scan tracked files and captured logs for secrets/tokens.
- [x] Confirm no Phase 3 Job/Application/Resume/AI/RAG implementation entered the diff.
- [ ] Build/test Extension with deterministic `.invalid` configuration, require real production values at runtime/build, and never claim that fake config is live Auth0 verification.
- [ ] Configure the production Web host to rewrite `/auth/error` to the SPA entry and set reviewed CSP/security response headers; this deployment-specific gate is not a permissive meta tag.

## Phase 2B Final Review and Acceptance

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
