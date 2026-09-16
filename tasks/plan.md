# Implementation Plan: Phase 11.2 — Final Reliability Closure

> Owner-approved on 2026-09-16 from V2 evaluation commit `51a4ab1` and real-job acceptance commit
> `0351de3`. Preserve V1/V2 results, the frozen 20-sample dataset and the 6/6 real-job acceptance. Do not
> restore Evidence Map UI, change Phase 7, add product scope or enter Phase 12.

## Objective

Classify the six frozen V2 failures before changing code, make only an evidence-backed reliability fix,
then rerun a three-feature gate and the unchanged 20-sample evaluation against the same Provider settings.

## Ordered increments

1. Freeze and analyze all six V2 failures without replaying them or persisting raw Provider output.
2. Audit Prompt, Schema, Parser, Validator and repair paths; do not modify a layer that none of the six
   failures reached.
3. If a code defect is proven, RED/GREEN the generic rule and commit it separately. Otherwise record why a
   no-code decision is the smallest correct change.
4. Run the fixed three-feature gate as `copilot-001`, `copilot-009`, `copilot-017`; the failed set has no
   Interview Prep sample, so `017` remains the repair-capable control. Require 3/3 final PASS.
5. After the gate passes, run all 20 unchanged samples to new output files and record first/final schema,
   repair, evidence, safety, relevance and latency metrics without overwriting V1/V2.
6. Run full regression/security/review/documentation gates. Re-run real jobs only if Prompt/Schema changes;
   otherwise retain the already completed 6/6 human acceptance.

## Acceptance and stop conditions

- Final evaluation at least 19/20; evidence grounding at least 98%; zero serious accepted unsupported
  evidence, fabricated existing experience, unsafe suggestion or gap wording error.
- All automated regression and security gates pass with Critical 0 and Required 0.
- If preflight is not 3/3, stop before the 20-sample run.
- If final evaluation is at most 18/20, keep `PHASE 11 BLOCKED`; never lower the threshold or cherry-pick.
- Preserve `操作手册.txt` as untracked and untouched.

## 2026-09-16 analysis checkpoint

- The six failures are five `AI_PROVIDER_UNAVAILABLE` and one `AI_TIMEOUT`; no raw Copilot content was
  received, no parser/validator ran and no repair was eligible.
- No Prompt/Schema/Parser/Validator/Retry code change is causally justified by these failures.
- The Codex subprocess does not inherit the configured Provider variables, so the real gate awaits execution
  from the project owner's already configured PowerShell.

---

# Historical Implementation Plan: Phase 11.1 — Copilot Reliability Hardening

> Owner-approved on 2026-09-15 from Phase 11 V1 acceptance commit `5c25c0c`. Keep the V1
> dataset/results/BC-01 through BC-07 immutable, preserve Phase 7 as
> `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`, and stop before Phase 12.

## Objective

Raise real Provider structured-generation reliability without adding product scope or weakening evidence
grounding. Compare frozen V1 with separately versioned V2, permit at most one structure-only Provider repair,
and retain first-pass metrics independently from final metrics.

## Ordered increments

1. Add a V1 diagnostic-only runner mode that replays only the seven failed synthetic samples and records
   failure category, expected schema, sanitized actual shape and validator issue without persisting raw output.
   Produce `COPILOT_V1_FAILURE_ANALYSIS.md` from real Provider observations before changing any Prompt.
2. RED/GREEN three separate V2 prompts, suggestion-safety rules, source allowlists and only the minimal Schema
   V2 changes proven necessary by Increment 1. Keep evidence source ownership and quote grounding fail-closed.
3. RED/GREEN one bounded structure-repair retry for `AI_INVALID_RESPONSE`; pass only sanitized validator issues,
   forbid new claims/evidence, preserve previous valid records, and record attempt/total latency separately.
4. Run one Match, one Resume Advice and one Interview Prep preflight. Freeze V2 only after 3/3 schema,
   evidence, suggestion safety and category relevance pass; otherwise stop for analysis.
5. Re-run the unchanged 20-sample dataset and report first-pass/final schema success, retry count, grounding,
   safety, relevance, quality and latency against the V1 baseline.
6. Re-run the original BOSS and Nowcoder Match/Resume Advice/Interview Prep tasks once, record attempt/retry/
   final latency and request owner PASS/FAIL for every successful output.
7. Run full regression, security, migration, browser and documentation gates. Mark Phase 11 PASS only when all
   approved acceptance thresholds hold; otherwise remain BLOCKED.

## Checkpoints

- **V1 diagnosis:** all seven failures have real, non-sensitive A–H classifications; no raw Provider output or
  secret is written.
