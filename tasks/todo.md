# Phase 3 — Job & Application Checklist

## Contracts and safety

- [x] Freeze product, data, API, architecture, roadmap and ADR-010.
- [x] Create `phase/3-job-application` from clean `adb8c40`.
- [x] Preserve `操作手册.txt`, old branches and `pre-local-first-cleanup`.
- [x] Keep Adapter, content script, ResumeVersion, AI/RAG and cloud work out of scope.

## Backend

- [x] RED/GREEN Job validation and URL normalization.
- [x] RED/GREEN Application transition and explicit-applied-confirmation rules.
- [x] Add only `jobs` and `applications` migration with upgrade/downgrade tests.
- [x] Implement focused repositories and services; never use the real runtime DB in tests.
- [x] Add Job/Application APIs, filters, pagination and safe public errors.
- [x] Reassess localhost writes: Host, Origin/Fetch Metadata, JSON and SQLite-busy behavior.
- [x] Upgrade schema before Uvicorn startup and prove restart persistence.

## Web and client

- [x] Add shared types and strict credential-free API client methods.
- [x] Implement API checking/unavailable recovery, empty Job library and manual Job form.
- [x] Implement list filters, details, edit and explicitly confirmed deletion.
- [x] Implement Application creation/status tracking and explicit applied confirmation.
- [x] Keep original-platform action as a safe external link with zero mutation.

## Acceptance

- [x] Run frozen/locked installs, tests, lint, format, typecheck and builds.
- [x] Run migration upgrade/downgrade, API import/startup and restart persistence.
- [x] Run real browser workflow at 320/768/1024/1440 plus API unavailable/recovery.
- [x] Verify no-proxy local workflow and security/local-first scans.
- [x] Run code review to Critical 0 / Required 0 and simplify confirmed complexity.
- [x] Synchronize documentation, commit coherent increments and stop before Phase 4.
