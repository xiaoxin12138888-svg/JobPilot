# JobPilot API Contract

> 状态：Phase 0–2A 已批准；ADR-006 authentication contract 已获准用于 Phase 2B 实现，真实 Auth0 配置仍待用户提供
>
> 覆盖范围：Roadmap Phase 1–4  
> 路径：业务 API 使用 `/api/v1`；基础设施探针使用 `/health`

本文档先定义 Web、Chrome Extension 与 API 之间的稳定业务契约，再由 FastAPI 实现。它不是 ORM、数据库表或 LLM Provider 响应的镜像。

## 1. 范围与约束

### 1.1 Phase 1–4 端点范围

| Phase    | 目标                                  | 本文覆盖的资源                      |
| -------- | ------------------------------------- | ----------------------------------- |
| Phase 1  | 工程基础与可部署性                    | 非版本化 health 探针                |
| Phase 2A | 认证架构门禁（无 endpoint 实现）      | auth strategy 与 transport contract |
| Phase 2B | 认证与用户数据边界                    | auth session、current account       |
| Phase 3  | Job Capture 与 Job Library            | jobs                                |
| Phase 4  | Application 与 ResumeVersion 基础闭环 | applications、resumes               |

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

| 参数        | 类型    | 默认值 | 约束          |
| ----------- | ------- | ------ | ------------- |
| `page`      | integer | `1`    | `>= 1`        |
| `pageSize`  | integer | `20`   | `1..100`      |
| `sortOrder` | enum    | `desc` | `asc`、`desc` |

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

| HTTP | 通用 code                                                                      | 语义                                      |
| ---- | ------------------------------------------------------------------------------ | ----------------------------------------- |
| 400  | `BAD_REQUEST`、`AMBIGUOUS_CREDENTIALS`、`IDEMPOTENCY_KEY_REQUIRED`             | 请求无法按协议处理或同时提供冲突凭据      |
| 401  | `AUTHENTICATION_REQUIRED`、`INVALID_CREDENTIALS`                               | 未认证或凭据无效                          |
| 403  | `FORBIDDEN`、`EMAIL_VERIFICATION_REQUIRED`、`RECENT_AUTHENTICATION_REQUIRED`   | 已认证但账号/当前会话不满足操作要求       |
| 404  | `RESOURCE_NOT_FOUND`                                                           | 当前用户范围内资源不存在                  |
| 405  | `METHOD_NOT_ALLOWED`                                                           | 路径存在但 HTTP method 不受支持           |
| 409  | `CONFLICT`、`IDENTITY_CONFLICT`、`IDEMPOTENCY_KEY_REUSED`、`QUOTA_EXCEEDED`    | 唯一性、identity 映射、幂等或资源配额冲突 |
| 413  | `PAYLOAD_TOO_LARGE`                                                            | 上传超限                                  |
| 415  | `UNSUPPORTED_MEDIA_TYPE`                                                       | 文件类型不支持                            |
| 422  | `VALIDATION_ERROR`                                                             | 语义校验失败                              |
| 429  | `RATE_LIMITED`                                                                 | 请求过多，并返回 `Retry-After`            |
| 500  | `INTERNAL_ERROR`                                                               | 未预期服务端错误                          |
| 503  | `SERVICE_NOT_READY`、`DEPENDENCY_UNAVAILABLE`、`IDENTITY_PROVIDER_UNAVAILABLE` | 服务、身份提供方或必要依赖暂不可用        |

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