- **V2 preflight:** 3/3 schema and evidence pass before the 20-sample run.
- **Synthetic acceptance:** final schema >= 19/20, evidence >= 98%, no accepted P0/P1 unsupported evidence,
  fabricated experience, unsafe resume suggestion or false inability wording.
- **Real acceptance:** same six tasks reach at least 5/6 without a systematic same-class failure; owner judges
  successful content.

## 2026-09-15 execution status

- V1 failure diagnostics: complete; five wrong-type string arrays, one evidence-structure failure and one
  non-reproduced response were recorded without invalid raw output.
- V2 prompt/schema/retry: complete; schema 1 remains readable, schema 2 is current, and repair is capped at one.
- V2 preflight: 3/3 final schema, 10/10 evidence, no automated safety/relevance violation.
- V2 20-sample run: Provider usable content 14/20; first-pass 13/20; final 14/20 after one repair; evidence
  43/43; five unavailable and one timeout. The frozen 19/20 combined threshold was not met.
- Automated regression and build gates pass. Browser automation is blocked by the local request-header policy;
  V2 real BOSS/Nowcoder generation and owner content acceptance completed 6/6 PASS on 2026-09-16. The
  synthetic threshold remains unmet, so the verdict stays `PHASE 11 BLOCKED`.

## 2026-09-16 UI consolidation

- Hide the redundant Evidence Map panel from Job Detail and direct users to Copilot Match.
- Keep all Evidence Map tables, migrations, records, backend services, endpoints and API-client methods.
- Update Resume empty-state copy, add a Web regression proving the hidden panel makes no Evidence Map request,
  and preserve Phase 7 as `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`.

## Stop conditions

- Do not change Prompt or Schema before the real V1 failure classifications exist.
- Do not retry more than once, silently create semantic fields, relax source ownership or accept invented IDs.
- Do not overwrite V1 records, change dataset/scoring, optimize latency, add Agent/RAG/framework/product scope,
  alter Phase 7 or enter Phase 12.
- Never read, modify, delete, stage or commit `操作手册.txt`; never expose Provider secrets or invalid raw output.

---

# Historical Implementation Plan: Phase 11 — AI Job Copilot

> Owner-approved on 2026-09-09 from Phase 10 commit `8609dee`. Phase 7 remains
> `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`. Preserve the protected untracked `操作手册.txt` and stop
> before Phase 12.

## Objective

Add explicit, optional and grounded Job Match, Resume Advice and Interview Preparation to Job Detail by
reusing the existing Provider and local Job/Resume/Interview context. Results are append-only,
fingerprinted and stale-aware; no model output mutates source data or performs an action.

## Implementation status

Slices 1–5, the synthetic dataset/real-output runner portion of Slice 6, and all technical closure work
in Slice 7 are complete. Provider validation on 2026-09-13 returned `NOT_CONFIGURED`, so no real output
metrics or Bad Cases were created. Automated regression, security/code review, documentation sync and
isolated real-Chrome UI verification passed; real BOSS/Nowcoder content judgment remains owner-only.

## Ordered slices

1. Freeze ADR-018, API/storage/prompt/grounding/privacy contracts and this checklist.
2. RED/GREEN strict result parser, source quote verification, contact redaction and fingerprints.
3. RED/GREEN append-only migration/repository/service plus latest/by-id reads and stale rules.
4. RED/GREEN Provider method and API contracts for Match, Resume Advice and Interview Prep.
5. RED/GREEN shared wire validation/client and Job Detail Copilot tabs/states.
6. Add 20 fictional evaluation samples and a real-output-only runner; record metrics/bad cases only when
   Provider is configured. Current run state is NOT RUN.
7. Run full gates, security/code review and isolated browser regression, then request real BOSS/Nowcoder
   owner acceptance. Do not claim PASS before that review.

## Stop conditions

- Never read/log/fixture real resume, Profile, interview content, Provider key or live SQLite.
- Never accept an ungrounded quote, imply “用户不会”, state an interview certainty or invent experience.
- Never add scores, auto-decisions/actions, Chat/RAG/Agent infrastructure or Phase 12 work.
- Never convert a missing Provider or deterministic Fake Provider coverage into real evaluation metrics.

---

# Historical Implementation Plan: Phase 10 — Local PDF / DOCX Resume Import

> Owner-approved on 2026-09-07 from clean Phase 9 commit `0189314`. Phase 7 remains
> `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`; this phase must not change Evidence Map or Phase 9
> Autofill behavior. The untracked `操作手册.txt` is protected and must not be read or committed.

## Objective

