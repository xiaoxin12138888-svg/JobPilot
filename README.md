# JobPilot

JobPilot 是一个面向求职者的跨招聘平台 AI 求职工作台。它将用户在不同招聘平台上主动浏览并收藏的岗位汇总到一个工作空间，逐步支持岗位管理、简历匹配、投递跟踪、面试准备与求职结果复盘。

JobPilot 不替代招聘网站，也不建设或批量抓取招聘职位数据库。岗位发现、HR 沟通和正式投递仍在原招聘平台完成。

## 当前阶段

Phase 0 已完成评审并获得项目负责人明确批准。项目当前严格处于 **Phase 1 — Engineering Skeleton**。

- 本阶段只建立可运行、可测试的 Web、浏览器扩展和 API 工程骨架。
- 不实现认证、数据库业务模型、岗位采集、AI、RAG 或其他正式业务功能。
- Phase 1 完成验收并获得明确批准前，不进入 Phase 2。

## Phase 1 当前实现

- `apps/web`：React/Vite 开发状态页，显示运行环境与 API 连接状态。
- `apps/extension`：Manifest V3 Popup，仅在用户打开 Popup 时读取当前标签页 URL，并检查 API 连接。
- `apps/api`：FastAPI 进程和唯一的 `GET /health` 基础设施探针。
- `packages/shared-types`：当前仅共享 `ApiHealthResponse`。
- `packages/api-client`：当前仅封装经响应校验的 `getHealth()`。

本阶段没有 PostgreSQL、ORM、认证、岗位数据、招聘网站解析或 AI/RAG 实现。

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

打开 `http://localhost:5173`。页面应显示 `API connection status: Connected`；API 探针位于 `http://localhost:8000/health`。

### 构建与加载 Extension

单次构建：

```powershell
pnpm build:extension
```

或在开发期间持续构建：

```powershell
pnpm dev:extension
```

在 Chrome/Chromium 扩展管理页开启 Developer mode，选择 **Load unpacked**，并指向 `apps/extension/dist`。调试时保持 API 运行；watch 构建后需在扩展管理页重新加载扩展。

### 环境变量与 CORS

- Vite 会从仓库根目录的 `.env` 读取 `VITE_API_BASE_URL`。该值是公开客户端配置，不是 secret。
- Extension 的 API `host_permissions` 从同一个 `VITE_API_BASE_URL` 生成；修改该值后必须重新构建 Extension。
- FastAPI 不自动读取根 `.env`，而是从 API 进程环境读取 `JOBPILOT_ENVIRONMENT` 和 `JOBPILOT_CORS_ORIGINS`。
- 未设置 API 变量时，开发环境默认精确允许 `http://localhost:5173`。`test` 和 `production` 默认不允许跨域来源。
- 多个 CORS origin 使用逗号分隔；任何环境都拒绝 `*`。生产环境必须在启动 API 的运行环境中显式注入精确 origin。

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
- [工程原则](docs/ENGINEERING_PRINCIPLES.md)
- [API 契约](docs/API_CONTRACT.md)
- [数据模型](docs/DATA_MODEL.md)
- [路线图](docs/ROADMAP.md)
- [架构决策记录](docs/DECISIONS/README.md)
