# Implementation Plan: Phase 6 — JD Structured AI Analysis

> Owner-approved on 2026-09-04. Phase 7 is not authorized.

## Objective

Turn one saved Job description into an optional, strict, evidence-grounded structured analysis,
persist one current result in local SQLite, and display it beside the always-visible original JD.
Do not add Resume/Evidence Map, matching scores, RAG, Agent frameworks, mock interviews or another
recruitment platform.

## Frozen contract

- Call chain is Web → FastAPI → JDAnalysisService → one OpenAI-compatible provider adapter.
- AI configuration is optional process environment; Key never enters browser bundles, Git, logs,
  errors or SQLite. Missing/malformed configuration cannot prevent core startup.
- Input is only title/company/description plus optional location/salary. JD is untrusted data.
- Schema version 1 and EvidenceItem fields are frozen by ADR-013; missing data is empty, unsupported
  evidence becomes null, invalid provider output is never persisted.
- One `jd_analysis_records` row per Job stores canonical JSON and the exact analysis-input fingerprint.
  GET computes stale; reanalysis updates; Job deletion cascades.
- GET returns `200` with `isConfigured` and nullable analysis for an existing Job. POST accepts `{}`.
- The Web shows all requested analysis states and fields without replacing the original JD.
- Automated tests use a Fake Provider. Real Provider evaluation is never fabricated.

## Ordered work

1. Freeze ADR-013, schema/API/persistence/provider/security rules and this Phase 7 stop boundary.
2. RED/GREEN domain parsing, normalization, evidence grounding and prompt-injection separation.
3. RED/GREEN optional configuration and one bounded OpenAI-compatible HTTP adapter.
4. RED/GREEN migration, repository, upsert, cascade, restart persistence and input-fingerprint stale.
5. RED/GREEN job analysis endpoints, stable errors and existing write-security middleware regression.
6. Extend shared types/api-client runtime validation and the Job Detail analysis states/fields.
7. Add 20+ de-identified JDs, human-reviewed gold labels, evaluator and honest V1/V2 records.
8. Run locked installs, full tests/lint/format/typecheck/build, migrations, security scans and core
   BOSS/Nowcoder/Job/Application/no-proxy regression.
9. When configuration is available, run the same V1/V2 evaluation and one real BOSS plus one real
   Nowcoder Job browser acceptance; otherwise record the external blocker.
10. Resolve Critical/Required findings, simplify and synchronize canonical docs; stop before Phase 7.

## Stop conditions

- Never weaken loopback Host/Origin/Fetch Metadata/JSON-only/no-credentials boundaries.
- Never persist an invalid result or silently display stale analysis as current.
- Never expose the Key or provider response through UI, logs, bundles, errors or evaluation fixtures.
- Do not add SDK/framework/provider abstractions without evidence that the one adapter cannot work.
- Do not claim real evaluation or acceptance when Provider configuration is unavailable.
- Do not begin Phase 7 without explicit owner approval.

---

# Historical Implementation Plan: Phase 5 — Nowcoder Adapter & Shared Capture Contract

> Owner-approved on 2026-09-04. Phase 6 is not authorized.

> Completed and accepted on 2026-09-04. BOSS and Nowcoder are `SUPPORTED — V1`; stop before
> Phase 6.

## Objective

Add one user-triggered Nowcoder Job-detail capture path to the existing Extension, Job API and Web
library, then compare it with the supported BOSS V1 Adapter and extract only proven shared capture
behavior. Do not add another platform, crawling, automatic submission, hidden APIs, AI/RAG, proxy
changes, telemetry or remote runtime dependencies.

## Frozen contract

- Job sources are `manual`, `boss`, and the new `nowcoder`; UI labels are “手动录入”, “BOSS直聘”,
  and “牛客”. No Job field or business table is added.
- Both platform Adapters return one `JobCaptureDraft`: `source`, current-tab `sourceUrl`, `title`,
  `company`, `location`, `salaryText`, plain-text `description`, plus Extension-only `warnings`.
- BOSS-specific responsibility remains its hostname/path/DOM detection and selectors. Nowcoder owns
  its independently verified hostname/path/DOM detection and selectors.
