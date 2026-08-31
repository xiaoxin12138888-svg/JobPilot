# ADR-007：以中国大陆普通网络可用性重选生产身份供应商

- **Status**：Accepted — Provider Direction
- **Date**：2026-08-31
- **Accepted**：2026-08-31（含 MVP / Production Gate 分层修正）
- **Decision owner**：JobPilot 项目负责人
- **Related decision**：[ADR-006](ADR-006-authentication-strategy.md)

## Context

JobPilot 的目标用户主要使用 BOSS 直聘、牛客、实习僧、猎聘、国聘等中国大陆招聘平台。认证不是外围功能：注册、登录、账号恢复、Web 会话建立、Extension 获取和刷新凭据，以及后续用户主动保存岗位，都位于核心使用链路上。

本 Gate 新增以下生产硬约束：

> **Core JobPilot workflow must operate without VPN/proxy in Mainland China.**

“普通网络可用”指用户不需要 VPN、代理或特殊 DNS，即可在中国大陆消费级固定宽带和移动网络上完成核心流程。它同时约束 JobPilot Web/API、身份供应商的 discovery/authorize/token/JWKS/revoke 端点、Chrome Extension redirect，以及邮箱/SMS 验证和账号恢复依赖；只有未来另行批准 RP-initiated/provider logout 时才把 end-session 加入当前核心流。单纯证明某个首页或健康检查可访问，不足以通过本 Gate。

[ADR-006](ADR-006-authentication-strategy.md) 在当时信息下接受 Auth0 作为 V1 参考实现，并成功冻结了 provider-isolated identity、双 transport 和安全边界。Task 5–7 已按该决定完成 deterministic 实现，但项目尚未创建或接入真实 Auth0 tenant，也没有真实生产用户或已验证的中国大陆普通网络结果。新的可达性约束使“Auth0 作为默认生产 Identity Provider”必须重新评估。

本 ADR 现已批准生产 provider 方向，但**不批准 adapter 迁移、生产 cutover、Task 8 或 Phase 3**。当前唯一获批的实施范围是 `Logto Verification Slice — Protocol & Mainland MVP Gate`：

- 暂停 Task 8 的真实 Auth0 配置和联调；
- 不创建 Auth0 tenant，不绑定真实 Client ID、Extension ID、audience、origin、redirect 或 secret；
- 只允许创建 local / isolated development Logto 实例、独立 Logto PostgreSQL、Web confidential application、Extension public application 和 JobPilot API resource；
- 不创建生产或收费资源，不配置社交登录、Google/GitHub/微信、企业 SSO、组织、RBAC、MFA 或短信；
- 不修改认证业务代码，不删除现有 Auth0 adapter；
- 不进入 Phase 3。

## Decision Drivers

1. 中国大陆无代理普通网络上的核心流程可用性是硬门槛，而不是加分项。
2. Web 继续使用 OIDC Authorization Code，经 FastAPI/BFF 建立 server-backed opaque session。
3. Chrome Extension 继续作为 public client 使用 Authorization Code + PKCE，不持有 client secret。
4. FastAPI 继续是唯一业务认证与授权边界。
5. 保留 `(issuer, subject) -> JobPilot User.id`，业务外键不得绑定 provider subject。
6. JobPilot 应避免直接保存密码，同时必须明确 self-hosting 转移回来的安全和运维责任。
7. 尽量复用 Task 5–7 已评审实现，避免为更换 provider 破坏公共 API 或客户端边界。
8. V1 同时衡量现金成本、工程成本、运维成本和安全事件成本，不能只比较供应商月费。

## Evidence Boundary

截至 2026-08-31：

- Logto 官方资料确认其开源核心可 self-host，基于 OIDC/OAuth 2.1，提供 Chrome Extension 与 FastAPI 集成指南；官方 Chrome Extension SDK 源码使用 code verifier、S256 code challenge 和 `chrome.identity.launchWebAuthFlow`。
- Logto 官方资料确认 API resource 使用 RFC 8707 resource indicator，JWT API access token 可由 FastAPI 通过 issuer/JWKS/audience 校验；密码恢复可使用 email/SMS verification connector。
- Logto OSS 生产部署需要 PostgreSQL、TLS/reverse proxy、数据库变更、升级、connector、备份和管理面控制。官方本地快速启动的 bundled PostgreSQL 明确不适用于生产。
- 当前仓库只证明 Auth0-compatible deterministic protocol behavior，没有真实 Auth0 或 Logto 的中国大陆网络证据。

