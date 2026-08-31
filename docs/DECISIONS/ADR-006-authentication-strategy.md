# ADR-006：采用托管 OIDC 身份与双通道会话

- **Status**：Accepted
- **Date**：2026-08-30
- **Decision owner**：JobPilot 项目负责人

> **Architecture change notice（2026-08-31）**：[ADR-007](ADR-007-mainland-china-identity-provider.md) 因新增“中国大陆普通网络无代理可用”硬约束，已接受 Self-hosted Logto OSS 作为 V1 provider direction，并将本 ADR 的 Auth0 production selection 标为 `amended / superseded in part`。本 ADR 继续以 Accepted 状态保留 provider-neutral identity、Web session、Extension PKCE、FastAPI authorization 与数据安全边界；不得把方向批准解释为迁移、生产资源、Task 8 或 Phase 3 授权。

## Context

JobPilot 的 React Web、Chrome Manifest V3 Extension 和 FastAPI 必须识别同一个用户。后续 Job、Application、ResumeVersion、Interview 与 Document 都是敏感的个人资源；认证方案既要降低密码、验证邮件、凭据恢复和会话安全的自建成本，也不能让第三方身份服务绕过 FastAPI 直接访问业务数据。

Web 与 Extension 处在不同的浏览器安全环境中：Web 适合一方 HttpOnly cookie，Extension 不能可靠复用 Web cookie，也不能把长期 bearer token 放进页面、`localStorage`、content script 或源码。V1 是个人求职工作台，不需要组织、团队、角色层级、企业 SSO 或自建 OAuth/IAM 平台。

## Options Considered

### Option A — Managed Authentication

由成熟托管身份服务管理密码、邮箱验证、凭据恢复、上游社交登录和主要会话能力。JobPilot 仍拥有本地 `User`、业务授权和全部业务数据。

托管候选中的取舍：

- **Auth0**：Hosted Universal Login、标准 OIDC/OAuth 2.0、Web 后端流和 Chrome Extension public-client PKCE 流最贴合当前拓扑；代价是远程 tenant、本地离线开发较弱以及增长后的价格/租户锁定风险。
- **Supabase Auth**：成本和开源迁移路径有吸引力，JWT/FastAPI 集成清晰；但当前方案若要同时做到 Web 不在 JavaScript 保存 session、Extension 使用 hosted redirect，通常需要更多一方登录页与会话桥接设计。
- **Clerk**：前端登录体验和集成便利较强；但 SDK、组件和专有 session 模型会进入更多客户端边界，迁移成本最高。

### Option B — Self-hosted FastAPI Authentication

FastAPI 自行保存密码哈希并实现注册、邮箱验证、重置、登录限流、access/refresh token、rotation、reuse detection、撤销、多设备和安全通知。

它可以避免身份供应商锁定，也能完全控制本地开发；但认证安全会成为 JobPilot 团队长期维护的非核心产品。仅“密码哈希 + JWT”远不足以构成可发布的身份系统。

### Option C — OAuth/OIDC-centric Without a First-party Account Path

只允许 Google 或其他外部账号登录，JobPilot 不提供 provider-managed email/password 路径。

该方案同样避免保存密码，并天然适配 OIDC；但单一外部账号会把账号可达性、恢复和目标用户覆盖完全交给上游。对于主要面向国内求职者的 V1，Google-only 不是可靠的唯一入口。本地 `User` 和业务授权仍然不可省略。

### Qualitative Matrix

