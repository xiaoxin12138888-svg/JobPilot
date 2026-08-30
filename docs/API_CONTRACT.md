# JobPilot API Contract

> 状态：Phase 0 已批准的 contract-first 基线；Phase 1 health 已实现并验证，等待验收  
> 覆盖范围：Roadmap Phase 1–4  
> 路径：业务 API 使用 `/api/v1`；基础设施探针使用 `/health`

本文档先定义 Web、Chrome Extension 与 API 之间的稳定业务契约，再由 FastAPI 实现。它不是 ORM、数据库表或 LLM Provider 响应的镜像。

## 1. 范围与约束

### 1.1 Phase 1–4 端点范围

| Phase | 目标 | 本文覆盖的资源 |
| --- | --- | --- |
| Phase 1 | 工程基础与可部署性 | 非版本化 health 探针 |
| Phase 2 | 认证与用户数据边界 | auth |
| Phase 3 | Job Capture 与 Job Library | jobs |
| Phase 4 | Application 与 ResumeVersion 基础闭环 | applications、resumes |

Phase 1–4 **不包含** interviews、documents、analytics、RAG、模拟面试或 AI 分析端点，也不包含招聘网站搜索、批量抓取或正式投递。

### 1.2 强制边界

- 所有业务资源都归当前用户所有。请求其他用户的资源统一返回 `404 RESOURCE_NOT_FOUND`，避免泄露资源是否存在。
- Job Capture 只接收用户在当前岗位页主动触发、确认后的数据；API 不访问招聘网站，也不接收隐藏接口响应或整页原始 HTML。
- API 使用显式请求/响应 DTO；不得序列化 ORM Model，不暴露 `userId`、去重键、对象存储 key、内容哈希等内部字段。
- LLM 的 prompt、原始文本、provider 元数据、token 统计和未验证输出不得进入公共响应。
- `saved` 是 Job 被收藏的事实，由 `savedAt` 表达；它不是 Application 状态。

## 2. 通用协议

### 2.1 URL、命名与版本

- 业务端点均位于 `/api/v1`，路径使用小写复数名词；约定客户端使用无尾斜杠形式。
- `GET /health` 是唯一不位于 `/api/v1` 的 Phase 1 运维端点，不承载业务资源或兼容性语义。
- JSON 字段与查询参数使用 `camelCase`。
- ID 是不透明字符串。客户端只能比较和回传，不得解析或假设 UUID/数据库主键格式。
- 时间使用 RFC 3339 UTC，例如 `2026-08-30T02:15:00Z`。
- 除文件上传外，请求和响应使用 `application/json`；JSON 文本使用 UTF-8 编码。
- v1 内允许新增可选字段；删除字段、改变字段类型或语义属于破坏性变更，必须进入新的主版本或先完成废弃迁移。

### 2.2 字段语义

- 响应中的可空字段固定返回 `null`，不会因无值而随机省略。
- PATCH 请求中，字段缺失表示“不修改”；显式 `null` 表示“清空”，但只适用于标记为 nullable 的字段。
- 请求出现未知字段、非法枚举或不满足约束时返回 `422 VALIDATION_ERROR`。
- 服务端返回的枚举值区分大小写；本契约中的枚举均为小写。
- 每个响应都返回 `X-Request-Id` header；客户端值必须匹配 `[A-Za-z0-9._:-]{1,128}`，缺失时由服务端生成，非法时返回 `400 BAD_REQUEST`。

### 2.3 成功响应

业务单资源响应：

```json
{
  "data": {}
}
```

列表响应：

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 0,
    "totalPages": 0
  }
}
```

需要说明创建结果时可以增加稳定的 `meta`，例如 Job 重复导入结果。`204 No Content` 不返回 JSON body。`GET /health` 使用直接的 `ApiHealthResponse`，不套业务 `data` envelope。

### 2.4 统一分页

所有列表端点接受：

| 参数 | 类型 | 默认值 | 约束 |
| --- | --- | --- | --- |
| `page` | integer | `1` | `>= 1` |
| `pageSize` | integer | `20` | `1..100` |
| `sortOrder` | enum | `desc` | `asc`、`desc` |

`sortBy` 的允许值由各端点定义，不能直接映射为任意数据库列。分页结果必须使用稳定的次级 ID 排序，避免同一时间戳下随机换页。

### 2.5 统一错误

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "title",
        "reason": "required"
      }
    ],
    "requestId": "req_opaque"
  }
}
```

