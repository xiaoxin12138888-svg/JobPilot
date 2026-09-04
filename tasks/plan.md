# Implementation Plan: Phase 4 — BOSS Direct Job Capture

> Owner-approved on 2026-09-03. Phase 5 is not authorized.
> Completed and accepted on 2026-09-04. Stop before Phase 5.

## Objective

Deliver one user-triggered, local-only vertical path from a specific BOSS 直聘 Job detail page,
through an editable Extension preview and the existing Job API/service, into SQLite and the JobPilot
Web Job library. Do not crawl, call BOSS APIs, automate applications, or add another platform.

## Frozen contract

- The only new source is `boss`; its user-facing label is `BOSS直聘`. `manual` remains supported.
- `JobCaptureDraft` reuses `CreateJobInput`: `source`, `sourceUrl`, `title`, `company`, `location`,
  `salaryText`, and plain-text `description`. Parser `warnings` stay inside the Extension.
- `title` and `company` are required before save. Optional missing fields produce warnings and remain
  editable. The API remains the authoritative length, control-character, source, and URL boundary.
- `sourceUrl` is the active tab HTTP/HTTPS URL. BOSS capture accepts only a verified BOSS Job detail
  hostname/path; DOM content cannot supply or replace it.
- The Extension uses `activeTab` + `scripting`, executes one read-only parser after a user click, and
  registers no persistent content script, background worker, BOSS host permission, or broad host.
- Save reuses `POST /api/v1/jobs`. Duplicate normalized URLs remain `409 DUPLICATE_JOB_URL`; the
  additive optional `resourceId` identifies the existing local Job so the Popup can open it.
- The `jobs.source` CHECK expands reversibly from `manual` to `manual|boss`; no other schema or table
  is added. Migration tests use temporary databases and a copy of runtime data, never the live file.
- Opening the original BOSS URL or saving a Job never creates or mutates an Application.

## Ordered work

1. Freeze this plan, ADR-011, API/data/permission contracts, and the Phase 4 stop boundary.
2. RED/GREEN source validation, plain-text sanitization, duplicate existing-Job metadata, and the
   reversible SQLite migration; prove Phase 3 manual/Application regression.
3. Observe a real user-opened BOSS Job detail page with VPN/proxy off; record only the minimum
   selector evidence needed for the Adapter.
4. RED/GREEN one `BossAdapter`: strict page detection, five field parsers, warnings, normalization,
   odd-text handling, and minimal sanitized fixtures.
5. RED/GREEN Popup states and user flow: health, explicit capture, preview/edit, save, duplicate,
   retry, manual fallback, and safe local Job detail link.
6. Add only necessary Web changes: source labels, captured Jobs in the library, and a local-ID detail
   deep link. Preserve the manual form and full Application lifecycle.
7. Run locked installs, affected/full automated gates, builds, migration upgrade/downgrade/upgrade,
   runtime persistence, artifact/CSP/secret/remote scans, and `git diff --check`.
8. Load the unpacked build in Chrome with action-time approval; validate the real BOSS flow,
   duplicate behavior, console/network/privacy, no-proxy operation, restart persistence, and Web at
   320/768/1024/1440.
9. Resolve all Critical/Required review findings, run the simplification pass, synchronize docs, and
   stop before Phase 5.

## Checkpoints

- Backend checkpoint: API/domain/migration/client tests and manual Job/Application regression pass.
- Capture checkpoint: live-DOM-informed Adapter tests pass with no over-collection or hidden API.
- UI checkpoint: Extension/Web tests, typecheck, lint, format, builds, and artifact gate pass.
- Final checkpoint: real no-proxy capture and duplicate scenario pass; review is Critical 0 /
  Required 0; tracked worktree is clean except the untouched `操作手册.txt`.

## Risks and mitigations

- BOSS DOM may change: use one evidence-based selector set with a few semantic fallbacks and warnings.
- Chrome user state is sensitive: inspect only visible necessary DOM; never read cookies, storage,
  tokens, recruiter private data, full-page snapshots, or unrelated tabs.
- SQLite constraint replacement can lose data if mishandled: use a reversible migration and verify
  it on fresh temporary data plus a copy of the real database.
- Duplicate save can race: keep normalized URL uniqueness in SQLite and return only the existing
  local Job ID in the bounded 409 error.

## Acceptance evidence

The project owner kept one real BOSS Job detail tab open with VPN/system/browser proxy off. The
stable-ID unpacked Extension completed capture, editable preview, first save and duplicate handling;
the Web detail showed the BOSS snapshot with no Application. API restart preserved the same Job ID,
canonical queryless URL and zero Applications. No credentials or session material were collected.
