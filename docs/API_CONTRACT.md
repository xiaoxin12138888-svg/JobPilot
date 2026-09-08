# JobPilot API Contract

> 状态：`GET /health`、Job/Application、BOSS/牛客 capture、Job Analysis、Resume Version、
> Evidence Map、Interview、Feedback Summary、Autofill Profile 与 Local Resume Import contract 已由
> ADR-017 冻结。Resume Import 实现和自动化已完成，等待真实简历人工验收。JSON 字段使用
> camelCase。

## 1. Runtime boundary

默认 API origin 为 `http://127.0.0.1:8000`，只支持 loopback。没有账号、cookie、token、
session 或用户 endpoint。客户端请求使用 `credentials: omit`、`cache: no-store`、
`redirect: error`。核心请求 timeout 为 5000 ms；显式 JD 分析请求使用 35000 ms 客户端 timeout，
Evidence Map 生成使用 65000 ms 客户端 timeout，后端 LLM Provider request timeout 集中配置为
60 秒。

写入还要求 loopback Host、安全的 Origin/Fetch Metadata 与 `application/json`。
CORS 只列精确 Web origin 和 `GET, POST, PUT, PATCH, DELETE`，不允许 credentials。
JobPilot Extension 只可写入 `POST /api/v1/jobs`，并要求精确 Origin
`chrome-extension://lgchonbleblfegkckndaaandoaekmgjf` 与 `Sec-Fetch-Site: none`；该 Origin
不属于 CORS allowlist，其他 Chrome Extension ID 即使格式合法也不受信任。
唯一例外读路径是 `GET /api/v1/autofill-profile`：精确 JobPilot Extension Origin、
`Sec-Fetch-Site: none` 与 loopback Host 的组合可读；其他 Extension、普通跨站网页或非 loopback
target 均为 403。Profile PUT 不向 Extension 开放。

`POST /api/v1/resume-imports/parse` 是唯一 multipart 例外：它不持久化数据，只接受精确合法 Web
Origin、非 cross-site Fetch Metadata 和 loopback Host。其他 POST/PUT/PATCH（包括 import confirm）
继续只接受 `application/json`。Parse 还要求有界 `Content-Length`，并在 multipart 解析前拒绝超过
10 MiB 文件上限加 64 KiB 协议开销的请求；文件读取后继续执行精确 10 MiB 二次校验。

## 2. Health

`GET /health` 返回：

```json
{"status":"ok","service":"jobpilot-api"}
```

该请求不查询数据库或远程服务。

## 3. Job endpoints

### `POST /api/v1/jobs`

```json
{
  "title": "AI 产品经理实习生",
  "company": "测试公司",
  "location": "上海",
  "salaryText": "200-300 元/天",
  "source": "manual",
  "sourceUrl": "https://example.com/jobs/1",
  "description": "JD 快照",
  "notes": "本地备注"
}
```

`title`、`company` 必填；其他字段可为 null/省略，source 可为 `manual`、`boss` 或 `nowcoder`。
`boss` 必须携带精确 `www.zhipin.com/job_detail/{id}.html` 岗位详情 URL；`nowcoder` 必须携带
精确 `www.nowcoder.com/jobs/detail/{numeric-id}` 岗位详情 URL。成功为 201。Web 手动录入与
两个 Extension Adapter 均进入此 endpoint 和同一个 Job service；不存在 capture 专用保存接口。
服务端会严格校验平台 hostname/path，并把 BOSS/牛客 `sourceUrl` 都规范化为 scheme、host、path，
不保存 query 或 fragment；因此同一岗位的不同 tracking/session query 返回相同的 409 重复结果。
`manual` URL 继续保留有意义的 query。

### `GET /api/v1/jobs`

Query：

- `keyword`：title/company/location 简单包含匹配，最多 200 字符；
- `source=manual|boss|nowcoder`；
- `applicationStatus`：正式 Application status；
- `limit`：默认 50，1–100；
- `offset`：默认 0，非负。