- 客户端必须按 `code` 分支，不得依赖可能调整或本地化的 `message`。
- `details` 可省略，只能包含可安全展示的字段级信息。
- 任何响应都不得包含堆栈、SQL、文件路径、密钥、第三方原始响应或内部异常文本。

| HTTP | 通用 code | 语义 |
| --- | --- | --- |
| 400 | `BAD_REQUEST`、`IDEMPOTENCY_KEY_REQUIRED` | 请求无法按协议处理 |
| 401 | `AUTHENTICATION_REQUIRED`、`INVALID_CREDENTIALS` | 未认证或凭据无效 |
| 403 | `FORBIDDEN` | 已认证但无权执行该操作 |
| 404 | `RESOURCE_NOT_FOUND` | 当前用户范围内资源不存在 |
| 409 | `CONFLICT`、`IDEMPOTENCY_KEY_REUSED`、`QUOTA_EXCEEDED` | 唯一性、幂等或资源配额冲突 |
| 413 | `PAYLOAD_TOO_LARGE` | 上传超限 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | 文件类型不支持 |
| 422 | `VALIDATION_ERROR` | 语义校验失败 |
| 429 | `RATE_LIMITED` | 请求过多，并返回 `Retry-After` |
| 500 | `INTERNAL_ERROR` | 未预期服务端错误 |
| 503 | `SERVICE_NOT_READY`、`DEPENDENCY_UNAVAILABLE` | 服务或必要依赖暂不可用 |

### 2.6 幂等键

`POST /jobs`、`POST /applications`、`POST /resumes` 必须携带 `Idempotency-Key`：

- key 必须匹配 `[A-Za-z0-9._:-]{8,128}`，不得包含用户内容、邮箱或其他秘密。
- key 在“当前用户 + HTTP 方法 + 路径”范围内生效，完成记录保留 24–72 小时后由后台回收，不无限增长。
- 相同 key 与相同请求重试，返回首次请求的状态码和响应，并设置 `Idempotency-Replayed: true`。
- 相同 key 搭配不同请求内容，返回 `409 IDEMPOTENCY_KEY_REUSED`。
- 服务端必须原子认领 key；同 key 并发请求只能有一次业务提交，其余请求等待已认领结果或得到可重试响应，不能各自创建资源。
- JSON 指纹基于规范化业务 body；multipart 指纹基于服务端流式计算的文件 SHA-256 与规范化 metadata，不能依赖临时文件路径或 part 顺序。
- 幂等仅处理重试；业务唯一性仍按各资源规则处理。

### 2.7 公共资源上限

以下是 v1 初始硬边界；实现只能在 Phase 规格评审后调整，并必须继续返回结构化错误：

| 输入 | 上限/格式 |
| --- | --- |
| JSON request body | 256 KiB；超限返回 `413 PAYLOAD_TOO_LARGE` |
| `email` | 规范化后最多 254 字符 |
| `displayName` | 100 字符 |
| `title`、`company` | 各 200 字符 |
| `sourceJobId` | 256 字符 |
| `salaryText`、`locationText` | 各 200 字符 |
| `description` | 100,000 字符，按纯文本处理 |
| Application `note`、`statusNote` | 各 5,000 字符 |
| Resume `label` | 120 字符 |
| `sourceUrl` | 最多 2,048 字符，仅允许无 userinfo 的 `http`/`https` URL；服务端不主动访问该 URL |

认证、普通业务写入和上传必须分别配置按 IP/用户的限流策略；确切阈值在所属 Phase 的安全规格中冻结。所有列表已有 `pageSize <= 100`；任何端点不得接受无界数组、无界文件或无限并发。

