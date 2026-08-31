# JobPilot Authentication Architecture

> **Status**：Phase 2A provider-neutral boundaries remain Accepted; Task 6 Web server-backed session and Task 7 Extension Authorization Code + PKCE are deterministically implemented. Task 8 real-provider work is paused at the ADR-007 Architecture Change Gate.
>
> **Decision records**：[ADR-006](DECISIONS/ADR-006-authentication-strategy.md)（implemented historical strategy）; [ADR-007](DECISIONS/ADR-007-mainland-china-identity-provider.md)（Proposed production-provider change）
>
> **Implementation gate**：Satisfied for the Task 6 Web and Task 7 Extension deterministic code/test slices. Do not create or bind real Auth0/Logto resources, migrate authentication code, start Task 8, or enter Phase 3 until ADR-007 and a separate provider verification slice are approved. Chrome Load unpacked and Mainland ordinary-network availability are not verified.

## 1. Scope

This document defines how the Web app, Chrome Extension, and FastAPI share one user identity while using transports appropriate to each runtime. It is both the accepted Phase 2B provider-neutral boundary and the implementation contract: Task 6 implements the Web/BFF/session portions and Task 7 implements the deterministic Extension public-client lifecycle. The current infrastructure adapter and fake protocol profile are Auth0-compatible; the production Identity Provider is reopened by ADR-007.

The implemented reference uses Auth0 as a managed OIDC identity provider. Production is not approved to use Auth0 while ADR-007 is open. Self-hosted Logto OSS is the preferred candidate, subject to Mainland reachability, protocol, recovery, operations, security, and compliance verification. In either case the provider software owns the credential protocol surface while JobPilot owns its local User, Web sessions, business authorization, account deletion orchestration, PostgreSQL business data, and all future private objects. With Self-hosted Logto, its identity database, logs and backups are also JobPilot-controlled stores; only a managed provider's inaccessible records may be handled through DPA/tenant disclosure.

The design deliberately does not include organizations, teams, roles, administrator matrices, enterprise SSO, a custom password database, or a JobPilot OAuth server.

### 1.1 Active Architecture Change Gate

The hard production constraint is:

> **Core JobPilot workflow must operate without VPN/proxy in Mainland China.**

This includes Web signup/login/session recovery, Extension authorization/token refresh/logout, account recovery delivery, and every runtime dependency. Self-hosting is not itself proof of reachability. Until the project owner accepts ADR-007 and separately authorizes verification/migration, the current code remains unchanged, both real Auth0 and Logto configuration are prohibited, and no live-provider PASS may be claimed.

The proposed provider change must preserve `(issuer, subject) -> User.id`, the Web opaque session, Extension PKCE and trusted storage, `POST /api/v1/auth/session`, `/api/v1/auth/me`, `VerifiedProviderIdentity`, `AuthenticatedUser`, and resource ownership. Exact Logto `resource`, client-auth, claim, refresh/reuse and revoke semantics are compatibility gates, not assumptions.

## 2. Architecture Summary

```mermaid
flowchart LR
    User((User))
    Web[React Web]
    Extension[Chrome MV3 Extension]
    IdP[OIDC Provider Adapter]
    Boundary[FastAPI Authentication Boundary]
    Context[AuthenticatedUser Context]
    Services[Application Services]
    DB[(JobPilot PostgreSQL)]

    User --> Web
    User --> Extension
    Web -->|OIDC via FastAPI BFF| IdP
    Extension -->|Authorization Code + PKCE| IdP
    Web -->|opaque HttpOnly session cookie| Boundary
    Extension -->|short-lived access bearer| Boundary
    Boundary --> Context --> Services --> DB
```

The two clients do not share browser storage or copy credentials between origins. They share one verified provider identity and one local `User.id`.

## 3. Identity Model

### 3.1 Provider identity and local User

The stable mapping is:

```text
(identity_issuer, identity_subject) -> JobPilot User.id
```

- `identity_issuer` is the exact configured OIDC issuer URL for the environment.
- `identity_subject` is the provider `sub`, treated as an opaque case-sensitive string.
- `User.id` is a JobPilot-generated stable UUID and is the only user foreign key used by business tables.
- `email` is a verified, mutable profile/contact attribute. It is not used as the authentication key and never auto-links two provider identities.
- `display_name`, `locale`, and `time_zone` are local product profile fields, not OIDC authorization claims.

The selected production provider must emit a stable `sub` across the Web and Extension clients in the same tenant/connection. A valid identity without a verified email cannot activate a JobPilot account or access business resources.

Claim sources are explicit: the Web callback validates the signed OIDC ID token and its approved email-verification claims. The current Auth0-compatible Extension profile expects collision-resistant namespaced email and email-verification claims emitted by a reviewed Action; a future Logto adapter must freeze its own exact built-in or custom claim source. FastAPI never assumes that a custom-API access token contains profile claims by default. Missing, unverified, or malformed claims fail provisioning.

JobPilot stores no password, password hash, social-provider access token, security answer, or recovery code in `User`.

### 3.2 Local provisioning

After a successful provider flow, cryptographic validation produces a `VerifiedProviderIdentity`. An identity application service idempotently resolves it:

1. Existing mapping: load the same local User and synchronize only approved mutable claims such as verified email.
2. No mapping: create the minimal local User after verification and explicit account creation/login completion. `display_name`, `locale`, and `time_zone` remain null until the authenticated user sets them through `PATCH /api/v1/auth/me`; provisioning never guesses them from untrusted client hints.
3. Same email with a different `(issuer, subject)`: stop and require an explicit future account-linking flow; never merge automatically.
4. Existing `deletion_pending` mapping: deny provisioning and continue deletion/recovery rather than restoring access. After provider acknowledgement and completed hard deletion, no identity tombstone is kept: a later explicit hosted authentication/account-creation flow may create a **fresh** local `User.id`, but no old data, ownership, session, or mapping is restored. V1's restore marker is keyed to the deleted `User.id`; it prevents backup resurrection, not future re-registration.

Only the Web callback and `POST /api/v1/auth/session` may use `VerifiedProviderIdentity` to provision. Normal business endpoints require an already active local User. Provisioning logic does not live in React, popup code, FastAPI routers, or generic JWT middleware.

### 3.3 Provider identity and authenticated user contexts

Provider validation first constructs a deliberately non-authorizing context:

```text
VerifiedProviderIdentity
- identity_issuer
- identity_subject
- verified_email
- authorized_party
- authentication_time (when supplied and validated)
```

This context can establish a JobPilot session/User only at the two provisioning boundaries above. It cannot read or mutate a business resource.

After mapping to an active local User, FastAPI constructs the immutable context used by application services:

```text
AuthenticatedUser
- user_id          # local JobPilot User.id
- identity_issuer  # audit/security boundary
- identity_subject # audit/security boundary
- session_kind     # web | extension
- session_id       # internal correlation/revocation identifier when available
```

Provider roles, arbitrary metadata, email, and client-supplied `userId` do not grant business permissions.

## 4. Web Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant Web as React Web
    participant API as FastAPI BFF
    participant IdP as Configured OIDC Provider
    participant Sessions as Server Session Store
    participant DB as JobPilot User Store

    User->>Web: Choose sign in or create account
    Web->>API: GET /api/v1/auth/web/authorize
    API->>API: Create one-time state, nonce, PKCE transaction and hash-bound browser handle
    API-->>User: Set short HttpOnly transaction cookie; 302 to exact provider authorize URL
    User->>IdP: Authenticate / verify email
    IdP-->>API: Authorization code + state
    API->>API: Verify state + transaction cookie; exchange code; validate issuer, nonce and claims
    API->>DB: Resolve or create local User by issuer + subject
    API->>Sessions: Create/rotate revocable server-side session
    API-->>User: Delete transaction cookie; set opaque session cookie; 303 to allowlisted Web path
    User->>Web: Load application
    Web->>API: GET /api/v1/auth/me with cookie
    API->>Sessions: Validate hash, expiry, revocation and User state
    API-->>Web: UserView
    Web->>API: GET /api/v1/auth/csrf with cookie
    API-->>Web: Session-bound CSRF value (no-store)