| Criteria                  | Managed                                                   | Self-hosted                                | OAuth-centric only                              |
| ------------------------- | --------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------- |
| Security responsibility   | Medium：供应商负责凭据核心，JobPilot 仍负责会话接入与授权 | High：凭据、恢复、token 与滥用防护全部自担 | Medium：无本地密码，但账号与 token 安全仍需处理 |
| Implementation complexity | Medium                                                    | High                                       | Medium                                          |
| Web compatibility         | Strong                                                    | Strong，但实现成本高                       | Strong                                          |
| Extension compatibility   | Strong，前提是标准 public-client PKCE                     | Medium，需要自建安全授权流                 | Strong，受上游 provider 能力限制                |
| FastAPI compatibility     | Strong：标准 issuer/audience/JWKS                         | Strong：完全自控                           | Strong：标准 OIDC 校验                          |
| Local development         | Medium：依赖远程 tenant 与 callback 配置                  | Strong，可完全本地                         | Medium：依赖外部 provider                       |
| Early cost                | Low，通常可从开发/免费层起步；增长价格需复核              | Low infrastructure、High engineering       | Low，仍受 provider 政策影响                     |
| Vendor lock-in            | Medium，可用 OIDC 与本地 User 限制                        | Low vendor、High custom-system ownership   | Medium–High，身份入口依赖单一上游               |
| Maintenance               | Low–Medium                                                | High                                       | Medium                                          |
| JobPilot fit              | Strong                                                    | Weak                                       | Medium                                          |

## Decision

V1 采用 **Managed Authentication**，参考实现选用 **Auth0 Universal Login + 标准 OIDC/OAuth 2.0**。项目负责人已批准本 ADR，并授权进入 Phase 2B 的最小实现；真实 Auth0 tenant/application 配置仍受下文人机门禁约束。

具体边界如下：