## 3. 认证机制与传输：Phase 2 ADR 决策门

Phase 0 **不拍板**身份提供方式，也不拍板 cookie、bearer token 或 extension 专用传输方式。Phase 2 开始实现前，必须先批准认证 ADR，至少决定：

- V1 使用本地邮箱/密码、外部身份提供方还是经过论证的其他最小方案；
- Web 与 Extension 是使用 HttpOnly cookie、bearer access/refresh token，还是经过论证的混合方案；
- 登录成功时凭据通过 response body、header 或 cookie 的确切形式；
- CSRF、CORS、token/cookie 存储、轮换、撤销、过期与退出语义；
- Extension 的交互式登录流程和最小权限；
- 日志脱敏、认证限流和本地开发策略。
- 账号删除、数据导出、保留期及凭据/会话清理的数据生命周期门；其中敏感文件责任必须在 Phase 4 前落实。

因此下列 auth 端点先固定“注册、登录、退出、读取当前用户”四个产品用例和 `UserView` 响应边界；邮箱/密码请求体是供评审的最小候选方案，不是已经批准的 credential 规范。ADR 通过后必须先回写请求体、header/cookie 和会话生命周期，再编写 Phase 2 代码。凭据在任何方案中都不得放入 URL/query string。

除 health 外的端点均标记为 `Auth: required`，具体传输由该 ADR 决定。

## 4. 公共模型

### 4.1 `UserView`

```json
{
  "id": "usr_opaque",
  "email": "user@example.com",
  "displayName": "Lin",
  "locale": "zh-CN",
  "timeZone": "Asia/Shanghai",
  "createdAt": "2026-08-30T02:15:00Z",
  "updatedAt": "2026-08-30T02:15:00Z"
}
```

`displayName` 可为 `null`。密码、密码哈希和认证内部字段永不返回。

### 4.2 `ApplicationStatus`

唯一合法值为：

```text
planned | applied | screening | assessment | interviewing | offer |
rejected | withdrawn | closed
```

`saved` 明确不在该枚举中；原始设想中的 `written_test` 统一归为 `assessment`。

## 5. Phase 1 — Health

### `GET /health`

- Auth：不需要。
- 用途：验证 API 进程可导入、启动并响应；不得调用数据库、对象存储、LLM 或招聘平台。
- `200`：直接返回 `ApiHealthResponse`：

```json
{
  "status": "ok",
  "service": "jobpilot-api"
}
```

Phase 1 不提供额外 readiness、数据库探测或 `/api/v1/health/*` 兼容端点。

## 6. Phase 2 — Auth

### `POST /api/v1/auth/register`

- Auth：不需要
- Request：`RegisterInput`

```json
{
  "email": "user@example.com",
  "password": "user-provided-secret",
  "displayName": "Lin",
  "locale": "zh-CN",
  "timeZone": "Asia/Shanghai"
}
```

`email`、`password`、`locale` 与 `timeZone` 必填；`email` 写入前规范化，`timeZone` 必须是受支持的 IANA 时区。`password` 不得写入日志或错误详情，其安全策略由 Phase 2 认证 ADR/安全规格固化。`displayName` 可选。

- `201`：`{"data": <UserView>}`；credential 传输待 ADR。
- 主要错误：`409 CONFLICT`（邮箱已注册）、`422 VALIDATION_ERROR`、`429 RATE_LIMITED`。

### `POST /api/v1/auth/login`

- Auth：不需要
- Request：`{"email":"user@example.com","password":"user-provided-secret"}`
- `200`：`{"data": <UserView>}`；credential 传输待 ADR。
- 主要错误：`401 INVALID_CREDENTIALS`，且不得区分“邮箱不存在”和“密码错误”；`429 RATE_LIMITED`。

### `POST /api/v1/auth/logout`

