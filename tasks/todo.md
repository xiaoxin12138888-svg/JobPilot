# Phase 7 — Resume Version & Evidence Map Checklist

## Contract and safety

- [x] Receive explicit Phase 7 approval and branch from clean Phase 6 HEAD.
- [x] Preserve `操作手册.txt`, runtime SQLite data, Phase 6 history and supported Adapters.
- [x] Freeze ADR-014, schema, lifecycle, consent/input/security boundaries and Phase 8 stop.
- [x] Keep file parsing/upload, generation/tailoring, scores, recommendation, RAG/Agent, interviews,
  automatic submission and new recruitment platforms out of scope.

## Backend and client

- [x] RED/GREEN Resume create/list/get/update/duplicate/delete with validation and guarded deletion.
- [x] RED/GREEN migration and restart-safe persistence for Resume and Application association.
- [x] RED/GREEN strict Evidence Map schema, requirement grounding, quote grounding and downgrade.
- [x] RED/GREEN Evidence Map persistence, stale detection, endpoints and failure preservation.
- [x] Extend shared types/api-client with strict runtime validation and no credentials.

## Web

- [x] Add accessible Resume empty/create/view/edit/duplicate/delete/delete-blocked states.
- [x] Add explicit Application Resume selector/save/clear without automatic selection or creation.
- [x] Add Evidence Map prerequisite/loading/success/stale/error/retry and consent states.
- [x] Keep plain-text rendering, original JD visibility and deterministic non-score totals.

## Validation and acceptance

- [x] Run migration cycles and all Python/TypeScript tests, lint, format, typecheck and builds.
- [x] Regress BOSS/Nowcoder capture, Job/Application, JD Analysis, SQLite and no-proxy core.
- [x] Run privacy, secret, raw-response, injection, XSS, remote-runtime and no-score scans.
- [x] Resolve code-review Critical/Required findings and complete simplification review.
- [x] RED/GREEN owner feedback: use semantic multi-quote evidence and bounded date inference instead
  of literal keyword equality, while keeping every quote grounded and inferred cohorts PARTIAL.
- [ ] Run user-assisted real BOSS + Nowcoder evidence acceptance with explicit external-AI consent.
- [x] Verify Application Resume association and Resume/Evidence persistence after API/Web restart.
- [ ] Record only real latency and owner-reviewed PASS/FAIL; synchronize docs and stop before Phase 8.

Isolated browser acceptance uses a temporary SQLite database and local Fake Provider only. It covers
Resume create/edit/duplicate, Application attach/change/clear, Evidence consent/loading/result/stale/error,
Provider-unconfigured degradation, API/Web restart persistence, clean console output and responsive layouts
at 320/768/1024/1440. It does not replace the project owner's real-resume BOSS/Nowcoder content review.

---

# Historical Phase 6 — JD Structured AI Analysis Checklist

## Contract and safety

- [x] Receive explicit Phase 6 approval and branch from clean Phase 5 HEAD.
- [x] Preserve `操作手册.txt`, runtime SQLite data, Phase 5 history and supported Adapters.
- [x] Freeze ADR-013, schema, provider/input/security boundaries, API semantics and Phase 7 stop.
- [x] Keep Extension, other recruitment platforms, Resume/matching, RAG and Agents out of scope.

## Backend

- [x] RED/GREEN strict structured schema, normalization and deterministic evidence grounding.
- [x] RED/GREEN prompt-injection separation and minimal five-field outbound input.
- [x] RED/GREEN optional config, explicit timeout and stable sanitized provider errors.
- [x] RED/GREEN migration, one-row upsert, cascade, restart persistence and stale fingerprint.
- [x] RED/GREEN GET/POST analysis API and Job/write-security regressions.

## Client and Web

- [x] Extend shared types and api-client with strict response validation and no credentials.
- [x] Add unconfigured, not analyzed, loading, success, failure and stale UI states.
- [x] Show every frozen field with lightweight evidence while keeping original JD visible.
- [x] Verify responsive, keyboard and accessible behavior without navigation redesign.

## Evaluation and acceptance

- [x] Add at least 20 de-identified realistic samples with human-reviewed gold labels.
- [x] Record actual V1 metrics and real bad cases on the fixed dataset when Provider is available.
- [x] Make V2 changes only from V1 bad cases and rerun the identical dataset.
- [x] Run real BOSS and Nowcoder Job analysis acceptance when Provider is available.
- [x] Run locked installs, all tests/lint/format/typecheck/build and migration cycles.
- [x] Regress BOSS, Nowcoder, Job/Application, SQLite restart and no-proxy local-first core.
- [x] Run secret/prompt-injection/raw-response/runtime dependency/telemetry security checks.
- [x] Resolve code-review Critical/Required findings, simplify and synchronize docs.
- [x] Commit coherent increments and stop before Phase 7.

---

# Historical Phase 5 — Nowcoder Adapter & Shared Capture Contract Checklist

## Contract and safety

- [x] Receive explicit Phase 5 approval and branch from clean Phase 4 HEAD.
- [x] Preserve `操作手册.txt`, runtime SQLite data, Phase 4 history and BOSS `SUPPORTED — V1`.
- [x] Audit BossAdapter responsibilities as platform-specific, shared-candidate, Popup and API/domain.
- [x] Freeze ADR-012, fields, permissions/privacy, acceptance and Phase 6 stop boundary.
- [x] Keep other platforms, AI/RAG, automation, crawling, hidden APIs and proxy changes out.

