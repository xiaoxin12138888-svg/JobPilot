# Implementation Plan: Phase 1 Engineering Skeleton

## Overview

Build the smallest runnable JobPilot monorepo skeleton: a React/Vite Web app, a Manifest V3 Extension popup, a FastAPI health endpoint, and one shared TypeScript health contract/client. No authentication, persistence, recruitment-platform parsing, AI, RAG, or product UI is included.

## Architecture Decisions

- Use one pnpm workspace for all TypeScript packages and one uv project for the Python API; commit both lock files.
- Treat `GET /health` as an unversioned infrastructure probe. Business APIs remain under `/api/v1` from Phase 2 onward.
- Keep one `VITE_API_BASE_URL` source at the repository root. The Extension build derives its API host permission from that value.
- Use `activeTab` only for reading the active tab URL when the user opens the popup; add no recruitment-site host permissions, background worker, or content-script behavior.
- Defer PostgreSQL and ORM setup because Phase 1 has no persistence consumer.

## Task List

### Foundation

- [x] Task 1: Initialize Git, workspace metadata, ignore rules, environment example, and project rules.
- [x] Task 2: Add pnpm/uv dependency manifests and generate reproducible lock files.
- [x] Task 3: Record Phase 1 documentation refinements and the package-management ADR.

### Checkpoint: Foundation

- [x] Workspace discovery succeeds and lock files are current.
- [x] No empty future-facing application or domain modules exist.

### API Slice

- [x] Task 4: Write failing health and CORS configuration tests.
- [x] Task 5: Implement the minimal FastAPI app and make the API tests pass.
- [x] Task 6: Run Ruff and API import/startup validation.

### Shared Contract Slice

- [x] Task 7: Write failing API-client tests for health success, malformed responses, and HTTP failure.
- [x] Task 8: Implement `ApiHealthResponse` and `getHealth`, then pass tests, lint, and typecheck.

### Web Slice

- [x] Task 9: Write a failing Web smoke test for the Phase 1 status page.
- [x] Task 10: Implement the minimal accessible Web page and API connection states.
- [x] Task 11: Pass Web tests, build, lint, and typecheck.

### Extension Slice

- [x] Task 12: Write failing popup and manifest/permission tests.
- [x] Task 13: Implement the popup, active-tab URL lookup, API status, and MV3 manifest build.
- [x] Task 14: Pass Extension tests, build, lint, and typecheck.

### Completion

- [x] Task 15: Run all repository quality gates and inspect the unpacked Extension output.
- [x] Task 16: Perform five-axis code review and resolve all required findings.
- [x] Task 17: Perform behavior-preserving simplification and rerun affected checks.
- [x] Task 18: Update README and Phase 1 documentation to match the verified implementation.

## Completion Evidence

- The reproducible green state is 16 TypeScript tests and 5 API tests, plus both production builds, ESLint, TypeScript strict typecheck, Prettier, Ruff, frozen pnpm install, locked uv sync, and API import validation.
- Real-browser Web checks cover the live health connection, clean console, accessibility structure, and 320/768/1024/1440 px responsive layouts.
- The unpacked Extension output was structurally inspected; the isolated browser did not expose a load-unpacked capability, so loading it in an actual Chrome extension manager remains a documented manual check.
- Initial RED console output for Tasks 4, 7, 9, and 12 was session-local and is not a repository artifact. This continuation preserved explicit RED→GREEN evidence for public API URL credential rejection and Web build-time environment validation.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Extension API URL and host permission drift | Extension health request fails | Generate `host_permissions` from the same root API base URL used by runtime config |
| Development CORS becomes an unsafe production default | Future private API exposure | Reject wildcard origins and require explicit production origins |
| Toolchain sprawl | Maintenance overhead | pnpm only for TypeScript; uv only for Python; Ruff covers Python lint/format |
| Phase 2 scope leakage | Invalid Phase 1 delivery | No database, auth, business entities, adapters, or placeholder services |

## Open Questions

- None block Phase 1. Authentication and persisted data boundaries remain Phase 2 decisions.