```

### 4.1 Web credential transport

The browser receives only an opaque, high-entropy session identifier. The production cookie is host-only and uses:

```text
__Host-jobpilot_session
HttpOnly; Secure; SameSite=Lax; Path=/; no Domain
```

Only a hash of the identifier is stored server-side. The Task 6 session record contains the local `user_id`, provider identity, opaque session/CSRF hashes, creation/last-use/idle/absolute-expiry times, and revocation state. Web requests only `openid profile email`; the callback discards the ID/access token after validation and stores no provider refresh token or grant material.

Before that session exists, `/auth/web/authorize` sets a different one-time cookie containing only a random transaction handle. In production it is `__Host-jobpilot_login_tx` with `HttpOnly; Secure; SameSite=Lax; Path=/; no Domain; Max-Age=600`; the Lax setting permits the top-level OIDC callback while preventing cross-site subrequest use. The server-side record expires no later than the same 10-minute limit. Callback requires both matching `state` and this browser-bound handle; success, denial, expiry, mismatch, or provider error always deletes the cookie with the exact attributes used to create it and invalidates the transaction. A callback URL copied to another browser therefore cannot establish the attacker's session for the victim.

Task 6 implements `intent=login|signup`. Login uses `prompt=login`, so a local JobPilot logout cannot be silently undone by a surviving provider SSO cookie; signup is only a provider-hosted UI hint. The current Auth0 adapter's exact hint remains implementation-specific. Recent reauthentication and revoke-all require a separately frozen session-binding contract and are deferred rather than partially implemented.

Initial targets are a 7-day idle timeout and 30-day absolute lifetime. The identifier rotates after login and security-sensitive renewal; logout/revoke marks the server record invalid before clearing the cookie.

React never receives a bearer or refresh token. A bearer in `localStorage`, IndexedDB, a readable cookie, URL, Redux/state store, or build-time configuration is forbidden.

### 4.2 XSS, CSRF, CORS, and SameSite

- HttpOnly limits direct credential exfiltration by XSS, but malicious same-origin JavaScript can still act as the user. Output encoding, no unsafe HTML rendering, CSP, dependency review, and input validation remain required.
- After login, React fetches a session-bound synchronizer value from `GET /api/v1/auth/csrf`, keeps it only in memory, and returns it in `X-CSRF-Token`. The endpoint is Web-session-only, exact-CORS protected, and `Cache-Control: no-store`.
- Every cookie-authenticated `POST`, `PATCH`, `PUT`, and `DELETE` request requires that CSRF value, exact `Origin` validation, and compatible Fetch Metadata checks.
- `SameSite=Lax` supports the top-level OIDC callback while reducing cross-site cookie sending. It is defense in depth, not the only CSRF control.
- `returnTo` accepts only an allowlisted relative Web path. Arbitrary redirect URLs are rejected.
- Production Web and API origins must be **schemeful same-site** so the `SameSite=Lax` session cookie is sent on API fetches; they may be cross-origin only with an exact Web-origin CORS allowlist and credentials. Wildcard/reflected origins are forbidden. A cross-site deployment requires reopening this ADR rather than silently changing the cookie to `SameSite=None`.
- Production static hosting must rewrite `/auth/error` to the Web SPA entry and set a reviewed CSP plus security response headers at the deployment boundary. Task 6 deliberately does not add a permissive meta CSP or guess a hosting-provider configuration.

## 5. Extension Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant Popup as Extension Popup
    participant Worker as Trusted Service Worker
    participant Chrome as chrome.identity
    participant IdP as Configured OIDC Authorization Server
    participant API as FastAPI

    User->>Popup: Choose sign in
    Popup->>Worker: Typed SIGN_IN intent
    Worker->>Worker: Generate state, nonce and PKCE verifier/challenge
    Worker->>Chrome: launchWebAuthFlow(exact authorize URL)
    Chrome->>IdP: Authorization request + PKCE challenge
    User->>IdP: Authenticate / consent
    IdP-->>Chrome: Redirect to exact chromiumapp callback with code + state
    Chrome-->>Worker: Final callback URL
    Worker->>Worker: Verify state; reject missing/duplicate/expired transaction
    Worker->>IdP: Exchange code + verifier (public client, no secret)
    IdP-->>Worker: Signed ID token + short API access token + rotating refresh token
    Worker->>Worker: OIDC client validates ID token iss/aud/signature/nonce, then discards it
    Worker->>Worker: Validate response; persist versioned refresh record, then volatile access token
    Worker->>API: Establish/read identity with Authorization: Bearer access token
    API->>API: Validate JWT and resolve issuer + subject to User.id
    API-->>Worker: UserView
    Worker-->>Popup: Signed-in profile state only; no token
```

### 5.1 Credential acquisition

- Login starts only after a user gesture.
- The Extension uses a separate provider public client with Authorization Code + PKCE S256. It has no client secret.
- `state` prevents login CSRF, `nonce` binds the identity response, and the PKCE verifier binds the intercepted code to the initiating Extension.
- Redirect URIs are generated from `chrome.identity.getRedirectURL()` and allowlisted exactly for each stable dev/prod Extension ID. Wildcards and caller-supplied redirects are forbidden.
- The trusted OIDC client/SDK validates the signed ID token's issuer, client audience, signature, times, and exact nonce, then discards it. The API accepts only the separate access token whose audience is the JobPilot API; an ID token is never accepted as an API bearer.
- Direct code exchange, refresh, and revoke fetches require the exact configured provider origin in `host_permissions`, separate from the exact JobPilot API permission. The current deterministic adapter uses an Auth0-compatible origin; no wildcard provider or general HTTPS permission is allowed.
- The access token used for first establishment carries reviewed verified-email claims from the selected provider's frozen token profile; the current Auth0-compatible profile uses namespaced claims and never assumes standard email claims in a custom API token.
- Extension API fetches use `credentials: omit` and explicitly attach the access bearer. CORS allowlists the stable `chrome-extension://<id>` origin and required headers; it never authorizes arbitrary extension IDs.
- On first login the shared bearer client calls `POST /api/v1/auth/session` and then `GET /api/v1/auth/me`; after a normal worker restart with usable credentials it calls `/auth/me` directly. `/auth/session` is an identity-establishment boundary: it may idempotently resolve/provision the local User and returns `UserView`, but it does not create a Web session, set a cookie, or mint a JobPilot token.

### 5.2 Credential storage

| Credential/state              | Current implementation location | Rule                                                                                                                                                  |
| ----------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| PKCE verifier, state, nonce   | `chrome.storage.session`        | One bounded, versioned login transaction; delete on success, cancel, timeout, malformed callback, provider error, or launch failure                   |
| Access token                  | `chrome.storage.session`        | Versioned and generation-bound; maximum accepted lifetime 10 minutes; removed before refresh/revoke and never written to disk-backed local storage    |
| Rotating refresh token record | `chrome.storage.local`          | Versioned `ready` record; `refresh_in_progress` contains generation/time only and never the old token                                                 |
| Local invalidation marker     | `chrome.storage.local`          | Credential-free `{version: 1, status: "locally_cleared"}` marker used to fail closed when physical removal cannot yet be confirmed                    |
| Display profile               | popup response/state only       | `id`, `email`, and `displayName`; no persistent profile cache, credential, provider claim, locale/time-zone payload, or provider protocol information |

