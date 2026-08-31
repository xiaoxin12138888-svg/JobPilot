# JobPilot

JobPilot 是一个面向求职者的跨招聘平台 AI 求职工作台。它将用户在不同招聘平台上主动浏览并收藏的岗位汇总到一个工作空间，逐步支持岗位管理、简历匹配、投递跟踪、面试准备与求职结果复盘。

JobPilot 不替代招聘网站，也不建设或批量抓取招聘职位数据库。岗位发现、HR 沟通和正式投递仍在原招聘平台完成。

## 当前阶段

Phase 0、Phase 1 和 Phase 2A 已完成评审并获得项目负责人明确批准。项目当前严格处于 **Phase 2B — Authentication Implementation & User Boundary** 的 Architecture Change Gate。

- [ADR-006](docs/DECISIONS/ADR-006-authentication-strategy.md) 是已实现认证边界的 Accepted 历史记录；新增 [ADR-007](docs/DECISIONS/ADR-007-mainland-china-identity-provider.md) 正在评审生产 Identity Provider。
- 新增硬约束：**Core JobPilot workflow must operate without VPN/proxy in Mainland China.**
- Task 6 已获项目负责人批准；Task 7A–7G 的 Extension Authorization Code + PKCE 确定性实现及 Task 7H 自动化、审查、简化和文档门禁均已完成。Task 8 的真实 provider 配置和联调现已暂停。
- 当前实现覆盖 Web 与 Extension 两种认证 transport、FastAPI/PostgreSQL 的最小认证闭环，以及由 Task 5 建立的 `issuer + subject -> JobPilot User.id` 服务端边界。
- Self-hosted Logto OSS 是当前首选候选，但尚未批准或迁移；Auth0 不再默认批准为生产 provider。不得创建真实 Auth0/Logto 资源或绑定 IDs、origins、redirects、connectors 与 secrets。
- 自动化继续使用 deterministic fake issuer/JWKS；Chrome Load unpacked、真实 provider flow 和中国大陆普通网络可用性均为 `NOT VERIFIED / BLOCKED`。
- 本阶段不实现 Job、Application、Resume、AI、RAG 或其他 Phase 3+ 能力；Phase 2B 验收前不得进入 Phase 3。

## 当前实现状态（截至 Task 7）

- `apps/web`：最小认证状态 UI；按 `/api/v1/auth/me` → `/api/v1/auth/csrf` 恢复 server-backed session，提供固定 login navigation、本地 logout、失败与重试状态。React 不处理 OAuth token。
- `apps/extension`：Manifest V3 trusted service worker 负责用户触发的 Authorization Code + PKCE S256、callback/state/nonce 验证、public-client code exchange、按需 single-flight refresh、`/auth/session` identity establishment、`/auth/me` 与真实语义的 logout；Popup 只发送精确 typed intents 并显示 credential-free 用户状态。
- `apps/api`：保留 `GET /health`，并实现 provider-neutral identity boundary、Web OIDC authorize/callback、opaque session、cookie `/auth/me`、CSRF 与本地 logout。
- PostgreSQL：通过 SQLAlchemy/Alembic 持久化 User、Identity、WebSession 与 LoginTransaction；session/CSRF 只存摘要，不保存 provider token/grant。
- `packages/shared-types`：共享 health、批准的 `UserView` 与 CSRF response 类型。
- `packages/api-client`：分别封装 Web cookie transport 与 Extension bearer transport；Extension 首次登录依次调用 `/auth/session` 和 `/auth/me`，请求固定使用 `credentials: omit`，并只投影批准的 User 字段。

当前仓库仍没有 Job、Application、Resume 等 Phase 3+ 业务 persistence、招聘网站解析或 AI/RAG。当前 Auth0-compatible deterministic implementation 保留不变；任何真实 provider flow 都必须等待 ADR-007 和后续 provider verification/migration slice 获得项目负责人批准。

## 目标技术栈