| 输入                             | 上限/格式                                                                        |
| -------------------------------- | -------------------------------------------------------------------------------- |
| JSON request body                | 256 KiB；超限返回 `413 PAYLOAD_TOO_LARGE`                                        |
| `email`                          | 规范化后最多 254 字符                                                            |
| `displayName`                    | 100 字符                                                                         |
| `locale`                         | 最多 35 字符，必须是服务端支持的 BCP 47 tag                                      |
| `timeZone`                       | 最多 100 字符，必须是服务端支持的 IANA time zone                                 |
| `title`、`company`               | 各 200 字符                                                                      |
| `sourceJobId`                    | 256 字符                                                                         |
| `salaryText`、`locationText`     | 各 200 字符                                                                      |
| `description`                    | 100,000 字符，按纯文本处理                                                       |
| Application `note`、`statusNote` | 各 5,000 字符                                                                    |
| Resume `label`                   | 120 字符                                                                         |
| `sourceUrl`                      | 最多 2,048 字符，仅允许无 userinfo 的 `http`/`https` URL；服务端不主动访问该 URL |

认证、普通业务写入和上传必须分别配置按 IP/用户的限流策略；确切阈值在所属 Phase 的安全规格中冻结。所有列表已有 `pageSize <= 100`；任何端点不得接受无界数组、无界文件或无限并发。

## 3. 认证机制与传输：Phase 2A Accepted Contract

[ADR-006](DECISIONS/ADR-006-authentication-strategy.md) 推荐 Auth0 Universal Login + OIDC/OAuth 2.0，并按运行环境采用两种传输：

- **Web**：FastAPI/BFF 完成 Authorization Code 流并签发 opaque、服务端可撤销的 host-only HttpOnly session cookie。React 不接收 provider access/refresh token。
- **Extension**：`chrome.identity.launchWebAuthFlow` + Authorization Code + PKCE S256；可信 service worker 使用短生命周期 Auth0 API access bearer，并通过 rotating refresh token 续期。
- **FastAPI**：cryptographic provider proof 先生成不能访问业务资源的 `VerifiedProviderIdentity`；只有 Web callback 与 `POST /api/v1/auth/session` 可以用它 provision。本地 active User 映射成功后，Web session adapter 与 Extension bearer adapter 才生成同一种 `AuthenticatedUser`。Bearer 必须校验固定 issuer、audience、algorithm、token type、authorized party、JWKS、时间与 `sub`；ID token、query token 和冲突双凭据均被拒绝。
- **本地 User**：唯一映射为 `(identity_issuer, identity_subject) -> User.id`；email 仅是 provider 已验证的可变属性，不能自动合并 identity。

Auth0 承担注册/登录页面、provider-managed email/password、邮箱验证、密码恢复、Extension authorize/token/revoke 等 provider 协议。JobPilot 不复制 `/register`、password `/login`、`/refresh`、`/verify-email` 或 `/reset-password` endpoint，也不接收用户密码。

Web cookie-authenticated unsafe request 必须提供 session-bound `X-CSRF-Token` 并通过精确 `Origin`/Fetch Metadata 校验。Extension bearer 只由 trusted service worker 附加，不进入 popup DOM、content script、页面、URL、日志或 `storage.sync`。生产 CORS 只允许精确 Web origin 与稳定的 `chrome-extension://<id>` origin；不得使用 `*`。

生产 Web 与 API 可以 cross-origin，但必须保持 schemeful same-site，才能让 `SameSite=Lax` session cookie 随 API fetch 发送；cross-origin 时仍需精确 CORS + credentials。若实际部署只能 cross-site，必须重开 ADR-006，不能把 `SameSite=None` 当作普通环境配置。

已签发的 stateless Extension access token 在 refresh revoke/logout 后最多继续有效到短期 `exp`。任何界面和 API 文档不得虚假承诺即时 JWT 失效。

本节与下列 Phase 2B endpoint 已随 ADR-006 获负责人批准，可作为 deterministic Phase 2B 实现依据。真实 tenant/application/ID/origin/redirect/secret 不得猜测，完整边界见 [AUTH_ARCHITECTURE.md](AUTH_ARCHITECTURE.md)。

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

`displayName`、`locale`、`timeZone` 在用户完成 profile onboarding 前可为 `null`。`email` 来自已验证 identity；密码、密码哈希、`identityIssuer`、`identitySubject`、provider claims/token、session ID/hash 与认证内部字段永不返回。

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

