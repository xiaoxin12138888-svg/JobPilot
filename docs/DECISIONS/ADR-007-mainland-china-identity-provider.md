# ADR-007：以中国大陆普通网络可用性重选生产身份供应商

- **Status**：Proposed — Architecture Change Gate
- **Date**：2026-08-31
- **Decision owner**：JobPilot 项目负责人
- **Related decision**：[ADR-006](ADR-006-authentication-strategy.md)

## Context

JobPilot 的目标用户主要使用 BOSS 直聘、牛客、实习僧、猎聘、国聘等中国大陆招聘平台。认证不是外围功能：注册、登录、账号恢复、Web 会话建立、Extension 获取和刷新凭据，以及后续用户主动保存岗位，都位于核心使用链路上。

本 Gate 新增以下生产硬约束：

> **Core JobPilot workflow must operate without VPN/proxy in Mainland China.**

“普通网络可用”指用户不需要 VPN、代理或特殊 DNS，即可在中国大陆消费级固定宽带和移动网络上完成核心流程。它同时约束 JobPilot Web/API、身份供应商的 discovery/authorize/token/JWKS/revoke 端点、Chrome Extension redirect，以及邮箱/SMS 验证和账号恢复依赖；只有未来另行批准 RP-initiated/provider logout 时才把 end-session 加入当前核心流。单纯证明某个首页或健康检查可访问，不足以通过本 Gate。

[ADR-006](ADR-006-authentication-strategy.md) 在当时信息下接受 Auth0 作为 V1 参考实现，并成功冻结了 provider-isolated identity、双 transport 和安全边界。Task 5–7 已按该决定完成 deterministic 实现，但项目尚未创建或接入真实 Auth0 tenant，也没有真实生产用户或已验证的中国大陆普通网络结果。新的可达性约束使“Auth0 作为默认生产 Identity Provider”必须重新评估。

本 ADR 只提出生产 provider 方向和影响范围，不批准迁移。当前立即生效的 Gate 是：

- 暂停 Task 8 的真实 Auth0 配置和联调；
- 不创建 Auth0 tenant，不绑定真实 Client ID、Extension ID、audience、origin、redirect 或 secret；
- 不创建或配置真实 Logto 生产实例，除非项目负责人另行批准验证切片；
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

## Proposed Decision

待项目负责人审批后，建议：

1. 将 **Self-hosted Logto OSS** 设为 JobPilot V1 生产 Identity Provider 的首选候选。
2. 将 **中国大陆无代理普通网络可用性** 设为不可豁免的生产验收条件。
3. Auth0 不再是默认批准的生产 provider。现有 Auth0 adapter 与 deterministic fixtures 保留，用于历史可追溯、回归和退出选择；本 ADR 不授权删除。
4. 不选择 FastAPI self-hosted authentication 作为 V1 默认方案。除非 Logto 验证失败且项目负责人重新打开本 ADR，否则不把 JobPilot 演变成自建 OAuth/IAM 产品。
5. 继续保留 ADR-006 中与 provider 无关的 identity、transport、session、authorization、storage、CSRF、CORS、生命周期和数据边界。
6. 不实现 runtime 多 provider 自动 failover。未设计的 provider 切换可能把同一个人映射成多个本地用户，也会扩大 token/配置攻击面。

因为本 ADR 状态仍是 `Proposed`，上述 provider 选择不是实施授权。ADR-006 继续保留 `Accepted` 历史状态，但其“Auth0 为生产默认”部分被本 Architecture Change Gate 暂停执行。如果本 ADR 获批，ADR-006 仍作为 provider-neutral identity/session/security contract 保持 Accepted；其生产 provider selection 将在 metadata 和 ADR index 中明确标为 `amended / superseded in part by ADR-007`。不得把整个 ADR-006 标成失效，也不得借 provider 迁移删除其余已接受边界。

## Preserved Interfaces and Invariants

若 Logto 通过 Gate，以下边界必须原样保留：

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

## Minimum Migration Scope After Approval

只有项目负责人接受本 ADR 并单独授权迁移切片后，才执行以下最小范围：