Before reading or writing any secret, attempt, or credential state, the worker must successfully apply `setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"})` to **both** `chrome.storage.local` and `chrome.storage.session`; failure in either area is fail-closed and no authorization launch, token exchange, refresh, or credential restore proceeds. `TRUSTED_CONTEXTS` is an access restriction, not a hardware vault. `chrome.storage.sync`, Web `localStorage`/`sessionStorage`, IndexedDB, source code, popup DOM, content scripts, recruitment pages, messages to page scripts, telemetry, and logs are forbidden credential locations.

`chrome.storage.local` is not a hardware vault. Its accepted V1 boundary is the signed-in OS/browser profile plus the Extension's trusted contexts. Device compromise or a malicious Extension update can still steal it; short access lifetime, rotating refresh, replay detection, revocation, minimal permissions, MV3 CSP, and release integrity reduce the impact.

### 5.3 MV3 lifecycle

The service worker is disposable. It does not use timers, hidden pages, or keepalive tricks to remain active. A single-flight promise only coalesces callers during the lifetime of the **current worker**; it is not a cross-restart lock. Chrome's two storage areas and the provider's rotation cannot form one atomic transaction, so V1 uses a fail-closed, crash-consistent protocol:

1. use a still-valid access token from trusted session storage; a missing access record with a committed refresh record is a valid refresh-only restart state;
2. before sending a refresh, replace the persisted refresh record with credential-free `refresh_in_progress` (next generation/start time) and remove session access while holding the old token only in worker memory;
3. send that old token once through the current worker/lifecycle single-flight request; the response must contain a different replacement refresh token and a bounded access token;
4. commit both initial and rotated credentials in the exact crash-consistent order `local ready.pending (new refresh) -> session access -> local ready.committed`;
5. restore only `ready.committed`. A `ready.pending`, `refresh_in_progress`, generation mismatch, corrupt record, ambiguous network result, or unacknowledged write fails closed, clears trusted credential state, and requires interactive login; the old token is never replayed;
6. before best-effort physical removal, write credential-free `locally_cleared`. `locally_cleared + no access` restores as signed out; incomplete removal poisons the current runtime and reports storage unavailable rather than treating residual state as authenticated;
7. if the provider rejects refresh (including `invalid_grant`) or any response/persistence step fails, clear local credential state and require interactive login. The client does not claim that it actively revoked the provider token family and currently has no security-event emitter; provider-side reuse-family behavior remains a real-tenant verification gate.

Only the final `ready.committed` acknowledgement makes the new generation restorable and releasable to callers. Losing availability and asking the user to sign in again is preferred to replaying a possibly rotated token and revoking the whole family. An arbitrary API `401` is not treated as proof of local expiry: the worker clears credentials and requires interaction instead of starting a speculative refresh/retry loop.

The popup never performs token refresh itself. Content scripts can send validated job-capture messages later, but cannot read authentication storage or attach credentials.

### 5.4 Worker, popup, manifest, and permission boundary

- The trusted service worker owns OAuth/OIDC protocol, storage, bearer API calls, refresh, revoke, and Web opening. Popup code owns only rendering and user intent.
- The popup can send exactly `GET_AUTH_STATE`, `SIGN_IN`, `SIGN_OUT`, and `OPEN_WEB_APP`, each with no payload. The worker requires the exact Extension ID, popup URL, Extension origin, and no `sender.tab`; missing or mismatched origin fails closed. Responses expose only popup-safe User fields and fixed error/revoke states.
- The current auth-only MV3 manifest contains `identity` and `storage`, exact API/provider origins, a module service worker, and `script-src 'self'; object-src 'self'`. It has no `activeTab`, `tabs`, content script, recruitment-site permission, `<all_urls>`, `unsafe-eval`, or remote executable script.
- `activeTab` belongs to the future, separately authorized Phase 3 user-triggered capture permission budget. It is not required by authentication or by `chrome.tabs.create()` for the fixed validated JobPilot Web origin.

## 6. FastAPI Authentication Boundary

FastAPI separates provider proof from local business authentication. Provider proof yields `VerifiedProviderIdentity`; mapping an active local User yields `AuthenticatedUser`. The two transport adapters converge only at the latter boundary for normal application services:

### 6.1 Web cookie adapter

1. Read the named host-only cookie; never accept it from query/body.
2. Hash the presented identifier and find an active server-side session.
3. Enforce idle/absolute expiry, revocation, expected session kind, and account state.
4. Rotate or refresh only through the dedicated session service.
5. Resolve local `User.id` and create `AuthenticatedUser`.

### 6.2 Extension bearer adapter

1. Require `Authorization: Bearer <access-token>`; reject query, fragment, cookie fallback, ID tokens, and malformed schemes.
2. Use an explicit algorithm allowlist; reject `none`, algorithm confusion, unexpected issuer or audience.
3. Validate signature against cached JWKS plus `iss`, `aud`, token type, allowed `azp`/client ID, `exp`, `nbf`, `iat`, and non-empty `sub`, with a small fixed clock-skew allowance.
4. Resolve keys only from the configured issuer's fixed HTTPS JWKS URI. An unknown `kid` may trigger at most one validator-wide, per-issuer single-flight refresh after a fixed cooldown; negative-cache the unknown `(issuer, kid)`, apply authentication/IP rate limits before refresh, and fail closed. Random `kid` values must not cause one outbound request per inbound request, and attacker-controlled key URLs are never fetched.
5. Produce `VerifiedProviderIdentity` from the validated claims.
6. For `POST /api/v1/auth/session`, pass that identity to the provisioning application service, which checks an existing `deletion_pending` mapping before the no-mapping branch and rejects it; for every other endpoint, require an existing active `(iss, sub)` mapping before creating `AuthenticatedUser`.

