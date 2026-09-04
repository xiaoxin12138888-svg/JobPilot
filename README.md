# JobPilot

JobPilot 是面向个人求职者的本地优先求职工作台。它计划把用户在招聘网站上主动查看并确认的信息整理到一个本机 workspace，逐步支持岗位管理、申请跟踪和简历版本关联。

JobPilot 不替代招聘网站，不建设职位数据库，也不代表用户自动搜索、抓取或投递。

## 当前状态

项目已通过 **Phase 3 — Job & Application Domain Foundation**。负责人已批准 **Phase 4 — BOSS Direct Job Capture**，当前在 `phase/4-boss-job-capture` 按冻结 contract 实现。Phase 3 能力包括：

- React Web：本机 API 状态、岗位库、手动录入、岗位详情/编辑/删除和投递状态管理；
- Chrome Extension：无 privileged Chrome API permission、无后台进程的本地健康 Popup；唯一 host permission 是 `http://127.0.0.1:8000/*`；
- FastAPI：公开 `GET /health` 以及最小 Job/Application REST API，默认绑定 `127.0.0.1`；
- SQLite、SQLAlchemy 与 Alembic：launcher 启动前自动升级 `runtime-data/jobpilot.db`，revision 只创建 `jobs` 与 `applications`；
- `packages/shared-types` 与 `packages/api-client`：提供 camelCase 业务契约、credential-free 请求和不可信响应校验。

Phase 4 只新增 BOSS 直聘当前岗位页的用户主动采集、确认编辑与本地保存。它不引入其他招聘平台、常驻 content script、后台抓取、AI、RAG、自动投递、云同步或上传。

## 本地优先意味着什么

- 一个安装实例就是一个本地 workspace；没有 JobPilot 账号、登录、云租户或多用户权限体系。
- 正常使用不需要 JobPilot 云服务器，不需要注册云账号，也不依赖 “JobPilot Cloud”。
- 已安装后的核心运行不需要 VPN、代理或特殊 DNS。
- 未来业务数据保存在用户自己的电脑，由操作系统账户和文件权限保护。
- Web 与 Extension 只访问 loopback FastAPI；不支持公网、局域网或远端 API。
- 招聘网站流量由用户自己的浏览器直接访问，不经过 JobPilot API 或 JobPilot 服务器。

## P0 no-proxy runtime

已安装核心必须在中国大陆普通网络、关闭 VPN/系统代理/浏览器代理/特殊 DNS 时工作。该要求覆盖 JobPilot Web、FastAPI、Extension Popup、未来 content script、岗位识别/保存/本地读写，以及 BOSS 直聘、牛客、实习僧、猎聘和国聘的后续 Adapter。

Auth0、Logto Cloud、Google APIs、Google reCAPTCHA、Cloudflare Turnstile、GitHub API/raw content、jsDelivr、unpkg、cdnjs、远程字体/JavaScript、境外 AI API、境外 telemetry/analytics 或境外 update API 永远不能成为核心 runtime dependency。未来可选远程能力即使经单独 ADR/批准，也必须显式启用、可降级，并且不阻塞本地核心。

当前 supported recruitment adapters：`none`。BOSS 直聘为 `IN PROGRESS / NOT SUPPORTED`；牛客、实习僧、猎聘和国聘均为 `NOT STARTED / NOT SUPPORTED`。必须等对应实现和以下 Gate 全部通过后才能改变状态。

Extension 必须满足：

- 所有 JavaScript 与样式随 bundle 分发，不执行远程代码；
- 不下载 CDN 资源，不修改或创建代理/VPN，不发送 telemetry；
- Phase 4 contract 只允许 `activeTab`、`scripting` 与精确 loopback API host permission，没有后台、常驻 content script、`tabs` permission 或招聘网站 host permission；
- 每个 Adapter 必须由用户主动触发，并且只读取当前已打开页面的已呈现 DOM；
- 每个 Adapter 都要在无代理真实网络上分别记录：招聘平台页面、Extension Popup、页面识别、岗位解析、保存到 JobPilot、JobPilot 岗位库的 `PASS / FAIL`；任一步依赖代理就不能标为支持。

依赖镜像、pnpm registry、PyPI 和 GitHub release 只属于开发或安装阶段，不得变成已安装运行时依赖。