Let a user select one local text-based PDF or DOCX, extract and deterministically structure it on the
loopback API, review and edit the preview in the Web, then explicitly create a Resume Version, update
selected Autofill Profile facts, or do both atomically. `Parse != Save`; the installed flow requires no
LLM, OCR, remote service or original-file persistence.

## 2026-09-08 owner amendment: structured project experience

The owner requested project experience as a third independent repeatable Profile collection during
real DOCX acceptance. Add `projects[]` with `name`, optional `role`, start/end month and optional
description. Parse only explicit PROJECT sections; Preview keeps every candidate editable and selected
by the user; Confirm appends only selected rows and preserves existing projects.

This is an additive Profile/API/database amendment. A reversible migration backfills existing singleton
profiles with an empty project array. The Web Profile and import review expose projects, while the
Extension resolver/executor intentionally ignores them: no new field mapping, permissions, page writes,
submit behavior or Phase 9 recruitment-site capability is approved.

Implementation order is contract → RED/GREEN domain/migration/API → RED/GREEN shared client/Web → full
gates and real re-import review. Phase 10 remains pending until the owner confirms the real candidates,
save and restart persistence; Phase 11 remains out of scope.

## Architecture decisions

- ADR-017 owns the 10 MiB limit, parser/resource/privacy boundaries, stateless preview, patch-like
  Profile import and one-transaction Confirm command.
- `POST /api/v1/resume-imports/parse` is the only reviewed multipart exception. It is Web-only,
  loopback-only and non-persistent; every other mutation remains JSON-only.
- Document extraction is split into focused PDF/DOCX infrastructure parsers. Deterministic section and
  candidate parsing is a pure domain module; uncertain facts remain editable raw text.
- `POST /api/v1/resume-imports/confirm` accepts only explicitly selected updates/additions. The repository
  loads current Profile state inside the same transaction, preserves unselected values/rows and creates
  the optional Resume Version atomically.
- No ResumeImport table is needed. Preview state lives only in Web memory; original files are never
  persisted. The owner-approved project amendment adds only `projects_json` to the existing singleton
  Profile through one reversible migration.

## Implementation status

PDF/DOCX extraction、deterministic structure parser、Web-only Parse、atomic Confirm、strict shared
client 与可编辑 Web preview 已完成。全量结果为 Python 256、API client 65、Extension 112、Web
55 tests 全部 PASS；locked offline installs、ESLint/Prettier/Ruff、typecheck、Web/Extension build、
artifact security、API import、migration cycle 与静态安全扫描均通过。虚构 PDF/DOCX 隔离浏览器
验收完成；真实 DOCX/PDF 内容质量继续由项目负责人验收，不能由自动化结果替代。

## Ordered slices

### Slice 1: Contract and dependency gate

- Freeze ADR-017, API/error/resource limits, third-party parser choices and this plan/checklist.
- Verify tracked-clean Phase 9 base, create `phase/10-resume-import`, and preserve protected local files.
- Add only compatible, maintained PDF/DOCX/multipart dependencies after license review.

Verification: docs/checklist consistency, lockfile update, dependency metadata/license audit.

### Slice 2: Document extraction and structure parsing

- RED/GREEN PDF selectable-text, multi-page/order, encrypted/no-text and page/text/time limits.
- RED/GREEN DOCX paragraph/table/mixed order, corrupt/package/ZIP/XML/external-content safety.
- RED/GREEN exact-heading sections, false-heading prevention, phone/email, conservative name,
  education/experience candidates and raw-text fallback.

Verification: focused pure/parser tests pass with fictional in-memory fixtures.

### Slice 3: Parse API and browser boundary

- RED/GREEN multipart parse endpoint, 10 MiB streaming read bound, extension/MIME/magic checks and stable
  sanitized errors.
- Prove parsing changes no Resume/Profile/Job/Application/Evidence rows, logs no content/name and makes no
  remote request.
- Return strict preview payload and non-sensitive metrics without storing an import session.

Verification: API/security tests plus existing JSON-only/Origin/Extension regressions.

### Slice 4: Atomic Confirm

- RED/GREEN explicit Resume-only, Profile-only and combined commands.
- Preserve current scalar values unless selected; append only selected rows; never delete existing rows.
- Prove combined rollback with a forced database failure and restart persistence on temporary SQLite.

Verification: domain/repository/API transaction tests.

### Slice 5: Shared contract and Web flow

- RED/GREEN shared types and api-client multipart/JSON transports with strict untrusted-response checks,
  no credentials, no redirects and bounded local timeout.
- RED/GREEN simple choose → local parse → editable preview → target selection → confirm → done UI.
- Show Current vs Imported, masked phone/email, explicit reveal/edit, duplicate hints, warnings and safe
  cancellation; render all file content as plain text.