The word `session` in this approved path means establishing/resolving the local identity context for the Extension. This endpoint does not create or return the opaque Web session described in section 4; Web session creation remains exclusively inside the server-side Web callback.

If a request presents both a Web session and bearer token, the boundary rejects ambiguous/conflicting credentials rather than guessing precedence. Provider claims are untrusted until all validation succeeds.

Routers only request an authenticated context, validate request data, call an application service, and map its result. OIDC, token refresh, User provisioning, and ownership rules do not spread through routers.

## 7. Session Lifecycle

| Event                                    | Web                                                                                   | Extension                                                                                                            | Server effect                                                                                                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Create account                           | Universal Login via FastAPI callback                                                  | Same hosted identity flow; no separate password form                                                                 | Provision one local User after verified identity                                                                                                                        |
| Login                                    | Authorization Code flow; opaque cookie                                                | Authorization Code + PKCE public-client flow                                                                         | Resolve same `(issuer, subject)`                                                                                                                                        |
| Authenticated request                    | Cookie automatically sent to exact API host                                           | Short access bearer explicitly attached by trusted worker                                                            | Produce one `AuthenticatedUser` context                                                                                                                                 |
| Renewal                                  | Server-side session/provider renewal                                                  | Single-flight rotating refresh                                                                                       | Enforce idle/absolute lifetime                                                                                                                                          |
| Access expiry                            | Session adapter rejects/renews per policy                                             | Worker refreshes or requires login                                                                                   | Return `401 AUTHENTICATION_REQUIRED` if unavailable                                                                                                                     |
| Logout current                           | Revoke the JobPilot server session and clear cookie; next login is forced interactive | Attempt direct refresh-grant revoke, clear trusted storage, warn if remote status is unknown                         | New local requests fail; provider SSO cookie is not claimed removed; remote Extension grant may survive a failed revoke and stateless access may survive to short `exp` |
| Revoke all (future capability)           | Revoke all local Web sessions after recent reauthentication                           | Revoke provider refresh grants; each worker clears local state only on its next observed auth failure or user action | Not implemented in Task 6/7; future contract must bound residual access without claiming remote storage deletion                                                        |
| Credential reset/security event (future) | Provider handles credential                                                           | Provider handles credential                                                                                          | Separately approved account-lifecycle capability; not exposed by current Task 6/7 OpenAPI                                                                               |
| Account deletion (future)                | Recent Web reauthentication required                                                  | Opens future Web deletion flow                                                                                       | Separately approved restore-ledger/deletion workflow; not implemented by current Task 6/7                                                                               |

Phase 2B must freeze exact values after checking the selected provider's real capabilities. Values may be made shorter without a new ADR; making them longer requires security review and documentation change.

## 8. Logout / Revocation

Logout and revocation are different:

- **Local Web logout** is immediate because FastAPI controls the opaque session record.
- Web logout uses a dedicated resolver. **Every** browser logout request, including one with a missing/expired/revoked cookie, first requires the exact allowed Web `Origin` plus compatible Fetch Metadata; failure returns `403` without changing cookies. A valid session additionally requires its CSRF token before revoke. After those gates, a missing/expired/revoked session can receive exact cookie deletion and `204`, preserving idempotency without cross-site forced logout.
- V1 Web logout is explicitly local. It does not claim to clear the provider SSO cookie; the next JobPilot login sends `prompt=login` so shared-device users cannot be silently restored. A future RP-initiated provider logout is a separate reviewed capability.
- **Extension logout** first claims the refresh grant so it cannot concurrently rotate, then runs provider revocation and complete local cleanup independently in parallel. `confirmed` means both are confirmed with no unknown in-flight grant; `not_applicable` means no local/in-flight grant existed; `unconfirmed` means local cleanup completed but remote state cannot be proved. Failure to confirm local cleanup is a storage error, not successful logout. An already issued JWT remains valid until its short `exp` unless a provider/local deny mechanism explicitly covers it.
- **Revoke all sessions** remains deferred after Task 7. It requires recent authentication and reviewed provider capability; the current OpenAPI must not expose a partial route.
- **Refresh reuse/rejection** is treated locally as authentication failure: clear local credentials and require interactive login without logging token content. Provider-side refresh-family reuse detection/revocation and any future server security event are account-lifecycle capabilities that must be verified or implemented separately; the current client does not claim them.
- A failed **server-side future Web/revoke-all** deletion step could use its local User/session workflow anchor for durable retry. A failed **Extension direct revoke** cannot: JobPilot never receives that refresh token. The Extension still clears local credentials but warns that remote revocation was not confirmed and that a copied grant may remain renewable. Web recent reauthentication plus revoke-all is the accepted **future** recovery capability, not a currently available Task 6/7 endpoint; no automatic retry or completed remote revoke is claimed.