## Backend, client and Web

- [x] RED/GREEN `manual|boss|nowcoder` source and strict Nowcoder source-URL validation.
- [x] Add/test a minimal reversible source CHECK migration using temporary databases only.
- [x] Preserve server-side URL canonicalization, duplicate handling and zero-Application behavior.
- [x] Extend shared types/api-client runtime validation and Web source label without redesigning UI.
- [x] Prove manual/BOSS Job and Application regressions remain green.

## Real DOM evidence and Adapter

- [x] Observe one real current Nowcoder Job detail page with VPN/system/browser proxy off.
- [x] RED/GREEN strict Nowcoder hostname + detail-page + rendered DOM detection.
- [x] RED/GREEN title, company, location, salary, description and warning behavior.
- [x] Cover unsupported pages, non-Nowcoder, malformed URL, missing fields, whitespace and plain text.
- [x] Commit only a minimal sanitized DOM fixture; never full HTML, account data, chats, HAR or tokens.

## Extension and shared review

- [x] Keep exact existing manifest permissions, stable ID, CSP and loopback mutation gate.
- [x] Add explicit BOSS/Nowcoder/unknown dispatch without factory/registry/plugins.
- [x] Reuse one Popup preview/edit/save/duplicate/error/retry/manual-fallback flow for both platforms.
- [x] Run Shared Adapter Review after both Adapters; extract only proven common contract/helpers.
- [x] Prove no save/open-source path creates or updates an Application.

## Acceptance

- [x] Run frozen/locked installs, all tests, lint, format, typecheck, builds and API import/startup.
- [x] Run migration upgrade/downgrade/upgrade, persistence and duplicate checks on safe DBs.
- [x] Run artifact/CSP/secret/remote/network/permission/DOM-log scans.
- [x] Run real Chrome Nowcoder read/preview/save/library/detail/duplicate/original-link/restart flow.
- [x] Run real Chrome BOSS read/preview/save-or-duplicate/library regression.
- [x] Verify all real flows with VPN/system/browser proxy off.
- [x] Run code review to Critical 0 / Required 0 and execute simplification findings.
- [x] Synchronize canonical docs, commit coherent increments, and stop before Phase 6.

---

# Historical Phase 4 — BOSS Direct Job Capture Checklist

## Contract and safety

- [x] Receive explicit Phase 4 approval and create `phase/4-boss-job-capture` from clean `c27a987`.
- [x] Preserve `操作手册.txt`, real `runtime-data/jobpilot.db`, Phase 3 commits, and old branches.
- [x] Freeze ADR-011, capture fields, duplicate metadata, permissions, and stop boundary.
- [x] Keep all non-BOSS platforms, AI/RAG, automation, crawling, hidden APIs, and proxy changes out.

## Backend and client

- [x] RED/GREEN `manual|boss` source validation and plain-text control-character sanitization.
- [x] Add and test a minimal reversible Job source CHECK migration.
- [x] Verify migration on a fresh temp DB and a copy of the real runtime DB, never the live file.
- [x] Preserve `POST /api/v1/jobs`, normalized URL dedupe, and expose existing local Job ID on 409.
- [x] Extend shared types/api-client validation while preserving manual Job/Application behavior.

## BOSS Adapter

- [x] Observe a real current BOSS Job detail DOM with VPN/proxy off before choosing selectors.
- [x] RED/GREEN strict BOSS hostname + detail-page detection.
- [x] RED/GREEN title, company, location, salary, description and whitespace normalization.
- [x] Cover unsupported/non-BOSS/missing required/optional missing/odd text/URL cases.
- [x] Commit only a minimal sanitized DOM fixture; never full HTML, cookies, IDs, chats, HAR, or tokens.

## Extension and Web

- [x] Add only `activeTab` and `scripting`; keep exact loopback host permission and no content script.
- [x] Fix the unpacked Extension ID with a public manifest key and allow only its exact write Origin.
- [x] RED/GREEN health, ready, parsing, preview/edit, warning, saving, saved, duplicate, failure, retry.
- [x] Use the shared api-client and existing Job creation endpoint/service.
- [x] Open the local Web detail using only the saved Job ID; manual fallback opens manual add.
- [x] Show `BOSS直聘` in Web list/detail and keep original-platform links mutation-free.
- [x] Prove capture/save does not create or mark an Application.

## Acceptance

- [x] Run frozen/locked installs and all TypeScript/Python tests, lint, format, typecheck, and builds.
- [x] Run migration, API import/startup, SQLite persistence, artifact/CSP, secret, remote, and log scans.
- [x] Load unpacked in Chrome after action-time approval and run the real BOSS capture twice.
- [x] Verify Popup, parse, preview, save, library, detail, duplicate, original URL, and restart.
- [x] Verify console/network/privacy and full workflow with VPN/system/browser proxy off.
- [x] Verify Web at 320/768/1024/1440 and keyboard/accessibility states.
- [x] Run code review to Critical 0 / Required 0 and simplify confirmed complexity.
- [x] Synchronize all canonical docs, commit coherent increments, and stop before Phase 5.
