# Implementation Plan: Phase 2B Authentication & User Boundary

## Objective

Implement the approved minimum authentication closure across React Web, Chrome Manifest V3 Extension, FastAPI, and PostgreSQL. Both credential transports must resolve the same verified `(issuer, subject)` to one local JobPilot `User.id`. The new production constraint is: **Core JobPilot workflow must operate without VPN/proxy in Mainland China.** Task 8 real-provider work is paused at ADR-007; this plan stops before Phase 3 and does not implement Job, Application, Resume, AI, RAG, account-management consoles, or enterprise IAM.

Phase 2A is preserved in commit `e3c4999` (`docs(auth): define phase 2 authentication architecture`). Task 6 is approved at the clean `ff8593c` baseline, and Task 7 is complete. ADR-007 now reopens the production Identity Provider choice: Self-hosted Logto OSS is the preferred candidate but not approved, Auth0 is no longer default-approved, and neither provider may be configured. Deterministic tests continue to use `.invalid` configuration and local fake protocol responses.

## Approved Contract Slice

- Web: `GET /api/v1/auth/web/authorize` -> hosted OIDC code flow -> callback -> opaque server-side session cookie.
- Web state: `GET/PATCH /api/v1/auth/me`, `GET /api/v1/auth/csrf`, and local `POST /api/v1/auth/logout`. Recent reauthentication and `POST /api/v1/auth/sessions/revoke-all` are deferred until a later approved contract.
- Extension: Authorization Code + PKCE through `chrome.identity.launchWebAuthFlow`, then `POST /api/v1/auth/session` and `GET /api/v1/auth/me` with an API access bearer.
- Public user response: the approved `UserView`; no provider subject, raw claims, access token, refresh token, session identifier, or database field leakage.
- Normal application code receives `AuthenticatedUser`, never an Auth0 payload.
- Phase 2B does not add a duplicate `/api/v1/me`; the approved endpoint is `/api/v1/auth/me`.
- The full `DELETE /api/v1/auth/account` write-ahead restore-ledger workflow is explicitly deferred under the project owner's latest instruction not to implement KMS/backup-resurrection infrastructure in this minimum closure. The accepted design remains authoritative and the API contract/roadmap will be synchronized; no unsafe reduced deletion endpoint is shipped.

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

- `PyJWT[crypto]`: validated JWT/JWK parsing, signature verification, registered-claim enforcement, and ID-token/access-token decoding; the standard library does not implement JWT or asymmetric verification safely.
- `httpx2`: move the already locked test dependency into runtime for fixed OIDC/JWKS/token/revoke HTTP calls; do not add a second Python HTTP client.
- `oauth4webapi`: Extension-side standards implementation for OAuth authorization responses, token exchange, refresh, ID-token checks, and PKCE primitives; do not add an Auth0 UI SDK or a second JWT library.
- `Alembic`: deterministic upgrade/downgrade history for PostgreSQL.
- `psycopg[binary]`: maintained PostgreSQL DBAPI driver; SQLite is not an acceptance substitute.

No Redis, Celery, Kafka, Auth0 React SDK, Axios, SQLModel, asyncpg, custom cryptography, or generic auth framework is added.

PyJWT + constrained orchestration is sufficient for the Python boundary because JobPilot has one fixed OIDC issuer and two fixed clients, not a generic OAuth client platform. JobPilot constructs only the fixed authorization request, persists high-entropy state/nonce/PKCE values generated by `secrets` and `hashlib`, exchanges a code at the configured HTTPS token endpoint with httpx2, and delegates all JWT/JWK cryptographic validation to PyJWT/cryptography. It does not implement signatures, key parsing, token algorithms, discovery, dynamic client registration, or a custom authorization server. Tests cover token response shape, nonce, `auth_time`, issuer, audience, signature, time, and provider-error mapping.

Web requests only `openid profile email`, never `offline_access`. After the callback validates the ID token and maps the User, all provider ID/access token material is discarded and no Web provider refresh grant is stored. Web logout is therefore explicitly local. Revoke-all remains deferred until recent reauthentication and a narrow provider capability boundary are separately approved.

## Persistence and Session Decision

