# ADR-008：采用 Local-first Single-user 无认证架构

- **Status**：Accepted
- **Date**：2026-08-31
- **Decision owner**：JobPilot 项目负责人
- **Recovery checkpoint**：`pre-local-first-cleanup`（`9a3e79a7e134142d800bf94a78ecafcad0cf9302`）

## Context

JobPilot 的长期产品形态收缩为中国大陆用户自行安装的个人求职 Desktop Companion。用户从代码发布渠道取得安装包，在自己的电脑启动 Web、FastAPI、本地数据库和 Chrome Extension，并在自己主动打开的招聘网站页面上使用后续岗位采集能力。当前不建设 SaaS、公网账户、远程数据同步或多人协作。

此前 Phase 2 为托管身份、Web session 和 Extension OAuth/PKCE 建立了完整实现，但 Phase 3 尚未开始，也没有真实业务数据依赖 User、Identity、WebSession 或 LoginTransaction。Git 历史与本 ADR 的 checkpoint 已完整保存旧实现，因此继续在当前工作树保留 hosted-auth 死代码只会增加依赖、攻击面和维护成本。

新增 P0 硬约束：

> **JobPilot 的日常核心使用流程必须在关闭 VPN / 代理的中国大陆普通网络环境下工作。**

## Decision

1. JobPilot 当前为 **Local-first / Single-user / Self-hosted Desktop Companion**。一个安装实例等于一个本地 workspace，不建立认证 User。
2. 当前产品不提供账户、登录、身份提供方、OAuth/OIDC/PKCE、JWT、Web session、refresh token、账号恢复或多用户授权。
3. Web 与 Extension 只连接本机 FastAPI；默认 API origin 为 `http://127.0.0.1:8000`。受支持的 launcher 只接受 IP-literal loopback bind，拒绝 `0.0.0.0`、`::`、LAN IP 和普通主机名。
4. 没有登录不等于可以暴露公网。CORS 只接受精确 allowlist，不允许 `*`、wildcard pattern 或 credential allowance。未来写接口必须重新评审 localhost CSRF、Origin/Host/Fetch Metadata 和 DNS-rebinding 风险。
5. PostgreSQL、SQLAlchemy 与 Alembic 工程骨架保留；当前所有 auth-only 表、revision、repository 和测试删除。当前 `/health`-only API 启动不创建数据库连接；保留的数据库 URL 只允许 loopback host，不支持远端 PostgreSQL。若未来确有个人资料需求，再设计产品数据 `LocalProfile`，不预留伪 User。
6. Extension runtime 全部随 bundle 分发，不执行远程 JavaScript，不从 CDN 下载代码，不运行 telemetry，不修改/创建代理或 VPN。当前 Popup 只检查本机 `/health`。
7. 招聘网站流量继续由用户浏览器直接访问，不经过 JobPilot 或境外服务器。未来 content script 只能在另行批准的精确平台域名上由用户主动触发并读取当前已呈现页面；禁止后台爬取、自动翻页、隐藏 API、绕过登录/验证码和扫描未打开页面。
8. Auth0、Logto Cloud、Google API/reCAPTCHA、Turnstile、GitHub API/raw、公共 CDN、远程字体/脚本、境外 AI、telemetry 和 update API 均不是核心 runtime dependency。依赖下载镜像只属于 development acquisition；安装后的核心 runtime 不能要求代理。
9. GitHub 只作为代码发布/下载渠道。安装完成后的日常运行不依赖 GitHub。
10. SaaS、多用户、远程同步、团队协作与公网部署无限期 deferred。任何重新引入都必须新增 ADR、威胁模型、认证/授权设计和负责人批准，不能在 local-first 默认配置上打开远程监听。

## Consequences

- 删除当前工作树中的 Auth0/Logto/provider/OAuth实现、认证 API、User/Identity/session schema、依赖、测试、基础设施和冗余文档；Git history 和 checkpoint 保留恢复路径。
- 当前产品尚未发布且没有真实业务数据；包含已删除 auth revision 的旧开发/测试数据库必须重建，不提供原地迁移兼容。
- `/health` 是当前唯一公开 API。Web 和 Extension 启动后直接进入本地服务状态，不出现登录、退出、账号或认证错误 UI。
- 测试数量会显著下降，这是产品范围收缩的正确结果；新基线只证明当前行为。
- OS 账户、文件权限和 loopback 网络是当前本地数据边界。本机其他受信进程仍可能访问 loopback API；本 ADR 不把 CORS 描述成对本地恶意进程的认证。
- 正式 Extension 分发与每个平台 Adapter 的 no-proxy 验收仍属于其后续 Phase，不在本 cleanup 实现。

## No-proxy Adapter Gate

以后每新增一个招聘平台 Adapter，都必须在 VPN、系统/浏览器代理和特殊 DNS 关闭时真实验证：平台页面、Popup、页面识别、岗位解析、本地保存和 JobPilot 岗位库。任一核心步骤只有开代理才能完成时，该 Adapter 不得标记为支持。

## Current Gate

本轮只执行 Authentication & Repository Simplification，不实现 Phase 3。完成全部自动化、浏览器、secret、loopback/CORS、manifest 和远程依赖检查并取得 Critical 0 / Required 0 后停止，等待负责人决定是否进入 Phase 3。