按 `updatedAt` 倒序。响应：

```json
{"items":[],"total":0,"limit":50,"offset":0}
```

item 是 Job response，并增加 `applicationStatus`（可为 null）。

### `GET /api/v1/jobs/{jobId}`

返回 Job 或 404。

### `PATCH /api/v1/jobs/{jobId}`

接受 create 字段的非空 patch（可使用 null 清空可选字段），返回更新后的 Job。

### `DELETE /api/v1/jobs/{jobId}`

成功为 204；真实删除 Job 并由数据库级联 Application、JD analysis 与 Evidence Map。Web 必须在
调用前明确确认。

Job response 字段为：`id`、`title`、`company`、`location`、`salaryText`、
`source`、`sourceUrl`、`description`、`notes`、`createdAt`、`updatedAt`。
`normalizedSourceUrl` 是持久化去重字段，不公开。

## 4. Application endpoints

### `POST /api/v1/jobs/{jobId}/application`

JSON body 固定为空对象 `{}`。创建 `planned` Application，成功为 201。Job 不存在为 404；
该 Job 已有关联 Application 为 409。

### `GET /api/v1/applications`

支持 `jobId`、`status`、`limit`、`offset`；岗位详情使用 `jobId` 精确读取其至多一条
Application。列表 item 除 Application 字段外增加 `jobTitle` 与 `company`。

### `GET /api/v1/applications/{applicationId}`

返回 Application 或 404。

### `PATCH /api/v1/applications/{applicationId}`

```json
{"status":"applied","confirmApplied":true}
```

也可只显式设置或清空本次实际使用的简历版本：

```json
{"resumeVersionId":"resume-id"}
```

```json
{"resumeVersionId":null}
```

状态必须符合领域流转表。任何进入 `applied` 的请求都要求 `confirmApplied: true`。不存在的
Resume Version 拒绝；省略 `resumeVersionId` 表示不修改该关联，不得自动推断。

结果说明与淘汰原因也通过同一 endpoint 显式设置或清空：

```json
{"outcomeNote":"二面后未通过","rejectionReason":"COMMUNICATION"}
```

`rejectionReason` 只允许在有效状态为 `rejected` 时非空；离开 `rejected` 且未显式提交该字段时，
已有原因会自动清空。允许值为 `TECHNICAL|EXPERIENCE|PRODUCT|BUSINESS|COMMUNICATION|ROLE_FIT|HEADCOUNT|UNKNOWN|OTHER`。
`outcomeNote` 是用户记录的普通结果说明，也承载最小 Offer 信息，不代表系统判断。

Application response 字段为：`id`、`jobId`、`status`、`resumeVersionId`、`outcomeNote`、
`rejectionReason`、`appliedAt`、`createdAt`、`updatedAt`。

## 5. Interview endpoints

### `GET /api/v1/applications/{applicationId}/interviews`

使用 `limit`（默认 50，1–100）与非负 `offset`，返回该 Application 的面试轮次及每轮完整
`questions` 数组，避免客户端逐轮查询。Application 不存在返回 404。

### `POST /api/v1/applications/{applicationId}/interviews`

```json
{
  "roundName": "一面",
  "interviewType": "VIDEO",
  "scheduledAt": "2026-09-07T10:00:00Z",
  "status": "PLANNED",
  "interviewerNote": "产品负责人",
  "wentWell": null,
  "couldImprove": null,
  "learningNotes": null,
  "otherNotes": null
}
```

`roundName` 必填；`interviewType` 为 `PHONE|VIDEO|ONSITE|OTHER`；`status` 默认为 `PLANNED`，
并只允许 `PLANNED|COMPLETED|CANCELLED`。成功为 201。创建、完成、取消或删除轮次不修改
Application 状态。

### `GET /api/v1/interviews/{interviewId}`

返回一个轮次及其 `questions`，不存在为 404。