- `users`: local business identity with `id`, normalized verified unique `email`, nullable `display_name`, nullable `locale`, nullable `time_zone`, `account_status`, nullable `deletion_requested_at`, and timezone-aware `created_at`/`updated_at`.
- `identities`: provider boundary (`id`, `user_id`, `issuer`, case-sensitive `subject`, timestamps) with unique `(issuer, subject)` and a foreign key to `users`.
- `web_sessions`: hash of an opaque cookie value, local user/identity references, hash of the synchronizer CSRF token, idle/absolute expiry, last-use and revocation timestamps.
- `login_transactions`: short-lived browser-bound Web OIDC transaction state, including hashed browser handle/state, nonce, PKCE verifier, intent, allowlisted relative return path, and expiry.

Provider identity is intentionally separated from the business User as required by the Phase 2B owner instruction. This refines the Phase 2A conceptual diagram without changing the invariant `(issuer, subject) -> User.id`; documentation is synchronized after implementation.

PostgreSQL stores the Web session because it is already the approved durable source of truth and avoids introducing Redis for an early single-service product. The browser receives only the opaque cookie value. Token/session material is never logged.

## Source Boundaries

```text
Web callback code
  -> fixed OIDC token exchange + ID-token validation
  -> VerifiedProviderIdentity
  -> identity application service (provisioning allowed)
  -> User + Identity
  -> opaque Web session

Opaque Web cookie
  -> session hash lookup + expiry/revocation/account-state checks
  -> existing User + Identity
  -> AuthenticatedUser (never provisions)

Extension bearer
  -> fixed JWT/JWKS validation
  -> VerifiedProviderIdentity
  -> /auth/session identity service (provisioning allowed)
     OR normal endpoint existing-identity lookup (never provisions)
  -> AuthenticatedUser
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
- API tests: missing/malformed/expired/wrong issuer/wrong audience/fixed-algorithm/`azp`/`nbf`/token-type bearer, ID-token-as-bearer, query-token, cookie+bearer ambiguity, bounded unknown-`kid` refresh, unknown identity, deletion-pending non-reprovision, `/auth/me`, Web session, logout, and raw-provider-error suppression.
- Cross-transport integration: fake Web callback and fake Extension bearer for the same `(issuer, subject)` return the same `User.id`.
- Authorization fixture: a test-only repository and temporary test table (never a production model, migration, or router) query by both `resource_id` and authenticated local `user_id`; another user's row is indistinguishable from missing.
- Browser-facing tests: React and popup component/DOM tests plus production builds. No real selected-provider browser flow may be claimed until ADR-007 and a separate provider-verification slice authorize and validate it.

## Incremental Tasks

The project owner's current Task 6 instruction supersedes the older Phase-level numbering that split persistence, BFF flow, and Web UI into Tasks 6–8. Current Task 6 is one bounded Web server-backed authentication closure delivered through the following independently tested sub-slices. Recent reauthentication and revoke-all are deferred; Task 7 is Extension Authorization Code + PKCE.

**Current status:** Task 6A–6D are approved. Task 7A–7G and the Task 7H deterministic validation/review/documentation gate are complete on `phase/2-authentication`. Task 8 is paused by the ADR-007 Architecture Change Gate. Self-hosted Logto OSS is the preferred candidate but not approved; Auth0 is no longer default-approved for production. Chrome Load unpacked, real provider behavior, account recovery, and Mainland ordinary-network availability remain `NOT VERIFIED / BLOCKED`.

### Task 7 delivery record

| Slice                               | Commits                                                          | Status   |
| ----------------------------------- | ---------------------------------------------------------------- | -------- |
| Plan                                | `a698454`                                                        | Complete |
| 7A — public config/manifest         | `e136dac`                                                        | Complete |
| 7B — PKCE authorization attempt     | `be9b15c`                                                        | Complete |
| 7C — public-client code exchange    | `1624633`                                                        | Complete |
| 7D — trusted credential persistence | `562f7d8`                                                        | Complete |
| 7E — bearer transport/current user  | `f10f14b`, `9d762ec`                                             | Complete |
| 7F — provider/credential lifecycle  | `dcb2c2f`, `a43ce6c`                                             | Complete |
| 7G — typed worker/popup UI          | `094dbce`, `efbdac0`                                             | Complete |
| 7H — independent review remediation | `b503867`                                                        | Complete |
| 7H — docs/final gate                | `docs(auth): record extension authentication flow` (this commit) | Complete |

### Task 1: Lock the approved dependencies and configuration contract

**Acceptance:** one ORM, one JWT library, one Python HTTP client, one Extension OAuth library; lockfiles update reproducibly; `.env.example` contains placeholders only.

**Verify:** frozen pnpm install, locked uv sync, dependency tree/audit, lint/typecheck.

**Dependencies:** None.

**Likely files:** `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/extension/package.json`, `pnpm-lock.yaml`, `.env.example`.

### Task 2: Add PostgreSQL User/Identity migration

**Acceptance:** User/Identity tables have the exact columns/nullability above, unique normalized email and `(issuer, subject)`, and a cascading Identity -> User foreign key. One Alembic head upgrades a clean PostgreSQL database, downgrades to base, and upgrades again.

**Verify:** real PostgreSQL migration tests and schema assertions; SQLite does not count.

**Dependencies:** Task 1.

**Likely files:** `apps/api/alembic.ini`, `apps/api/migrations/**`, `jobpilot_api/infrastructure/database/models.py`, `jobpilot_api/infrastructure/database/engine.py`, PostgreSQL test fixtures.

### Task 3: Persist and resolve local identity

**Acceptance:** first verified identity creates one User + Identity; repeat `(issuer, subject)` returns the same User; different subjects create different users; same normalized email on another identity conflicts; unique constraints protect the race path.

**Verify:** red-green PostgreSQL repository/service tests.

**Dependencies:** Task 2.

**Likely files:** provider-neutral identity domain types, identity application service, SQLAlchemy identity repository, repository tests.

### Checkpoint A: Identity persistence

- Real PostgreSQL upgrade/down/up passes.
- Identity mapping and race tests pass.
- Ruff and API import pass.

### Task 4: Add bearer verification and current-user API

**Acceptance:** fixed HTTPS issuer/JWKS/token endpoints and fixed RS256 algorithm/client allowlists are validated. Malformed, expired, wrong-issuer, wrong-audience, wrong-signature, wrong-algorithm, wrong-`azp`, future-`nbf`, wrong-token-type, ID-token-as-bearer, query token, and random unknown-`kid` credentials fail closed; an unknown `kid` causes at most one bounded refresh per cache window without sophisticated distributed caching.

**Verify:** deterministic RSA fake issuer/JWKS tests; no external network.

**Dependencies:** Task 1.

**Likely files:** infrastructure auth JWT validator/provider client and focused unit tests.

### Task 5: Add Extension provisioning and current-user API

**Acceptance:** `POST /api/v1/auth/session` alone may provision a previously unknown identity from a fully verified bearer; `GET/PATCH /api/v1/auth/me` require an existing active identity and return/update approved `UserView`. Unknown identity on `GET/PATCH /auth/me`, every existing `deletion_pending` mapping, mixed cookie+bearer credentials, and unverified email fail without provisioning or reprovisioning a User.

**Verify:** API integration tests against PostgreSQL and deterministic JWT fixtures.

**Dependencies:** Tasks 3 and 4.

**Likely files:** auth DTO/router/dependencies, identity application service, API tests, TypeScript shared/API client contract.

### Task 6A: Add Web session persistence migration

**Status:** Complete in `c312949`.

**Acceptance:** WebSession and LoginTransaction tables contain only the minimum opaque-hash/CSRF/expiry/revocation and short-lived OIDC transaction fields; migration upgrades and downgrades cleanly without changing User/Identity semantics.

**Verify:** PostgreSQL migration and persistence tests.

**Dependencies:** Task 2.

**Likely files:** second Alembic revision, database models/repositories, session tests.

### Task 6B: Add Web BFF login/callback flow

**Status:** Complete in `4fba2a3` and `ea5a297`.

**Acceptance:** authorize creates a 10-minute browser-bound `login|signup` transaction; callback handles success/cancel/timeout/provider-error with exact cleanup, validates nonce and required claims, discards provider tokens, rotates against session fixation, and redirects only to an allowlisted relative path. Recent reauthentication and revoke-all remain absent from OpenAPI.

**Verify:** API integration tests for success and negative cookie/CSRF/origin paths.

**Dependencies:** Tasks 3, 4, and 6.

**Likely files:** Web auth service, infrastructure OIDC provider, auth router/dependencies, Web session integration tests.

### Task 6C: Add cookie current-user, CSRF, and local logout

**Status:** Complete in `ed692ae` and `bfd640f`.

**Acceptance:** Web cookie and Extension bearer converge on `/api/v1/auth/me` while mixed credentials are rejected. Idle/absolute expiry, revocation, malformed/unknown sessions, session-bound CSRF, exact Origin/Fetch gates, idempotent local logout, and store-outage no-cookie-clear behavior pass.

**Verify:** API/PostgreSQL integration tests for cookie `/me`, PATCH, CSRF, logout, expiry, and revocation.

**Dependencies:** Tasks 6A and 6B.

### Task 6D: Add the minimal Web authenticated UI

**Status:** Complete in `df8d76b` and `bad3b37`.

**Acceptance:** signed-out UI offers login; signed-in UI shows display name/email and local User ID; logout clears state; React never receives a bearer/refresh token.

**Verify:** Vitest DOM tests and Web production build.

**Dependencies:** Tasks 5 and 6C.

**Likely files:** shared/API client auth contract, Web App/session client/tests/styles.

### Checkpoint B: API and Web closure

- [x] Bearer and Web cookie API tests pass.
- [x] Web component tests/typecheck/build and 320px browser runtime verification pass.
- [x] No provider token reaches React, browser storage, build output, or logs.
- [x] At Task 6 completion, real Auth0 Web verification was blocked on project-owner tenant/application configuration and no live PASS was claimed; ADR-007 now additionally pauses that configuration and reopens the production provider choice.

### Task 7A: Freeze Extension public configuration and manifest boundary

**Acceptance:** deterministic test/build configuration uses explicit `.invalid` issuer/IDs and is never described as live. Missing or malformed API, Web, issuer, authorize, token, JWKS, revoke, audience, or public-client values fail before runtime use. Manifest uses a module service worker, keeps MV3 CSP free of `unsafe-eval`, and grants only `identity`, `storage`, and exact API/provider origins required by Task 7. The obsolete Phase 1 current-tab diagnostic and its `activeTab` permission are removed with the Task 7 popup replacement. No client-secret input exists.

**Verify:** RED -> GREEN config/manifest tests, typecheck, and deterministic Extension build artifact inspection.

**Dependencies:** Tasks 1 and 5.

**Likely files:** Extension config, manifest, Vite input, `.env.example`, focused tests.

### Task 7B: Add PKCE attempt and `launchWebAuthFlow` boundary

**Acceptance:** a user intent creates an unpredictable state, nonce, RFC 7636 verifier, S256 challenge, and runtime `chrome.identity.getRedirectURL()` value. Before persisting the attempt or reading any secret, the worker awaits successful `TRUSTED_CONTEXTS` restriction for both Chrome storage areas. One versioned attempt is then stored only in trusted session state with a bounded lifetime. The worker validates exact callback shape/state and consumes the attempt on success, missing/mismatched/stale state, missing code, provider error, cancellation, malformed callback, or launch failure.

**Verify:** RED -> GREEN PKCE/attempt/callback/launch tests, including injected cryptographic-randomness boundary and known S256 vector.

**Dependencies:** Task 7A.

**Likely files:** auth attempt/PKCE module, Chrome identity adapter, tests.

### Task 7C: Exchange and validate the public-client authorization code

**Acceptance:** after the trusted-storage gate, `oauth4webapi` uses public-client `none` authentication and the stored verifier. The authorize request freezes `response_type=code`, `code_challenge_method=S256`, the JobPilot API audience, and minimum `openid profile email offline_access` scope. The worker validates token-endpoint responses plus the signed ID token issuer, client audience, RS256 signature, times, and exact nonce, then discards the ID token. Only `token_type=bearer`, bounded `expires_in`, a short-lived access token, and a replacement-capable rotating refresh token enter the credential boundary; missing/malformed material fails closed.

**Verify:** RED -> GREEN deterministic fake token/JWKS tests for success, malformed response, wrong signature/issuer/audience/nonce, missing access/refresh/ID token, and excessive/invalid expiry.

**Dependencies:** Task 7B.

**Likely files:** provider protocol adapter and focused tests.

### Task 7D: Add trusted crash-consistent credential storage

**Acceptance:** every secret read/write is behind the awaited `TRUSTED_CONTEXTS` gate for both Chrome storage areas. Attempt/access state uses `chrome.storage.session`; one versioned refresh record uses `chrome.storage.local`. Initial exchange and every rotation commit `ready.pending (new refresh) -> access (same generation) -> ready.committed`; only committed state is restorable. `refresh_in_progress` and best-effort `locally_cleared` contain no credential. Normal restart restores a valid committed record, including refresh-only state when session access is missing. Corrupt/pending/in-progress/generation-mismatched state, request-start interruption, ambiguous network outcome, response interruption, or unacknowledged write clears credentials and requires interaction without replaying the old token.

**Verify:** RED -> GREEN storage/bootstrap/ordering/corruption/restart tests, including each crash boundary and positive ready-record restoration.

**Dependencies:** Task 7C.

**Likely files:** trusted credential store and focused tests.

### Task 7E: Establish and restore the local user through the shared API client

**Acceptance:** the shared `packages/api-client` owns bearer injection, `credentials: omit`, URL construction, error parsing, and `UserView` validation. Initial login calls `POST /auth/session` before `GET /auth/me`; restart with a usable access token calls `/auth/me` directly. Local expiry/near-expiry can trigger one current-worker single-flight rotation before a request. An arbitrary API `401` is not treated as proof of expiry and instead clears credentials; no refresh/retry loop exists.

**Verify:** RED -> GREEN API-client and auth-service tests for establishment order, direct restore, local expiry, concurrent callers, invalid/revoked bearer, and bounded failures.

**Dependencies:** Task 7D.

**Likely files:** shared API client, Extension auth service, focused tests.

### Task 7F: Add refresh failure and truthful logout handling

**Acceptance:** a locally expired token rotates exactly once through the current worker's shared in-flight promise. Rotation persists `refresh_in_progress` without the old token before the request, accepts only a replacement refresh token, and never replays an ambiguous or rejected token. `invalid_grant`, provider/network failure, malformed response, and persistence failure clear state. Logout attempts direct revoke and always clears local access, refresh, attempt, and profile state; its popup-safe result distinguishes confirmed, not-applicable, and unconfirmed remote revocation without claiming server retry.

**Verify:** RED -> GREEN rotation/single-flight/`invalid_grant`/outage/ambiguous/revoke-result tests.

**Dependencies:** Task 7E.

**Likely files:** auth service/provider boundary and focused tests.

### Task 7G: Add the typed worker boundary and minimal popup UI

**Acceptance:** runtime message parsing uses an exact schema and trusted popup sender/context allowlist; unknown types, extra fields, other extension/page contexts, and credential-shaped payloads are rejected. Responses contain only popup-safe state. The popup renders signed-out, authenticating, signed-in, error, and revoke-unconfirmed states; signed-in state shows only approved `UserView` fields and can open the configured Web home. Popup code contains no URL literal, PKCE, callback parsing, token, storage, refresh, or provider protocol logic and uses accessible native controls.

**Verify:** RED -> GREEN worker-message and popup DOM tests for all states, unknown/untrusted messages, credential-free payloads, keyboard/accessibility semantics, and Web opening.

**Dependencies:** Task 7F.

**Likely files:** background entry/message contract, popup HTML/controller/styles/main/tests.

### Task 7H: Validate, review, simplify, and document Task 7

**Status:** Complete. The full deterministic suite contains 293 TypeScript tests and 452 Pytest tests (745 total); Task 7 added 252 tests over the approved 493-test Task 6 baseline. Frozen/locked installs, lint, format, strict typecheck, Web/Extension builds, API import/startup, dependency audit, PostgreSQL-backed identity invariant, and security/artifact scans pass. Independent review is Critical 0 / Required 0 after `b503867`; simplification found no Required refactor. Chrome Load unpacked is `NOT VERIFIED` and real Auth0 is `BLOCKED / USER ACTION REQUIRED`.

**Acceptance:** rerun the existing deterministic Web-cookie/Extension-bearer `(issuer, subject) -> same User.id` integration invariant; inspect minimum permissions/CSP and built artifacts; run the complete TypeScript/Python gates and security scans; resolve all Critical/Required review findings; simplify only changed code; synchronize Task 7 documentation; leave a clean worktree without entering Task 8 or Phase 3.

**Verify:** `pnpm install --frozen-lockfile`; `uv sync --project apps/api --locked`; `pnpm test`; `pnpm lint`; `pnpm format:check`; `pnpm typecheck`; `pnpm build:extension`; `pnpm build:web`; `pnpm api:test`; `pnpm api:lint`; `pnpm api:format:check`; `pnpm api:import:check`; package audits and repository secret/token/storage/layer/manifest/CSP scans; `git diff --check`; `git status --short`. Real Chrome/Auth0 results remain truthfully gated when unavailable.

**Dependencies:** Tasks 7A–7G.

### Task 8: Phase 2B Integration & Authentication Acceptance

**Status:** Paused by ADR-007. Do not create/bind real Auth0 or Logto resources and do not resume from deterministic Task 7 completion. Task 8 requires: (1) project-owner approval of ADR-007, (2) a separately approved provider deployment/protocol/Mainland verification slice, and (3) explicit authorization after that slice reports its real results.

**Acceptance:** Web cookie and Extension bearer for one provider identity return the same User ID; unauthorized and cross-user requests reveal no user data; exact CORS/cookie properties pass; secrets/tokens/raw provider errors are absent from tracked files, logs, and responses.

**Verify:** API/PostgreSQL integration suite plus repository secret scan.

**Dependencies:** Tasks 5, 6, and 7.

**Likely files:** cross-transport integration tests, test-only ownership fixture, security/config tests.

### Task 9: Review, simplify, document, and accept

**Acceptance:** independent five-axis review has no Critical/Required findings; simplification removes unnecessary wrappers/placeholders without behavior changes; README/architecture/API/data/roadmap/tasks match the implementation; all final gates pass.

**Verify:** frozen installs, all tests, Ruff/ESLint/Prettier, typecheck, both builds, import/startup, PostgreSQL up/down/up, `git diff --check`, clean Git status.

**Dependencies:** Tasks 1-8.

**Likely files:** only documentation/checklists plus any changed files required to resolve review findings.

### Checkpoint C: Phase 2B acceptance

- Full Python/TypeScript/database gates pass.
- Independent review has no Critical/Required findings.
- Simplification and documentation are complete.
- The selected real provider and Mainland ordinary-network result are reported truthfully as PASS/BLOCKED/NOT VERIFIED; Phase 3 has not started.

## Checkpoints and Commits

Each completed task/slice remains buildable and uses a single-purpose Conventional Commit. Every slice runs affected tests -> review -> simplify before its commit; checkpoints then run cumulative gates. Shared contract changes land before Web/Extension consumers. Database migrations remain rollback-capable.

## Security Scope Substitution

The requested `security-and-hardening` skill is unavailable in the active skill catalog. Its absence does not relax the gate: Phase 2A security invariants, the code-review security axis, explicit negative tests, dependency audit, secret scan, fixed issuer/JWKS URLs, exact CORS/Origin policy, HttpOnly session cookies, CSRF, trusted Extension storage, and no-token logging are the substitute controls.

The following advanced future designs remain documented but are not over-engineered in Phase 2B: distributed JWKS single-flight, sophisticated negative cache, KMS lifecycle, backup resurrection ledger infrastructure, multi-region failover, enterprise audit pipelines, anomaly detection, and device fingerprinting.

## Risks and Mitigations

| Risk                                                         | Impact                                     | Mitigation                                                                                                |
| ------------------------------------------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| No PostgreSQL runtime is initially available on this machine | Migration acceptance cannot be proven      | Provision a temporary local PostgreSQL instance before database work; never substitute SQLite             |
| Production Identity Provider is not approved                 | Live hosted flow cannot be verified        | Complete ADR-007 first; do not configure Auth0/Logto or infer approval from deterministic tests           |
| Mainland ordinary-network flow is unavailable or untested    | Core JobPilot workflow fails a hard gate   | Verify Web, Extension, recovery and runtime dependencies on approved no-proxy fixed/mobile network matrix |
| Web/Extension claim drift                                    | Same human could map differently           | Freeze issuer/subject and verified-email claim validation; cross-transport test the same fixture          |
| Cookie CORS/CSRF misconfiguration                            | Session abuse or broken production login   | Exact schemeful-same-site configuration validation and negative tests                                     |
| MV3 worker termination during refresh                        | Token replay or forced grant-family revoke | Persist `refresh_in_progress`, never replay an ambiguous old token, require interactive login             |
| Scope expansion into Phase 3                                 | Invalid phase acceptance                   | Changed-path and terminology review; no Job/Application/Resume code                                       |

## Production Identity Provider Architecture Change Gate

[ADR-007](../docs/DECISIONS/ADR-007-mainland-china-identity-provider.md) compares Self-hosted Logto OSS, current Auth0, and FastAPI self-hosted authentication. It preserves the implemented provider-neutral boundaries and identifies the minimal future Logto seams: Web provider/composition wiring, Extension `audience` versus RFC 8707 `resource`, exact token/claim/client profile, refresh/reuse/revoke behavior, provider configuration and focused fixtures. Its Mainland Gate also requires objective PASS/FAIL fields to be frozen before testing and covers Extension installation, controlled signing/stable ID, reachable update hosting, N-1 compatibility, and rollback without assuming Chrome Web Store reachability.

Current result: `PROPOSED / AWAITING PROJECT-OWNER APPROVAL`. No Auth0 or Logto tenant/application/configuration is authorized. If the owner approves Logto as the preferred candidate, the next work is a separate deployment/protocol/Mainland verification plan—not immediate business-code migration. Until that verification and a subsequent authorization pass, Task 8 and Phase 3 remain paused.
