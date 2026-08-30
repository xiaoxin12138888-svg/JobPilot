# Implementation Plan: Phase 2B Authentication & User Boundary

## Objective

Implement the approved minimum authentication closure across React Web, Chrome Manifest V3 Extension, FastAPI, and PostgreSQL. Both credential transports must resolve the same verified `(issuer, subject)` to one local JobPilot `User.id`. This plan stops before Phase 3 and does not implement Job, Application, Resume, AI, RAG, account-management consoles, or enterprise IAM.

Phase 2A is preserved in commit `e3c4999` (`docs(auth): define phase 2 authentication architecture`). Real Auth0 tenant/application configuration remains a user-action gate; deterministic tests use a local fake issuer/JWKS and never guess real identifiers or secrets.

## Approved Contract Slice

- Web: `GET /api/v1/auth/web/authorize` -> hosted OIDC code flow -> callback -> opaque server-side session cookie.
- Web state: `GET /api/v1/auth/me`, `GET /api/v1/auth/csrf`, and `POST /api/v1/auth/logout`.
- Extension: Authorization Code + PKCE through `chrome.identity.launchWebAuthFlow`, then `POST /api/v1/auth/session` and `GET /api/v1/auth/me` with an API access bearer.
- Public user response: the approved `UserView`; no provider subject, raw claims, access token, refresh token, session identifier, or database field leakage.
- Normal application code receives `AuthenticatedUser`, never an Auth0 payload.
- Phase 2B does not add a duplicate `/api/v1/me`; the approved endpoint is `/api/v1/auth/me`.

## Dependency Decision Gate

### ORM and migration comparison

| Criterion                  | SQLAlchemy 2.x + Alembic                                           | SQLModel + Alembic                                                    |
| -------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------------- |
| FastAPI compatibility      | Mature and framework-neutral                                       | Mature FastAPI integration                                            |
| Persistence/API separation | Explicit declarative models remain inside infrastructure           | Encourages sharing persistence and Pydantic models                    |
| Migration control          | Alembic's native model and metadata layer                          | Still relies on SQLAlchemy/Alembic underneath                         |
| Type clarity               | Typed `Mapped[]` models and explicit DTO mapping                   | Concise, but persistence/API concerns are easier to couple            |
| Future Job/Application fit | Direct support for constraints, indexes, transactions, and locking | Capable, with an extra abstraction that does not solve a current need |

**Decision:** use synchronous SQLAlchemy 2.x + Alembic + psycopg 3. The existing FastAPI skeleton is synchronous, PostgreSQL is the required source of truth, and explicit ORM/DTO separation is already an approved project boundary. Do not install SQLModel or another ORM.

### Authentication and HTTP dependencies

- `PyJWT[crypto]`: validated JWT/JWK parsing and signature verification; the standard library does not implement JWT or asymmetric verification safely.
- `httpx2`: move the already locked test dependency into runtime for fixed OIDC/JWKS/token/revoke HTTP calls; do not add a second Python HTTP client.
- `oauth4webapi`: Extension-side standards implementation for OAuth authorization responses, token exchange, refresh, ID-token checks, and PKCE primitives; do not add an Auth0 UI SDK or a second JWT library.
- `Alembic`: deterministic upgrade/downgrade history for PostgreSQL.
- `psycopg[binary]`: maintained PostgreSQL DBAPI driver; SQLite is not an acceptance substitute.

No Redis, Celery, Kafka, Auth0 React SDK, Axios, SQLModel, asyncpg, custom cryptography, or generic auth framework is added.

## Persistence and Session Decision

- `users`: local business identity (`id`, normalized verified `email`, optional `display_name`, account state, timestamps).
- `identities`: provider boundary (`id`, `user_id`, `issuer`, case-sensitive `subject`, timestamps) with unique `(issuer, subject)` and a foreign key to `users`.
- `web_sessions`: hash of an opaque cookie value, local user/identity references, hash of the synchronizer CSRF token, idle/absolute expiry, last-use and revocation timestamps.
- `login_transactions`: short-lived browser-bound Web OIDC transaction state, including hashed browser handle/state, nonce, PKCE verifier, intent, allowlisted relative return path, and expiry.