## 6. Phase 2B — Auth and Current Account

### 6.1 Provider-owned operations（不是 JobPilot endpoint）

以下操作由 Auth0 标准 authorize/token/revoke、Universal Login 或 provider account flow 承担：

- provider-managed email/password 注册与登录；
- 邮箱验证与凭据恢复；
- 未来可选 Google connection；
- Extension Authorization Code + PKCE exchange 与 rotating refresh；
- provider refresh grant revoke。

JobPilot 不代理用户密码，不把这些路径伪装成 `/api/v1/auth/register`、password `/login` 或 `/refresh`。Auth0 原始响应也不是 JobPilot 公共 API 契约。

### `GET /api/v1/auth/web/authorize`

- Auth：不需要现有会话。该路径仅供顶层浏览器导航，不作为 fetch JSON API。
- Query：`intent=login|signup`，以及可选 `returnTo`。`returnTo` 只能是 allowlist 中的相对 Web 路径，不能是完整 URL、protocol-relative URL 或任意调用方 origin。
- `intent=login` 使用 `prompt=login`，因此 JobPilot local logout 后，即使 Auth0 SSO cookie 仍在，也不能静默恢复原用户；`signup` 只增加明确的 provider signup hint，注册页面和凭据仍由 Universal Login 所有。
- 语义：创建最长 10 分钟的一次性 server-side login transaction（intent、state、nonce、PKCE、过期时间）及其随机 browser handle hash；生产设置 host-only `__Host-jobpilot_login_tx`（`HttpOnly; Secure; SameSite=Lax; Path=/; no Domain; Max-Age=600`），显式 loopback development 使用 `jobpilot_dev_login_tx`（同属性但不设 `Secure`），然后 `302` 到精确 Auth0 authorize URL。
- 限流：应用基线按可信连接 IP 使用每 60 秒最多 10 次 login-start 的有界滚动窗口；超过时返回 `429 RATE_LIMITED` 与 `Retry-After`。多实例生产入口必须在可信边缘实施相同或更严格的聚合策略，应用不自行信任调用方提供的转发 IP header。
- 主要错误：`400 BAD_REQUEST`、`429 RATE_LIMITED`、`503 DEPENDENCY_UNAVAILABLE`。

### `GET /api/v1/auth/web/callback`

- Auth：不需要；只接受 state、server-side transaction 与发起浏览器的一次性 login-transaction cookie 三者同时匹配的 provider callback。
- Query：Auth0 返回的 `code`、`state` 或标准错误字段；所有值都视为不可信。
- 语义：验证 browser-bound transaction，交换 code，验证 OIDC identity，生成 `VerifiedProviderIdentity`。Login/signup 解析或创建本地 User、丢弃所有 provider token，并建立全新的 opaque Web session。
- 成功：以创建时完全一致的属性删除 login-transaction cookie，`303` 到已保存的 allowlisted Web path，并设置生产 `__Host-jobpilot_session` 或仅限 loopback development 的 `jobpilot_dev_session` HttpOnly cookie。credential 不进入 redirect URL。
- 失败：无论 state/cookie 是否匹配，都使可识别 transaction 失效并用完全匹配属性删除 login-transaction cookie，再 `303` 到配置中固定、同站点且不携带 provider 参数的 `/auth/error` 页面；不得透传 provider 原始错误，也不按错误类型改变 redirect target。`INVALID_CREDENTIALS`、`EMAIL_VERIFICATION_REQUIRED`、`IDENTITY_CONFLICT`、rate limit 与 provider outage 是内部安全分类，不改变浏览器可观察的 callback redirect。
- 启动例外：若 Auth/数据库 runtime 根本未配置，服务无法验证任何先前 transaction、确定部署 cookie policy 或构造固定 Web error origin；此 bootstrap 故障返回通用 `503 SERVICE_NOT_READY` JSON。已配置 runtime 内的 callback 失败仍必须遵守上面的固定 `303` 语义。