这些资料证明“协议和部署能力候选”，**不证明任何方案已经满足中国大陆可用性**。Logto、Auth0 和自建方案的真实可达性在完成项目负责人批准的网络验收前一律为 `NOT VERIFIED`。

## Options Compared

### Option A — Self-hosted Logto OSS

在 JobPilot 可控制的、面向中国大陆普通网络可达的基础设施上部署 Logto OSS。Logto 作为独立 IdP 管理密码、验证和恢复流程；JobPilot 应用仍只接收验证后的 OIDC identity，不接收密码。

### Option B — Current Auth0

保留当前 Auth0 managed OIDC 方案，由 Auth0 SaaS 承担 hosted login、凭据、恢复与 token 服务。当前代码和 deterministic tests 已以该 token/profile 契约实现，但真实 tenant 与中国大陆可用性均未验证。

### Option C — FastAPI self-hosted authentication

由 JobPilot/FastAPI 自行实现并运营账号、密码、验证、恢复、滥用防护和 token/session 生命周期。如果还要保留 Web OIDC 与 Extension Authorization Code + PKCE，就必须另外实现一个合规 OAuth/OIDC authorization server；FastAPI 框架本身不提供这些能力。

## Comparison Matrix

| Criteria                                   | Self-hosted Logto OSS                                                                                                                | Current Auth0                                                                                                | FastAPI self-hosted authentication                                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| 中国大陆无代理可用性                       | **可达性控制面最强候选 / NOT VERIFIED**：部署位置、域名、DNS、TLS 和 connector 可控；仍须在普通网络实测，不能因“自建”自动判定 PASS   | **当前不通过审批门槛**：没有 tenant 或大陆普通网络证据，且核心流依赖外部 SaaS data plane；不能继续默认批准   | **条件性可控**：可与 JobPilot 同域/同区域部署，但邮件/SMS、CAPTCHA、DNS/TLS 等仍须实测；可达性不等于认证安全成熟度 |
| Web OIDC                                   | 原生 OIDC；可保持 FastAPI confidential-client/BFF，但 exact discovery、client auth 和登录参数需按固定版本验证                        | 原生且当前 adapter 已实现；真实配置未验证                                                                    | FastAPI 本身不是 IdP；要保持 OIDC 必须自建/集成 authorization server                                               |
| Chrome Extension Authorization Code + PKCE | 官方 Extension 指南与 SDK 支持 `chrome.identity` 和 PKCE；精确 callback、`resource`、refresh/revoke 语义仍是 Gate                    | 当前 Task 7 已 deterministic 实现 `launchWebAuthFlow` + PKCE；真实 Auth0 flow 未验证                         | 必须自行实现 authorization policy/UI、code、PKCE、public-client token/revoke 和安全 UI，工作量与风险最高           |
| FastAPI compatibility                      | 官方提供 JWT/FastAPI 验证路径；现有 PyJWT/JWKS 边界可适配，不能放宽现有校验来“兼容”                                                  | 当前 FastAPI adapter/validator 已实现并经过 deterministic tests                                              | 应用代码直接可控，但若没有独立 IdP，会把 credential 与业务 API 责任耦合                                            |
| Task 5–7 代码复用                          | **条件性高**：主体可保留；前提是 resource-bound access/refresh、replacement refresh token 和 revoke Gate 通过，否则重开 lifecycle    | **最高**：当前实现保持不变                                                                                   | **低到中**：本地 User/session 可保留，但 hosted OIDC、Extension token 生命周期和恢复边界需要重做                   |
| 密码/账号恢复安全责任                      | Logto 软件提供 credential/recovery flow；JobPilot 运维承担部署、补丁、密钥、数据库、connector delivery、滥用防护配置、备份和事故响应 | Auth0 承担 credential 核心；JobPilot 仍承担 tenant/config、业务 session、授权、供应商治理和故障降级          | JobPilot 对密码哈希、验证、恢复、限流、防枚举、防撞库、rotation/reuse、撤销、通知和应急响应负全部责任              |
| 部署复杂度                                 | **中高**：独立 PostgreSQL、固定版本镜像、TLS/reverse proxy、Admin Console 隔离、connector、迁移、备份、监控和升级                    | **低**：主要是 tenant/application 配置和 secret 管理                                                         | **高**：除基础设施外还要构建、审计和运营完整身份系统                                                               |
| 长期维护                                   | **中高**：跟踪上游安全发布、执行数据库 alteration、回归协议与 connector；少于自建认证但多于 SaaS                                     | **低到中**：供应商维护核心服务，JobPilot 维护集成与退出计划                                                  | **最高**：安全标准、攻击面、恢复和兼容性成为 JobPilot 长期核心工作                                                 |
| Vendor lock-in                             | **低到中**：MPL-2.0 开源、自有部署且使用标准协议；仍绑定 Logto schema、Console、connector 和 token semantics                         | **中高**：标准 OIDC 降低协议锁定，但 hosted UI、Actions/claims、Management API、tenant export 和定价形成锁定 | **低 vendor / 高 custom lock-in**：不依赖供应商，但自有协议和安全债务可能更难迁移                                  |
| V1 成本                                    | 无按用户的软件许可费预期；需要大陆可达基础设施、数据库、邮件/SMS、备份监控和持续运维时间。官方建议的基础资源也必须计入               | 早期现金成本可能较低，但实际套餐、配额、增长价格和大陆可用性未获批准；即使免费也不能绕过硬约束               | 软件许可费低，但工程、安全评审、邮件/SMS、值守和事件响应使 V1 总拥有成本最高                                       |