1. **身份来源**：Auth0 管理 provider-managed email/password、邮箱验证、凭据恢复和未来可选的 Google 登录。V1 不能只提供 Google 登录。
2. **本地身份**：FastAPI 只信任完成签名、issuer、audience、时间与 nonce/state 校验后的身份。它以 `(identity_issuer, identity_subject)` 唯一映射到稳定的本地 `User.id`；email 不是身份主键，也不得用于未经确认的跨 provider 自动合并。
3. **业务边界**：Auth0 不直连 JobPilot PostgreSQL，也不授权 Job/Application/Resume 等业务资源。所有客户端都必须经过 FastAPI。
4. **Web transport**：Web 登录使用 FastAPI 作为 OIDC confidential client/BFF。Authorize 时除 `state` 外还设置短期、host-only、HttpOnly 的一次性 login-transaction cookie；callback 必须同时匹配 state、transaction cookie 与服务端记录，并在成功/失败后清理。FastAPI 随后建立高熵、opaque、服务端可撤销的 `HttpOnly + Secure + SameSite=Lax` host-only session cookie；React 永远不读取 access/refresh token。
5. **Extension transport**：Extension 是独立 OIDC public client。仅在用户主动登录时调用 `chrome.identity.launchWebAuthFlow`，使用 Authorization Code + PKCE S256、`state`、`nonce` 和精确 allowlist 的 extension redirect URI。它以短生命周期 bearer access token 调用 FastAPI，并使用 provider 的 rotating refresh token 续期。
6. **FastAPI boundary**：cryptographic provider validation 先产出不具备业务权限的 `VerifiedProviderIdentity`；只有 Web callback 与 `POST /api/v1/auth/session` 可以用它幂等创建/解析本地 User。Provisioning 必须先检查现有 `deletion_pending` mapping 再进入 no-mapping 分支，残余 token 不能创建新 User。其他认证边界接受 Web session cookie 或 Extension `Authorization: Bearer`，但不接受 ID/query token，也不允许一个请求混用冲突凭据。Extension bearer 固定校验 issuer、audience、algorithm、token type、authorized party/client ID、JWKS 与时间；映射 active User 后才产出 `AuthenticatedUser`。
7. **会话默认值**：Web session 目标 idle timeout 7 天、absolute lifetime 30 天；Extension access token 目标 5–10 分钟、refresh session 目标 inactivity 30 天、absolute lifetime 90 天。Phase 2B 必须在 Auth0 当前能力和套餐内核实并冻结这些值，不能静默放宽。
8. **Extension storage**：access token 只放 service worker 内存或 `chrome.storage.session`；rotating refresh token 只放 `chrome.storage.local`，并将 access level 限制为 `TRUSTED_CONTEXTS`。不得进入 popup DOM、content script、招聘页面、`storage.sync`、日志或源码。
9. **Web CSRF**：所有 cookie-authenticated unsafe request 同时校验 session-bound CSRF token、精确 `Origin` 和 Fetch Metadata；`SameSite=Lax` 是辅助防线，不替代 CSRF 校验。
10. **退出与撤销**：Web logout 立即撤销服务端 session 并清 cookie，但 V1 明确是 local logout，不宣称清除 Auth0 SSO cookie；下一次 login 强制 `prompt=login`。Recent reauthentication 使用绑定当前 session/User 的 `prompt=login + max_age=0` transaction 并校验 `auth_time`。Extension logout 先尝试直接撤销当前 refresh grant，再清本地存储；若网络/provider 故障使撤销无法确认，必须提示远端 grant 仍可能续期并引导用户在恢复网络后从 Web recent-reauth 执行 revoke-all，不得虚构服务端自动重试。已签发的 stateless access token 最多继续有效到短期 `exp`，不得宣称 logout 能瞬时收回它。
11. **账号删除**：任何 `202` 或 cleanup 前先向普通应用备份之外的耐久 restore-control store 写入 keyed `HMAC(User.id)`、HMAC key version 和 workflow state 的 `pending` marker，再事务性标记本地 User 为 `deletion_pending`。任一步失败都不得确认删除；所有 pending/failed/completed marker 在 restore 时都阻止旧 User 重新 active，且 key version 保留到所有引用 marker 过期。随后 JobPilot 编排本地业务数据、对象、派生索引和 Auth0 identity 删除，失败可重试。Provider 确认不再签发 token 后，必须继续保留 `deletion_pending` mapping 至少一个最大 access-token lifetime + clock skew，使残余 JWT 无法 reprovision；之后才硬删 User 并完成 marker。V1 不保留 `(issuer, subject)` tombstone；quarantine 完成后的明确 hosted re-registration 创建全新 `User.id`，不恢复旧数据或 ownership。
12. **数据生命周期**：JobPilot-controlled live store 在账号删除请求后尽快清理且最迟 30 天；JobPilot 生产备份从创建起最多保留 30 天，恢复开放流量前必须重放独立 deletion ledger；认证/安全日志中的伪名用户关联最多保留 30 天。Phase 2B 的 `/auth/me` 提供当前 User profile；Phase 3 冻结并实现 User/Job 机器可读导出，Phase 4 在接受 ResumeVersion 文件前补齐 Application、ResumeVersion 和原始文件导出。上述是已接受的 V1 设计上限，不表示 Phase 2B 必须过度实现尚无现实基础设施的高级编排；Auth0 自有 logs/backups/legal retention 不在 JobPilot 保证内，须按当期 DPA/tenant 能力披露和批准。
13. **V1 权限模型**：只有普通用户，没有组织、workspace、团队、管理员矩阵或 RBAC。

## Why

- Auth0 的 hosted login 让密码、验证邮件和重置流程不进入 React、Extension 或 JobPilot 数据库。
- 标准 OIDC/OAuth 2.0 能让 Web BFF 与 Chrome Extension PKCE 分别采用适合自身环境的传输，而不伪装成“一种 token 到处用”。
- FastAPI 仍是唯一业务认证与授权边界，满足 PostgreSQL 作为业务事实来源的既有决定。
- `(issuer, subject) -> User.id` 把 provider 标识隔离在 identity 边界，业务外键不会绑定 Auth0。
- 短期 access token 与旋转 refresh token 把 Extension 凭据泄露后的影响限制在可控窗口。
- 方案避免自建密码、邮件验证、重置和完整 OAuth Server，同时保留可测试的本地会话与撤销边界。

## Security Consequences

正面影响：