### `POST /api/v1/auth/session`

- Auth：verified provider identity required，而不是普通业务 `AuthenticatedUser`；Phase 2B 仅允许完整验证的 Auth0 API access bearer，用于 Extension 完成 JobPilot identity establishment。Web callback 在服务端调用同一 application service，不需要从 React 调此 endpoint。
- Command 语义：路径中的 `session` 表示“建立/解析 JobPilot identity context”，不是创建 JobPilot Web session；成功只返回 `UserView`，不签发 JobPilot cookie/token。
- Request：无业务 body；不得上传 ID token、refresh token、email、`userId` 或 provider profile JSON。
- 语义：完整 JWT 校验先生成不具备业务权限的 `VerifiedProviderIdentity`。Access token 必须包含 Phase 2B 冻结的 collision-resistant namespaced email 与 `email_verified` claims；缺失/未验证时拒绝。随后才按 `(issuer, subject)` 幂等解析/创建本地 User，并同步 allowlist 中的可变 claim。
- 删除门禁：若 `(issuer, subject)` 已映射 `deletion_pending` User，必须返回通用 `401 AUTHENTICATION_REQUIRED`，不能把它降格为“no mapping”或创建新 User；该 invariant 持续到 provider cutoff + max access-token lifetime + clock-skew quarantine 完成并硬删除 mapping。
- `200`：`{"data": <UserView>}`；重复调用返回同一 local User，不签发 JobPilot token。
- 主要错误：`401 AUTHENTICATION_REQUIRED`、`403 EMAIL_VERIFICATION_REQUIRED`、`409 IDENTITY_CONFLICT`、`503 IDENTITY_PROVIDER_UNAVAILABLE`。

### `GET /api/v1/auth/me`

- Auth：required；接受 Web session cookie 或 Extension API access bearer，不能同时提供冲突凭据。
- `200`：`{"data": <UserView>}`。
- `401`：`AUTHENTICATION_REQUIRED`；session/token 过期、撤销或不存在时使用同一外部语义，不泄露内部原因。

### `PATCH /api/v1/auth/me`

- Auth：required；接受 Web session cookie 或 Extension API access bearer。
- Web CSRF：cookie transport 必须提供有效 `X-CSRF-Token`、精确 `Origin` 并通过 Fetch Metadata 校验；bearer transport 不使用 cookie CSRF。
- Request：以下字段至少一个：

```json
{
  "displayName": "Lin",
  "locale": "zh-CN",
  "timeZone": "Asia/Shanghai"
}
```

`displayName` 可用 `null` 清空；`locale` 必须是支持的 BCP 47 tag，`timeZone` 必须是支持的 IANA time zone。首次 provider provisioning 不猜测这三个值，它们保持 `null` 直到用户明确设置。

- `200`：`{"data": <UserView>}`。
- 主要错误：`401 AUTHENTICATION_REQUIRED`、`422 VALIDATION_ERROR`。

### `GET /api/v1/auth/csrf`

- Auth：required；只接受有效 Web session cookie，不接受 Extension bearer。
- `200`：`{"data":{"csrfToken":"opaque-session-bound-value"}}`，并设置 `Cache-Control: no-store`。
- 语义：返回当前 Web session 的 synchronizer token。React 只保存在内存，并在每个 cookie-authenticated unsafe request 的 `X-CSRF-Token` header 回传；它不是认证 credential，不能替代 session cookie。
- `401`：`AUTHENTICATION_REQUIRED`。

### `POST /api/v1/auth/logout`