## Runtime architecture

```text
React Web ---------\
                    > exact loopback HTTP -> FastAPI -> health + Job/Application
Chrome Extension --/                            |
                                                 v
                                      runtime-data/jobpilot.db (SQLite)

BOSS current rendered DOM -- user click/read-only --> Chrome Extension
Web original-platform link -> user's browser -> recruitment website
JobPilot API never proxies recruitment website traffic
```

## Development setup

### Prerequisites

- Git
- Node.js `^22.22.2`、`^24.15.0` 或 `>=26.0.0`
- pnpm `11.19.0`
- Python `>=3.12,<3.13`
- uv `0.12.7` 或兼容版本
- Chrome/Chromium（用于加载 unpacked Extension）

### Install

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

默认首次运行不需要 `.env`、PostgreSQL、Docker、数据库账号、Extension ID、VPN 或代理。可选 `.env` 只供 Vite 读取 `VITE_*` 本机开发覆盖并已被 Git 忽略；API override 必须设置为启动进程的环境变量。不得提交 `.env` 或其他 secret。

### Start API and Web

分别在两个终端执行：

```powershell
pnpm run api:dev
```

```powershell
pnpm run dev:web
```

打开 `http://127.0.0.1:5173`。API 探针位于 `http://127.0.0.1:8000/health`。受支持的 API launcher 会在 Uvicorn 启动前执行 Alembic upgrade；停止再启动不会覆盖已有数据库。

关闭 API：在运行 API 的终端按 `Ctrl+C`。再次执行 `pnpm run api:dev` 即可重启并恢复本地数据。

### Build and load Extension

```powershell
pnpm run build:extension
```

在 Chrome/Chromium 扩展管理页开启 Developer mode，选择 **Load unpacked**，并指向 `apps/extension/dist`。Popup 打开时只检查精确的 `http://127.0.0.1:8000/health`；用户随后明确点击时，开发中的 Phase 4 流程才会读取当前 BOSS 岗位详情页并显示可编辑预览。

Extension 通过 manifest 中精确的 `http://127.0.0.1:8000/*` host permission 直接读取 health，不需要也不允许把 Extension ID 加到 API CORS。API CORS 仅服务精确的 loopback Web origin。

## Local configuration

- `VITE_API_BASE_URL`：Web 与 Extension 共用的 build-time loopback API base；同时构建 Extension 时必须保持精确 `http://127.0.0.1:8000`，Web 单独运行才可接受 `localhost` 或 `[::1]`；
- `JOBPILOT_API_BIND_HOST`：API 监听地址，只接受 IP-literal loopback；
- `JOBPILOT_CORS_ORIGINS`：逗号分隔的精确 loopback Web origins；

数据库固定为本地 SQLite 文件，不读取 database URL。默认路径是 `runtime-data/jobpilot.db`；整个目录被 Git 忽略，并且测试、clean、build 和格式化流程都不得删除、替换或写入真实数据库。测试与 Alembic 验证必须显式使用临时 SQLite 路径。

每个 SQLite connection 都启用外键和 5000 ms busy timeout。当前单用户、单进程且没有并发写入证据，因此保留默认 rollback journal；需要 WAL 时必须先提供运行证据和独立评审。

## Verification

```powershell
pnpm run test
pnpm run lint
pnpm run format:check
pnpm run typecheck
pnpm run build:web
pnpm run build:extension
pnpm run api:test
pnpm run api:lint
pnpm run api:format:check
pnpm run api:import:check
```

## Documentation

- [产品规格](docs/PRODUCT_SPEC.md)
- [系统架构](docs/ARCHITECTURE.md)
- [API 契约](docs/API_CONTRACT.md)
- [数据模型](docs/DATA_MODEL.md)
- [工程原则](docs/ENGINEERING_PRINCIPLES.md)
- [路线图](docs/ROADMAP.md)
- [架构决策记录](docs/DECISIONS/README.md)

本地产品边界由 [ADR-008](docs/DECISIONS/ADR-008-local-first-single-user-no-authentication.md) 固定，SQLite 存储由 [ADR-009](docs/DECISIONS/ADR-009-local-sqlite-storage.md) 固定。被移除的历史认证实现和 ADR 可从 annotated tag `pre-local-first-cleanup` 恢复；它们不是当前产品文档。