## Decision

1. 将 **Self-hosted Logto OSS** 正式批准为 JobPilot V1 生产 Identity Provider 的首选方向。
2. 将 **中国大陆无代理普通网络可用性** 设为不可豁免的生产验收条件。
3. Auth0 不再是默认批准的生产 provider。现有 Auth0 adapter 与 deterministic fixtures 保留，用于历史可追溯、回归和退出选择；本 ADR 不授权删除。
4. 不采用 FastAPI self-hosted password authentication。除非 Logto 验证失败且项目负责人重新打开本 ADR，否则不把 JobPilot 演变成自建 OAuth/IAM 产品。
5. 继续保留 ADR-006 中与 provider 无关的 identity、transport、session、authorization、storage、CSRF、CORS、生命周期和数据边界。
6. 不实现 runtime 多 provider 自动 failover。未设计的 provider 切换可能把同一个人映射成多个本地用户，也会扩大 token/配置攻击面。

`Accepted — Provider Direction` 只批准方向和本 ADR 明示的验证切片，不代表 Logto production readiness、生产资源或迁移授权。ADR-006 继续保留 `Accepted` 历史状态并作为 provider-neutral identity/session/security contract；其 Auth0 production-provider selection 由本 ADR 标记为 `amended / superseded in part`。不得把整个 ADR-006 标成失效，也不得借验证或未来迁移删除其余已接受边界。

## Preserved Interfaces and Invariants

当前验证和任何未来 Logto 迁移都必须原样保留：

- exact `(identity_issuer, identity_subject) -> JobPilot User.id`；
- provider `sub`、token 或 credential 不进入业务表外键；
- Web 仍由 FastAPI/BFF 完成 OIDC callback，并建立 PostgreSQL-backed opaque HttpOnly session；
- React 仍只通过 `GET /api/v1/auth/me` 观察会话，不持有 provider token；
- Extension 仍使用用户触发的 Authorization Code + PKCE、可信 service worker/storage、短期 bearer、按需 single-flight refresh 和 fail-closed rotation；
- `POST /api/v1/auth/session` 仍是 Extension identity establishment command；
- `/api/v1/auth/me`、`PATCH /api/v1/auth/me`、CSRF 与 local logout 的公共 API/DTO 不因 provider 改名；
- `VerifiedProviderIdentity` 与 `AuthenticatedUser` 继续隔离 cryptographic identity 和业务权限；
- 所有业务资源继续使用 `resource_id + authenticated_user_id` 授权；
- email 仍只是已验证的可变联系属性，不得用于跨 issuer 自动合并。

## Authorized Verification Scope

当前 `Logto Verification Slice — Protocol & Mainland MVP Gate` 只允许：