Access and refresh tokens, cookie values, authorization codes, PKCE verifiers, client secrets, session hashes, full claims, and provider error payloads never enter application logs.

## 9. Account Deletion

Account deletion is initiated from Web after recent provider reauthentication and explicit confirmation. It is an idempotent workflow, not a best-effort sequence hidden in one router.

### 9.1 Deletion order

1. Before returning `202` or starting cleanup, write a `pending` marker to an independent durable restore-control store outside ordinary application backups. The marker contains only a keyed `HMAC(User.id)`, HMAC key version, request time, workflow version/state, and nullable expiry; it contains no email, issuer/subject, or user content. HMAC key material stays in the restore-control KMS, never in application backups, and each version remains available until every marker using it has expired. If the marker write fails, do not acknowledge or begin deletion.
2. In one local transaction set `User.account_status=deletion_pending` and `deletion_requested_at`; every auth adapter immediately denies business access. Return `202` only after both the write-ahead marker and this transition are durable.
3. If the local transition fails after the marker write, return a dependency error and retain the `pending` marker for reconciliation. Any restore that finds a `pending`, `failed`, or `completed` marker quarantines the matching User rather than making it active.
4. Revoke all Web sessions and provider refresh grants. Use the still-present, non-login-capable User row plus the independent marker as retry anchors; attempts are idempotent and record only step/status metadata needed to resume.
5. Delete private objects and derived data, then relational child data.
6. Delete/disable the selected provider identity, revoke renewable grants, and record the provider acknowledgement/cutoff after which no new JobPilot API token can be issued. If this cannot be proved, keep the local User and marker pending and retry; never restore business access or silently reprovision.
7. Keep the local `(issuer, subject) -> deletion_pending User` mapping through a credential-quarantine interval of at least the configured maximum Extension access-token lifetime plus accepted clock skew, measured from the provider cutoff. Web callback and `POST /api/v1/auth/session` continue to resolve that mapping and reject it, so a residual JWT cannot provision a fresh User.
8. Only after child cleanup, provider acknowledgement, and the quarantine interval have all completed, hard-delete the local User and update the marker to `completed` with its calculated expiry.

The user loses interactive access when the local transition succeeds. JobPilot-controlled live stores should complete deletion as soon as operationally possible and within 30 days. Encrypted JobPilot production backups expire no later than 30 days after creation. Before a restore can receive traffic, the restore process uses every still-required key version to compute markers for restored User IDs and resumes/quarantines every match. Unresolved `pending`/`failed` markers and their keys never expire; after completion, a marker and its key version remain available until seven days after the newest JobPilot backup that could contain the user has expired, then may be removed after restore-safety verification.

Completed deletion intentionally permits future re-registration as a new account **after credential quarantine**. JobPilot does not retain a privacy-sensitive HMAC of `(issuer, subject)` to ban it: once every previously issued access token is outside its accepted lifetime, a later verified hosted flow creates a new `User.id`, and neither the deletion ledger nor matching email can reconnect old data. Any future longer re-registration ban would require a separate privacy review and ADR.

### 9.2 Resource policy

| Resource                  | Account deletion policy                                                                                                                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Job                       | Hard-delete user-owned snapshots and dedupe data                                                                                                                                                                        |
| Application               | Hard-delete records and internal status events                                                                                                                                                                          |
| ResumeVersion             | Delete private object first/with a recoverable workflow, then metadata and derived text                                                                                                                                 |
| Interview                 | Delete records plus future audio/transcript objects and derived evaluations                                                                                                                                             |
| Document                  | Delete original objects, metadata, chunks, embeddings, and processing artifacts                                                                                                                                         |
| Evidence                  | Delete mappings and dependent derived representations                                                                                                                                                                   |
| Logs/metrics              | Never contain credentials, user content, email, or provider subject; pseudonymous user correlation expires within 30 days and aggregate metrics contain no user-level identifier                                        |
| Backups                   | Encrypted, access-controlled, and retained at most 30 days from creation; pre-traffic restore must replay the independent deletion ledger                                                                               |
| Provider identity/records | Request identity deletion and record acknowledgement; Self-hosted IdP database/logs/backups enter JobPilot deletion and restore controls, while managed-only inaccessible records follow reviewed DPA/tenant capability |

Normal resource archive/history rules do not override account deletion. Before Phase 4 accepts resume uploads, object-store deletion, orphan recovery, and backup behavior must be implemented and tested.

### 9.3 Data export and retention policy