- Platform-independent candidates are only the result contract, visible-text cleanup and warning
  semantics. They may be extracted only after both Adapters exist and the review proves duplication.
- Popup-specific behavior remains health, explicit read, preview/edit, source label, save, duplicate,
  retry and manual fallback. API/domain-specific behavior remains validation, URL canonicalization,
  duplicate detection, persistence and Application invariants.
- The active tab uses a small explicit BOSS/Nowcoder dispatch; no factory, registry, DI container,
  plugins, empty Adapters or persistent content scripts.
- Permissions remain exactly `activeTab`, `scripting`, and the exact loopback API host. Stable
  Extension ID and exact mutation Origin/Fetch-Metadata gate remain unchanged.
- Save reuses `POST /api/v1/jobs`. The server canonicalizes supported platform URLs and SQLite owns
  duplicate uniqueness. Save/open-source never creates or mutates an Application.
- Nowcoder selectors must be based on a real user-opened current Job page with all proxies/VPN off.
  Until real end-to-end acceptance passes, Nowcoder stays `NOT SUPPORTED`.

## Ordered work

1. Freeze ADR-012, this plan, responsibility classification, permission/privacy and Phase 6 stop.
2. RED/GREEN `nowcoder` source validation, URL rules, shared types/client/Web label, and a reversible
   SQLite CHECK migration; prove manual/BOSS/Application regression.
3. Ask the project owner to keep one real Nowcoder Job detail page open with VPN/proxy off; inspect
   only the minimum rendered DOM evidence needed for selectors.
4. RED/GREEN `NowcoderAdapter` and explicit dual-platform current-tab dispatch with sanitized minimal
   fixtures and fail-closed unsupported behavior.
5. Reuse the existing Popup preview/save/error/duplicate flow and make only platform-neutral copy and
   source-label changes.
6. Run Shared Adapter Review; extract only demonstrated stable common contract/helpers and preserve
   platform-specific detection/selectors.
7. Run locked installs, all TypeScript/Python gates, builds, migration cycles, artifact/security/
   permission scans, SQLite persistence, and `git diff --check`.
8. Run user-assisted real Chrome Nowcoder acceptance, BOSS regression, no-proxy/network/privacy
   checks, duplicate/original-link/zero-Application/restart checks.
9. Resolve Critical/Required review findings, simplify, synchronize canonical docs, and stop before
   Phase 6.

## Phase 5 checkpoints and stop conditions

- Contract checkpoint: Phase 5 boundaries are committed before implementation.
- Backend checkpoint: source/migration/client/Web tests pass with manual/BOSS/Application regression.
- Capture checkpoint: live-DOM-informed Adapter and multi-platform dispatch tests pass.
- Final checkpoint: real no-proxy Nowcoder and BOSS flows pass; review is Critical 0 / Required 0;
  tracked worktree is clean except untouched `操作手册.txt`.
- If a real current Nowcoder page cannot be observed, do not guess selectors; report
  `USER ACTION REQUIRED` and keep Nowcoder unsupported.
- If `activeTab` + `scripting` is insufficient, stop before any permission change.
- If the real flow requires proxy/VPN, hidden API, remote parser or over-collection, keep Nowcoder
  `NOT SUPPORTED`.
- Do not begin Phase 6 without explicit owner approval.

## Completion evidence

- Real Nowcoder page `https://www.nowcoder.com/jobs/detail/448241` passed page detection, field
  parsing, editable preview, first save, local Job detail, original URL, duplicate handling and API
  restart persistence with VPN/system/browser proxy off.
- Persisted Job `715302b0-f6e5-402f-90d3-4f15926626bb` uses canonical queryless source URL; SQLite
  contains one Nowcoder row and zero Applications for it.
- The project owner confirmed the full BOSS regression passed.
- Shared review extracted the draft/result contract, explicit dispatch, Popup/save/duplicate flow and
  source labels. Platform detection/selectors and self-contained injected DOM helpers remain local to
  each Adapter; no factory or registry was added.
- Locked installs, 113 TypeScript tests, 102 Python tests, lint, format, typecheck, builds, API import,
  migration, artifact/permission/CSP/secret/remote-runtime and Git checks passed.

---

# Historical Plan: Phase 4 — BOSS Direct Job Capture

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