- Auth：required（凭据的具体传输待 ADR；已失效上下文按幂等退出语义处理）
- Request：无业务 body
- 语义：使当前认证上下文失效；重复调用应安全。
- `204`：无 body。cookie/token 清理与撤销细节待 ADR。

### `GET /api/v1/auth/me`

- Auth：required
- `200`：`{"data": <UserView>}`
- `401`：`AUTHENTICATION_REQUIRED`

Phase 2 不同时接入多个身份提供方，也不包含组织/RBAC 或管理员 API。若 ADR 选择本地邮箱/密码，必须同时决定邮箱验证、凭据恢复及其公开发布门槛；本草案不以“暂不写 endpoint”假装这些安全问题不存在。

## 7. Phase 3 — Jobs

### 7.1 模型

`JobSource`：

```text
boss | nowcoder | shixiseng | liepin | iguopin | generic | manual
```

`CaptureMethod`：

```text
automatic | selection | manual
```

`CreateJobInput`：

```json
{
  "source": "boss",
  "sourceJobId": "platform-visible-id",
  "sourceUrl": "https://example.com/job/123",
  "title": "AI Product Manager",
  "company": "Example Co.",
  "salaryText": "20-30K",
  "locationText": "上海",
  "description": "User-confirmed job description",
  "captureMethod": "automatic",
  "capturedAt": "2026-08-30T02:15:00Z"
}
```

- `title`、`company`、`description`、`source`、`captureMethod`、`capturedAt` 必填。
- `sourceJobId`、`salaryText`、`locationText` 可为 `null`。`captureMethod` 为 `automatic` 或 `selection` 时 `sourceUrl` 必填；只有 `manual` 路径允许 URL 为 `null`。
- 不接受 `rawHtml`、cookie、页面脚本、隐藏接口 payload 或其他会话数据。

`JobView`：

```json
{
  "id": "job_opaque",
  "source": "boss",
  "sourceJobId": "platform-visible-id",
  "sourceUrl": "https://example.com/job/123",
  "title": "AI Product Manager",
  "company": "Example Co.",
  "salaryText": "20-30K",
  "locationText": "上海",
  "description": "User-confirmed job description",
  "captureMethod": "automatic",
  "capturedAt": "2026-08-30T02:15:00Z",
  "savedAt": "2026-08-30T02:16:00Z",
  "archivedAt": null,
  "createdAt": "2026-08-30T02:16:00Z",
  "updatedAt": "2026-08-30T02:16:00Z"
}
```

列表使用 `JobSummary`，字段同 `JobView`，但省略 `description`。

### 7.2 重复导入规则

Job 去重只在当前用户内部执行，不建立跨用户共享职位库：

1. 优先使用规范化后的 `source + sourceJobId`；
2. 缺少平台 ID 时使用 `source + 规范化 sourceUrl`；
3. 没有稳定标识的 generic/manual 内容不做模糊文本合并，只依靠 `Idempotency-Key` 防重试重复。

命中已有 Job 时不静默覆盖用户修改，返回现有资源与 `importOutcome: duplicate`。规范化键属于服务端实现细节，不向客户端暴露，客户端也不得自行构造。

### `POST /api/v1/jobs`

- Auth：required
- Header：`Idempotency-Key` required
- Request：`CreateJobInput`
- 新建：`201`，`{"data": <JobView>, "meta":{"importOutcome":"created"}}`
- 重复导入：`200`，`{"data": <JobView>, "meta":{"importOutcome":"duplicate"}}`
- 主要错误：`400 IDEMPOTENCY_KEY_REQUIRED`、`422 VALIDATION_ERROR`。

### `GET /api/v1/jobs`

- Auth：required
- Filters：`source`、`isArchived`（默认 `false`）、`q`；`q` 对规范化后的岗位名称和公司名称做不区分大小写的包含匹配，长度上限 100 字符
- Sort：`sortBy=savedAt|updatedAt`，默认 `savedAt desc`
- `200`：分页 `JobSummary[]`

### `GET /api/v1/jobs/{jobId}`

- Auth：required
- `200`：`JobView`
- `404`：`RESOURCE_NOT_FOUND`