Verification: client/component tests, keyboard/accessibility and responsive states.

### Slice 6: Final gates and human acceptance

- Run full Python/TypeScript/lint/format/typecheck/build/import/security/migration regressions with LLM
  configuration absent and temporary SQLite only.
- Run isolated browser parse/preview/confirm/no-auto-save/restart checks with fictional files; record only
  non-sensitive latency/size/page/character metrics.
- Complete five-axis review and simplification, synchronize canonical/technical/dependency/bad-case docs,
  then request owner testing with one de-identified real DOCX and PDF.

Verification: Critical 0 / Required 0. Until separate real DOCX/PDF/Save/Profile checks are confirmed,
report `USER ACTION REQUIRED — REAL RESUME IMPORT ACCEPTANCE` and do not mark Phase 10 PASS.

## Checkpoints

- Parser checkpoint: both formats and resource/security failures are deterministic and no OCR/remote call
  exists.
- Persistence checkpoint: parse writes nothing; confirm preserves unselected data and combined writes roll
  back together.
- UI checkpoint: every candidate and target is reviewable/editable; no button before final confirmation
  mutates SQLite.
- Final checkpoint: all automated/browser/security gates pass and real acceptance remains human-owned.

## Risks and mitigations

- Parser abuse: 10 MiB input, format signatures, PDF page/text/time limits and DOCX ZIP/XML preflight.
- Wrong structure: exact heading aliases, conservative facts and raw-text fallback instead of inference.
- Existing-data loss: patch-like selected fields, append-only selected rows and one DB transaction.
- Privacy leak: no filename/content logs, no original-file storage, plain-text DOM and no remote runtime.
- Scope expansion: no OCR/AI/parser framework/import table/Resume builder/tailoring/Extension upload.

## Stop conditions

- Never read `操作手册.txt`, live runtime SQLite, Provider secrets or unselected files.
- Never copy OpenResume or add GPL/AGPL dependencies; stop and report if license review fails.
- Never infer missing education duration/degree, overwrite unselected Profile facts, or persist a parse result.
- Never alter Phase 7 semantics, Phase 9 Autofill, Extension permissions or no-submit behavior.
- Never declare real DOCX/PDF content quality PASS automatically, and never begin Phase 11 without approval.

---

# Historical Implementation Plan: Phase 9 — Profile Vault & Safe Job Form Autofill

> Owner-approved on 2026-09-07 from clean Phase 8 commit `eb3c9e8`. Phase 7 remains
> `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`; this phase must not change Evidence Map behavior.

## Objective

Reduce repeated recruitment-form typing with one local structured Profile and a deterministic,
user-triggered `Scan → Resolve → Preview → Confirm → Fill → Human Submit` path. The complete Phase must
work with every `JOBPILOT_LLM_*` variable absent, keep existing Extension permissions, never persist
Profile data in the Extension and never submit or advance a recruitment form.

## Implementation status

Profile/API/Web and Extension Scanner/Resolver/Preview/Executor implementation is complete. On
2026-09-07, locked dependency checks, 222 TypeScript and 224 Python tests, TypeScript typecheck, ESLint,
Prettier, Ruff, Web/Extension production builds, Extension artifact security, API import/start and
migration `upgrade -> downgrade -> upgrade` passed. All Python runtime checks used explicit temporary
SQLite databases with LLM configuration absent.

An isolated Web browser run persisted one fictional Profile with two education and two experience
entries across reload. The local form fixture passed UTF-8, DOM/accessibility structure, no-overflow and
clean-console checks after adding an explicit document charset. A real Chrome run on the China Mobile
campus recruitment form detected 37 fields (READY 1, REVIEW_REQUIRED 2, MANUAL 26, UNMAPPED 8), selected
and filled one name field, recorded attempts/success/failure 1/1/0 and did not trigger Submit/Continue.
The owner accepted the mapping and page result. Phase 9 is PASS and stops before Phase 10.

## Frozen contract

- ADR-016 owns the data, API, browser-permission, privacy and no-submit decisions. `Scan != Fill !=
  Submit` is a P0 invariant, not UI wording only.
- `AutofillProfile` is a single local resource distinct from Resume Version and Application. It contains
  the approved minimal `personal`, `education[]`, `experience[]` and `links` facts. GET returns a nullable
  wrapper; PUT performs a full validated replacement. No list, identity, history, sync or Resume import.
- `0009_autofill_profile` adds one singleton JSON-backed table and preserves every existing row. Tests and
  migration cycles use explicit temporary SQLite only; the live database receives only standard upgrade
  during later runtime acceptance.
- Extension permissions remain exactly `activeTab`, `scripting` and the approved loopback host. Profile
  and Fill Plan are ephemeral Popup memory; no storage, content script, background or recruitment host.