1. **冻结部署规格**：选定 Logto OSS 精确版本、许可审查结果、部署区域/域名、PostgreSQL、TLS、镜像来源、connector、备份、监控和升级/回滚 runbook；禁止直接使用浮动 `latest` 作为可重复生产基线。
2. **创建隔离应用**：在批准的非生产 Logto 实例中配置独立 Web confidential application，以及作为 OAuth public client、无 secret 的 Logto SPA application 供 Extension 使用；冻结 exact redirect、CORS origin、API resource 和 scopes。当前 Web 是 local logout、Extension 是 direct revoke，不要求 hosted post-logout URI；只有另行批准 RP-initiated/provider logout 时才增加该配置。
3. **验证 discovery 和 token profile**：记录 exact issuer、authorize/token/JWKS/revoke endpoint、alg/`typ`、audience、`client_id` 或 `azp`、nonce、`auth_time`、email/verification claim 来源和 access lifetime；end-session 只在未来 provider logout 获批时验证。
4. **替换 Web adapter wiring**：新增 Logto-specific `WebAuthProvider` 实现并在 composition root 切换；保留 application service、login transaction、Web session 和 routers。
5. **适配 Extension request/config**：将 Auth0-specific `audience` 请求语义按实测替换为 Logto RFC 8707 `resource` 等精确参数；冻结 resource 在 authorize、code exchange 和 refresh grant/token request 中的精确位置、与 scopes 的绑定、首次 code exchange 是否直接得到 JobPilot API JWT（而不是仅用于 `userinfo` 的 opaque token），以及 refresh 后是否仍返回同一 resource 的 access token。任何额外 resource-token grant 还必须纳入现有 crash-safe storage/rotation 状态机。保留 oauth4webapi、PKCE、callback、trusted storage、worker 和 Popup 边界。
6. **收紧而非放宽 bearer validation**：建立 Logto-specific token profile/adapter，精确校验 issuer、resource audience、authorized client、signature、time、token type 和 verified-email source；不得为了通过测试接受模糊 issuer、任意 claim 或任意 algorithm。
7. **验证 refresh/revoke**：证明 public client 无 secret、`offline_access`、resource-bound grant、每次成功 refresh 都返回不同 replacement refresh token、reuse-family 行为、crash-safe rotation、direct revoke 或 grant revocation，以及 logout UI 的真实语义符合现有安全契约；不兼容时不得降级现有 fail-closed lifecycle，必须重新开 Gate。
8. **最小回归**：保留全部 provider-neutral tests，只替换或新增 provider-specific fixtures；证明 Web 与 Extension 的同一 Logto identity 映射同一 `User.id`，且 `/auth/session`、`/auth/me` 和用户隔离无变化。
9. **真实大陆验收**：完成下述网络、恢复、部署和安全 Gate 后才允许把生产 provider 状态改为 `APPROVED`。
10. **延后清理**：Auth0-specific adapter/config 的删除必须是另一个经批准的 cleanup；本迁移切片不顺手删除退出路径。

当前仓库状态和项目负责人本轮指令没有提供已创建的 Auth0 tenant、真实用户或 provider identity 数据证据，因此迁移估算暂不包含生产用户搬迁；这不是持久架构事实。任何 cutover 计划开始前必须重新审计真实 tenant、Identity rows、有效 Web sessions 和外部环境。如果发现任何真实 Auth0 用户或有效会话，必须设计旧 provider 重新认证/显式绑定、会话撤销和审计方案，**绝不能按相同 email 自动链接**。

## Required Verification Gates

### 1. Mainland ordinary-network acceptance

项目负责人必须先批准可重复的测试矩阵；至少覆盖相互独立的中国大陆消费级固定宽带和移动网络，且测试设备不得配置 VPN、代理或特殊 DNS。一次开发机成功不代表生产 PASS。

测试矩阵必须在任何验收执行前冻结客观判定字段，并由项目负责人批准；不得在看到结果后为了“通过”回填或放宽。当前 ADR 不替负责人猜测具体数值，但矩阵至少必须明确：

- 覆盖的运营商、地域、消费级固定宽带/移动数据网络组合，以及支持的浏览器、操作系统和版本范围；
- 每条流程的执行次数、测试时段、连续观测窗口和故障重试规则；
- 分步骤 timeout、端到端成功率和 P95 延迟阈值；
- 邮件/SMS 验证与恢复消息的送达成功率、送达时延和超时阈值；
- 脱敏证据的留存格式、时间戳、provider/应用版本和网络环境元数据；
- 单项与总体 `FAIL`、`NO-CUTOVER`、回滚触发和重新测试标准。

一次或少量偶然成功不得判定为 `PASS`；缺少预先冻结的阈值或可审计证据时，结果只能是 `NOT VERIFIED`。

必须验证：