### `PATCH /api/v1/jobs/{jobId}`

- Auth：required
- Request：以下字段至少一个：

```json
{
  "title": "AI Product Manager",
  "company": "Example Co.",
  "salaryText": null,
  "locationText": "上海",
  "description": "Corrected description",
  "isArchived": false
}
```

`salaryText`、`locationText` 可用 `null` 清空。来源、来源 URL、采集方式和采集时间属于 provenance，本 Phase 不可修改。`isArchived` 只改变 `archivedAt`，不会创建 Application 状态。

- `200`：更新后的 `JobView`
- 主要错误：`404 RESOURCE_NOT_FOUND`、`422 VALIDATION_ERROR`

Phase 3 不提供永久删除 Job、批量导入或服务端抓取端点。

## 8. Phase 4 — Applications

### 8.1 模型

`ApplicationSummary`：

```json
{
  "id": "app_opaque",
  "jobId": "job_opaque",
  "job": {
    "title": "AI Product Manager",
    "company": "Example Co.",
    "source": "boss"
  },
  "resumeVersionId": "res_opaque",
  "status": "screening",
  "statusChangedAt": "2026-08-30T03:00:00Z",
  "appliedAt": "2026-08-30T02:30:00Z",
  "closedAt": null,
  "note": null,
  "createdAt": "2026-08-30T02:20:00Z",
  "updatedAt": "2026-08-30T03:00:00Z"
}
```

`resumeVersionId`、`appliedAt`、`closedAt`、`note` 可为 `null`。`statusChangedAt` 是当前状态最后一次写入 JobPilot 的服务端时间，不等同于现实流程发生时间。只读 `job` projection 随 Application 返回，避免列表客户端逐项请求 Job；它只包含展示所需稳定字段，不替代 `GET /jobs/{jobId}`。

`ApplicationView` 当前与 `ApplicationSummary` 字段相同。状态事件通过受限、分页的嵌套读取端点返回，不随每次 Application 创建、查询或更新无界嵌入。

`ApplicationStatusEventView`：

```json
{
  "fromStatus": "applied",
  "toStatus": "screening",
  "kind": "progress",
  "note": null,
  "occurredAt": "2026-08-30T02:55:00Z",
  "recordedAt": "2026-08-30T03:00:00Z"
}
```

`occurredAt` 是用户明确提供的现实发生时间，未知时为 `null`；`recordedAt` 是服务端录入时间。创建时也记录首条事件（`fromStatus` 为 `null`）。每项是 Application 的内部追加式子记录，不是顶级业务资源，也不暴露内部事件主键。

### 8.2 状态变更规则

- 创建默认状态为 `planned`，也允许用户录入已发生流程并指定其他合法状态。
- `kind=progress` 表示真实流程变化；终止态 `rejected`、`withdrawn`、`closed` 不能再以 `progress` 离开。
- `kind=correction` 表示用户修正误录状态，可从任意状态改为任意不同合法状态，并必须提供非空 `statusNote`。
- 招聘流程不是强制单向流水线；非终止态之间不凭空限制为固定先后顺序。
- 同值 PATCH 是 no-op，不新增历史。每次真实改变都由服务端更新 `statusChangedAt` 为本次 `recordedAt` 并追加历史。
- `statusOccurredAt` 可空且只可与 `status` 同时提交；它不得晚于服务端允许的时钟偏差范围。阶段耗时优先使用 `occurredAt`，缺失时必须标注为基于 `recordedAt` 的近似统计。
- 进入 `closed` 时，`closedAt` 取 `statusOccurredAt`，未提供则取服务端 `recordedAt`；通过 correction 离开 `closed` 时清空。其他终止状态不写 `closedAt`。
- 未提供 `status` 时提交 `statusChangeKind`、`statusNote` 或 `statusOccurredAt` 返回 `422 VALIDATION_ERROR`。

### `POST /api/v1/applications`

- Auth：required
- Header：`Idempotency-Key` required
- Request：