| 区域       | 技术选择                                               |
| ---------- | ------------------------------------------------------ |
| Web        | React、TypeScript、Vite                                |
| 浏览器扩展 | Chrome Extension、Manifest V3、TypeScript              |
| API        | Python、FastAPI                                        |
| 数据库     | PostgreSQL；需要 RAG 时启用 pgvector                   |
| AI         | LLM API、Structured Output、服务抽象                   |
| 文件存储   | S3-compatible object storage abstraction               |
| 基础设施   | Docker、Git、GitHub；GitHub Actions 在后续阶段按需加入 |
| 可观测性   | 结构化日志；后续按需加入 Sentry                        |

## 目标架构速览

JobPilot 采用 **monorepo + modular monolith**：

- `apps/web`：在后续阶段负责 Web 交互和呈现，通过统一 API 访问业务能力。
- `apps/extension`：在 Phase 3 起只解析用户当前主动打开的岗位页面、提供确认交互，并通过统一 API 保存岗位。
- `apps/api`：在相应阶段逐步承担认证、业务规则、数据持久化、AI/RAG 编排和对象存储抽象。
- `packages/shared-types`：仅容纳 Web 与 Extension 真正共享且稳定的 TypeScript 契约。
- `packages/api-client`：为两个 TypeScript 客户端提供统一 API 调用边界。
- PostgreSQL 是业务事实来源；前端和扩展不得各自定义业务状态。

以上是分阶段目标责任。Phase 1 只创建了当前有真实消费者的应用和 package，没有预建未来业务模块。

## Development Setup

### 前置条件

| 工具            | 要求                                      |
| --------------- | ----------------------------------------- |
| Git             | 当前稳定版                                |
| Node.js         | `^22.22.2`、`^24.15.0` 或 `>=26.0.0`      |
| pnpm            | `11.19.0`（仓库 `packageManager` 已固定） |
| Python          | `>=3.12,<3.13`                            |
| uv              | `0.12.7` 或兼容版本                       |
| Chrome/Chromium | 用于加载 unpacked Extension               |

安装 pnpm 或 uv 后如果当前终端仍找不到命令，请重新打开终端，再用 `pnpm --version` 和 `uv --version` 确认。

### 配置与安装

在仓库根目录执行：

```powershell
Copy-Item .env.example .env
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

Bash 中复制环境文件可使用 `cp .env.example .env`。`.env` 已被 Git 忽略，不得在其中放入需要提交的真实 secret。

### 启动 API 与 Web

分别在两个终端中执行：

```powershell
pnpm api:dev
```

```powershell
pnpm dev:web
```

打开 `http://localhost:5173`。Web 会先检查 `/api/v1/auth/me`，并显示 checking、signed-out、signed-in、callback error 或 unavailable 状态；API 探针位于 `http://localhost:8000/health`。未注入完整 Auth0/数据库运行时配置时，认证端点会 fail closed，不能据此声称真实登录已验证。

### 构建与加载 Extension

单次构建：

```powershell
pnpm build:extension
```

只验证确定性构建产物（使用已跟踪的 `.invalid` public-client 配置，不能登录真实 provider）：

```powershell
pnpm build:extension:test
```

或在开发期间持续构建：

```powershell
pnpm dev:extension
```

在 Chrome/Chromium 扩展管理页开启 Developer mode，选择 **Load unpacked**，并指向 `apps/extension/dist`。调试时保持 API 运行；watch 构建后需在扩展管理页重新加载扩展。

### 环境变量与 CORS

