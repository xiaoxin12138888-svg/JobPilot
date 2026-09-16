# Phase 11.2 — Final Reliability Closure Checklist

## Frozen failure analysis

- [x] Preserve V1 13/20, V2 14/20, the dataset/scoring contract and real-job 6/6 PASS.
- [x] Classify all six V2 failures using the approved A–L taxonomy without raw output or secrets.
- [x] Record `COPILOT_V2_FAILURE_ANALYSIS.md` before any implementation change.
- [x] Audit Prompt/Schema/Parser/Validator/Retry: all six failures stopped at Provider/transport.
- [x] Do not make an unrelated parser or schema change; no code defect is evidenced by these six failures.

## Real rerun gate

- [ ] Run the frozen three-feature preflight to a new file; require 3/3 final PASS.
- [ ] After preflight PASS, rerun the unchanged 20 samples to a new file without overwriting V2.
- [ ] Record first/final schema, retry, evidence, safety, relevance and latency metrics.
- [ ] Run final Python/API client/Web/Extension/type/lint/format/build/security review gates.
- [ ] Update final evaluation docs and stop before Phase 12.

Current gate (2026-09-16): analysis is complete. Five failures are `AI_PROVIDER_UNAVAILABLE`, one is
`AI_TIMEOUT`, and none returned content to the structured-output pipeline. The configured Provider variables
are not present in the Codex subprocess, so real preflight/final evaluation remain NOT RUN here. Phase 11 stays
BLOCKED and Phase 12 is not started.

---

# Historical Phase 11.1 — Copilot Reliability Hardening Checklist

## V1 failure diagnosis

- [x] Preserve V1 dataset, `COPILOT_RESULTS.md` baseline and BC-01 through BC-07 unchanged.
- [x] RED/GREEN diagnostic replay for only the seven V1 failures without persisting raw Provider output.
- [x] Classify each failure A–H with expected schema, sanitized actual shape, root cause and candidate fix.
- [ ] Locate the single unsupported V1 evidence and record whether it is ID, quote, ownership or semantic overreach; V1 did not persist per-sample attribution, so this remains unknowable without a prohibited raw replay.
- [x] Commit `COPILOT_V1_FAILURE_ANALYSIS.md` before changing Prompt or Schema.

## V2 structured reliability

- [x] RED/GREEN separate `match-v2`, `resume-advice-v2` and `interview-prep-v2` JSON-only prompts.
- [x] Simplify only Schema fields proven unnecessary; keep evidence grounding unchanged or stronger.
- [x] RED/GREEN conditional suggestion safety and JD-driven interview categories.
- [x] RED/GREEN one structure-only retry for `AI_INVALID_RESPONSE`, maximum two Provider calls.
- [x] Record first-attempt/final status, retry count and latency without raw response or secrets.

## V2 evaluation and acceptance

- [x] Run 3-sample real Provider preflight; require 3/3 schema/evidence and safety/relevance PASS.
- [x] Freeze V2 against unchanged dataset v1, model, temperature 0 and timeout 60s.
- [x] Re-run the same 20 samples and compare every approved V1/V2 metric.
- [x] Re-run the original BOSS and Nowcoder six tasks; 2026-09-16 result 6/6 generation and content PASS.
- [x] Obtain owner PASS/FAIL for all successful real-job outputs; owner confirmed all six PASS.
- [ ] Run full regression/security/browser/documentation gates and stop before Phase 12.
- [x] Hide the redundant Job Detail Evidence Map panel while retaining historical data and API compatibility.

Current gate (2026-09-15): V2 preflight is 3/3, but the unchanged 20-sample run obtained usable Provider content
for only 14/20 samples (five `AI_PROVIDER_UNAVAILABLE`, one `AI_TIMEOUT`). The 14 received results reached
14/14 final schema and 43/43 grounding, with one bounded repair, but combined final 14/20 is below the frozen
19/20 threshold. Real V2 BOSS/Nowcoder six-task owner acceptance is complete at 6/6 PASS; browser automation
remains blocked by the local request-header policy. Phase 11 stays BLOCKED and Phase 12 is not started.

---

# Historical Phase 11 — AI Job Copilot Checklist