1. 从官方来源选择并记录 Logto OSS 精确固定版本、许可、不可变镜像/源码和最小运行要求；禁止 `latest`。
2. 使用最简单可重复方案创建 local / isolated development Logto 与独立 PostgreSQL；Logto Identity DB 不与 JobPilot business DB 共用 schema 或 ownership boundary。
3. 最小配置 Web confidential application、无 client secret 的 Extension public application 和 JobPilot API resource；只使用本地 email/password 测试账号。
4. 真实验证 Web OIDC、Extension Authorization Code + PKCE S256、API token profile、refresh replacement/rotation/reuse、revoke/logout、same issuer/subject 和 same JobPilot `User.id`。
5. 在不修改认证业务代码的前提下，把差异分类为 `COMPATIBLE`、`ADAPTER CHANGE REQUIRED` 或 `CONTRACT INCOMPATIBLE`；不得放宽 validator 或 fail-closed lifecycle。
6. 在中国大陆普通固定宽带和移动网络/热点上各完成一次关闭 VPN、代理和特殊 DNS 的 MVP smoke；当前执行环境不能切换时如实标记 `BLOCKED — USER ACTION REQUIRED`。
7. 只在真实协议与 fixture 不一致或发现真实 bug 时增加最小 regression test；不以测试数量为目标。
8. 按 [Logto Verification Summary](../LOGTO_VERIFICATION_SUMMARY.md) 输出脱敏结果，给出 `UNCHANGED`、`MINOR ADAPTER CHANGE` 或 `MAJOR CONTRACT CHANGE`，然后停止等待迁移授权。

## Candidate Minimal Migration Scope After Verification

以下只记录未来可能的最小迁移影响面，**不是本 Slice 的实施授权**。即使 MVP Development Gate 通过，下一步也只能是另行批准的 `Minimal Logto Adapter Migration`：

1. 新增 Logto-specific `WebAuthProvider` 实现并在 composition root 切换；保留 application service、login transaction、Web session 和 routers。
2. 将 Auth0-specific `audience` 请求语义按实测替换为 Logto RFC 8707 `resource` 等精确参数；冻结 resource 在 authorize、code exchange 和 refresh grant/token request 中的位置、与 scopes 的绑定，以及首次与刷新后的 API resource token 语义。任何额外 grant 都必须进入现有 crash-safe storage/rotation 状态机。
3. 建立 Logto-specific token profile/adapter，精确校验 issuer、resource audience、authorized client、signature、time、token type 和 verified-email source；不得接受模糊 issuer、任意 claim 或任意 algorithm。
4. 保留全部 provider-neutral tests，只替换或新增必要的 provider-specific fixtures，证明 `/auth/session`、`/auth/me`、Web session、Extension lifecycle 和用户隔离无变化。
5. Auth0-specific adapter/config 的删除必须是更晚的单独 cleanup；迁移切片不得顺手删除退出路径。

当前仓库状态和项目负责人本轮指令没有提供已创建的 Auth0 tenant、真实用户或 provider identity 数据证据，因此迁移估算暂不包含生产用户搬迁；这不是持久架构事实。任何 cutover 计划开始前必须重新审计真实 tenant、Identity rows、有效 Web sessions 和外部环境。如果发现任何真实 Auth0 用户或有效会话，必须设计旧 provider 重新认证/显式绑定、会话撤销和审计方案，**绝不能按相同 email 自动链接**。

## Verification Gate Layers

### 1. MVP Development Gate — ACTIVE

本轮只验证开发可行性，不宣称 production readiness。必须覆盖：固定 Logto 版本、独立 PostgreSQL、最小 Web/Extension/API resource 配置、Web OIDC、Extension PKCE/no-secret、FastAPI 精确 token profile、refresh/revoke、same identity、same JobPilot `User.id`、核心 runtime dependency，以及中国大陆固定宽带和移动网络各一次 no-proxy smoke。

`ADAPTER CHANGE REQUIRED` 在 provider-neutral contract 与 fail-closed lifecycle 均未削弱时可以支持 MVP PASS；`CONTRACT INCOMPATIBLE` 必须使本 Gate 为 `FAIL`。

Mainland MVP smoke 只能证明记录的时间、地点范围、运营商/网络类型、设备、OS/浏览器/Extension 版本、Logto 固定版本和当前构建下，用户无需 VPN/代理/特殊 DNS 即可完成被实际执行的流程。它不证明多地域、多运营商长期可用性、P95/SLA、正式分发、恢复消息送达、生产运维、合规或 DR。无法切换到真实固定宽带或移动网络时，对应结果必须为 `BLOCKED — USER ACTION REQUIRED`，MVP Development Gate 也保持 `BLOCKED`；不得用 synthetic probe、`.invalid` fixture 或推测替代。