- public DNS、TLS chain、Web、API 和 self-hosted Logto endpoint；
- OIDC discovery、authorize、callback、token、JWKS、refresh 和 direct revoke；只有另行批准 provider logout 时才验证 end-session；
- Web signup/login/session restore/local logout；
- Extension `launchWebAuthFlow`、`chromiumapp.org` redirect interception、首次 `/auth/session`、`/auth/me`、refresh 与 logout；
- Extension 在中国大陆普通网络上的完整分发生命周期：支持的 Chromium 浏览器必须有无需代理可达的安装渠道，不得默认假设 Chrome Web Store 可用；发布包必须由受控私钥签名并保持稳定 Extension ID，签名私钥不得进入仓库、构建日志或分发主机；
- Extension 的 update manifest 与 artifact host 必须无需代理可达，并验证包完整性、版本固定、分阶段发布、失败回滚、N-1 客户端兼容以及旧版本最低支持/强制升级语义；验收必须覆盖全新安装、N-1 升级和回滚，而不只是已安装开发包；
- 邮箱或 SMS 验证、忘记密码和账号恢复的实际送达；
- 新用户运行时不依赖 Auth0、Logto Cloud、GitHub/GHCR、Google service、Have I Been Pwned、境外 CAPTCHA/CDN 或其他未批准且可能不可达的域名；构建/升级 artifact 应使用可审计镜像或缓存；
- 失败时清晰降级且不泄露 raw provider error、token 或用户枚举信息。

大陆区域 synthetic probe 可作为持续监控，但不能替代真实 Chrome/Web 普通网络验收。

### 2. Protocol compatibility

针对固定 Logto 版本用真实响应证明：

- exact issuer、trailing slash、discovery 与 same-origin endpoint policy；
- Web confidential-client authentication method、`prompt=login`、signup first-screen/hint 和 nonce behavior；
- Extension public-client PKCE S256、exact callback/CORS、RFC 8707 resource、无 client secret；
- JWT/JWKS algorithm、key size、`typ`、audience、`client_id`/`azp`、email 与 verified-email claims；
- Web 和 Extension 两个 application 对同一账号生成稳定相同的 `(issuer, sub)`；
- access token 不超过已接受的 5–10 分钟窗口；refresh rotation/reuse、grant TTL、revocation 和 logout 的实际残余窗口有测试和 UI 语义；
- provider outage、unknown `kid`、worker termination 和 ambiguous refresh outcome 继续 fail closed。

任何不匹配都必须通过明确 adapter 或重新审批的 contract 解决，不能静默削弱 JWT、PKCE、storage、session 或 identity 校验。

### 3. Self-hosted operations and security

上线前必须具备：

- Logto 与 JobPilot 业务数据库的清晰 ownership/backup 边界，恢复演练和数据库 alteration runbook；
- 固定版本、漏洞/安全公告跟踪、可审计镜像、升级回滚和 connector 供应链管理；
- HTTPS、key/secret vault、签名密钥轮换、最小化 Admin Console 暴露和单管理员恢复流程；
- 登录/恢复限流、防枚举、密码策略、邮件/SMS sender reputation 与滥用告警；
- 可用性、延迟、错误率、证书/DNS、邮件/SMS delivery 和备份监控；
- provider 数据、日志、备份、删除和事故响应责任说明；
- Self-hosted Logto 的 identity database、audit/security logs 与 backups 属于 JobPilot-controlled stores，必须进入删除传播、backup expiry、restore quarantine/ledger 和 incident-response scope；不能沿用 managed-SaaS DPA 例外；
- 根据实际部署位置完成适用的 ICP、数据保护、网络安全和跨境依赖合规评估。本文记录工程门禁，不构成法律意见。

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

Task 8 保持暂停。若本 ADR 获批，应先执行独立的 Logto deployment/protocol/Mainland verification slice，再决定是否授权认证 adapter 迁移和最终 Phase 2B acceptance。Phase 3 必须继续等待 Phase 2B 生产 identity decision 和验收，不得并行绕过。

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

**Current result: `PROPOSED / AWAITING PROJECT-OWNER APPROVAL`.**

- Task 8 real-provider configuration and integration: `PAUSED`.
- Real Auth0 production selection: `NOT APPROVED`.
- Self-hosted Logto OSS production selection: `PREFERRED CANDIDATE / NOT YET APPROVED`.
- Mainland ordinary-network verification: `NOT VERIFIED`.
- Authentication business-code migration: `NOT STARTED`.
- Phase 3: `NOT AUTHORIZED`.

批准前到此停止。项目负责人可以接受本 ADR、要求修改比较/验收门槛，或拒绝首选方向；任何一种决定都必须先记录，再开始真实资源配置或代码迁移。