## Contract and foundation

- [x] Owner approval, branch and Phase 12 stop boundary confirmed.
- [x] ADR-018 and technical contract freeze minimal inputs, outputs, evidence and stale behavior.
- [x] RED/GREEN domain parser, contact redaction and deterministic fingerprints.
- [x] RED/GREEN `copilot_records` migration, repository and service.

## P0 features

- [x] Job Match API, Provider prompt and Web state.
- [x] Resume Advice API, Provider prompt and Web state.
- [x] Interview Prep API, Provider prompt and Web state.
- [x] Strict shared client validation and duplicate-generation prevention.

## Evaluation and acceptance

- [x] Add and validate 20 fictional BOSS/Nowcoder-style samples plus the real-output-only runner.
- [ ] Run the 20 samples against a configured real Provider and record only actual metrics.
- [x] Cover BC-01 unsupported strength, BC-02 inability wording, BC-03 fabricated experience and BC-04 certainty with deterministic rejection regressions.
- [x] Run API, Web, Extension, lint, format, type, build, security and migration regressions.
- [ ] Obtain real BOSS and Nowcoder human review from the owner.
- [x] Synchronize canonical docs and stop before Phase 12.

Provider validation (2026-09-13): `NOT_CONFIGURED`. Real output metrics, actual Provider Bad Cases and
human content review remain `NOT RUN`; no Fake Provider result is counted as evaluation evidence.

Technical closure (2026-09-13): Python 274、API client 69、Web 62、Extension 112 tests PASS；
type/lint/format/import/build、isolated migration、security scans 和真实 Chrome 四工具/console/
responsive 验收通过。只有 Provider 真实 20 样本与 BOSS/牛客负责人内容验收继续未勾选。

---

# Historical Phase 10 — Local PDF / DOCX Resume Import Checklist

## 2026-09-08 project experience amendment

- [x] Receive owner approval to add project experience as an independent Profile/import collection.
- [x] Freeze additive `projects[]` fields, append-only Confirm semantics and reversible migration plan.
- [x] Keep Extension project mapping/filling, permissions and submit behavior unchanged.
- [x] RED/GREEN ProjectEntry validation, persistence migration and existing-data backfill.
- [x] RED/GREEN explicit PROJECT section parsing, editable candidates and conservative no-inference rules.
- [x] RED/GREEN Parse/Confirm/shared-client contracts, strict validation and atomic selected-only append.
- [x] RED/GREEN Web Profile maintenance, existing/imported project rows, duplicate hint and selection UX.
- [x] Run full Python/TypeScript/lint/format/typecheck/build/migration/security regressions.
- [ ] Obtain owner confirmation of real project candidates, selected save and restart persistence.
- [ ] Record the real Bad Case and remain stopped before Phase 11.

Isolated project-experience evidence (2026-09-08): temporary API/Web services exposed the Profile project
editor with add/delete, name, role, month and description controls; 320/768/1024/1440 widths had no
horizontal overflow and the browser console stayed clean. Automated project parse/preview/Confirm,
duplicate, rollback, migration and restart-persistence regressions all passed. This does not replace the
unchecked real-file candidate/save/restart acceptance items above.

## Contract and dependency gate

- [x] Receive explicit Phase 10 approval from clean Phase 9 commit `0189314` and create
  `phase/10-resume-import`.
