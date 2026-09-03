# Implementation Plan: Phase 2.5 — Local Runtime Foundation Finalization

> Execution status（2026-09-03）：Tasks 1–8 已完成；真实 Chrome 与项目负责人确认已经关闭 Extension-ID CORS 和 no-proxy 两项不确定性。完整验收、五轴审查、简化和文档同步均通过。Phase 3 仍未开始。

## Objective

Finalize the local runtime foundation without entering Phase 3. Replace the unused local
PostgreSQL skeleton with one SQLite database at `runtime-data/jobpilot.db`, keep SQLAlchemy 2.x
and Alembic, add a bounded health request timeout, and prove the Chrome Extension artifact is
minimal and safe. Real Chrome verification is required when tooling permits; otherwise the gate
must remain `BLOCKED / NOT VERIFIED` until the project owner performs the documented steps.

This work starts from clean `phase/2-authentication` at
`bab46af18c6c060082bc47bacfb6dedc26822755` on branch `phase/2.5-local-runtime`. The
`pre-local-first-cleanup` checkpoint and `phase/2-authentication` branch remain untouched. Do not
implement Job, Application, ResumeVersion, recruitment adapters, content scripts, AI, RAG, or
any other Phase 3 capability.

## Architecture Decisions

- SQLite is the only runtime database. There is no dual-database mode, strategy factory, or
  PostgreSQL compatibility layer.
- The repository-relative default is `runtime-data/jobpilot.db`; the supported launcher creates
  the directory and database on first run and reuses them on later runs.
- Tests always pass an explicit temporary database path and never read, replace, or delete the
  real runtime database.
- SQLAlchemy owns connections and transaction boundaries. Every SQLite connection enables
  `PRAGMA foreign_keys=ON` and a small busy timeout. WAL is enabled only if runtime evidence shows
  a present need; the current empty, single-process foundation defaults to the simpler rollback
  journal.
- Alembic remains the schema migration mechanism and uses the same SQLite URL resolution as the
  supported runtime.
- The health client gets one small request timeout with user-triggered retry; no retry framework
  or background polling is introduced.
- The Extension remains Popup-only with one exact loopback host permission and no remote code,
  background worker, content script, privileged permission, proxy, storage, identity, or
  telemetry surface.

## Ordered Tasks

### Task 1 — Record the SQLite storage decision

**Acceptance criteria:**

- ADR-009 compares SQLite and PostgreSQL on the requested criteria and accepts SQLite as the only
  current runtime database.
- ADR-002 and ADR-008 are explicitly superseded only where they selected PostgreSQL.
- Phase 3 remains unstarted.

**Verification:** Markdown formatting, decision links, `git diff --check`.

**Dependencies:** None.

### Task 2 — TDD the SQLite runtime contract

**Acceptance criteria:**

- Failing tests first require the default repository-local path, automatic directory/database
  creation, restart persistence, `foreign_keys=ON`, hidden SQL parameters, and temp-only test data.
- The supported server initializes the configured/default database before Uvicorn starts.
- Initialization is idempotent and uses explicit SQLAlchemy transaction boundaries.

**Verification:** Targeted Pytest RED, minimal GREEN, then all API tests/lint/format/import checks.

**Dependencies:** Task 1.

### Task 3 — Remove PostgreSQL-only runtime surface

**Acceptance criteria:**

- Remove psycopg and all libpq/PGHOSTADDR/PostgreSQL URL helpers, tests, environment variables,
  and active documentation.
- Keep SQLAlchemy 2.x and Alembic with one SQLite URL contract and no database strategy layer.
- Regenerate `uv.lock` and prove locked installation.

**Verification:** PostgreSQL residual scan, locked uv sync, API gates.

**Dependencies:** Task 2.

### Checkpoint — Storage foundation

- SQLite tests and API gates pass.
- A clean temporary database initializes twice without replacement.
- Alembic connects to the same temporary database.
- The real `runtime-data/jobpilot.db` is untouched by tests.