- Auth：optional Web session，由专用 logout resolver 处理；不接受 Extension bearer，也不使用普通 required-auth dependency。
- 所有请求：无论 cookie 是否存在/有效，都必须先提供精确允许的 Web `Origin` 并通过 Fetch Metadata；失败返回 `403 FORBIDDEN` 且不得发送清理 cookie，防止跨站顶层 POST 利用未随请求发送的 `SameSite=Lax` cookie 强制退出。
- 有效 session：在通用 Origin/Fetch 门禁之外，还必须提供有效 `X-CSRF-Token`，然后撤销 session。CSRF 失败返回 `403`，不清除有效 session。
- 缺失、过期、未知或已撤销 session：通过通用 Origin/Fetch 门禁后不要求 CSRF，仍使用与创建时完全一致的 cookie attributes 发送清理 cookie 并幂等返回 `204`。Session store 不可用时返回 `503` 且不修改 cookie。
- Request：无业务 body。
- 语义：幂等撤销当前 JobPilot Web server session并清 session cookie。Web callback 只请求 `openid profile email`，不保存 provider grant，所有 ID/access token 在验证后丢弃；因此 V1 这是明确的 **JobPilot local logout**，不宣称清除 Auth0 SSO cookie。下一次 login 强制 `prompt=login`，避免静默恢复共享设备上的旧账号。
- `204`：无 body；不可把 session 是否曾存在或 provider revoke 细节泄露给客户端。

Extension logout 不向 JobPilot 上传 refresh token：trusted worker 先尝试调用 Auth0 revoke，再清除 `chrome.storage.session`/trusted `chrome.storage.local`，并丢弃 popup profile。若网络或 provider 故障使撤销无法确认，本地退出仍完成，但 UI 必须明确提示远端 grant 状态未知；被复制的 refresh token 在 provider 撤销或自身过期前仍可能续期。恢复网络后，用户应从 Web 完成 recent reauthentication 并调用 revoke-all。由于 JobPilot 从未取得该 refresh token，本流程不虚构服务端自动重试。已签发 access token 最多存活到短期 `exp`。

### Deferred — `POST /api/v1/auth/sessions/revoke-all`

该 endpoint 不属于 Task 6 当前公开实现。它需要 recent reauthentication、session/User binding 与经真实 Auth0 capability 审批的 provider grant 撤销边界；这些条件冻结前，OpenAPI 不得暴露半实现路由。以下保留为后续 Phase 2B contract 草案：

- Auth：required；只允许完成 recent reauthentication 的 Web session。
- CSRF：required。
- Request：无业务 body。
- 语义：撤销当前 User 的全部 JobPilot Web sessions 与 Auth0 refresh grants。客户端必须展示已签发 access JWT 的最大残余有效窗口。
- `204`：无 body，并清当前 Web cookies。
- 主要错误：`403 RECENT_AUTHENTICATION_REQUIRED`、`503 IDENTITY_PROVIDER_UNAVAILABLE`。部分失败进入可重试安全状态，不能虚报完全成功。

### Deferred — `DELETE /api/v1/auth/account`

该 endpoint 不属于 Task 6 当前公开实现；在 restore-control durable store/KMS 与完整生命周期基础设施获批前，不发布不安全的缩减版本。以下保留为后续 contract：