### `PATCH /api/v1/interviews/{interviewId}`

接受 create 字段的非空 patch，可独立清空可选文本/时间。手动复盘字段为 `wentWell`、
`couldImprove`、`learningNotes`、`otherNotes`。返回更新后的轮次与全部 questions。

### `DELETE /api/v1/interviews/{interviewId}`

成功为 204，并级联该轮所有问题。Web 调用前必须明确确认。

### `POST /api/v1/interviews/{interviewId}/questions`

```json
{
  "question": "请描述一次需求取舍",
  "category": "PRODUCT",
  "answerSummary": "用户自己的回答摘要",
  "performance": "OK",
  "note": "需要补充量化依据"
}
```

`question` 与 `category` 必填。category 允许
`PRODUCT|AI|TECHNICAL|PROJECT|BEHAVIORAL|BUSINESS|OTHER`；performance 默认为 `NOT_SURE`，
允许 `GOOD|OK|POOR|NOT_SURE`。成功为 201。

### `PATCH /api/v1/interview-questions/{questionId}`

接受 question create 字段的非空 patch，返回更新后的问题。

### `DELETE /api/v1/interview-questions/{questionId}`

成功为 204。轮次与问题响应中的文本都是本地不可信纯文本；API 不调用 Provider、不写内容日志。

Interview Question response 字段为：`id`、`interviewRoundId`、`question`、`category`、
`answerSummary`、`performance`、`note`、`createdAt`、`updatedAt`。Interview Round response 字段为：
`id`、`applicationId`、`roundName`、`interviewType`、`scheduledAt`、`status`、
`interviewerNote`、四个复盘字段、`questions`、`createdAt`、`updatedAt`。

## 6. Feedback Summary endpoint

### `GET /api/v1/feedback-summary`

无 body/query，返回请求时直接从 SQLite 计算的事实：

```json
{
  "hasData": true,
  "totals": {
    "savedJobs": 1,
    "applications": 1,
    "interviewApplications": 1,
    "interviews": 1,
    "questions": 3,
    "offers": 0,
    "rejected": 1
  },
  "funnel": [
    {"stage": "SAVED_JOBS", "count": 1, "conversionRate": null},
    {"stage": "APPLICATIONS", "count": 1, "conversionRate": 1.0},
    {"stage": "INTERVIEW_APPLICATIONS", "count": 1, "conversionRate": 1.0},
    {"stage": "OFFERS", "count": 0, "conversionRate": 0.0}
  ],
  "questionCategories": [],
  "performances": [],
  "weakCategories": [],
  "rejectionReasons": [],
  "unrecordedRejectionReasons": 0,
  "resumeVersions": [],
  "sources": []
}
```

`conversionRate` 以前一阶段 count 为分母；分母为零或后一阶段 count 大于前一阶段时为 null。
`weakCategories` 只统计 `OK + POOR`，并返回 `category`、`questionCount`、`weakCount`。来源与简历
版本分组只含 `applications`、`interviewApplications`、`offers`。该 endpoint 不存派生结果、不读取
简历正文、不调用 Provider，也不返回分数、建议或因果结论。

## 7. Job analysis endpoints

### `GET /api/v1/jobs/{jobId}/analysis`

存在的 Job 始终返回 200：

```json
{"isConfigured":true,"analysis":null}
```

`analysis: null` 表示从未分析。未配置时 `isConfigured: false`；读取不调用 Provider。已有结果包含
`id`、`jobId`、`schemaVersion: 1`、`result`、`isStale`、`createdAt`、`updatedAt`。

### `POST /api/v1/jobs/{jobId}/analysis`

严格空 JSON body `{}`。创建或覆盖该 Job 唯一的当前分析，成功返回与 GET 相同的资源结构。
只发送 title/company/description 与可选 location/salaryText；空 JD 为 422，Job 不存在为 404。

