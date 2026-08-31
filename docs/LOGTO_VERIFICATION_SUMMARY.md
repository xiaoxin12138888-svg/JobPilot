# Logto Verification Summary

> Status: `BLOCKED — USER ACTION REQUIRED`
>
> Evidence rule: never include raw token, authorization code, PKCE verifier, cookie, secret, client identifier, email, subject, local User ID, or provider payload. Link only redacted evidence.

## ADR-007 Status

- Status: `Accepted — Provider Direction`
- Authorized slice: `Logto Verification Slice — Protocol & Mainland MVP Gate`
- Production cutover: `NOT AUTHORIZED`
- Migration / Task 8 / Phase 3: `NOT AUTHORIZED`

## Logto Version

- Logto OSS version: `v1.42.0`
- Release source: [official v1.42.0 release](https://github.com/logto-io/logto/releases/tag/v1.42.0), peeled commit `3a8f4a6ef2a00fec105d802c7dd3fbb520a07a3d`
- Image digest or immutable artifact reference: `ghcr.io/logto-io/logto:1.42.0@sha256:aac94e24ab7bef59be5d1809b1481b179495aaa75bb9dc2895ceae46e4117854`
- License: `MPL-2.0`
- PostgreSQL reference: official `postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`
- Minimum runtime: official recommendation `2 vCPU / 8 GiB RAM / 256 GiB disk`; pinned container supplies Node, source engine is `^22.14.0`
- Verification timestamp and timezone: `2026-08-31 / Asia/Shanghai`

## Deployment Used

- Environment: `LOCAL / ISOLATED DEVELOPMENT — COMPOSE BASELINE CREATED; RUNTIME NOT STARTED`
- Logto database: `INDEPENDENT POSTGRESQL 17 WITH DEDICATED VOLUME — NOT STARTED`
- Web confidential application: `NOT CREATED — RUNTIME BLOCKED`
- Extension public application / no client secret: `NOT CREATED — RUNTIME BLOCKED`
- JobPilot API resource: `NOT CREATED — RUNTIME BLOCKED`
- Production/paid/social/MFA/RBAC/SMS resources created: `NO`
- Redacted evidence references: [`infra/logto`](../infra/logto/README.md), [official artifact evidence](../infra/logto/OFFICIAL_ARTIFACT_EVIDENCE.md), and [local runtime blocker evidence](../infra/logto/LOCAL_RUNTIME_EVIDENCE.md)

## Web OIDC Verification

- Result: `BLOCKED`
- Flow exercised: `NOT RUN`
- Issuer/discovery/endpoints/client authentication: `NOT OBSERVED`
- ID-token/nonce/email-verification profile: `NOT OBSERVED`
- Evidence: current Task 6 code/profile audit only; no live Logto response
- Blocker or failure: no Docker/Podman/Linux-container runtime, no usable WSL distribution, no local PostgreSQL, and no trusted local HTTPS issuer boundary

## Extension PKCE Verification

- Result: `BLOCKED`
- Authorization Code + PKCE S256: `NOT RUN`
- Public client / no secret: existing Task 7 invariant retained; live Logto app not created
- Exact callback: current code requires exact `https://<extension-id>.chromiumapp.org/` root; live registration not performed
- Resource/code exchange/offline access: `NOT RUN`; static audit confirms current authorize request sends Auth0-style `audience`, not Logto RFC 8707 `resource`
- Evidence: current Task 7 code/profile audit only; no live browser/provider response
- Blocker or failure: isolated Logto runtime and trusted HTTPS endpoint are unavailable; Chrome flow cannot be exercised

## Token Profile

- Issuer/discovery consistency: `NOT OBSERVED`
- Signing algorithm and `typ`: live Logto token `NOT OBSERVED`; current validator requires `RS256` and `typ=JWT`
- API resource/audience: live value `NOT OBSERVED`; `audience` to RFC 8707 `resource` request adaptation is required
- Authorized-client claim: live value `NOT OBSERVED`; current validator requires exact Extension `azp`, while Logto `client_id`/claim profile requires verification
- Access-token lifetime and scopes: `NOT OBSERVED`; current contract requires integer lifetime `1–600` seconds and the approved scopes
- Required identity/email claims: `NOT OBSERVED`; current bearer adapter requires two exact namespaced verified-email claims
- No raw credential or identity value included: `CONFIRMED`

## Refresh / Revoke Compatibility

- Result: `NOT VERIFIED — BLOCKED`; no `COMPATIBLE / ADAPTER CHANGE REQUIRED / CONTRACT INCOMPATIBLE` refresh/revoke classification is possible without a live grant
- Replacement/rotation behavior: `NOT OBSERVED`; current lifecycle requires a different replacement refresh token after every success
- Reuse behavior: `NOT OBSERVED`
- Revoke/logout behavior: `NOT OBSERVED`; current Extension uses public-client RFC 7009 direct revoke and local logout
- Existing fail-closed lifecycle preserved: `YES IN CURRENT CODE`; real Logto behavior not yet proven compatible
- Evidence: current lifecycle contract audit only; the separately confirmed `audience` to `resource` authorization-request seam does not prove refresh/revoke behavior

## Same Identity Verification

- Web issuer vs Extension issuer: `NOT VERIFIED — RUNTIME BLOCKED`
- Web subject vs Extension subject: `NOT VERIFIED — RUNTIME BLOCKED`
- JobPilot User.id: `NOT VERIFIED — RUNTIME BLOCKED`
- Sensitive values omitted: `CONFIRMED`

## Mainland No-Proxy Smoke Test

> Point-in-time MVP development evidence only. It never satisfies the Production Release Gate.

- Fixed broadband: `BLOCKED — USER ACTION REQUIRED`
- Mobile network/hotspot: `BLOCKED — USER ACTION REQUIRED`
- VPN/proxy/special DNS absent: current WinHTTP reports direct access, but no Logto/JobPilot smoke was run and this is not PASS evidence
- Operator/network type/region, minimized: `NOT CAPTURED`
- Device, OS, browser and Extension version: `NOT CAPTURED`
- Flows exercised: `NONE — PROVIDER RUNTIME NOT STARTED`
- Observed runtime dependency hosts, redacted: `NOT OBSERVED`; the connector-free Compose intentionally blocks container egress, but live verification is still required
- Evidence: local runtime inventory only; no network-flow evidence
- USER ACTION REQUIRED: provide a usable Linux Docker/Compose environment, then perform separate fixed-broadband and mobile/hotspot runs with VPN/proxy/special DNS disabled
- Observed failure: verification could not start because the host has no Docker, Podman, usable WSL distribution or PostgreSQL

## Existing Code Reuse

- Task 5: `STATIC PROVISIONAL — LIKELY MINOR ADAPTER CHANGE` because identity domain/service/mapping/API remain provider-neutral; final grade awaits the live bearer profile
- Task 6: `STATIC PROVISIONAL — LIKELY MINOR ADAPTER CHANGE` because WebAuthProvider protocol, transactions and opaque session remain provider-neutral; final grade awaits client-auth, ID-token and browser flow evidence
- Task 7: `STATIC PROVISIONAL — UNCONFIRMED` because PKCE, storage, orchestration, worker and Popup are provider-neutral, but replacement refresh/reuse/revoke may still force a lifecycle contract change; final grade is blocked
- Authentication migration performed: `NO`

## Required Adapter Changes

- Changes required: Logto Web adapter/profile; Extension RFC 8707 `resource` request propagation; exact `client_id`/`azp`, ID/access-token header and verified-email claim adapter; verified refresh/revoke parameters. Trusted HTTPS development issuer setup is also required before live integration.
- Provider-neutral contract change required: `NO BASED ON STATIC AUDIT; LIVE VERIFICATION BLOCKED`
- Changes implemented in this Slice: `NO`

## Bugs Found

- Critical: `0`
- Required: `0 code bugs confirmed; 1 environment blocker`
- Optional: `0`

## Security Review

- Critical: `0`
- Required: local secret must remain ignored/redacted; trusted HTTPS, empty-volume initialization, persistence, token profile and runtime dependency behavior must be proven before PASS
- Optional: `0`
- Unresolved Critical/Required: live security evidence is blocked by the missing runtime; no security invariant was waived

## MVP Development Gate

- Result: `BLOCKED`
- Rationale: fixed artifacts and an isolated Compose baseline are ready, but no Logto/PostgreSQL process, application/resource configuration or live Web/Extension flow exists
- Missing evidence or blocker: Docker/Podman/Linux-container runtime or another approved isolated Linux Docker host; trusted local HTTPS; Web/Extension/token/refresh/revoke/same-identity evidence; fixed-broadband and mobile smoke
- Production readiness claimed: `NO`

## Production Release Gate

- Status: `DEFERRED`
- Multi-carrier/region/long-window matrix: `DEFERRED`
- Formal Extension signing/distribution/update/N-1/rollback: `DEFERRED`
- Full backup/restore and DR: `DEFERRED`
- Formal recovery-delivery SLA: `DEFERRED`
- Production monitoring: `DEFERRED`
- ICP/compliance: `DEFERRED`
- This MVP smoke satisfies the Production Release Gate: `NO`

## Current Git Status

- Branch: `phase/2-authentication`
- HEAD: result commit is reported in the final handoff; parent authorization baseline is `9c08d57`
- Worktree: target `CLEAN AFTER RESULT COMMIT`; final handoff must verify it
- Secrets or production configuration tracked: `NO`
- Migration or Phase 3 changes present: `NO`

## Next Step

- If MVP PASS: `Minimal Logto Adapter Migration — REQUIRES SEPARATE PROJECT-OWNER AUTHORIZATION; DO NOT START AUTOMATICALLY.`
- If MVP BLOCKED: `USER ACTION REQUIRED: install/enable a modern Linux Docker + Compose runtime (Docker Desktop with a usable WSL2 backend, or provide an approved isolated Linux Docker host), then rerun this Slice; separately provide fixed-broadband and mobile/hotspot network switching for the no-proxy smoke.`
- If MVP FAIL: `STOP — record incompatibility; do not start migration.`
- Phase 3: `NOT AUTHORIZED`