- Auth：required；仅允许完成 recent provider reauthentication 的 Web session。
- CSRF：required；还需要显式不可逆确认，但确认文本/交互不属于 API credential。
- Request：无业务 body。
- 语义：幂等启动 [账号删除工作流](AUTH_ARCHITECTURE.md#9-account-deletion)。在返回 `202` 或清理任何数据前，先在普通应用备份之外持久写入 keyed `HMAC(User.id)` 的 `pending` restore marker，再把本地 User 事务性改为 `deletion_pending`；任一步未持久成功都不得确认删除。Marker 已写但本地事务失败时返回 `503` 并保留 marker 供 reconciliation/restore quarantine。两步成功后立即阻止业务访问并撤销会话，再清理所有用户业务/对象/派生数据与 provider identity。
- `202`：

```json
{
  "data": {
    "status": "deletion_pending"
  }
}
```

响应后清 Web cookies。删除 provider identity/renewable grants 并确认不能再签发 JobPilot API token 后，本地 `deletion_pending` identity mapping 仍须保留至少“已配置最大 Extension access-token lifetime + clock skew”；该 quarantine 结束前，Web callback 与 `/auth/session` 均拒绝 provisioning。只有 quarantine 和其他 cleanup 都完成后才硬删 User，避免残余 JWT 创建新账号。

JobPilot-controlled live store 尽快完成、最迟 30 天；JobPilot 生产备份从创建起最多保留 30 天。任何恢复必须在开放流量前重放独立 ledger；`pending`/`failed` marker 不过期并隔离匹配 User，`completed` marker 保留到最后一个可能含该用户的备份失效后 7 天。Ledger 只保存 keyed `HMAC(User.id)`、HMAC key version、删除时间、workflow 状态/版本和失效时间，不保存 email、provider subject 或用户内容；restore-control KMS 的相应 key version 至少保留到所有引用 marker 过期。Auth0 自有日志、备份和法定留存不受 JobPilot 30 天保证控制，必须按 Phase 2B 当期 DPA/tenant 能力披露并由负责人接受。

完成 quarantine 与硬删除后，JobPilot 不保留 `(issuer, subject)` tombstone。用户以后通过明确 hosted flow 重新注册时会得到新的 `User.id`；API 不恢复旧数据、资源 ownership、session 或 identity mapping，也不按 email 自动链接。

- 主要错误：`403 RECENT_AUTHENTICATION_REQUIRED`、`409 CONFLICT`（存在不可安全处理的生命周期冲突）、`503 DEPENDENCY_UNAVAILABLE`。

Phase 2B 不包含组织、RBAC、管理员 API、用户枚举、任意 session 管理面板、MFA 产品、自建 password/JWT issuer 或多个 provider 的账号自动合并。

### 6.2 数据导出与保留责任（不新增 Phase 2B endpoint）

- Phase 2B 的 `GET /api/v1/auth/me` 已提供当前最小 User profile 的机器可读表达；当前没有业务资源，因此不创建空壳式通用 export endpoint。
- 首个业务资源 Job 在 Phase 3 验收前必须冻结账户导出 contract，并导出 User 与全部用户自有 Job 数据。Phase 4 在接受 ResumeVersion 文件前必须把 Application、ResumeVersion 元数据和原始文件纳入导出，形成完整 MVP 账户导出。
- 删除确认页必须在删除前提供或指向当期机器可读导出，但用户无需先导出才能删除。导出只包含用户资料、自有业务记录和原始文件；不包含密码、token、session、provider 内部字段、对象 key、安全事件内部字段或 deletion ledger。
- 导出产物必须是私有、授权下载且有短期 TTL；具体格式、异步状态、下载次数与 TTL 在 Phase 3 contract review 由项目负责人批准，不能以未决定的实现细节阻塞账号删除。
- Active 业务数据在用户保留账号期间按各资源生命周期保存；账号删除的 live data、backup、ledger 和日志时限只约束 JobPilot-controlled stores。认证/安全日志不得含 credential、内容、email 或 provider subject；如需关联，只使用轮换密钥生成的伪名标识并在 30 天内删除。聚合指标不得保留用户级标识，意外写入的直接标识属于删除传播范围。Auth0 provider-side retention 按已披露并批准的 DPA/tenant policy 处理。

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

### Phase 2A 当前门禁

- [x] Managed/self-hosted/OAuth-centric 选项、Web/Extension transport、FastAPI identity/authorization boundary 和账号删除政策已形成并获批准。
- [x] Provisional password `/register`/`/login` contract 已移除；provider 与 JobPilot endpoint ownership 已明确。
- [x] 项目负责人批准 ADR-006、Auth0 参考方案与 deterministic Phase 2B 实施范围；真实 Auth0 配置仍为单独的人机门禁。

### Phase 2B–4 未来验收

- [ ] Phase 2B–4 的业务端点全部位于 `/api/v1`。
- [ ] Web session/CSRF 与 Extension PKCE/rotation 通过 AUTH_ARCHITECTURE 的负向测试，日志没有 credential。
- [ ] JWT 错误 issuer/audience/algorithm/signature/time/token type 均被拒绝；未知 `kid` 只触发可信 issuer 的有界 JWKS refresh。
- [ ] logout/revoke 测试准确表达 Extension access token 的残余 `exp` 窗口，不虚报即时撤销。
- [ ] 所有 Web logout（含缺失/失效 session）先通过 exact Origin/Fetch Metadata；只有有效 session 再要求 CSRF，跨站请求不能清 cookie。
- [ ] Extension rotation 覆盖 worker 在 request/response/storage 边界终止、`refresh_in_progress` 重启和不确定网络结果；旧 refresh token 从不重放。
- [ ] 随机 unknown `kid` 不产生逐请求 JWKS fetch；固定 URI、single-flight、cooldown、negative cache 与限流均通过测试。
- [ ] account deletion 立即阻止访问，并能从各个部分失败点幂等恢复。
- [ ] account deletion 的独立 write-ahead marker 先于 `202`/cleanup，restore 对 pending/failed/completed marker 均 fail closed。
- [ ] provider cutoff 后的残余 JWT 在整个 max-lifetime + clock-skew quarantine 中只能命中 `deletion_pending`，不能通过 `/auth/session` 创建 User；quarantine 前不硬删 mapping。
- [ ] 删除完成后的重新注册生成新 User，跨用户/旧 ID 测试证明任何旧资源都不会重新关联。
- [ ] Extension direct revoke outage 明确区分本地退出与远端 grant 未确认状态，不虚构不可实现的重试。
- [ ] 当前 Phase 的账户导出覆盖全部已实现资源；live deletion、backup age、ledger replay/expiry 和伪名日志保留通过生命周期测试。
- [ ] Web 与 Extension 调用同一业务 API，不复制状态枚举。
- [ ] 所有列表端点通过统一分页契约测试。
- [ ] 所有错误通过统一错误 schema 测试，内部异常不泄露。
- [ ] 所有私有资源通过跨用户访问隔离测试。
- [ ] 写接口覆盖同 key 重试、并发认领、key/body 冲突、multipart 指纹、TTL 回收以及公共长度/格式上限。
- [ ] Job 创建覆盖同岗位重复导入和 manual 无稳定标识测试。
- [ ] Application 状态枚举、`occurredAt`/`recordedAt`、终止态、显式 correction、分页事件及 ResumeVersion 锁定通过契约测试。
- [ ] ResumeVersion 上传覆盖大小/MIME、配额/并发、不可变版本、失败补偿和对象存储字段不泄露测试。
- [ ] ADR-006 获批且实际 tenant/client/origin/redirect/lifetime 配置已冻结后，Phase 2B 认证实现才可开始。

## 12. 当前开放决策

Phase 2B 实现前必须批准 ADR-006，并接受或修改 Auth0 的可达性、远程 tenant、本地开发、增长成本、数据处理和 DPA/provider-retention 取舍。项目负责人还必须批准或缩短 JobPilot-controlled live deletion 30 天、backup age 30 天、ledger safety margin 7 天与伪名日志 30 天上限，并接受 Phase 3/4 export milestones。实际 dev/prod issuer、audience、algorithms、authorized-party/client-ID allowlist、schemeful-same-site origins、Extension IDs、redirect/logout URLs、claim allowlist、session/access-token lifetimes 与 clock skew、provider token-issuance cutoff semantics、JWKS refresh controls、restore-ledger KMS/key retention、revoke-all/account-deletion provider capability 与最小 Management API scopes、secret storage 和依赖仍待 Phase 2B entry review；Phase 2A 不创建这些外部配置。其他新增资源、AI/RAG 能力和简历内容访问均由后续 Roadmap Phase 按需扩展。