`result` 固定字段：`summary`、`responsibilities`、`mustHaveRequirements`、
`preferredRequirements`、`skills`、`experienceRequirements`、`educationRequirements`、
`domainKeywords`、`interviewFocus`。除 summary/skills/keywords 外的数组 item 为
`{"text":"...","evidence":"..."|null}`。缺失信息用空字符串/数组，不返回 Markdown。

## 8. Resume Version endpoints

### `GET /api/v1/resume-versions`

支持 `limit`（默认 50，1–100）与非负 `offset`，按 `updatedAt` 倒序返回标准分页结构。
每项字段为 `id`、`name`、`content`、`applicationCount`、`createdAt`、`updatedAt`。

### `POST /api/v1/resume-versions`

```json
{"name":"AI 产品经理版","content":"虚构或用户主动粘贴的纯文本简历正文"}
```

名称和正文必填；成功为 201。正文只按不可信纯文本保存。

### `GET /api/v1/resume-versions/{resumeVersionId}`

返回一个 Resume Version 或 404。

### `PATCH /api/v1/resume-versions/{resumeVersionId}`

接受 `name` 和/或 `content` 的非空 patch；返回更新结果。正文变化不会删除旧 Evidence Map，
读取时会显示 stale。

### `POST /api/v1/resume-versions/{resumeVersionId}/duplicate`

```json
{"name":"AI 产品经理版 副本"}
```

复制原正文并使用用户提供的新名称；成功为 201。

### `DELETE /api/v1/resume-versions/{resumeVersionId}`

未被 Application 引用时成功为 204，并级联该版本的 Evidence Map；被引用时返回
`409 RESUME_VERSION_IN_USE`，不删除历史关联。

## 9. Evidence Map endpoints

### `GET /api/v1/jobs/{jobId}/evidence-map?resumeVersionId={resumeVersionId}`

存在的 Job 与 Resume Version 返回 200，读取不会调用 Provider：

```json
{"isConfigured":true,"evidenceMap":null}
```

已有记录包含 `id`、`jobId`、`resumeVersionId`、`schemaVersion: 1|2`、`result`、`isStale`、
`createdAt`、`updatedAt`。schema 1 是只含 must-have/preferred 的旧记录；schema 2 是六类条件的
当前格式。当前 JD Analysis 或 Resume content 指纹变化时 `isStale: true`。

### `POST /api/v1/jobs/{jobId}/evidence-map`

```json
{"resumeVersionId":"resume-id","confirmExternalAi":true}
```

`confirmExternalAi` 只接受字面值 `true`，证明 Web 已完成本次外发告知。Job/Resume 缺失为 404；
JD Analysis 缺失、stale 或其他前置条件非法为 422；Provider 未配置/不可用为 503；Provider
响应非法为 502。失败不覆盖最后一个有效记录。成功的新生成固定写入 schema version 2，并在
同一个 Job + Resume Version 记录上原位更新。

`result` 只有 `mappings`；每项只有原始 `requirementText`、
`coverage: DIRECT|PARTIAL|GAP`、`resumeEvidence: [{quote}]` 与 `reason`。schema 1 的
`requirementType` 只允许 `MUST_HAVE|PREFERRED`；schema 2 允许
`MUST_HAVE|PREFERRED|RESPONSIBILITY|SKILL|EXPERIENCE|EDUCATION`。顺序固定为硬性要求、
加分项、岗位职责、技能、经验、学历，并保持各 JD Analysis 数组的原顺序。摘要、领域关键词和
面试重点不进入 mappings。Web 根据 coverage 确定性生成逐项明确结论、全图计数、待确认项与
主要证据缺口；API 不返回分数、匹配率、推荐或 Offer 概率。