- JobPilot 不保存密码、密码哈希或 provider 社交凭据。
- Web 页面 JavaScript 无法读取 session secret；Extension token 不进入不可信页面上下文。
- provider token 和 claims 在 FastAPI 仍被视为外部输入，必须严格验证后才能映射本地 User。
- 业务查询必须同时使用 `authenticated_user_id` 与 resource ID，不能依赖前端隐藏或事后判断 owner。

新增责任与风险：

- FastAPI 仍需正确实现 OIDC callback、state/nonce、server session、CSRF、JWT/JWKS 校验、CORS、日志脱敏和删除编排。
- Unknown `kid` 处理必须使用固定 JWKS URI、per-issuer single-flight、cooldown、negative cache 与限流，不能让随机 key ID 放大为逐请求 provider fetch。
- Auth0 tenant 配置、callback/redirect allowlist、密钥轮换与 Management API 权限成为生产安全配置。
- Extension refresh token 位于浏览器 profile 中；恶意扩展、被攻陷的 JobPilot Extension 或本机账户失陷仍可能窃取。短生命周期、rotation、reuse detection 和 revoke 限制损失，但不能消除本机攻陷风险。
- Extension 直连 revoke 在网络/provider 故障时无法由 JobPilot 自动重试，因为 refresh token 从未上传；本地退出与远端 grant 撤销必须在 UI 和测试中区分。
- Provider 或网络不可用会阻止新登录/刷新；已有短期会话的降级边界必须在 Phase 2B 测试。
- JobPilot 需要实施数据导出、备份过期、恢复前 deletion-ledger 重放、日志最小化与删除传播；托管身份不会替代这些本地数据责任。
- 不保留 provider identity tombstone 减少删除后的身份数据留存，但也意味着完成删除后的重新注册是一个允许的全新账号；测试必须证明它不能链接旧资源。

## Extension Consequences

- Phase 2B 需要明确增加 `identity`、`storage`、精确 JobPilot API host permission，以及 direct token exchange/revoke 所需的精确 Auth0 tenant origin host permission，并固定 dev/prod extension ID；Phase 2A 不修改 manifest。
- OIDC redirect 必须精确绑定 `https://<extension-id>.chromiumapp.org/...`，禁止 wildcard 和任意 `redirect_uri`。
- PKCE verifier、state 和 nonce 是一次性登录事务数据；trusted OIDC client 必须验证签名 ID token 的 issuer、audience 与 nonce，随后立即丢弃 ID token。登录完成、取消、超时或失败后必须清理全部事务数据。
- service worker 负责 token 与 API 调用；popup 只发送受 schema 校验的意图，content script 永远拿不到 token。
- MV3 worker 不靠 timer/keepalive 保活；刷新采用按需 single-flight，rotation 过程中并发请求共享同一结果。
- Single-flight 只覆盖当前 worker 生命周期。Refresh 前持久化 `refresh_in_progress`，成功后先写新 refresh record 再写 volatile access token；worker 中止或结果不确定时不重放旧 token，而是清理并要求交互式登录。
- Direct revoke 失败后 worker 仍清除本地 credential，但必须展示远端状态未知及 Web revoke-all 恢复路径；不能声称 provider grant 已失效或已排队重试。

## Web Consequences

- React 只观察 `GET /api/v1/auth/me` 的会话状态，不保存、解析或刷新 provider token。
- 生产 cookie 使用 `__Host-` 约束、`Secure`、`HttpOnly`、`SameSite=Lax`、`Path=/` 且不设置 `Domain`。只有显式 loopback development 可使用不带 `Secure` 的 `jobpilot_dev_session` / `jobpilot_dev_login_tx`；login transaction 最长 10 分钟，其他非 HTTPS 环境启动失败。
- Web 与 API 的生产 origin **必须 schemeful same-site**；可以 cross-origin，但此时只允许精确 Web origin、`credentials=true`，绝不允许 `*`。若部署只能 cross-site，必须重开本 ADR，不能静默把 cookie 放宽为 `SameSite=None`。
- HttpOnly 降低 token 被 XSS 直接窃取的风险，但 XSS 仍可代表用户发请求；CSP、安全渲染、CSRF 与输入输出校验仍然必需。

