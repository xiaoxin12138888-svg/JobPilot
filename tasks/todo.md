# Phase 4 — BOSS Direct Job Capture Checklist

## Contract and safety

- [x] Receive explicit Phase 4 approval and create `phase/4-boss-job-capture` from clean `c27a987`.
- [x] Preserve `操作手册.txt`, real `runtime-data/jobpilot.db`, Phase 3 commits, and old branches.
- [x] Freeze ADR-011, capture fields, duplicate metadata, permissions, and stop boundary.
- [ ] Keep all non-BOSS platforms, AI/RAG, automation, crawling, hidden APIs, and proxy changes out.

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
- [x] RED/GREEN health, ready, parsing, preview/edit, warning, saving, saved, duplicate, failure, retry.
- [x] Use the shared api-client and existing Job creation endpoint/service.
- [x] Open the local Web detail using only the saved Job ID; manual fallback opens manual add.
- [x] Show `BOSS直聘` in Web list/detail and keep original-platform links mutation-free.
- [x] Prove capture/save does not create or mark an Application.

## Acceptance

- [ ] Run frozen/locked installs and all TypeScript/Python tests, lint, format, typecheck, and builds.
- [ ] Run migration, API import/startup, SQLite persistence, artifact/CSP, secret, remote, and log scans.
- [ ] Load unpacked in Chrome after action-time approval and run the real BOSS capture twice.
- [ ] Verify Popup, parse, preview, save, library, detail, duplicate, original URL, and restart.
- [ ] Verify console/network/privacy and full workflow with VPN/system/browser proxy off.
- [ ] Verify Web at 320/768/1024/1440 and keyboard/accessibility states.
- [ ] Run code review to Critical 0 / Required 0 and simplify confirmed complexity.
- [ ] Synchronize all canonical docs, commit coherent increments, and stop before Phase 5.