- Scanner returns only the frozen `FormFieldDescriptor`, ignores prohibited fields and never reads current
  values or modifies the page. Stable refs prefer unique id/name and otherwise use a round-trip DOM path.
- Resolver is finite and deterministic: exact/normalized → READY, unique fuzzy → REVIEW_REQUIRED,
  sensitive/missing-value/non-fillable → MANUAL, unknown → UNMAPPED. No confidence percentage or LLM.
- Preview masks phone/email, defaults only READY to selected and lets the user deselect. REVIEW_REQUIRED
  needs an explicit user selection; MANUAL/UNMAPPED cannot be filled.
- Executor validates page/ref/signature, uses native setters and standard events, fills only unambiguous
  native selects/combobox options and never touches file/password/CAPTCHA/legal fields. It never calls any
  submit/continue/agreement action and never creates or mutates Application.
- Third-party research remains reference-only unless an explicit later diff records MIT attribution.
  jobApplier source is never copied; private React/Phoenix component hooks are never used.

## Ordered slices

1. Freeze ADR-016, this plan/checklist and Phase 10 stop boundary; verify the starting branch and protected
   local files.
2. RED/GREEN Profile domain, singleton migration, repository/service and GET/PUT API. Verify validation,
   empty state, full replacement, restart persistence and upgrade/downgrade/upgrade on temporary SQLite.
3. RED/GREEN shared wire types and api-client strict validation/credential-free GET/PUT; prove malformed
   profile responses and non-loopback bases fail closed.
4. RED/GREEN Web “求职资料” view with create/edit/save, multiple education/experience rows, data-minimization
   copy, loading/error/empty states, keyboard access and 320/768/1024/1440 layouts.
5. RED/GREEN Extension Scanner and stable refs using a synthetic local form fixture. Cover labels, supported
   controls, visibility, prohibited inputs, options, JobPilot UI and no mutation/value reads.
6. RED/GREEN deterministic Resolver and Fill Preview. Cover aliases, normalization, fuzzy review, sensitive
   manual handling, unknown/missing values, multi-row order, masking and deselection.
7. RED/GREEN Fill Executor for text/textarea/native select/date/conservative combobox, standard events,
   missing/stale refs, changed page and partial failure. Add explicit no-submit/no-private-API safety tests.
8. Integrate Popup states and API/profile navigation without regressing BOSS/Nowcoder capture. Build and scan
   the final artifact for permissions, storage, secrets, remote runtime, telemetry and submit capabilities.
9. Synchronize canonical and technical docs, run locked installs and all TypeScript/Python/lint/format/
   typecheck/build/import/migration gates, then perform code review and simplification.
10. Run isolated browser fixture acceptance and then one real user-opened recruitment/ATS form. Record only
    factual metrics and real Bad Cases. Stop for owner mapping/page-result confirmation before Phase 9 PASS.

## Checkpoints

- Profile checkpoint: API, migration, client and Web persistence pass with no Provider configuration.
- Browser logic checkpoint: Scanner/Resolver/Executor tests prove conservative mapping and no submit.
- Integration checkpoint: Extension capture and Autofill coexist with the unchanged manifest surface.
- Final checkpoint: all automated/security/regression gates pass; real form is filled without Submit; owner
  explicitly accepts mapping and page result; Critical 0 and Required 0.

## Risks and mitigations

- Wrong field/DOM: finite aliases, fuzzy review-only, per-field signature validation and stale-session abort.
- Sensitive action: manual policy precedes mapping; prohibited input kinds are ignored or non-fillable.
- Framework compatibility: native setters and standard events only; unsupported widgets fail conservatively.
- Profile leakage: SQLite only, ephemeral Extension memory, plain-text rendering and content-free logs/tests.
- Scope explosion: generic current DOM first, no ATS registry, platform Adapter, automation DSL or AI mapper.

## Stop conditions

- Never read, log, commit or remotely transmit real Profile values; tests/fixtures use fictional data only.
- Never add broad permissions, persistent scripts/storage, cookies, webRequest, proxy, history or private APIs.
- Never auto-submit, click continue/agreement, upload files, solve verification or infer Application state.
- Never change Phase 6/7 AI behavior or claim Phase 7 PASS.
- Never claim real acceptance before user review, and never begin Phase 10 without explicit approval.

---

# Historical Implementation Plan: Phase 8 — Interview Record & Feedback Loop

> Owner-approved on 2026-09-06. Phase 7 remains `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`;
> this independent phase must not change its Evidence Map prompt, schema, evaluation or acceptance.

## Objective

