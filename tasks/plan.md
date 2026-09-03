# Implementation Plan: Phase 3 — Job & Application Domain Foundation

> Owner-approved on 2026-09-03. Phase 4 is not authorized.

## Objective

Deliver a genuinely usable local workflow: manually create a Job, browse and edit the job library,
create one Application, explicitly confirm real submission, track its allowed status, and preserve
the data across restart. Keep the existing single-user, loopback-only, SQLite and no-proxy boundaries.

## Frozen decisions

- Only `manual` Jobs can be created. A normalized HTTP/HTTPS source URL is unique; no URL means no fuzzy dedupe.
- Job deletion is explicitly confirmed in Web and cascades its one optional Application.
- Application statuses are `planned`, `applied`, `screening`, `assessment`, `interviewing`, `offer`, `rejected`, `withdrawn`, `closed`.
- Every transition into `applied` requires `confirmApplied: true`. Opening `source_url` never mutates state.
- API JSON is camelCase. Lists use bounded `limit`/`offset` (50 default, 100 maximum).
- Domain rules and services stay outside routers. Repositories are business-specific, not generic CRUD.
- Only `jobs` and `applications` are migrated. Tests use explicit temporary databases.

## Ordered work

1. Synchronize canonical contracts and ADR-010.
2. RED/GREEN domain validation, URL normalization and Application transition rules.
3. RED/GREEN Alembic migration, constraints, repository persistence and automatic startup upgrade.
4. RED/GREEN Job and Application services/API, public errors and localhost write boundary.
5. Add shared transport types and a validating credential-free API client.
6. Build the responsive Job library, manual form, details and Application controls.
7. Verify full automation, real browser sizes/states, restart persistence and no-proxy runtime.
8. Resolve Critical/Required review findings, simplify, update docs and stop before Phase 4.

## Final gate

Phase 3 passes only when the specified real scenario survives API/Web restart, all automated gates
pass, real browser validation covers 320/768/1024/1440 and review reaches Critical 0 / Required 0.