### Task 4 — TDD a bounded health request

**Acceptance criteria:**

- Failing client test proves an overlong request is aborted after a small default timeout.
- Web and Extension keep their existing checking/ready-or-available/unavailable and manual retry
  behavior.
- No automatic retry framework or remote dependency is added.

**Verification:** api-client, Web, and Extension tests plus typecheck/build.

**Dependencies:** None.

### Task 5 — Make Extension artifact checks executable

**Acceptance criteria:**

- A small automated gate builds and inspects `apps/extension/dist`.
- The gate rejects remote scripts, `unsafe-eval`, proxy/auth/storage/tab permissions, unexpected
  hosts, content scripts, and background workers.
- The built artifact contains only bundled local runtime assets and the exact loopback target.

**Verification:** Extension tests, production build, artifact gate, manifest/CSP scan.

**Dependencies:** Task 4.

### Task 6 — Real Chrome and CORS verification

**Acceptance criteria:**

- Attempt Load unpacked using available browser tooling and truthfully report PASS/BLOCKED.
- Verify ready, unavailable, and retry recovery against the real local FastAPI process when
  possible.
- Determine from real Chrome behavior whether an Extension ID must be copied into CORS config;
  never replace exact origins with wildcard CORS.

**Verification:** Real Popup console/network/runtime evidence, or explicit `USER ACTION REQUIRED`.

**Dependencies:** Tasks 2 and 5.

**Recorded evidence:** Chrome Load unpacked 无 manifest/load error、无 JobPilot service worker；真实 Popup 完成 available → API stopped/unavailable → restart + Retry/available。Extension ID 为浏览器安装细节，不需要复制到 CORS；Extension 依靠精确 loopback host permission，API CORS 只服务 Web。项目负责人确认验证时未手动配置 `.env`/Extension ID，并关闭 VPN/系统/浏览器代理。

### Task 7 — Synchronize local-runtime documentation

**Acceptance criteria:**

- README first run no longer requires `.env`, PostgreSQL, Docker, cloud accounts, VPN, or proxy.
- Canonical architecture/data/principles/roadmap/decision/task documents describe SQLite and the
  real Extension/CORS finding.
- No active document presents Job/Application/Adapter/AI as implemented.

**Verification:** Stale-reference/link/format scans and manual cross-document review.

**Dependencies:** Tasks 3 and 6.

### Task 8 — Full validation, review, and simplification

**Acceptance criteria:**

- All requested frozen/locked install, test, lint, format, typecheck, build, API, SQLite, runtime,
  security, Extension, and Git gates run with recorded results.
- `code-review-and-quality` reaches Critical 0 / Required 0.
- `code-simplification` removes only confirmed Phase 2.5 dead code and adds no abstraction.
- Commits are coherent, branch/HEAD are reported, and Phase 3 is not started.

**Verification:** Final validation matrix and clean working tree.

**Dependencies:** Tasks 1–7.

## Risks and Mitigations

- **User data deletion:** all automated database tests use temporary directories; cleanup commands
  never target `runtime-data/`.
- **CORS assumptions:** only real Chrome evidence can mark the Extension/CORS gate PASS; otherwise
  keep it blocked and request the exact manual test. Phase 2.5 已取得该证据，当前实现不接受 Extension origin。
- **SQLite concurrency:** keep the single-process default simple, enable foreign keys and a bounded
  busy timeout, and defer WAL until actual concurrent writes exist.
- **Scope drift:** no business tables or APIs are created; empty metadata and migration history are
  valid until Phase 3 is separately approved.

## Final Gate

Phase 2.5 can pass only with Critical 0 / Required 0 and real Chrome evidence for the requested
manual gates. If Chrome cannot be controlled, report
`PHASE 2.5 BLOCKED — USER ACTION REQUIRED` and stop without entering Phase 3.