新生成的 DIRECT/PARTIAL 每项含一至三条 quote，可组合完整 Resume Version 中不同 section 的
真实连续原文；措辞不必与 requirement 相同。DIRECT 表示这些事实组合后无需补充用户事实即可
完整证明要求；PARTIAL 表示存在明显相关事实，但仍缺少关键组成部分或需要用户确认；只有扫描
完整简历仍无合理支持事实时才使用 GAP。Provider 不得利用外部知识补全能力等级、工作年限、
学历、毕业年份、项目规模或其他未写事实。仅有入学时间和在读状态、没有明确毕业年份、预计毕业
时间或培养年限时，届别最多为 PARTIAL，且不得推导目标毕业年份。quote 的精确 grounding 和
旧存量记录的有界读取兼容保持不变。

## 10. Autofill Profile endpoints

### `GET /api/v1/autofill-profile`

当前尚无 Profile 时返回：

```json
{"profile":null}
```

存在时返回 single-user 当前资源：

```json
{
  "profile": {
    "personal": {
      "name": "示例用户",
      "phone": "13800000000",
      "email": "candidate@example.test",
      "currentCity": "示例市"
    },
    "education": [
      {
        "school": "示例大学",
        "major": "信息工程",
        "degree": "本科",
        "start": "2022-09",
        "end": "2026-06"
      }
    ],
    "experience": [],
    "projects": [
      {
        "name": "示例项目",
        "role": "产品负责人",
        "start": "2025-06",
        "end": "2025-08",
        "description": "完成需求分析与阶段验收。"
      }
    ],
    "links": {
      "github": "https://github.com/example-candidate",
      "portfolio": null,
      "homepage": null
    },
    "createdAt": "2026-09-07T08:00:00Z",
    "updatedAt": "2026-09-07T08:00:00Z"
  }
}
```

### `PUT /api/v1/autofill-profile`

请求体是完整替换对象，结构与上例 `profile` 相同但不含时间字段。`personal`、`education`、
`experience`、`projects`、`links` 五段必需；所有事实可为空，但整个 Profile 至少包含一个事实。
教育、经历与项目各最多 20 条，单条不得全空；月份只接受 `YYYY-MM`；链接只接受无 userinfo 的
HTTP(S)。短文本最多 300 字符，phone/email 最多 320，经历/项目描述最多 20,000，URL 最多
2,048。成功返回上面的
`{"profile": {...}}`；非法输入为 422。

该 PUT 只接受精确 loopback Web Origin、非 cross-site Fetch Metadata 与 `application/json`，不接受
Extension Origin。接口不提供 list/delete/history/sync，不接收 `userId`、Resume 文件或 Provider
配置。

## 11. Resume Import endpoints

### `POST /api/v1/resume-imports/parse`

请求为 `multipart/form-data`，只接受一个名为 `file` 的 part。只支持声明 MIME、extension 和
magic/package structure 一致的 `.pdf` 与 `.docx`，文件上限 10 MiB；缺失/畸形/超过安全边界的
`Content-Length` 在 form parsing 前拒绝。成功返回 200：

```json
{
  "fileType": "DOCX",
  "extractedText": "基本信息\n示例候选人\n...",
  "blocks": [
    {"kind": "HEADING", "text": "基本信息"},
    {"kind": "TEXT", "text": "示例候选人"},
    {"kind": "TABLE_ROW", "text": "示例大学 | 信息管理 | 本科 | 2022.09-2026.06"}
  ],
  "sections": [
    {"type": "BASIC", "heading": "基本信息", "text": "示例候选人"},
    {"type": "EDUCATION", "heading": "教育经历", "text": "示例大学 ..."}
  ],
  "profileCandidates": {
    "personal": {"name": "示例候选人", "phone": null, "email": "candidate@example.invalid", "currentCity": null},
    "education": [],
    "experience": [],
    "projects": [],
    "links": {"github": null, "portfolio": null, "homepage": null}
  },
  "warnings": [
    {"code": "TABLE_ORDER_REVIEW", "message": "检测到表格内容，请在导入前检查阅读顺序。"}
  ],
  "metrics": {
    "fileSizeBytes": 12345,
    "pageCount": null,
    "parseLatencyMs": 18,
    "extractedCharacterCount": 560
  }
}
```

