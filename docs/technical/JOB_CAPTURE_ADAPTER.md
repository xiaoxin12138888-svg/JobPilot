# Job Capture Adapters

## Responsibility

`BossAdapter` and `NowcoderAdapter` each have three responsibilities: reject unsupported pages,
read the minimum visible Job-detail text from the current page, and return an editable capture draft
with warnings. Neither Adapter saves a Job, calls a recruitment-platform network API, modifies the
page, or creates an Application.

The API/domain layer is authoritative for URL validation and persistence normalization. BOSS removes
query/fragment data before the draft leaves the page; Nowcoder submits the active-tab URL and the API
removes its query/fragment before storing or deduplicating it.

## User-triggered boundary

Opening the Popup checks only `GET /health`. A second explicit click obtains the active tab, selects
one parser from a small hostname dispatch, and runs it once with `chrome.scripting.executeScript`.
The manifest uses `activeTab`, `scripting` and the exact `http://127.0.0.1:8000/*` host permission.
There is no recruitment-platform host permission, `tabs` permission, background worker, registered
content script, page listener, crawler or timer.

The manifest carries a public key that fixes the unpacked Extension ID to
`lgchonbleblfegkckndaaandoaekmgjf`; the API mutation gate permits that identity only for
`POST /api/v1/jobs` and requires its exact Origin with `Sec-Fetch-Site: none`. The key is public
identity material, not a private signing key or secret, and the Extension Origin is not added to the
Web CORS allowlist.

## Shared capture contract

Both Adapters return the same Extension contract:

```text
source       "boss" | "nowcoder"
sourceUrl    current active-tab Job-detail URL
title        required plain text, max 200 at the API boundary
company      required plain text, max 200 at the API boundary
location     optional plain text, max 300 at the API boundary
salaryText   optional plain text, max 300 at the API boundary
description  optional plain text snapshot, max 100000 at the API boundary
warnings     Extension-only parser warnings; never sent to the Job API
```

The Popup lets the user edit every captured Job field except source/source URL before saving.
Required-field or partial-parse failures never silently create a Job.

## DOM read rules

- Require an exact supported hostname, a platform-specific Job-detail path and recognizable detail
  DOM.
- Read only rendered text for title, company, location, salary and description.
- Do not read or retain full HTML, `outerHTML`, scripts, hidden application state, network responses,
  cookies, storage, tokens, account data, recruiter private information or unrelated page content.
- Do not mutate DOM, style, buttons, forms, navigation, requests or page JavaScript.
- Keep selectors in the owning Adapter and base them on a real current page, not old examples.

### BOSS verified selector scope

- title/salary/location: `.job-primary .name > h1`, `.job-primary .name > .salary`,
  `.job-primary .text-desc.text-city`;
- company: the `.sider-company` whose direct `.title` is `公司基本信息`, then its first non-empty
  `.company-info a`;
- description: the `.job-detail .job-detail-section` whose header is `职位描述`, then `.job-sec-text`;
- recommendation cards, competition analysis, recruiter information, company introduction and maps
  are outside the capture scope.

### Nowcoder verified selector scope

- supported URL: `https://www.nowcoder.com/jobs/detail/{numeric-id}`;
- detail root and title: `.job-detail-wrap`, then `.info h1.title`;
- salary/location: `.info .salary`, `.info > .extra .el-tooltip`;
- company: `.job-detail-wrap .tw-whitespace-pre-wrap`, removing only a trailing recruiter marker such
  as `·HR`;
- description root: `.job-detail-word .job-detail-infos`; only the semantic `岗位职责` and `岗位要求`
  headings and their next siblings are included;
- keyword and recommendation sections are outside the capture scope.

## Save, duplicate and fallback

Both platforms use the shared api-client and `POST /api/v1/jobs`, which applies the existing Job
service, server-side URL normalization and SQLite uniqueness. `409 DUPLICATE_JOB_URL` may include the
existing local Job `resourceId`; the Popup shows “该岗位已保存” and can open
`http://127.0.0.1:5173/?jobId=<local-id>`. Parse failure offers the manual Job form without building
cross-page draft storage. Saving or opening an original-platform URL never creates or mutates an
Application.

## Shared Adapter Review

Extracted after both real Adapters existed:

- `JobCaptureDraft`, `JobCaptureResult` and the two supported platform values;
- one current-tab orchestration and explicit BOSS/Nowcoder dispatch;
- one Popup state, preview/edit, warning, save, duplicate, retry and manual-fallback flow;
- canonical source labels from the shared wire types.

Kept platform-specific:

- hostname/path/detail-DOM detection;
- selector sets and platform-specific company/description semantics;
- DOM visible-text helpers inside each injected parser.

The DOM helpers intentionally remain duplicated. A function passed to `executeScript` must be
self-contained; importing shared closures would require a new injected runner/config/factory and make
the two readable parsers harder to audit. With only two platforms, that abstraction would relocate
complexity rather than remove it.

## Testing and acceptance

- Unit tests use only minimal, synthetic, de-identified DOM fragments for supported/unsupported,
  missing-field, whitespace, odd-text and URL cases.
- Dispatch tests prove BOSS routes only to `BossAdapter`, Nowcoder only to `NowcoderAdapter`, and
  unknown pages inject nothing.
- Popup tests fake Chrome/API boundaries and cover health, explicit capture, preview/edit, save,
  duplicate, errors, retry and local detail links for the shared flow.
- Real Chrome acceptance passed for a user-opened Nowcoder Job-detail page and a BOSS regression with
  VPN/system/browser proxy off. The Nowcoder Job persisted with its canonical queryless URL, produced
  no Application, reopened after API restart and returned the existing local Job on duplicate save.