- [x] Read canonical docs, ADRs, technical docs and owning Resume/Profile/API/Web implementation.
- [x] Freeze ADR-017, Parse/Preview/Confirm/privacy/resource limits and the Phase 11 stop boundary.
- [x] Keep Phase 7 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`; preserve Phase 9 Autofill behavior.
- [x] Preserve untracked `操作手册.txt`, runtime SQLite, Provider secrets and existing user data.
- [x] Add locked parser dependencies only after compatible-license review.

## Document extraction and structure parsing

- [x] RED/GREEN selectable-text/multi-page PDF, line order, encrypted/no-text and resource limits.
- [x] RED/GREEN DOCX paragraph/table/mixed order and corrupt/ZIP/XML/external-content safety.
- [x] RED/GREEN exact section headings, false-heading prevention, phone/email and conservative name.
- [x] RED/GREEN partial education/experience candidates, projects/skills and raw-text fallback.

## Parse and atomic confirm APIs

- [x] RED/GREEN Web-only multipart Parse with extension/MIME/magic/10 MiB checks and stable errors.
- [x] Prove Parse writes no business data, stores no original file, logs no filename/content and calls no
  remote service.
- [x] RED/GREEN Resume-only, Profile-only and combined Confirm with at least one selected target.
- [x] RED/GREEN selected scalar updates, append-only selected rows and no silent overwrite/deletion.
- [x] RED/GREEN combined transaction rollback and temporary-database restart persistence.

## Shared client and Web

- [x] RED/GREEN shared preview/confirm types and strict api-client validation for untrusted responses.
- [x] RED/GREEN credential-free, redirect-rejecting multipart upload with bounded local timeout.
- [x] RED/GREEN choose/parse/preview/target/confirm/done states and unsupported/oversize/parser errors.
- [x] Make Resume name/text and Profile candidates editable; mask contacts by default.
- [x] Show Current vs Imported and deterministic possible-duplicate hints; require explicit selections.
- [x] Render all imported content as text and cover keyboard/responsive/loading/error/cancel states.

## Validation and acceptance

- [x] Run all Python/TypeScript/lint/format/typecheck/build/API/migration gates with temporary SQLite and no
  LLM configuration.
- [x] Regress BOSS, Nowcoder, Job, Application, JD AI, Resume, Evidence Map, Interview, Feedback, Profile
  Vault and Safe Autofill.
- [x] Run parser/license/privacy/ZIP/XML/MIME/log/remote/original-file/Extension artifact security checks.
- [x] Complete isolated browser parse → preview → confirm → restart acceptance with fictional files.
- [x] Complete five-axis review/simplification with Critical 0 and Required 0; synchronize docs and commits.
- [ ] Obtain separate owner acceptance of one de-identified real DOCX and PDF plus real save/profile merge.
- [x] Stop at `USER ACTION REQUIRED — REAL RESUME IMPORT ACCEPTANCE`; do not start Phase 11.

Fictional isolated-browser evidence (2026-09-07): PDF 1,208 bytes / 2 pages / 228 characters / 0 ms;
DOCX 37,037 bytes / 189 characters / 31 ms first parse and 16 ms after restart. Parse-cancel wrote no
Resume/Profile; selected DOCX Confirm persisted Resume/Profile across restart; duplicate rows defaulted
unselected; hostile HTML-looking text remained text; unsupported type, responsive widths and clean console
all passed. This is technical fixture evidence only and does not replace the unchecked real-file gate.

---

# Historical Phase 9 — Profile Vault & Safe Job Form Autofill Checklist

## Contract and safety

- [x] Receive explicit Phase 9 approval from clean Phase 8 commit `eb3c9e8` and create
  `phase/9-safe-autofill`.
- [x] Read current canonical docs, ADRs, technical docs and owning API/Web/Extension implementation.
- [x] Freeze ADR-016, Profile/API/Scanner/Resolver/Executor/privacy contracts and the Phase 10 stop.
- [x] Keep Phase 7 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`; do not change Evidence Map behavior.
- [x] Preserve the protected local manual, runtime SQLite, existing records and Provider secrets.

## Profile foundation

- [x] RED/GREEN minimal Profile validation and singleton repository/service.
- [x] RED/GREEN reversible `0009_autofill_profile` migration on temporary SQLite only.
- [x] RED/GREEN nullable GET and full-replacement PUT API with existing write-security semantics.
- [x] RED/GREEN shared types/api-client strict parsing, no credentials and loopback-only transport.
- [x] RED/GREEN accessible Web “求职资料” editor with multiple education/experience rows.

## Scanner, resolver and preview

- [x] RED/GREEN current-page Scanner, supported kinds, label priority, visibility/prohibited inputs and
  stable refs against the synthetic local fixture.
- [x] RED/GREEN finite aliases, normalized exact mapping, fuzzy review-only, sensitive/manual, unknown and
  missing-value behavior.
- [x] RED/GREEN existing DOM-order mapping for multiple education/experience rows without clicking add.
- [x] RED/GREEN preview masking, default selections, explicit fuzzy confirmation and user deselection.

