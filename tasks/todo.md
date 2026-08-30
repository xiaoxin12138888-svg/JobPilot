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

## Dependency and Database Foundation

- [ ] Lock only approved runtime/development dependencies and document their purposes.
- [ ] Extend `.env.example` with non-secret database/Auth0/session/Web/Extension configuration.
- [ ] Create SQLAlchemy models for User, Identity, WebSession, and LoginTransaction only.
- [ ] Create one Alembic migration with PostgreSQL constraints and indexes.
- [ ] Prove clean upgrade -> downgrade -> upgrade against real PostgreSQL.
- [ ] Prove User persistence, identity uniqueness, email conflict, and duplicate-race protection.

## FastAPI Boundary

- [ ] Define provider-neutral `VerifiedProviderIdentity` and `AuthenticatedUser` types.
- [ ] Keep JWT/OIDC/provider code inside infrastructure/auth.
- [ ] Implement deterministic fixed-issuer/JWKS validation with mature crypto.
- [ ] Implement idempotent Identity -> User mapping in an application service.
- [ ] Implement `POST /api/v1/auth/session` for Extension provisioning.
- [ ] Implement `GET /api/v1/auth/me` without provider/session leakage.
- [ ] Reject missing, malformed, expired, wrong-issuer, wrong-audience, wrong-signature, wrong-token-type, and unverified-email credentials.
- [ ] Keep routers free of JWT parsing, provider calls, and User creation logic.

## Web Authentication

- [ ] Implement bounded browser login transactions and exact relative `returnTo` validation.
- [ ] Implement authorize/callback with state, nonce, PKCE, and safe provider-error mapping.
- [ ] Store only an opaque HttpOnly session cookie in the browser.
- [ ] Implement session restore through `/api/v1/auth/me`.
- [ ] Implement session-bound CSRF plus exact Origin/Fetch Metadata checks.
- [ ] Implement idempotent local logout and exact cookie deletion.
- [ ] Render only signed-out/signed-in User state and logout in React.
- [ ] Prove expiry behavior and that React never stores provider tokens.

## Extension Authentication

- [ ] Add only `identity`, `storage`, and exact API/Auth0 host permissions needed for auth.
- [ ] Build a trusted MV3 service worker; popup sends typed intents only.
- [ ] Implement Authorization Code + PKCE/state/nonce with no client secret.
- [ ] Apply `TRUSTED_CONTEXTS` before secret storage.
- [ ] Keep access token in memory/session storage and versioned rotating refresh state in local storage.
- [ ] Fail closed on `refresh_in_progress`, worker restart, or ambiguous refresh outcome.
- [ ] Call `/auth/session` and `/auth/me` through bearer transport.
- [ ] Clear local credentials on logout and distinguish remote revoke failure.
- [ ] Render only minimal signed-out/signed-in popup state.

## Integration, Authorization, and Security

- [ ] Prove Web session and Extension bearer for the same identity return the same JobPilot User ID.
- [ ] Prove different subjects map to different User IDs.
- [ ] Prove the ownership query fixture uses both resource ID and authenticated User ID.
- [ ] Prove production CORS never permits `*` and only exact configured origins.
- [ ] Prove production cookie flags and development loopback exception.
- [ ] Prove unauthorized responses and provider failures reveal no user/credential/provider internals.
- [ ] Scan tracked files and captured logs for secrets/tokens.
- [ ] Confirm no Phase 3 Job/Application/Resume/AI/RAG implementation entered the diff.

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