Complete the local job-search feedback loop from Application through interview rounds, actual
questions, manual self review and outcome facts. Compute a deterministic local Feedback Summary
directly from SQLite. The whole phase must work with every `JOBPILOT_LLM_*` variable absent and must
not add LLM, RAG, Agent, telemetry, event tracking, scoring or an analytics framework.

## Implementation status

Backend, shared contracts, Web Interview/Question/Application outcome flows, factual Feedback Summary
and responsive styling are implemented through `a463613`; supporting documentation is current through
`066a11b`. Automated and provider-free isolated browser acceptance use an explicit temporary SQLite
database and verify one completed round, three fictional questions, self review, outcome/rejection
reason, Resume Version and source groups, clean console output, four responsive widths and API restart
persistence.

Final real-workspace acceptance passed on 2026-09-07. The stale 8001 process was identified and stopped
by exact PID, then the supported current API upgraded `runtime-data/jobpilot.db` from revision
`0007_evidence_map_schema_v2` to `0008_interview_feedback`. Existing counts remained unchanged: three
Jobs, two Applications, three JD Analyses, one Resume Version and three Evidence Maps. The acceptance
reused the existing Nowcoder Application without duplication, created one de-identified round and three
questions, edited a question, persisted all four self-review fields and exercised
PLANNED -> COMPLETED -> CANCELLED -> COMPLETED while the Application stayed `planned`.

SQLite-derived Feedback values, restart persistence, required-field PATCH null 422 behavior, existing
BOSS/Nowcoder/Job/Application/JD Analysis/Resume/Evidence Map behavior and security scans all passed.
Critical and Required findings remain zero. Phase 8 is PASS; stop before the next phase.

## Frozen contract

- `InterviewRound` belongs to one Application and contains a name, `PHONE|VIDEO|ONSITE|OTHER` type,
  optional schedule, `PLANNED|COMPLETED|CANCELLED` status, interviewer note and four optional manual
  review fields: what went well, what could improve, learning notes and other notes.
- `InterviewQuestion` belongs to one round and contains the actual question, one of the seven approved
  categories, the user's manual answer summary, `GOOD|OK|POOR|NOT_SURE` self-assessment and a note.
- Application adds nullable `outcomeNote` and `rejectionReason`. `outcomeNote` also covers minimal Offer
  information; no separate Offer or Outcome state machine is created. A non-null rejection reason is
  valid only while the effective Application status is `rejected`, and leaving that status clears it.
- Creating or completing a round never changes Application status. Updating Application status or
  outcome remains a separate explicit user action.
- Round deletion cascades questions. Application deletion cascades rounds and questions; Job deletion
  continues to cascade through Application. All content is untrusted plain text stored only in SQLite.
- Resource endpoints follow the existing camelCase/error conventions. Application interview lists are
  paginated and include each round's questions to avoid client N+1 requests; writes remain JSON-only.
- `GET /api/v1/feedback-summary` performs direct factual queries. It stores no derived rows and calls no
  external service. Counts cover Jobs, Applications, Applications with at least one InterviewRound,
  rounds, questions, offers and rejected Applications.
- Funnel stages are saved Jobs -> Applications -> Applications with a recorded interview -> current
  Offer Applications. Each rate uses the immediately preceding count as denominator and is `null` when
  that denominator is zero or incomplete intermediate records make the later count exceed it. Counts
  remain factual and are never clamped or inferred. Empty feedback never renders a misleading 0% success
  rate.
- Category/performance/rejection-reason summaries are counts. Weak categories use deterministic
  `OK + POOR`, include only positive weak counts and sort by weak count, question count and enum order.
  Resume-version and source summaries report Application, interviewed-Application and Offer counts
  without causal conclusions or recommendations.

## Ordered work

1. Freeze ADR-015, this plan/checklist, model/API/statistics/privacy rules and the next-phase stop.
2. RED/GREEN domain validation, migration, persistence, cascades and Application outcome fields.
3. RED/GREEN round/question CRUD and deterministic feedback-summary API without Provider configuration.
4. RED/GREEN shared wire types and credential-free api-client response validation.
5. RED/GREEN Job Detail interview records, questions, self review and explicit outcome UX.
6. RED/GREEN factual Feedback Summary view, empty/populated states, responsive and keyboard behavior.
7. Synchronize canonical docs; run Python/TypeScript/build/migration/security and existing regression gates.
8. Run one user-visible local acceptance, restart persistence, code review and simplification; stop.

## Checkpoints

- Backend: fresh/head migration, CRUD, cascade, outcome and deterministic statistics tests pass.
- Client: shared contract/api-client tests reject malformed responses and keep `credentials: omit`.
- Web: all interaction states pass component tests and 320/768/1024/1440 browser checks.
- Final: provider-free operation, privacy/security scans and existing BOSS/Nowcoder/Job/Application/JD AI/
  Resume/Evidence Map regressions pass with Critical 0 and Required 0.