```json
{
  "jobId": "job_opaque",
  "resumeVersionId": "res_opaque",
  "status": "planned",
  "statusOccurredAt": null,
  "appliedAt": null,
  "note": null
}
```

`status` 省略时为 `planned`。`statusOccurredAt` 可选，用于明确的历史补录。`planned` 不得同时提交非空 `appliedAt`。Job 与 ResumeVersion 必须属于当前用户。每个用户对同一 Job 最多一条 Application。

- `201`：`ApplicationView`
- 主要错误：`404 RESOURCE_NOT_FOUND`、`409 CONFLICT`（Application 已存在）、`422 VALIDATION_ERROR`

### `GET /api/v1/applications`

- Auth：required
- Filters：`status`（可重复传入）、`jobId`
- Sort：`sortBy=updatedAt|statusChangedAt|appliedAt`，默认 `updatedAt desc`
- `200`：分页 `ApplicationSummary[]`

### `GET /api/v1/applications/{applicationId}`

- Auth：required
- `200`：`ApplicationView`
- `404`：`RESOURCE_NOT_FOUND`

### `GET /api/v1/applications/{applicationId}/status-events`

- Auth：required
- Sort：仅允许 `sortBy=recordedAt`，默认 `recordedAt desc`；使用统一分页及 `sortOrder=asc|desc`
- `200`：分页 `ApplicationStatusEventView[]`
- `404`：`RESOURCE_NOT_FOUND`

该端点只读；状态事件只能由 Application 创建或状态更新用例追加，客户端不能直接创建、修改或删除历史。

### `PATCH /api/v1/applications/{applicationId}`

- Auth：required
- Request：以下业务字段至少一个：

```json
{
  "resumeVersionId": "res_opaque",
  "status": "interviewing",
  "statusChangeKind": "progress",
  "statusNote": null,
  "statusOccurredAt": "2026-08-30T02:55:00Z",
  "appliedAt": "2026-08-30T02:30:00Z",
  "note": "Prepare product case"
}
```

`note` 可用 `null` 清空。`resumeVersionId` 在 `planned` 时可设置、替换或清空；离开 `planned` 后只允许为空时补录一次，一旦非空即不能通过普通 PATCH 替换或清空。同一请求离开 `planned` 时可以同时绑定版本。`appliedAt` 只允许在状态进入或已经越过 `applied` 后从 `null` 补录一次，普通 PATCH 不得覆盖或清空已知值。提供 `status` 时 `statusChangeKind` 默认为 `progress`；`statusNote` 只写入本次状态事件，不覆盖 Application 的 `note`。

- `200`：更新后的 `ApplicationView`
- 主要错误：`404 RESOURCE_NOT_FOUND`、`409 CONFLICT`（非法状态变更、简历版本或历史时间已锁定）、`422 VALIDATION_ERROR`

Application 不提供 DELETE；退出或结束流程使用明确状态并保留审计历史。

## 9. Phase 4 — Resume Versions

ResumeVersion 是不可变文件版本；更新内容必须上传新版本，而不是覆盖旧对象。

`ResumeVersionView`：

```json
{
  "id": "res_opaque",
  "versionNumber": 3,
  "label": "AI PM - Chinese",
  "originalFilename": "resume-v3.pdf",
  "mimeType": "application/pdf",
  "sizeBytes": 248311,
  "createdAt": "2026-08-30T02:15:00Z"
}
```

`label` 可为 `null`。对象存储 key、内部 URL、内容哈希和 `userId` 不得返回。

### `POST /api/v1/resumes`