`fileType` 为 `PDF|DOCX`；block kind 为 `TEXT|TABLE_ROW|HEADING`；section type 为
`BASIC|EDUCATION|EXPERIENCE|PROJECT|SKILLS|CERTIFICATES|AWARDS|OTHER`。warnings 是有界
JobPilot-owned code/message，不包含 parser traceback 或文件内容。Parse 不创建数据库行，不保存
原始文件/文件名，不调用 Provider 或远端服务。

### `POST /api/v1/resume-imports/confirm`

请求为 JSON。`resumeVersion` 与 `profileImport` 至少一项非 null：

```json
{
  "resumeVersion": {
    "name": "导入简历 2026-09-07",
    "content": "用户在预览中检查和编辑后的纯文本"
  },
  "profileImport": {
    "personal": {"email": "candidate@example.invalid"},
    "education": [
      {"school": "示例大学", "major": "信息管理", "degree": "本科", "start": "2022-09", "end": "2026-06"}
    ],
    "experience": [],
    "projects": [
      {"name": "示例项目", "role": null, "start": "2025-06", "end": "2025-08", "description": "完成需求分析。"}
    ],
    "links": {}
  }
}
```

`personal`/`links` 中省略的 scalar 和现有 education/experience/projects 全部保留；数组只追加
请求明确提交的行。请求不能用 null 清空 Profile 字段。两项同时提交时，在一个 SQLite
transaction 中创建新
Resume Version 并更新 singleton Profile；任一失败全部回滚。成功响应字段为
`resumeVersion: ResumeVersion|null` 与 `profile: AutofillProfile|null`；未选择的 target 为 null。

Confirm 不接受 filename/parse token，不修改已有 Resume Version、Job、Application 或 Evidence
Map。

## 12. Errors

所有公开错误保持：

```json
{
  "error": {
    "code": "DUPLICATE_JOB_URL",
    "message": "该岗位链接已经保存",
    "requestId": "req_...",
    "resourceId": "existing-local-job-id"
  }
}
```

`resourceId` 仅在能安全标识相关本地资源时出现。BOSS/牛客重复 URL 的 409 使用它指向已有
Job，便于 Extension 打开本机详情；其他错误保持原有三字段 envelope。

主要状态：

- 404：Job/Application/Interview/Interview Question/Resume Version 不存在；
- 409：重复 normalized URL、一个 Job 已有 Application，或 Resume Version 正被 Application 引用；
- 422：request/domain validation、非法状态流转或 Evidence Map 前置条件失败；
- 502：`AI_INVALID_RESPONSE`，Provider envelope/content/schema 无法验证；公开响应不增加诊断字段，
  本机日志只记录固定白名单失败分类，不记录任何输入或原始响应；
- 503：SQLite 暂时 locked/busy，或 `AI_NOT_CONFIGURED` / `AI_PROVIDER_UNAVAILABLE`；
- 403/415：localhost Profile 读/写与通用 mutation 安全边界；
- 500：统一未知错误，不返回 exception、SQL 或 traceback。

Resume Import 另有：

- 413 `RESUME_FILE_TOO_LARGE`；
- 415 `UNSUPPORTED_RESUME_FILE_TYPE`；
- 422 `RESUME_FILE_SIGNATURE_MISMATCH`、`RESUME_PDF_ENCRYPTED`、
  `RESUME_PDF_NO_TEXT`、`RESUME_PDF_INVALID`、`RESUME_DOCX_INVALID`、
  `RESUME_TEXT_TOO_LARGE`、`RESUME_PARSE_TIMEOUT`。

响应均带 `X-Request-Id`，其值与 error envelope 一致。
AI 错误只使用 JobPilot 文案，不返回 Key、Provider URL、raw response、HTTP body 或 traceback。