## Fill executor and integration

- [x] RED/GREEN text/textarea native setters and standard input/change events.
- [x] RED/GREEN conservative native select, date and combobox behavior.
- [x] RED/GREEN missing/stale ref, changed-page and partial-failure handling.
- [x] RED/GREEN no password/CAPTCHA/file/legal fill and no form.submit/requestSubmit/submit-button action.
- [x] Integrate explicit Scan and Fill buttons/states without BOSS/Nowcoder capture regression.
- [x] Keep manifest permissions exact and Extension Profile/Fill Plan memory-only.

## Validation and acceptance

- [x] Add the local fixture and verify UTF-8, DOM/accessibility structure, no-overflow and clean console
  in an isolated browser.
- [x] Complete real Extension runtime Scan/Preview/Fill/no-Submit acceptance against a user-opened form.
- [x] Run locked installs, all Python/TypeScript/lint/format/typecheck/build/API/migration gates using
  explicit temporary SQLite for Python runtime and migration checks.
- [x] Run artifact permission/secret/storage/remote/telemetry/private-API/auto-submit security scans.
- [x] Regress BOSS, Nowcoder, Job, Application, JD AI, Resume, Evidence Map, Interview and Feedback through
  the full automated TypeScript/Python suites.
- [x] Complete code review and simplification with Critical 0 and Required 0 after adding final-write
  sensitive-field enforcement and aria-disabled rejection.
- [x] Run one real recruitment/ATS form, record factual metrics and real Bad Cases without Submit.
- [x] Obtain owner confirmation for mapping correctness, proposed values, page result and no unexpected action.
- [x] Synchronize canonical/technical documentation and commit coherent implementation increments.
- [x] Stop before Phase 10 after the real Autofill acceptance decision.

---

# Historical Phase 8 — Interview Record & Feedback Loop Checklist

## Contract and safety

