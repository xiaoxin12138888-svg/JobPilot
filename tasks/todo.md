# Phase 2.5 — Local Runtime Foundation Checklist

## Safety and scope

- [x] Confirm clean `phase/2-authentication` at `bab46af18c6c060082bc47bacfb6dedc26822755`.
- [x] Create `phase/2.5-local-runtime` without deleting the old branch or rewriting history.
- [x] Preserve checkpoint `pre-local-first-cleanup`.
- [x] Keep Phase 3, business models/APIs, recruitment adapters, content scripts, AI, and RAG out of scope.

## Storage decision

- [x] Add ADR-009 and compare SQLite/PostgreSQL on the approved criteria.
- [x] Accept SQLite as the only current runtime database and supersede the PostgreSQL storage choice.
- [x] Keep SQLAlchemy 2.x and Alembic; do not add a database strategy or dual mode.

## SQLite TDD and implementation

- [x] RED: default database resolves to `runtime-data/jobpilot.db` without `DATABASE_URL`.
- [x] RED: initialization creates the directory/database and restart preserves existing data.
- [x] RED: every connection has `foreign_keys=ON` and a bounded busy timeout.
- [x] RED: supported API startup initializes SQLite before Uvicorn.
- [x] GREEN: implement the smallest SQLite engine/path/initialization flow.
- [x] Prove Alembic connects to an explicit temporary SQLite database.
- [x] Prove tests do not create or modify the real runtime database.
- [x] Keep rollback journal mode unless present evidence justifies WAL.

## PostgreSQL removal

- [x] Remove psycopg from `pyproject.toml` and `uv.lock`.
- [x] Remove PostgreSQL/libpq/PGHOSTADDR URL logic and tests.
- [x] Remove PostgreSQL-only environment variables.
- [x] Remove PostgreSQL-only statements from active documentation.
- [x] Confirm no runtime PostgreSQL consumer remains.

## Health client TDD

- [x] RED: a hanging health request is aborted after a small default timeout.
- [x] GREEN: implement one AbortController-based timeout without automatic retry.
- [x] Preserve Web and Extension unavailable/manual retry behavior.

## Extension artifact and real runtime

- [x] Build `apps/extension/dist` and validate its required structure.
- [x] Add an automated artifact gate for remote code, CSP, permissions, hosts, background, and content scripts.
- [x] Attempt real Chrome Load unpacked and report PASS/BLOCKED truthfully.
- [x] Verify real Popup ready → unavailable → retry → ready when tooling permits.
- [x] Determine whether users still need to copy the Extension ID into CORS settings.
- [x] Keep wildcard CORS forbidden.
- [x] Verify no-proxy local runtime when tooling permits.

## Documentation

- [x] Update README first-run flow and local configuration.
- [x] Update architecture, data model, engineering principles, roadmap, decision index, and active ADR amendments.
- [x] Update product/API/agent context where old PostgreSQL or Extension-ID statements would otherwise conflict.
- [ ] Keep unsupported future capabilities explicitly unimplemented.

## Complete validation

- [ ] `pnpm install --frozen-lockfile`.
- [ ] `uv sync --project apps/api --locked`.
- [ ] `pnpm test`, lint, format check, typecheck, Web build, Extension build.
- [ ] API tests, lint, format check, import check.
- [ ] SQLite clean-temp initialization, restart persistence, Alembic connection.
- [ ] API startup and `GET /health`.
- [ ] Secret, remote-runtime, proxy/telemetry, manifest/CSP, loopback, tracked-artifact scans.
- [ ] `git diff --check` and final `git status`.

## Review and delivery

- [ ] Run `code-review-and-quality`; resolve Critical and Required findings.
- [ ] Run `code-simplification`; remove confirmed dead Phase 2.5 code only.
- [ ] Commit coherent, verified increments.
- [ ] Produce the required Phase 2.5 Summary and stop before Phase 3.
