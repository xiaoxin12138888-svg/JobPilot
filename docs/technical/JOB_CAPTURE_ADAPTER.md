# BOSS Job Capture Adapter

## Responsibility

`BossAdapter` has three responsibilities only: reject unsupported pages, read the minimum visible
Job detail text from the current page, and return an editable capture draft with warnings. It never
saves a Job, calls BOSS network APIs, or modifies the page. It strips query/fragment data before the
draft leaves the page; the API repeats this canonicalization as the authoritative persistence boundary.

## User-triggered boundary

Opening the Popup checks only `GET /health`. A second explicit click obtains the active tab and runs
the parser once with `chrome.scripting.executeScript`. The manifest uses `activeTab`, `scripting` and
the exact `http://127.0.0.1:8000/*` host permission. There is no BOSS host permission, `tabs`
permission, background worker, registered content script, page listener, crawler, or timer.
The manifest also carries a public key that fixes the unpacked Extension ID to
`lgchonbleblfegkckndaaandoaekmgjf`; the API mutation gate permits that identity only for
`POST /api/v1/jobs` and requires its exact Origin with `Sec-Fetch-Site: none`. The key is public
identity material, not a private signing key or secret, and the Extension Origin is not added to the
Web CORS allowlist.

## DOM read rules

- Require an exact supported BOSS hostname, a Job detail URL shape, and recognizable Job detail DOM.
- Read only rendered text for title, company, location, salary and description.
- Do not read or retain full HTML, `outerHTML`, scripts, hidden application state, network responses,
  cookies, storage, tokens, account data, recruiter private information, or unrelated page content.
- Do not mutate DOM, style, buttons, forms, navigation, requests, or page JavaScript.
- Selectors must be based on a real current BOSS page and kept to a small semantic set. This document
  records the final evidence-based selectors only after that observation.

Verified selector scope:

- title/salary/location: `.job-primary .name > h1`, `.job-primary .name > .salary`,
  `.job-primary .text-desc.text-city`;
- company: the `.sider-company` whose direct `.title` is `公司基本信息`, then its first non-empty
  `.company-info a`;
- description: the `.job-detail .job-detail-section` whose header is `职位描述`, then `.job-sec-text`;
- recommendation cards, competition analysis, recruiter information, company introduction and maps
  are outside the capture scope.

## Field contract

```text
source       "boss"
sourceUrl    canonical active-tab BOSS Job detail URL without query or fragment
title        required plain text, max 200
company      required plain text, max 200
location     optional plain text, max 300
salaryText   optional plain text, max 300
description  optional plain text snapshot, max 100000
warnings     Extension-only parser warnings; never sent to the Job API
```

The Popup lets the user edit every captured Job field except source/source URL before saving.
Required-field or partial-parse failures never silently create a Job.

## Save, duplicate and fallback

Save uses the shared api-client and `POST /api/v1/jobs`, which applies the existing Job service,
server-side URL normalization and SQLite uniqueness. `409 DUPLICATE_JOB_URL` may include the
existing local Job `resourceId`; the Popup shows “该岗位已保存” and can open
`http://127.0.0.1:5173/?jobId=<local-id>`. Parse failure offers the manual Job form without building
cross-page draft storage.

## Testing

- Unit tests use only minimal, synthetic, de-identified DOM fragments for supported/unsupported,
  missing-field, whitespace, odd-text and URL cases.
- Popup tests fake Chrome/API boundaries and cover health, explicit capture, preview/edit, save,
  duplicate, errors, retry and local detail links.
- Final acceptance uses one user-opened real BOSS Job detail page with VPN/system/browser proxy off,
  then inspects Console, Network, manifest/CSP, duplicate behavior and restart persistence.