- [x] Receive explicit Phase 8 approval from the latest committed Phase 7 baseline.
- [x] Keep Phase 7 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`; do not change Evidence Map behavior.
- [x] Freeze ADR/model/API/statistics/privacy rules and the next-phase stop boundary.
- [x] Preserve `操作手册.txt`, runtime SQLite data, Provider secrets and all existing user records.
- [x] Prove all Phase 8 behavior works with no LLM Provider configuration.

## Backend

- [x] RED/GREEN InterviewRound validation, create/list/get/update/delete and persistence.
- [x] RED/GREEN InterviewQuestion create/update/delete, category/performance and round cascade.
- [x] RED/GREEN Application outcome note/rejection reason consistency and deletion cascades.
- [x] RED/GREEN deterministic feedback counts, funnel, categories, performance, rejection reasons,
  Resume Version groups, source groups, empty state and zero denominators.
- [x] Verify upgrade/downgrade/upgrade on explicit temporary SQLite databases only.

## Client and Web

- [x] Extend shared types/api-client with strict Interview and Feedback contracts and no credentials.
- [x] Add accessible interview create/edit/complete/cancel/delete and self-review UX in Job Detail.
- [x] Add question create/edit/delete with category, actual answer, performance and notes.
- [x] Add explicit Application outcome detail and clearly label rejection reason as a user record.
- [x] Add factual Feedback Summary empty/populated views with no score or recommendation language.
- [x] Verify keyboard behavior and 320/768/1024/1440 responsive layouts.

## Validation and acceptance

- [x] Run all Python/TypeScript tests, lint, format, typecheck, builds and import/startup gates.
- [x] Regress BOSS, Nowcoder, Job, Application, JD AI, Resume and existing Evidence Map behavior.
- [x] Run privacy/XSS/log/telemetry/remote-call/schema/cascade safety review.
- [x] Complete code review and simplification with Critical 0 and Required 0.
- [x] Use one existing Application to enter one local round, at least three fictional/historical questions,
  manual self review and completion; confirm factual Feedback Summary values without database edits.
- [x] Restart API/Web and confirm round, questions, review, outcome and feedback persistence.
- [x] Stop before the next phase and wait for project-owner approval.

Isolated browser acceptance note (2026-09-06): with every Provider variable absent, a temporary
SQLite database and local 8002/5176 stack persisted one fictional Job/Application, one completed round,
three questions, self review, a user-recorded rejection reason and a linked fictional Resume Version
across API restart. Feedback counts/groups and 320/768/1024/1440 layouts matched the frozen contract;
the browser console had no errors or warnings. At that time the user's 8001 process still served the
pre-Phase-8 Application contract, so the isolated run correctly left the live database untouched.

Real-workspace acceptance note (2026-09-07): the stale 8001 API was stopped by exact PID and the
supported launcher upgraded the existing database from `0007_evidence_map_schema_v2` to
`0008_interview_feedback`, preserving three Jobs, two Applications, three JD Analyses, one Resume
Version and three Evidence Maps. The existing Nowcoder Application was reused with no duplicate; one
de-identified round, three questions, one question edit and all four self-review fields persisted across
API/Web restart. Round status followed PLANNED -> COMPLETED -> CANCELLED -> COMPLETED while the
Application remained `planned`. Feedback reported Jobs 3, Applications 2, interviewed Applications 1,
Interviews 1, Questions 3, Offers 0 and Rejected 0; PRODUCT/AI/PROJECT and GOOD/OK/POOR each counted one.
Source groups reported BOSS 1/0 and Nowcoder 1/1 for Application/interviewed Application; the unlinked
Resume Version correctly reported 0/0/0 for Application/interview/Offer. Required-field PATCH null
returned 422, prior BOSS/Nowcoder/Job/Application/JD Analysis/Resume/Evidence Map records remained
readable, and privacy/security review remained Critical 0 / Required 0.

---

# Historical Phase 7 — Resume Version & Evidence Map Checklist

## Phase 7C semantic evidence refinement — approved 2026-09-06

- [x] RED/GREEN prompt contract for complete-Resume semantic search, non-lexical wording and 1–3
  combined grounded quotes.
- [x] RED/GREEN semantic cases A–E with B frozen as PARTIAL and the 2027 cohort case forbidding
  customary-program-length inference.
- [x] Replace the Evidence Map prompt without changing Schema, Provider, timeout, persistence or UI.
- [x] Add allowlisted local diagnostics for invalid Provider envelope/JSON/schema/requirement/evidence
  limits without logging payloads or changing the public `AI_INVALID_RESPONSE` contract.
- [x] Synchronize canonical docs and pass all Python/TypeScript/build/security gates.
- [x] Complete review/simplification with Critical 0 and Required 0.
- [ ] Run separately consented real BOSS and Nowcoder semantic acceptance; owner must judge PASS/FAIL.
- [ ] Stop before Phase 8 and do not announce Phase 7 PASS.

Real acceptance note (2026-09-06): two separately confirmed Nowcoder generation attempts showed the
same bounded generic Web error. The second completed in 61,509 ms; terminal evidence subsequently
confirmed HTTP 502 rather than 503. After restarting with sanitized diagnostics, one separately
confirmed run succeeded with all 25 mappings returned (23 DIRECT, 0 PARTIAL, 2 GAP) and a clean Web
console. Browser confirmation handling made the 82,897 ms end-to-end observation unsuitable as a pure
Provider latency measurement. Owner semantic content acceptance remains paused by product decision;
Phase 7 is not PASS.

## Comprehensive Evidence Map amendment — approved 2026-09-06

- [x] RED/GREEN six-group JD criteria, schema 2 persistence, schema 1 read compatibility and migration.
- [x] RED/GREEN shared types and strict API-client validation for Evidence Map schemas 1 and 2.
- [x] RED/GREEN explicit per-item conclusions, six UI groups, whole-map totals and principal gaps.
- [x] Synchronize canonical docs and pass all Python/TypeScript/build/migration/security gates.
- [ ] Run one user-confirmed real regeneration, record latency and obtain owner content PASS/FAIL.
- [ ] Stop before Phase 8; do not add scores, recommendations, generation or resume rewriting.

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
- [x] RED/GREEN owner feedback: use whole-Resume semantic multi-quote evidence instead of literal
  keyword equality, while keeping every quote grounded and forbidding external cohort inference.
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