- Auth：required
- Header：`Idempotency-Key` required
- Content-Type：`multipart/form-data`
- Parts：`file`（required）、`label`（optional）
- 初始允许 `application/pdf` 与 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`；单文件上限 10 MiB。服务端必须校验声明 MIME 与实际文件类型，且不得直接信任原始文件名。
- V1 初始配额为每用户最多 50 个 ResumeVersion、总原始文件不超过 200 MiB、同时最多 2 个上传请求；超出数量/总量返回 `409 QUOTA_EXCEEDED`，超出并发返回 `429 RATE_LIMITED`。
- 服务端必须流式计数和计算哈希，使用服务端生成的私有 object key；对象不得公开或以内联可执行内容返回。恶意文件隔离/拒绝策略在 Phase 4 安全规格中冻结。
- 对象写入成功但数据库提交失败时执行补偿删除；删除失败进入可观测的孤儿对象回收流程。数据库不得指向未完成或不可确认的对象。
- `201`：新建的 `ResumeVersionView`；`versionNumber` 在当前用户范围内由服务端递增。
- 主要错误：`409 QUOTA_EXCEEDED`、`413 PAYLOAD_TOO_LARGE`、`415 UNSUPPORTED_MEDIA_TYPE`、`422 VALIDATION_ERROR`、`429 RATE_LIMITED`、`503 DEPENDENCY_UNAVAILABLE`

### `GET /api/v1/resumes`

- Auth：required
- Sort：仅允许 `sortBy=versionNumber`，默认 `versionNumber desc`；支持统一分页参数及 `sortOrder=asc|desc`。
- `200`：分页 `ResumeVersionView[]`

### `GET /api/v1/resumes/{resumeVersionId}`

- Auth：required
- `200`：`ResumeVersionView` 元数据
- `404`：`RESOURCE_NOT_FOUND`

Phase 4 不提供覆盖文件、对象存储直链、解析文本、AI 评分或简历匹配端点。若后续 Phase 需要下载/预览，将先补充受控内容访问契约。

## 10. 未来 AI 接口规则（非 Phase 1–4 端点）

- 不建立泛化的 `/api/v1/ai`、`/chat` 或“任意 prompt”端点。
- AI 能力应挂在对应业务资源的分析子资源下，例如未来 Job 分析属于 Job 的 analysis 子资源；只有进入对应 Roadmap Phase 后才定义具体路径和模型。
- 服务端流程必须是“Application Service → AI Service abstraction → Provider → Structured Result → Schema Validation → Domain DTO”。
- 公共响应只返回经过版本化 schema 校验、可解释的结构化业务结果；不得返回 provider 原始输出。
- 启用 Provider 前必须完成用户告知、最小化出站字段、留存/训练政策、区域/子处理方、删除传播和密钥隔离评审；不得把对象存储凭据或未选择的用户资料发送给模型。

本节只固定边界，不预先设计未来几十个 endpoint。

## 11. Phase 1–4 契约验收

### Phase 1 当前验收

- [x] OpenAPI 中只有 `GET /health`，且响应与 `ApiHealthResponse` 契约一致。

### Phase 2–4 未来验收

- [ ] Phase 2–4 的业务端点全部位于 `/api/v1`。
- [ ] Web 与 Extension 调用同一业务 API，不复制状态枚举。
- [ ] 所有列表端点通过统一分页契约测试。
- [ ] 所有错误通过统一错误 schema 测试，内部异常不泄露。
- [ ] 所有私有资源通过跨用户访问隔离测试。
- [ ] 写接口覆盖同 key 重试、并发认领、key/body 冲突、multipart 指纹、TTL 回收以及公共长度/格式上限。
- [ ] Job 创建覆盖同岗位重复导入和 manual 无稳定标识测试。
- [ ] Application 状态枚举、`occurredAt`/`recordedAt`、终止态、显式 correction、分页事件及 ResumeVersion 锁定通过契约测试。
- [ ] ResumeVersion 上传覆盖大小/MIME、配额/并发、不可变版本、失败补偿和对象存储字段不泄露测试。
- [ ] Phase 2 认证 ADR 获批且已回写 credential 传输细节后，认证实现才可开始。

## 12. 当前开放决策

Phase 2 实现前必须批准身份提供方式、credential 传输、会话生命周期与账号数据生命周期门。其他新增资源、AI/RAG 能力和简历内容访问均由后续 Roadmap Phase 按需扩展，不属于本草案。