### 2. Protocol compatibility — ACTIVE

针对固定 Logto 版本用真实响应证明：

- exact issuer、trailing slash、discovery 与 same-origin endpoint policy；
- Web confidential-client authentication method、`prompt=login`、signup first-screen/hint 和 nonce behavior；
- Extension public-client PKCE S256、exact callback/CORS、RFC 8707 resource、无 client secret；
- JWT/JWKS algorithm、key size、`typ`、audience、`client_id`/`azp`、email 与 verified-email claims；
- Web 和 Extension 两个 application 对同一账号生成稳定相同的 `(issuer, sub)`；
- access token 不超过已接受的 5–10 分钟窗口；refresh rotation/reuse、grant TTL、revocation 和 logout 的实际残余窗口有测试和 UI 语义；
- provider outage、unknown `kid`、worker termination 和 ambiguous refresh outcome 继续 fail closed。

任何不匹配都必须通过明确 adapter 或重新审批的 contract 解决，不能静默削弱 JWT、PKCE、storage、session 或 identity 校验。

### 3. Production Release Gate — DEFERRED

以下要求全部保留，但不得阻塞当前 MVP 开发，也不得在本轮写成 PASS：

- 多运营商、多地域、重复运行、长期观测窗口，以及预先冻结的 timeout、成功率、P95 和正式 SLA 矩阵；
- Extension 正式签名、稳定生产 ID、无代理分发渠道、update manifest/artifact host、N-1 compatibility、staged rollout、forced upgrade 和 production rollback；
- 完整生产数据库备份/恢复演练、backup expiry、restore quarantine/ledger 和 disaster recovery；
- 正式邮件/SMS 验证与账号恢复送达 SLA；本 MVP Slice 不配置 SMS；
- production monitoring/alerting、证书/DNS、secret/key vault、Admin Console 加固、漏洞/升级/回滚、connector 供应链和事故响应；
- Self-hosted Logto identity database、credential store、audit/security logs 与 backups 的删除传播、数据生命周期和安全响应；
- ICP、数据保护、网络安全和跨境依赖合规评估。本文记录工程门禁，不构成法律意见。

## Impact Analysis

### Application and public API

- **无 schema 变更**：`User`、`Identity`、`WebSession`、`LoginTransaction` 和唯一约束继续适用。
- **无公共 API 变更**：`/auth/session`、`/auth/me`、CSRF、logout 和 `UserView` 保持 provider-neutral。
- **无业务模块变更**：未来 Job/Application/Resume 只引用本地 `User.id`。
- **无客户端凭据边界变更**：Web 不见 token；Extension public client 无 secret；Popup/content script 不见 credential。

### Known provider-specific seams

未来迁移主要集中在：

- FastAPI 的 `Auth0WebProvider` 和 composition-root wiring；
- Web token exchange 的 client authentication、signup hint 与 ID-token claim profile；
- Extension authorize request 中 Auth0-style `audience`；
- Logto 官方 Chrome 示例使用 `chromiumapp.org/callback`，而当前 Extension 只接受 `chrome.identity.getRedirectURL()` 的精确 root callback；必须先验证 Logto 能否注册 root，不能兼容时才做最小 callback/config 适配；
- bearer validator 的 namespaced email claims、exact `azp` 和 token header/profile 假设；
- refresh replacement、reuse detection 和 direct-revoke semantics；future end-session 只有在单独批准 provider logout 后才进入迁移范围；
- provider-specific environment comments、fixtures 和 integration tests。

现有 `WebAuthProvider` protocol、identity application service、session services、routers、shared API client、Extension PKCE/storage/worker/Popup 以及 PostgreSQL repositories 均应复用。预计不需要新增 Logto client SDK；是否维持现有标准协议依赖由迁移 Gate 的最小性审查决定。

### Security responsibility shift

相较 Auth0 SaaS，Self-hosted Logto 仍让 JobPilot 应用代码避免接触密码，但把 IdP availability、数据库和密钥保护、补丁、connector、备份、管理面和事故响应转给 JobPilot 运维。它明显少于自建 FastAPI authentication 的协议/产品责任，但不能被描述为“供应商替我们负责安全”。

