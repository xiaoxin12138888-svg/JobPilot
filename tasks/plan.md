# Architecture Plan: Phase 2A Authentication Decision Gate

## Overview

Decide how one JobPilot identity is authenticated across the React Web app, Chrome Manifest V3 Extension, and FastAPI without implementing authentication. Phase 2A produced a reviewed and Accepted decision, security boundaries, a minimal Phase 2B contract, and synchronized planning documents, then stopped for project-owner approval. It installed no dependencies, created no auth schema, and wrote no authentication code.

## Assumptions and Boundaries

- Phase 0 and Phase 1 are approved and preserved in baseline commit `c8821a7e2ea966ebfd96f55dcec5d195c451fd57`.
- Work occurs on `phase/2-authentication`; the project owner has approved Phase 2A and explicitly requested its commit before Phase 2B implementation.
- V1 has one ordinary job-seeker role. Organizations, teams, administrator matrices, enterprise SSO, and RBAC are out of scope.
- PostgreSQL remains the source of truth for JobPilot business ownership. A managed identity provider, if selected, does not gain direct access to business resources.
- Authentication establishes an identity; every application service must still authorize access using both the authenticated user and requested resource identifier.
- No auth SDK, ORM, Alembic, provider account, OAuth app, database table, login UI, token implementation, or middleware is created in this phase.

## Decision Dependencies

```text
Approved Phase 0-1 constraints
  -> identity provider strategy
  -> Web credential transport
  -> Extension interactive login and credential storage
  -> FastAPI verification and authenticated-user mapping
  -> session/account lifecycle and authorization policy
  -> minimal Phase 2B API and data contracts
  -> cross-document acceptance review
```

## Task List

### Gate 1: Git Baseline and Context

- [x] Validate repository-local author and committer identity.
- [x] Inspect and commit the approved Phase 0-1 baseline without inventing historical commits.
- [x] Create and switch to `phase/2-authentication`.
- [x] Reload README, agent rules, product/architecture/engineering/API/data/roadmap documents, and all accepted ADRs.

### Gate 2: Architecture Comparison

- [x] Compare managed authentication, self-hosted FastAPI authentication, and OAuth/OIDC-centric authentication using the required qualitative criteria.
- [x] Select a minimal V1 strategy only after resolving Web, Extension, FastAPI, local-development, cost, maintenance, and migration trade-offs.
- [x] Freeze credential acquisition, storage, lifetime, rotation, revocation, logout, and failure semantics for both clients.

### Gate 3: Primary Decision Documents

- [x] Create `docs/DECISIONS/ADR-006-authentication-strategy.md`; preserve the accepted ADR-005 toolchain decision.
- [x] Create `docs/AUTH_ARCHITECTURE.md` with identity, Web, Extension, FastAPI, lifecycle, deletion, authorization, and threat boundaries.
- [x] Include readable Mermaid sequence diagrams for Web and Extension authentication.

### Gate 4: Contract Synchronization

- [x] Update only the User identity section and diagrams in `docs/DATA_MODEL.md`.
- [x] Replace the provisional pre-decision auth draft in `docs/API_CONTRACT.md` with the minimal Phase 2B contract implied by the decision.
- [x] Split Phase 2A and Phase 2B in `docs/ROADMAP.md` without changing later product sequencing.
- [x] Update the ADR index and current-phase wording in README/AGENTS where required.

### Gate 5: Acceptance Review

- [x] Verify Markdown links, headings, tables, and Mermaid block structure.
- [x] Verify terminology and lifecycle consistency across ADR, architecture, data model, API contract, roadmap, README/AGENTS, and task files.
- [x] Verify no dependencies, source code, database schema, auth UI, provider configuration, or Phase 2B implementation entered the diff.
- [x] Complete independent architecture, security, and contract reviews and resolve every required finding.
- [x] Record final Git status and stop for project-owner approval before Phase 2B; explicit approval has now been received.

## Verification Strategy

- Repository: `git status --short --branch`, `git diff --name-status`, `git diff --stat`, and `git diff --check`.
- Scope: changed-file allowlist plus searches for dependency/source/schema additions and forbidden Phase 2B implementation artifacts.
- Documentation: local link validation, required-section checks, Mermaid fence/diagram structural checks, and terminology searches.
- Architecture: independent reviews of option fit, browser/Extension token risks, FastAPI authorization, and account deletion.

## Risks and Mitigations

| Risk                                                                            | Impact                                                     | Mitigation                                                                                                                                    |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| A Web-only cookie design leaves the Extension unauthenticated                   | Phase 3 cannot safely save jobs                            | Make the Extension flow a first-class decision with explicit credential acquisition and storage                                               |
| Browser-stored long-lived credentials expand XSS or extension-compromise impact | Account/data exposure                                      | Prefer short-lived access credentials, protected refresh handling, rotation, revocation, and no tokens in page contexts                       |
| Managed auth is mistaken for business authorization                             | Cross-user data exposure                                   | Resolve every credential to a local User and scope repository/service queries by both user and resource ID                                    |
| Provider details leak through domain and API contracts                          | Vendor lock-in                                             | Store portable issuer/subject identity mapping and isolate provider validation/clients at the auth boundary                                   |
| Extension direct revoke fails after local cleanup                               | A copied refresh grant may remain renewable                | Distinguish local logout from remote confirmation, warn the user, and route recovery through Web recent-reauth plus revoke-all                |
| Account deletion/export/retention is documented vaguely                         | Sensitive data survives or cannot be recovered by the user | Freeze deletion state/order, phased export ownership, live/backup/log windows, restore ledger, and later object/vector cleanup responsibility |
| Phase 2A drifts into implementation                                             | Invalid stage gate                                         | Enforce a documentation-only changed-file allowlist and dependency/source-code diff check                                                     |

## Open Questions

- Will the project owner accept Auth0 reachability, remote-tenant development, pricing growth, data-processing, and migration trade-offs?
- Resolved: the project owner accepted the documented lifecycle design limits and Phase 3/4 export milestones; Phase 2B is not required to over-engineer future infrastructure to prove those long-term controls.
- Phase 2B code, dependency, and schema work is approved. Actual tenant/apps, origins, Extension IDs, redirects, claims, algorithms, lifetimes, Management API capabilities/minimum scopes, and secret values remain a separate user-action configuration gate and were not created in Phase 2A.
