# Phase 3 — Job & Application Checklist

## Contracts and safety

- [ ] Freeze product, data, API, architecture, roadmap and ADR-010.
- [x] Create `phase/3-job-application` from clean `adb8c40`.
- [x] Preserve `操作手册.txt`, old branches and `pre-local-first-cleanup`.
- [ ] Keep Adapter, content script, ResumeVersion, AI/RAG and cloud work out of scope.

## Backend

- [ ] RED/GREEN Job validation and URL normalization.
- [ ] RED/GREEN Application transition and explicit-applied-confirmation rules.
- [ ] Add only `jobs` and `applications` migration with upgrade/downgrade tests.
- [ ] Implement focused repositories and services; never use the real runtime DB in tests.
- [ ] Add Job/Application APIs, filters, pagination and safe public errors.
- [ ] Reassess localhost writes: Host, Origin/Fetch Metadata, JSON and SQLite-busy behavior.
- [ ] Upgrade schema before Uvicorn startup and prove restart persistence.

## Web and client

- [ ] Add shared types and strict credential-free API client methods.
- [ ] Implement API checking/unavailable recovery, empty Job library and manual Job form.
- [ ] Implement list filters, details, edit and explicitly confirmed deletion.
- [ ] Implement Application creation/status tracking and explicit applied confirmation.
- [ ] Keep original-platform action as a safe external link with zero mutation.

## Acceptance

- [ ] Run frozen/locked installs, tests, lint, format, typecheck and builds.
- [ ] Run migration upgrade/downgrade, API import/startup and restart persistence.
- [ ] Run real browser workflow at 320/768/1024/1440 plus API unavailable/recovery.
- [ ] Verify no-proxy local workflow and security/local-first scans.
- [ ] Run code review to Critical 0 / Required 0 and simplify confirmed complexity.
- [ ] Synchronize documentation, commit coherent increments and stop before Phase 4.
