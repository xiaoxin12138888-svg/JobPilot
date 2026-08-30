# Phase 2A Authentication Architecture Checklist

## Git Baseline

- [x] Repository-local `user.name` and `user.email` are configured; global Git configuration is untouched.
- [x] `GIT_AUTHOR_IDENT` and `GIT_COMMITTER_IDENT` resolve to the intended GitHub noreply identity.
- [x] Phase 0-1 baseline commit exists on `main` as `c8821a7e2ea966ebfd96f55dcec5d195c451fd57`.
- [x] `phase/2-authentication` exists and is checked out at the baseline commit.

## Context and Decision

- [x] Approved project documents and all existing ADRs have been reread.
- [x] Managed, self-hosted, and OAuth/OIDC-centric approaches are compared qualitatively.
- [x] The selected V1 architecture explicitly covers Web, Extension, and FastAPI.
- [x] Web cookie/bearer and Extension storage choices include XSS, CSRF, CORS, SameSite, MV3, and token-lifetime reasoning.

## Deliverables

- [x] `ADR-006-authentication-strategy.md` contains every required decision and consequence section.
- [x] `AUTH_ARCHITECTURE.md` contains identity, both client flows, FastAPI, lifecycle, revocation, deletion, authorization, and threats.
- [x] `DATA_MODEL.md` has only the minimum authentication-driven User changes.
- [x] `API_CONTRACT.md` exposes only the minimum Phase 2B JobPilot auth/session contract.
- [x] `ROADMAP.md` distinguishes Phase 2A architecture from Phase 2B implementation.
- [x] ADR index, README/AGENTS, and task files reflect the current phase.

## Security and Scope

- [x] Resource access requires `resource_id + authenticated_user_id`; cross-user misses return `404`.
- [x] Account create/login/logout/expire/revoke/delete and future resource deletion responsibilities are defined.
- [x] Data export ownership, live/backup/log retention, restore ledger, and deletion propagation have explicit owner gates and verification milestones.
- [x] No token, password, secret, provider credential, or sensitive content is logged or placed in URLs.
- [x] No RBAC, organization, team, admin, or enterprise IAM design was added.
- [x] No dependency, source-code, schema, UI, provider account, OAuth app, or middleware implementation was added.

## Acceptance

- [x] Markdown links, Mermaid structure, required headings, and terminology checks pass.
- [x] Independent architecture/security/contract reviews have no unresolved required findings.
- [x] Git diff contains only approved Phase 2A documentation and planning changes.
- [x] Work stopped before Phase 2B; explicit project-owner approval and Phase 2A commit authorization have now been received.