- Vite 会从仓库根目录的 `.env` 读取 `VITE_API_BASE_URL`、`VITE_WEB_APP_URL`、`VITE_AUTH_ISSUER`、`VITE_AUTH_AUTHORIZE_URL`、`VITE_AUTH_TOKEN_URL`、`VITE_AUTH_JWKS_URL`、`VITE_AUTH_REVOKE_URL`、`VITE_AUTH_AUDIENCE` 与 `VITE_AUTH_EXTENSION_CLIENT_ID`。这些都是 public-client 配置，不是 secret；Extension 没有也不得新增 client-secret 输入。
- Auth issuer 必须是带结尾 `/` 的 canonical HTTPS root；authorize/token/JWKS/revoke endpoint 必须是同一 issuer origin 的固定 HTTPS URL。API 与 Web origin 在远端必须使用 HTTPS；HTTP 只允许精确 `localhost`、`127.0.0.1` 或 `[::1]` loopback。非法值在 Vite 构建与 worker runtime 使用前 fail closed。
- Extension 的 API/provider `host_permissions` 从上述验证配置生成；修改任一 origin 后必须重新构建 Extension。当前 manifest 权限只有 `identity` 与 `storage`，不含 `activeTab`、`tabs`、content script 或招聘网站权限。
- FastAPI 不自动读取根 `.env`，而是从 API 进程环境读取 `JOBPILOT_*` 数据库、Auth0、Web session 与 CORS 配置；`JOBPILOT_AUTH_WEB_CLIENT_SECRET` 只允许注入服务端，绝不能使用 `VITE_` 前缀。
- 未设置 API 变量时，开发环境默认精确允许 `http://localhost:5173`。`test` 和 `production` 默认不允许跨域来源。
- 多个 CORS origin 使用逗号分隔；任何环境都拒绝 `*`。生产环境必须在启动 API 的运行环境中显式注入精确 origin。
- 生产 Web host 必须把 `/auth/error` rewrite 到 SPA entry，并在部署层配置经评审的 CSP 与安全响应头；仓库不使用宽松的 meta CSP 伪装生产配置。

真实 Extension 登录当前受 ADR-007 Architecture Change Gate 阻断：

1. 不执行原 Auth0 tenant/application/API audience setup checklist，不绑定真实 Auth0 Client ID 或 Extension ID。
2. 不直接创建 Self-hosted Logto OSS 生产实例或迁移代码；先等待项目负责人审批 ADR-007。
3. 若 Logto 方向获批，后续独立 Gate 必须冻结 exact issuer/resource、Web confidential client、Extension public/SPA client、callback/CORS、claims、5–10 分钟 access-token 上限、refresh rotation/reuse/revoke 语义与 connector。
4. Web、Extension、账号恢复和全部运行时依赖必须在中国大陆普通网络、无 VPN/代理条件下实测；`.invalid` fixture 不构成可达性证据。
5. 在真实 provider 和 Mainland acceptance 通过前，不开始 Task 8 或 Phase 3。

### 验证命令

| 命令                    | 作用                                                                |
| ----------------------- | ------------------------------------------------------------------- |
| `pnpm test`             | 运行 api-client、Web 和 Extension 的 TypeScript 测试；不包含 Pytest |
| `pnpm api:test`         | 运行 FastAPI/Pytest 测试                                            |
| `pnpm lint`             | 运行 ESLint                                                         |
| `pnpm typecheck`        | 运行 TypeScript strict typecheck                                    |
| `pnpm format:check`     | 检查 Prettier 格式                                                  |
| `pnpm api:lint`         | 运行 Ruff lint                                                      |
| `pnpm api:format:check` | 检查 Ruff 格式                                                      |
| `pnpm build:web`        | 生成 Web production build                                           |
| `pnpm build:extension`  | 生成 `apps/extension/dist` unpacked Extension                       |
| `pnpm api:import:check` | 验证 FastAPI 应用可导入                                             |

## 项目文档

- [产品规格](docs/PRODUCT_SPEC.md)
- [系统架构](docs/ARCHITECTURE.md)
- [认证架构（Phase 2A Accepted；Task 6 Web 与 Task 7 Extension deterministic slices implemented）](docs/AUTH_ARCHITECTURE.md)
- [工程原则](docs/ENGINEERING_PRINCIPLES.md)
- [API 契约](docs/API_CONTRACT.md)
- [数据模型](docs/DATA_MODEL.md)
- [路线图](docs/ROADMAP.md)
- [架构决策记录](docs/DECISIONS/README.md)