## Risks and mitigations

- Misleading funnel claims: derive interview participation from recorded rounds, publish denominators and
  return nullable rates rather than treating missing history as 0% success or showing a rate above 100%.
- Sensitive interview text leakage: never log payloads, render only React text nodes and use fictional tests.
- Cascade data loss: require explicit Web confirmation and verify round/Application/Job cascade paths.
- Large Job Detail component: keep interview and feedback UI in focused components with typed callbacks.

## Stop conditions

- Do not call an LLM or change the Phase 6/7 prompts, schemas, evaluation data or scoring rules.
- Do not create Analytics/Event/FeedbackRecord/Insight/Score storage or automatic recommendations.
- Do not infer Application status from interview actions or infer rejection reasons.
- Do not claim real acceptance or restart persistence without observing it.
- Do not begin the next phase without explicit owner approval.

---

# Historical Implementation Plan: Phase 7 — Resume Version & Evidence Map

> Owner-approved on 2026-09-05; comprehensive Evidence Map expansion approved on 2026-09-06.
> Phase 8 is not authorized.

## Objective

Add local plain-text Resume Versions, record the version explicitly used by an Application, and map
the current non-stale JD requirements to grounded quotes from one user-selected Resume Version.
Use DIRECT/PARTIAL/GAP plus deterministic counts instead of a score. Preserve every Phase 6 and
local-first boundary.

## Frozen contract

- Resume Version V1 is name + untrusted plain-text content with create/read/list/update/duplicate and
  guarded delete. No file parsing, upload, rich text, generation, full rewrite or version graph.
- `Application.resumeVersionId` is nullable and changes only through an explicit user save. Job save,
  Application creation and Evidence Map generation never infer it.
- A referenced Resume Version returns `RESUME_VERSION_IN_USE`; unused deletion cascades only its
  Evidence Map records.
- One current Evidence Map per Job + Resume Version stores versioned JSON and exact JD-analysis and
  Resume-content fingerprints. GET computes stale; failed reanalysis preserves the last valid row.
- New generation uses schema 2 and maps six current JD Analysis groups: must-have, preferred,
  responsibilities, skills, experience and education. Schema 1 must-have/preferred records remain
  readable. Summary, domain keywords and interview focus are context/preparation fields, not matching
  criteria, and stay outside the Evidence Map.
- Quotes must occur in normalized Resume content; unsupported evidence is removed and unsupported
  DIRECT/PARTIAL is downgraded to GAP. Each item shows an explicit conclusion before its grounded
  evidence and reasoning.
- Provider input is minimal and treats JD/Resume as untrusted data. It reuses the existing optional
  Provider configuration, 60-second timeout, redirect rejection, no-proxy transport and sanitized
  errors. Every outbound Resume request requires a same-action UI disclosure and confirmation.
- Web adds a minimal Resume page, Evidence Map on Job Detail and an explicit Application selector.
  It renders plain text only and displays deterministic whole-map counts, pending confirmation and
  evidence gaps across the six groups, never matching/ATS/Offer scores.

## Approved comprehensive Evidence Map increment

### Contract

- Additive requirement types are `RESPONSIBILITY`, `SKILL`, `EXPERIENCE` and `EDUCATION`; existing
  `MUST_HAVE` and `PREFERRED` values remain unchanged.
- New records use `schemaVersion: 2`; reads accept existing schema 1 and current schema 2. The SQLite
  table remains the same, with a reversible constraint migration allowing versions 1 and 2.
- The Provider must return every supplied criterion once, in the original type/text/order. It must
  lead each reason with a direct support or uncertainty conclusion and retain exact Resume quotes.
- Overall totals, items needing confirmation and evidence gaps are computed from validated mappings
  in the Web; they are not Provider-authored scores or recommendations.

### Ordered tasks and verification

1. RED/GREEN domain, migration and API tests for six-group input, schema 2 persistence, schema 1 read
   compatibility and strict unknown-type rejection.
2. RED/GREEN shared-types/api-client validation for both schema versions and all six requirement
   types; reject invalid version/type combinations.
3. RED/GREEN Web grouping, explicit conclusion, deterministic whole-map summary and main gaps while
   preserving consent/loading/error/stale behavior and responsive plain-text rendering.
4. Synchronize ADR/product/API/data/technical docs; run Python and TypeScript test/lint/format/typecheck
   and Web build gates, migration upgrade/downgrade/upgrade, review and simplification.