Provider identity is intentionally separated from the business User as required by the Phase 2B owner instruction. This refines the Phase 2A conceptual diagram without changing the invariant `(issuer, subject) -> User.id`; documentation is synchronized after implementation.

PostgreSQL stores the Web session because it is already the approved durable source of truth and avoids introducing Redis for an early single-service product. The browser receives only the opaque cookie value. Token/session material is never logged.

## Source Boundaries

```text
HTTP cookie or bearer
  -> transport dependency
  -> infrastructure/auth provider validation
  -> VerifiedProviderIdentity
  -> identity application service
  -> users + identities repository
  -> AuthenticatedUser
  -> router response/application service
```

- Auth0/OIDC-specific code lives under `jobpilot_api/infrastructure/auth`.
- SQLAlchemy and psycopg details live under `jobpilot_api/infrastructure/database`.
- Application/domain modules do not import Auth0 libraries, FastAPI, or SQLAlchemy models.
- Routers accept validated dependencies and call services; they do not parse JWTs, create users, or exchange codes.
- React components call an injected API/session client and contain no OAuth/token logic.
- Extension popup sends typed intents only; PKCE, token storage, refresh, and revoke stay in trusted service-worker auth modules.

## Testing Strategy

- Small tests: normalization, DTO mapping, API client validation, Web state rendering, PKCE/storage state transitions, cookie/CSRF policy.
- PostgreSQL integration tests: Alembic up/down/up, User/Identity persistence, uniqueness, duplicate identity race protection, session expiry/revocation.
- API tests: missing/malformed/expired/wrong issuer/wrong audience bearer, provisioning behavior, `/auth/me`, Web session, logout, raw-provider-error suppression.
- Cross-transport integration: fake Web callback and fake Extension bearer for the same `(issuer, subject)` return the same `User.id`.
- Authorization fixture: a test-only protected row is queried by both `resource_id` and authenticated local `user_id`; another user's row is indistinguishable from missing.
- Browser-facing tests: React and popup component/DOM tests plus production builds. A real Auth0 browser flow is not claimed without user-supplied tenant configuration.

## Incremental Tasks

### Task 1: Lock the approved dependencies and configuration contract

**Acceptance:** one ORM, one JWT library, one Python HTTP client, one Extension OAuth library; lockfiles update reproducibly; `.env.example` contains placeholders only.

**Verify:** frozen pnpm install, locked uv sync, dependency tree/audit, lint/typecheck.

**Likely files:** `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/extension/package.json`, `pnpm-lock.yaml`, `.env.example`.

### Task 2: Add PostgreSQL metadata and Alembic lifecycle

**Acceptance:** User/Identity/WebSession/LoginTransaction tables have explicit constraints; one Alembic head upgrades a clean PostgreSQL database, downgrades to base, and upgrades again.

**Verify:** real PostgreSQL migration tests and schema assertions; SQLite does not count.

**Likely files:** `apps/api/alembic.ini`, `apps/api/migrations/**`, `jobpilot_api/infrastructure/database/**`, PostgreSQL test fixtures.

### Task 3: Persist and resolve local identity

**Acceptance:** first verified identity creates one User + Identity; repeat `(issuer, subject)` returns the same User; different subjects create different users; same normalized email on another identity conflicts; unique constraints protect the race path.

**Verify:** red-green PostgreSQL repository/service tests.

### Task 4: Add bearer verification and current-user API

**Acceptance:** `POST /api/v1/auth/session` provisions only a fully verified provider identity; `GET /api/v1/auth/me` returns `UserView`; malformed, expired, wrong-issuer, wrong-audience, wrong-signature, wrong-token-type, and unverified-email tokens fail closed.

**Verify:** deterministic RSA fake issuer/JWKS tests; no external network.

### Task 5: Add Web BFF session flow

**Acceptance:** authorize creates a bounded browser transaction; callback validates it, maps the identity, rotates an opaque HttpOnly session, and redirects only to an allowlisted relative path; `/auth/me`, CSRF, expiry, and local logout work with exact Origin/Fetch checks.