- Phase 2B exposes the current minimal User profile as machine-readable `GET /api/v1/auth/me`; it does not create an empty general-purpose export endpoint before business data exists.
- Before Phase 3 is accepted, JobPilot must freeze an account-export contract and support export of the User profile plus every owned Job. Each later resource joins that export in the same Phase that begins storing it; Phase 4 must include Application, ResumeVersion metadata, and original resume files before MVP acceptance.
- The deletion confirmation flow offers the current export before destructive confirmation, but export is optional and deletion cannot be held hostage by export generation. Export includes user-authored/profile data and owned records/files, while excluding credentials, session/provider internals, private object keys, security-only metadata, and the deletion ledger.
- Generated archives are private, authorization-checked, and short-lived. Phase 3 contract review must obtain project-owner approval for format, asynchronous status, download controls, and artifact TTL before implementation.
- Active-account business records otherwise follow their resource lifecycle. Direct identifiers and content are prohibited from authentication/security logs; a needed correlation value uses a rotating-key pseudonym and expires within 30 days. Any accidental directly identifying log field is treated as deletion-propagation scope, not as an exemption.
- The 30-day live-deletion deadline, 30-day maximum backup age, restore replay rule, ledger safety margin, and 30-day pseudonymous-log window apply to JobPilot-controlled stores and are Accepted V1 design limits. A Self-hosted Logto database, logs and backups are JobPilot-controlled and must be brought into these deletion/restore controls; exact schema propagation is frozen before deployment. Only managed-provider records that JobPilot cannot control use DPA/tenant disclosure. Making any accepted limit longer requires a new security review and explicit project-owner approval.

## 10. Authorization Boundary

Authentication proves who the caller is. It never proves that a requested resource belongs to that caller.

Every private repository/service operation requires the authenticated local user ID as an explicit input. A single-resource lookup follows this invariant:

```text
WHERE resource.id = :resource_id
  AND resource.user_id = :authenticated_user_id
```

The same compound boundary applies to update/delete, list filters, nested resources, idempotency keys, object keys, RAG retrieval, AI context selection, and references such as `job_id` or `resume_version_id`.

- Never fetch by resource ID and let React/Extension decide ownership.
- Never trust `userId` from path, query, body, header, provider metadata, or Extension message.
- A missing resource and another user's resource both return `404 RESOURCE_NOT_FOUND`.
- Cross-user relationship creation is rejected by querying every referenced record with the same authenticated user.
- Business tables reference local `User.id`, never provider `sub`.

V1 has one ordinary-user permission set. A generic RBAC layer would add complexity without solving the actual ownership boundary and is prohibited.

## 11. Threat Considerations

| Threat                                          | Primary control                                                                                          | Residual boundary                                                                     |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Web token theft through XSS                     | Opaque HttpOnly cookie; CSP and safe rendering                                                           | XSS may still perform actions, so CSRF alone is insufficient                          |
| Cookie CSRF                                     | Session-bound token, exact Origin, Fetch Metadata, SameSite                                              | Same-site compromised origins remain high risk and must not be broadly trusted        |
| Forced logout                                   | Exact allowed Origin + Fetch Metadata on every logout; CSRF additionally for a valid session             | A compromised allowed Web origin can still initiate logout                            |
| OAuth login CSRF/session swapping/open redirect | One-time state/nonce, browser-bound transaction cookie, exact callbacks, relative allowlisted `returnTo` | Compromised client code can still start malicious flows                               |
| Authorization-code interception                 | PKCE S256, one-time short code, exact redirect                                                           | Compromised browser profile remains outside app isolation                             |
| Extension refresh-token theft                   | Trusted-only local storage, rotation/reuse detection, revoke                                             | Browser/OS or signed Extension compromise can still read it                           |
| Rotation race/replay                            | Current-worker single-flight, versioned in-progress record, never replay ambiguous old token             | Safe failure may require interactive login; provider reuse behavior still needs tests |
| JWT confusion/forgery                           | Fixed issuer/audience/algorithm; trusted JWKS; time checks                                               | Provider signing-key compromise is a supplier incident                                |
| Unknown `kid` / provider outage                 | Fixed JWKS URI, per-issuer single-flight, cooldown, negative cache, rate limit, fail closed              | New logins/rotated keys may be temporarily unavailable                                |
| IDOR / cross-user access                        | `resource_id + user_id` in every query; cross-user negative tests                                        | Raw/manual SQL requires the same review discipline                                    |
| Credential leakage in logs/URLs                 | Redaction allowlist; no query credentials; structured safe errors                                        | Infrastructure access logs also require configuration review                          |
| Malicious recruitment page                      | Tokens never enter content/page contexts; typed message validation                                       | Extension compromise or excessive permissions remains critical                        |
| MV3 worker termination during rotation          | Versioned in-progress record; persist new refresh before access; ambiguous state requires login          | Safe failure can cause an extra interactive login                                     |
| Session fixation                                | Rotate opaque session after login/security changes                                                       | Stolen post-login cookie remains valid until revoke/expiry                            |
| Automatic account takeover by email linking     | `(issuer, subject)` identity; no automatic merge                                                         | Future provider migration needs explicit reauthentication                             |
| Provider/tenant misconfiguration                | Config review, exact origins/redirects, separate environments                                            | Managed auth reduces but does not outsource configuration responsibility              |

## 12. Local Development and Configuration

The Auth0-specific items below document the currently implemented adapter and deterministic profile; they are not active instructions to create a real tenant. ADR-007 pauses all real provider configuration.

