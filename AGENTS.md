# JobPilot Agent Rules

## Current phase

Phase 6 JD Structured AI Analysis is complete and accepted. Phase 7 Resume Version & Evidence Map is `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`. Phase 8 Interview Record & Feedback Loop is owner-approved and implemented on `phase/8-interview-feedback`; automated and isolated browser acceptance are complete, while real runtime acceptance remains blocked until the latest API process is started. Keep only local Interview Round/Question records, manual self review, additive Application outcome detail and deterministic factual feedback statistics. Stop before the next phase. Do not change Phase 6/7 prompts, schemas, datasets or evaluation; do not add file parsing/upload, resume generation or whole-resume rewriting, matching/ATS/Offer scores, recommendations, RAG, embeddings, vector databases, Agent frameworks, AI interview features, recording/transcription, automatic submission, another recruitment platform, cloud sync, authentication, telemetry or analytics frameworks.

## Canonical context

Read ADR-008 through ADR-015, `tasks/plan.md`, `tasks/todo.md`, README, PRODUCT_SPEC, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ROADMAP, ENGINEERING_PRINCIPLES and the files in `docs/technical/`. Historical remote-identity experiments exist only at `pre-local-first-cleanup` and are not current design input.

## Toolchains

- TypeScript: pnpm; tests: Vitest.
- Python: uv; tests: Pytest; lint/format: Ruff.
- Do not create npm/Yarn locks, Poetry/Pipenv workflows, Black or isort configuration.

## Commands

- Web: `pnpm run dev:web`, `pnpm run build:web`, `pnpm run test:web`.
- Extension: `pnpm run dev:extension`, `pnpm run build:extension`, `pnpm run test:extension`.
- TypeScript gates: `pnpm run test`, `pnpm run lint`, `pnpm run format:check`, `pnpm run typecheck`.
- API: `pnpm run api:dev`, `pnpm run api:test`, `pnpm run api:lint`, `pnpm run api:format:check`, `pnpm run api:import:check`.

## Boundaries

- One installation is one local workspace. There is no account, login, session, User or multi-user ownership boundary.
- The API exposes `GET /health` plus the frozen Job, Application, JD Analysis, Resume Version, Evidence Map, Interview and factual Feedback Summary contracts. BOSS and Nowcoder capture both reuse `POST /api/v1/jobs` and the same bounded duplicate metadata. The supported launcher upgrades local SQLite before starting Uvicorn.
- Web and Extension connections to the JobPilot API and the API bind are loopback-only. Never document or default the JobPilot service to `0.0.0.0`, LAN or public hosts. Future Extension access to recruitment pages is a separate, user-triggered exact-host permission governed below.
- CORS uses exact reviewed loopback Web origins and no credentials; never use wildcard or regex. Writes additionally enforce loopback Host, safe browser origin/fetch metadata and JSON content. The Extension Origin is not in API CORS; its mutations require the exact stable JobPilot Extension Origin derived from the manifest public key plus `Sec-Fetch-Site: none`, never an arbitrary valid Extension ID.
- Preserve SQLite/SQLAlchemy/Alembic and existing runtime data; never delete, replace, inspect through tests, or commit `runtime-data/jobpilot.db`. Phase 8 adds only `interview_rounds`, `interview_questions`, nullable Application outcome fields and no derived-statistics storage.
- Installed core must work in Mainland China without VPN, proxy or special DNS and without remote identity, CDN, fonts/scripts, telemetry, update APIs or mandatory foreign AI.
- Extension bundles all code, never modifies proxies, and uses only `activeTab`, `scripting` and the exact loopback host. BOSS and Nowcoder capture require a user gesture, current rendered DOM and separate real no-proxy acceptance; there is no background/content script or recruitment-site host permission.
- Treat API responses, DOM, pasted text, URLs and files as untrusted at their boundaries.
- Write a failing behavior test before logic, implement the smallest GREEN, and run affected gates after each increment.
- Resume content is untrusted private plain text. It stays in local SQLite unless the user explicitly confirms an Evidence Map request; then send only the selected version content and current non-stale JD requirements through the existing optional Provider. Never log, fixture, commit, render as HTML, or expose raw Provider content.
- Ground every displayed Resume quote after whitespace normalization. New generation may combine one to three continuous quotes found anywhere in the complete selected Resume; remove unsupported quotes and downgrade DIRECT/PARTIAL with no valid quote to GAP. Match semantic evidence rather than keyword overlap, but never add or upgrade an unwritten user fact. Enrollment plus degree-in-progress does not establish a graduation cohort without an explicit graduation year, expected graduation date or stated program duration. New Evidence Maps use schema 2 and preserve the current JD Analysis order across must-have, preferred, responsibility, skill, experience and education; schema 1 remains read-only compatible. Each item leads with an explicit conclusion, and whole-map totals/gaps are deterministic, never scores.
- Interview questions, answers, review and outcome text remain untrusted local-only content: never log it, send it remotely, expose it to the Extension or use it in tracked real-data fixtures. Interview actions never infer or mutate Application status.
- Write a failing behavior test before logic, keep coherent changes incremental, synchronize docs, remove dead abstractions, and stop before the next phase until the project owner explicitly approves it.