**Verify:** API integration tests for success and negative cookie/CSRF/origin paths.

### Task 6: Add the minimal Web authenticated UI

**Acceptance:** signed-out UI offers login; signed-in UI shows display name/email and local User ID; logout clears state; React never receives a bearer/refresh token.

**Verify:** Vitest DOM tests and Web production build.

### Task 7: Add Extension PKCE service-worker flow

**Acceptance:** login starts from a user gesture through `launchWebAuthFlow`; trusted storage is applied before credentials; refresh rotation persists `refresh_in_progress` before network and fails closed on ambiguous restart; popup contains no PKCE/token logic; logout always clears local credentials and reports unconfirmed remote revoke truthfully.

**Verify:** deterministic service-worker/storage tests, manifest permission tests, popup tests, Extension build.

### Task 8: Prove unified identity, authorization, and security boundaries

**Acceptance:** Web cookie and Extension bearer for one provider identity return the same User ID; unauthorized and cross-user requests reveal no user data; exact CORS/cookie properties pass; secrets/tokens/raw provider errors are absent from tracked files, logs, and responses.

**Verify:** API/PostgreSQL integration suite plus repository secret scan.

### Task 9: Review, simplify, document, and accept

**Acceptance:** independent five-axis review has no Critical/Required findings; simplification removes unnecessary wrappers/placeholders without behavior changes; README/architecture/API/data/roadmap/tasks match the implementation; all final gates pass.

**Verify:** frozen installs, all tests, Ruff/ESLint/Prettier, typecheck, both builds, import/startup, PostgreSQL up/down/up, `git diff --check`, clean Git status.

## Checkpoints and Commits

Each completed slice remains buildable and uses a single-purpose Conventional Commit. At every checkpoint: test -> review -> simplify -> commit. Shared contract changes land before Web/Extension consumers. Database migrations remain rollback-capable.

## Security Scope Substitution

The requested `security-and-hardening` skill is unavailable in the active skill catalog. Its absence does not relax the gate: Phase 2A security invariants, the code-review security axis, explicit negative tests, dependency audit, secret scan, fixed issuer/JWKS URLs, exact CORS/Origin policy, HttpOnly session cookies, CSRF, trusted Extension storage, and no-token logging are the substitute controls.

The following advanced future designs remain documented but are not over-engineered in Phase 2B: distributed JWKS single-flight, sophisticated negative cache, KMS lifecycle, backup resurrection ledger infrastructure, multi-region failover, enterprise audit pipelines, anomaly detection, and device fingerprinting.

## Risks and Mitigations

| Risk                                                         | Impact                                     | Mitigation                                                                                                |
| ------------------------------------------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| No PostgreSQL runtime is initially available on this machine | Migration acceptance cannot be proven      | Provision a temporary local PostgreSQL instance before database work; never substitute SQLite             |
| Real Auth0 values are unavailable                            | Live hosted flow cannot be verified        | Complete deterministic code/tests, provide exact setup checklist, report `BLOCKED / USER ACTION REQUIRED` |
| Web/Extension claim drift                                    | Same human could map differently           | Freeze issuer/subject and verified-email claim validation; cross-transport test the same fixture          |
| Cookie CORS/CSRF misconfiguration                            | Session abuse or broken production login   | Exact schemeful-same-site configuration validation and negative tests                                     |
| MV3 worker termination during refresh                        | Token replay or forced grant-family revoke | Persist `refresh_in_progress`, never replay an ambiguous old token, require interactive login             |
| Scope expansion into Phase 3                                 | Invalid phase acceptance                   | Changed-path and terminology review; no Job/Application/Resume code                                       |

## Real Auth0 Configuration Gate

Code and deterministic tests may complete without a tenant. Live verification requires the project owner to supply/create a dev Auth0 Regular Web Application, a Native/public Chrome Extension Application, and a custom API audience, then provide exact callback/logout/origin/redirect values and non-committed secrets. Until then the final state is `Real Auth0 Integration — BLOCKED / USER ACTION REQUIRED`.