- Dev and production use separate Auth0 applications/clients and API audiences; production secrets never enter local `.env` or the repository.
- Web localhost callbacks and the unpacked Extension callback are explicitly allowlisted, not wildcarded.
- A stable development Extension ID is required before registering its callback. The Auth0 public client ID and the 32-character Chrome Extension ID are distinct values. Current code obtains `https://<extension-id>.chromiumapp.org/` from `chrome.identity.getRedirectURL()` and accepts only that exact root callback shape; the manifest currently has no `key`, so stable dev/prod IDs and exact Allowed Callback URLs remain `USER ACTION REQUIRED`. Only a public manifest key/config may be committed; no signing private key is stored in Git.
- Public Extension configuration comprises the canonical HTTPS issuer, same-origin fixed authorize/token/JWKS/revoke endpoints, API audience, Auth0 Extension public client ID, validated JobPilot API base URL, and exact Web origin. Remote API/Web values require HTTPS; HTTP is limited to exact `localhost`, `127.0.0.1`, or `[::1]` loopback. No Extension client secret exists.
- Live Auth0 must use a Native/public application with Authorization Code + PKCE, `offline_access`, Rotating Refresh Token, approved access lifetime, and reviewed namespaced verified-email claims. FastAPI must receive the same public client ID for `azp` validation and exact `chrome-extension://<extension-id>` in `JOBPILOT_CORS_ORIGINS`; provider-side Allowed Web Origin/CORS for direct token/revoke is configured only if the real tenant requires it. Current revoke-only logout does not use an Auth0 hosted logout callback or Allowed Logout URL.
- Production requires HTTPS and the two `__Host-` cookies. Explicit development mode on loopback may instead use `jobpilot_dev_session` and `jobpilot_dev_login_tx` with `HttpOnly; SameSite=Lax; Path=/; no Domain` and without `Secure`; the transaction cookie retains `Max-Age=600`. Those names are forbidden outside loopback development, and non-loopback insecure startup fails.
- CI uses a deterministic fake issuer/JWKS and local session fixtures. It does not depend on a live provider tenant. After separate approval, a small manual/integration check against the selected non-production IdP verifies real redirect configuration and Mainland ordinary-network behavior.
- Provider domain, issuer, resource/audience, client IDs, exact origins, callback URLs, logout URLs, lifetimes, and required claims are validated configuration, not scattered literals.

## 13. Phase 2B Verification Requirements

### 13.1 Completed Task 6/7 deterministic gates

- valid Web login/session/logout plus session fixation, CSRF, Origin, Fetch Metadata, and cookie defenses;
- Extension state/nonce/PKCE handling, cancellation, expiry, exact callback, current-worker single-flight, termination at every rotation/storage boundary, ambiguous-outcome fail-closed behavior, provider rejection, dual trusted-storage boundaries, and direct-revoke outage messaging without false retry claims;
- JWT rejection for wrong issuer, audience, algorithm, signature, key, expiry, not-before, authorized party, and token type, plus bounded random-`kid` refresh behavior;
- exact CORS behavior for Web/Extension fixtures with no wildcard, and the same verified Web/Extension `(issuer, subject)` resolving to one local `User.id`;
- unverified email, `deletion_pending` identity, expired/revoked session, provider outage, API `401`, corrupt storage, and normal worker restart behavior;
- application/Uvicorn outputs, tracked source, built Popup bundle, and Extension storage/message surfaces contain no credential, code, verifier, cookie, raw provider payload, or sensitive claims;
- deterministic manifest/build evidence contains only `identity`, `storage`, exact API/provider origins, self-only CSP, and no Phase 3 content/tab capability.

### 13.2 Remaining integration and deferred account-lifecycle gates

- Task 8 is paused and may resume only after ADR-007 approval plus a separately approved provider deployment/protocol/Mainland verification slice; it still includes the test-only ownership fixture for user A versus user B resources;
- real Chrome Load unpacked, stable Extension origin/CORS, live provider redirect/token/rotation/revoke behavior, recovery delivery, and Mainland ordinary-network availability remain `NOT VERIFIED / BLOCKED`;
- production reverse proxies must drop/redact credential-bearing query data and production origins/headers must be verified in the actual deployment;
- the separately approved future account-deletion implementation must prove write-ahead marker gating, backup-restore quarantine, provider cutoff plus credential quarantine, non-reprovision, complete resource export/deletion, and fresh-User re-registration. These design gates do not claim that Task 6/7 shipped an account-deletion endpoint.

## 14. Explicit Non-goals

- No auth implementation or dependency in Phase 2A.
- No local password authentication, custom OAuth authorization server, MFA product, organization, team, RBAC, admin console, or enterprise SSO in V1.
- No direct Web/Extension access to PostgreSQL or any provider Management API.
- No login or account credential inside recruitment-page content scripts.
- No promise of zero-delay JWT revocation; the maximum bounded window is part of the contract.

## 15. Open Gate Items

ADR-006 and the deterministic Task 6/7 Phase 2B slices are implemented and reviewed. ADR-007 is `Proposed`: Self-hosted Logto OSS is the preferred candidate, Auth0 is no longer default-approved for production, and neither provider may be configured yet. Exact deployment region/domain, ordinary-Mainland-network results, recovery connector, issuer/resource/endpoints, client types, stable Extension ID, redirect/CORS, token claims/lifetimes, refresh/reuse/revoke behavior, provider data lifecycle and operations runbook remain `USER ACTION REQUIRED / NOT VERIFIED`. Tests continue to use a fake issuer/JWKS. Chrome Load unpacked remains `NOT VERIFIED`; Task 8 and Phase 3 remain paused pending explicit approval.