Self-hosted Logto 的 identity records、credential store、audit/security logs 和 backups 都是 JobPilot-controlled data。账号删除、备份过期、恢复前 deletion replay/quarantine 和安全事件响应必须覆盖 Logto 数据面；只有继续使用 managed provider 时，无法由 JobPilot 直接控制的 logs/backups 才按 DPA/tenant disclosure 单独审批。具体 Logto schema/workflow 在 deployment Gate 冻结，但不能把它排除在数据生命周期之外。

### Delivery and schedule

Task 8 保持暂停。当前先执行已授权的 Logto deployment/protocol/Mainland MVP Verification Slice；其 Summary 完成后，再由项目负责人决定是否另行授权 Minimal Logto Adapter Migration 和最终 Phase 2B acceptance。Phase 3 必须继续等待 Phase 2B 生产 identity decision 和验收，不得并行绕过。

## Rejected or Deferred Alternatives

- **继续默认批准 Auth0，之后再观察可达性**：拒绝。可达性是核心生产硬约束，不能在绑定 tenant/config 后再补证据。
- **立即把 Auth0 adapter 改名为 generic OIDC 并指向 Logto**：拒绝。当前存在 resource、claim、client-auth、refresh 和 revoke 等未验证差异，改名会掩盖而不是消除耦合。
- **同时运行 Auth0 与 Logto 自动 failover**：拒绝。它引入 identity split、issuer migration、双配置和撤销不一致，不是 V1 的最小方案。
- **立即删除 Auth0 代码**：拒绝。尚无获批替代实现，且会丢失可回归的历史 adapter。
- **FastAPI email/password + JWT 作为快捷替代**：拒绝。它不能自动满足 OIDC/PKCE，并把完整 credential/recovery/security 产品责任转给 JobPilot。
- **只测试 API health 或单一 Wi-Fi**：拒绝。无法证明用户实际 signup/login/recovery/Extension 核心链路。

## Evidence References

以下官方资料于 2026-08-31 核对。文档和上游行为会变化，实施时必须针对固定版本复核：

- [Logto documentation overview — OIDC/OAuth 2.1 and self-hosted OSS](https://docs.logto.io/llms.txt)
- [Logto OSS — Get started](https://docs.logto.io/logto-oss/get-started-with-oss)
- [Logto OSS — Deployment and configuration](https://docs.logto.io/logto-oss/deployment-and-configuration)
- [Logto OSS — Upgrading](https://docs.logto.io/logto-oss/upgrading-oss-version)
- [Logto — Chrome Extension quick start](https://docs.logto.io/quick-starts/chrome-extension)
- [Logto Chrome Extension SDK source](https://github.com/logto-io/js/blob/master/packages/chrome-extension/src/index.ts)
- [Logto — Protect FastAPI with JWT validation](https://docs.logto.io/api-protection/python/fastapi)
- [Logto — API resources and RFC 8707 resource indicators](https://docs.logto.io/quick-starts/chrome-extension#api-resources)
- [Logto — Custom access-token claims](https://docs.logto.io/developers/custom-token-claims)
- [Logto — Password reset](https://docs.logto.io/end-user-flows/sign-up-and-sign-in/reset-password)
- [Logto — Sign-out and offline access](https://docs.logto.io/end-user-flows/sign-out)
- [Logto — Grant revocation](https://docs.logto.io/sessions/grants-management)
- [Logto OSS repository license — MPL-2.0](https://github.com/logto-io/logto/blob/master/LICENSE)

## Approval Gate Outcome

**Current result: `ACCEPTED — PROVIDER DIRECTION / VERIFICATION SLICE ACTIVE`.**

- Task 8 real-provider configuration and integration: `PAUSED`.
- Real Auth0 production selection: `NOT APPROVED`.
- Self-hosted Logto OSS provider direction: `ACCEPTED`.
- Logto Verification Slice: `AUTHORIZED / ACTIVE`.
- Logto Production Readiness: `NOT VERIFIED`.
- MVP Mainland ordinary-network smoke: `NOT VERIFIED`.
- Production Release Gate: `DEFERRED`.
- Authentication business-code migration: `NOT AUTHORIZED`.
- Phase 3: `NOT AUTHORIZED`.

本 Slice 完成后必须输出脱敏 Verification Summary 并停止。若 MVP Development Gate 为 PASS，唯一候选下一步是 `Minimal Logto Adapter Migration`，仍须项目负责人单独授权；不得自动开始 Task 8、迁移或 Phase 3。