5. After restart, request new action-time consent before one real Provider regeneration; record real
   latency and require owner content-quality PASS/FAIL. Do not enter Phase 8.

### Success criteria

- A JD whose must-have array contains only a cohort requirement still produces mappings for any
  available responsibilities, skills, experience and education criteria.
- The UI answers each criterion explicitly, summarizes all six groups without a score, and exposes
  pending confirmation and unsupported criteria without inventing Resume facts.
- Old schema 1 records remain readable and become stale when the expanded criterion fingerprint is
  applied; successful regeneration replaces the same row with schema 2.

## Phase 7C — Semantic Evidence Matching Refinement

> Owner-approved on 2026-09-06 after real acceptance exposed overly lexical matching. Phase 7 is
> not accepted yet, and Phase 8 remains unauthorized.

### Frozen behavior

- Evidence matching is semantic: understand each requirement first, then search the complete selected
  Resume Version. Different wording and evidence from multiple sections may support the same item.
- DIRECT requires one to three grounded quotes that together prove the requirement without adding a
  user fact. PARTIAL has relevant grounded evidence but lacks a key component or needs user
  confirmation. GAP is allowed only after the complete Resume contains no reasonable supporting fact.
- Semantic inference may explain how written facts support a requirement. It may not infer or upgrade
  proficiency, work duration, education, graduation year, project scale or any other unwritten fact.
- A start date plus degree-in-progress does not establish a graduation cohort through a customary
  program-length assumption. Without an explicit graduation year, expected graduation date or stated
  program duration, a cohort requirement is at most PARTIAL and must identify the missing fact.
- Quote grounding, requirement identity/order, prompt-injection separation, schema 2, privacy,
  optional Provider behavior, no-score rules and failure preservation remain unchanged.

### Ordered tasks and verification

1. RED prompt-contract tests for whole-Resume semantic search, different wording, one-to-three combined
   quotes and the ban on customary-program-length graduation inference.
2. RED/GREEN fake-provider cases A–E for semantic DIRECT/PARTIAL/GAP outputs while retaining exact
   requirement identity and Resume quote grounding.
3. Replace the current Evidence Map instruction with the smallest frozen semantic-grounded revision;
   do not add embeddings, RAG, a vector database, LangChain or production text-specific rules.
4. Synchronize ADR/product/technical/agent docs, run all Python/TypeScript/build/security gates, then
   complete code review and simplification with Critical 0 / Required 0.
5. After restart, obtain separate action-time consent for real BOSS and Nowcoder regeneration. Record
   latency and require the owner to judge semantic quality; never declare acceptance automatically.

### Success criteria

- Cases A/C are DIRECT using differently worded, grounded Resume facts; case B is frozen as PARTIAL
  because collaboration/closure is relevant but does not alone prove end-to-end cross-team ownership.
- Case D is GAP because the complete Resume has no sales fact; case E is PARTIAL without customary
  study-duration reasoning or an asserted graduation year.
- Existing BOSS, Nowcoder, JD AI, Application, grounding, injection, privacy, Provider-optional and
  no-score regressions all remain green.

## Ordered work

1. Freeze ADR-014, plan/checklist, data/API/privacy/grounding rules and the Phase 8 stop boundary.
2. RED/GREEN Resume domain validation, migration, repository, service and CRUD/duplicate endpoints.
3. RED/GREEN nullable Application association, guarded Resume deletion and restart persistence.
4. RED/GREEN Evidence Map strict schema, requirement/quote grounding, prompt separation and stale.
5. RED/GREEN Evidence Map persistence/endpoints and failure preservation through the existing seam.
6. Extend shared types/api-client runtime validation; build Resume management, Application selector
   and Job Detail Evidence Map states with accessible responsive UI.
7. Run locked installs, all tests/lint/format/typecheck/build, migrations, security/static scans,
   BOSS/Nowcoder/Job/Application/JD-analysis regressions, review and simplification.
8. Ask the owner to create/paste one de-identified real Resume in the UI. Only after their explicit
   confirmation, run real BOSS and Nowcoder Evidence Map acceptance, Application association and
   restart checks; record real latency and owner PASS/FAIL.
9. Synchronize canonical docs and stop before Phase 8.

## Stop conditions

- Never read a Resume file from elsewhere on disk or send Resume content without current UI consent.
- Never weaken loopback/Origin/Fetch-Metadata/JSON-only/no-credentials or Provider security.
- Never persist/display an ungrounded quote, invented requirement, numeric score or stale result as
  current.
- Never claim real acceptance without the owner's UI action and human result review.
- Do not begin Phase 8 without explicit owner approval.

---

# Historical Implementation Plan: Phase 6 — JD Structured AI Analysis

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