## Migration / Lock-in

- 业务表只引用本地 `User.id`；Auth0 `sub` 不进入 Job、Application、ResumeVersion 等外键。
- provider 细节被限制在 OIDC client、JWT validator、session/revocation adapter 和账号生命周期 adapter。
- 通用登录使用 Authorization Code、PKCE、OIDC claims 与 JWKS；这些部分可迁移到其他兼容 provider。
- Hosted UI 配置、Auth0 Actions/claims、Management API、refresh/revocation 语义和 tenant export 属于真实锁定点，必须维护配置清单和退出 runbook。
- 迁移 provider 时不得仅凭相同 email 自动链接账号。应在旧身份仍可验证时完成显式重新认证/绑定，再将新的 `(issuer, subject)` 映射到原本地 `User.id`。

## Rejected Alternatives

- **FastAPI 自建 email/password + JWT**：拒绝。它把验证邮件、密码重置、凭据泄露响应和 refresh token 安全变成长期核心维护工作。
- **Google-only**：拒绝。目标用户可达性和账号恢复过度依赖单一外部 provider；未来可以作为 Auth0 connection 增加，但不是唯一入口。
- **Web bearer token 放 `localStorage`/IndexedDB**：拒绝。XSS 可直接导出长期 credential。
- **Extension 复用 Web cookie**：拒绝。Extension origin 与 Web 不同，cookie/第三方策略、CSRF 与多环境行为不可靠，也无法形成清晰权限边界。
- **长期 JWT 永久放 `chrome.storage.local`**：拒绝。泄露后缺少短期失效、rotation 和可控 revoke 窗口。
- **JWT 放 URL、OAuth implicit flow、禁用 PKCE 的 code flow**：拒绝。URL 会进入历史/日志，implicit 缺少现代 code exchange 防护，public client 不能保存 client secret。
- **Clerk 作为 V1 默认**：不采用。当前价值不足以抵消更强的前端/SDK/session 模型锁定。
- **Supabase Auth 作为 V1 默认**：保留为备选，但当前 hosted Web BFF + Extension public-client 流需要比 Auth0 更多一方会话/UI 设计。若 Auth0 的可达性或成本不可接受，必须重新打开本 ADR，而不是静默替换。

## Evidence References

以下只用于验证协议与产品能力；套餐额度和供应商行为仍须在 Phase 2B 配置当日复核：

- [Auth0 Authorization Code Flow with PKCE](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce)
- [Auth0 Refresh Token Rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation)
- [Auth0 JWT Validation](https://auth0.com/docs/secure/tokens/json-web-tokens/validate-json-web-tokens)
- [Chrome `identity` API](https://developer.chrome.com/docs/extensions/reference/api/identity)
- [Chrome `storage` API](https://developer.chrome.com/docs/extensions/reference/api/storage)
- [Supabase Auth Sessions and PKCE](https://supabase.com/docs/guides/auth/sessions)
- [Clerk Chrome Extension SDK Overview](https://clerk.com/docs/reference/chrome-extension/overview)

## Phase 2B Entry Gate Outcome

- 项目负责人已接受本 ADR、Auth0 参考方案、Phase 2B 最小代码/依赖/schema 实施范围，以及 JobPilot-controlled lifecycle 设计上限和 Phase 3/4 export milestones。
- 自动化实现必须使用 deterministic fake issuer/JWKS，且可以提交不含秘密的配置模板。
- 真实 Auth0 tenant、Web application、Extension public application、API audience、dev/prod origins、stable Extension IDs、redirect/logout URLs、issuer/audience/algorithm/authorized-party allowlist、lifetimes、clock skew、provider capabilities、Management API scopes、DPA/retention disclosure 与 secrets 仍为 `USER ACTION REQUIRED`。
- 在这些真实值由项目负责人提供前，不得创建收费资源、猜值、提交 secret 或声称真实 Auth0 integration 已验证；该门禁不阻止 deterministic Phase 2B 代码和自动化测试。
