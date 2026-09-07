# JobPilot

JobPilot 是面向个人求职者的本地优先求职工作台。它把用户主动确认的岗位、投递、简历版本、
面试记录与结果复盘整理到一个本机 workspace。

JobPilot 不替代招聘网站，不建设职位数据库，也不代表用户自动搜索、抓取或投递。

## 当前状态

项目已通过 **Phase 3 — Job & Application Domain Foundation**、**Phase 4 — BOSS Direct Job Capture**、**Phase 5 — Nowcoder Adapter & Shared Capture Contract**、**Phase 6 — JD Structured AI Analysis**、**Phase 8 — Interview Record & Feedback Loop** 与 **Phase 9 — Profile Vault & Safe Job Form Autofill**。Phase 9 已在真实中国移动校招表单完成 Scan → Preview → Confirm → Fill → 人工检查，填写 1/1 个确认字段且未触发 Submit/Continue。**Phase 10 — Local Resume Import** 已获批准并处于实现中，目标是本机 PDF/DOCX → Parse → Review → 明确确认后创建 Resume Version/更新 Profile；解析本身不保存。**Phase 7 — Resume Version & Evidence Map** 已实现，但真实语义质量验收仍为 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。核心能力包括：

- React Web：本机 API 状态、岗位库、纯文本简历版本、本地求职资料、岗位详情/编辑/删除、投递状态/使用简历记录、面试轮次与题目、自我复盘、Application 结果记录、事实型求职复盘，以及可选 JD Analysis/Evidence Map；
- Chrome Extension：使用 `activeTab` + `scripting` 的用户主动 Popup，支持 BOSS/牛客岗位采集与当前申请表的 Scan → Preview → Confirm → Fill；无后台进程，唯一 host permission 是 `http://127.0.0.1:8000/*`；
- FastAPI：公开 `GET /health`、Job/Application/Resume Version、Autofill Profile、Interview 与事实型 Feedback Summary，以及每个 Job 的可选分析/Evidence Map API，默认绑定 `127.0.0.1`；
- SQLite、SQLAlchemy 与 Alembic：launcher 启动前自动升级 `runtime-data/jobpilot.db`，业务表另含 single-user singleton `autofill_profiles`；
- `packages/shared-types` 与 `packages/api-client`：提供 camelCase 业务契约、credential-free 请求和不可信响应校验。

Phase 4 已交付 BOSS 直聘当前岗位页采集；Phase 5 在同一确认编辑与本地保存链路上新增牛客岗位详情页。两个 Adapter 都只读取用户当前打开页面的必要可见文本。Phase 6 不改 Extension，只允许 Web 在用户点击后把单个已保存 Job 的最小 JD 字段经 FastAPI 发送给显式配置的 Provider。Phase 7 增加本地纯文本 Resume Version、Application 显式使用版本和 Evidence Map；新生成结果会综合当前非 stale JD Analysis 的硬性要求、加分项、职责、技能、经验与学历六类条件，并从完整简历中寻找一至三段可追溯的语义证据，而非要求关键词相同。语义判断不能补全简历未写的能力、年限、学历、毕业年份或其他用户事实。只有用户在当次操作中确认后，所选简历正文才会与这些条件一起发往同一个可选 Provider。不开 AI 时本地核心照常工作。

Phase 8 不调用 LLM：用户可在已有 Application 下记录多轮面试、实际题目、回答摘要、自评和手动
复盘，并为淘汰/Offer 等终态保存自己的结果说明。`求职复盘` 直接从 SQLite 计算岗位、投递、
面试、题目、结果、来源和简历版本事实；不存派生统计，不给 AI 分数、推荐或因果结论。面试动作
不会自动改变 Application 状态。

Phase 9 同样不调用 LLM：用户在 Web 的“求职资料”中维护最小结构化事实；只有点击 Extension 的
“扫描当前表单”后，当前页面才被一次性扫描。确定性规则把精确/规范化字段设为“可填写”，把唯一
模糊候选设为“需确认”，敏感、文件、单选/复选、缺值和未知字段分别保持手动或未识别。只有用户
在 Preview 中确认并点击“填写已确认字段”后才写入页面；JobPilot 永不点击 Submit/Continue，
也不创建或推进 Application。Profile 和 Fill Plan 只存在于本机 SQLite 与当次 Popup 内存。

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

当前 supported recruitment adapters：BOSS 直聘与牛客均为 `SUPPORTED — V1`。实习僧、猎聘、智联和国聘为 `NOT SUPPORTED`；Phase 6 暂停横向 Adapter 扩展。

Extension 必须满足：

- 所有 JavaScript 与样式随 bundle 分发，不执行远程代码；
- 不下载 CDN 资源，不修改或创建代理/VPN，不发送 telemetry；
- 当前 contract 只允许 `activeTab`、`scripting` 与精确 loopback API host permission，没有后台、常驻 content script、`tabs` permission 或招聘网站 host permission；
- 每个 Adapter 必须由用户主动触发，并且只读取当前已打开页面的已呈现 DOM；
- 每个 Adapter 都要在无代理真实网络上分别记录：招聘平台页面、Extension Popup、页面识别、岗位解析、保存到 JobPilot、JobPilot 岗位库的 `PASS / FAIL`；任一步依赖代理就不能标为支持。

依赖镜像、pnpm registry、PyPI 和 GitHub release 只属于开发或安装阶段，不得变成已安装运行时依赖。

## Runtime architecture

```text
React Web ---------\
                    > exact loopback HTTP -> FastAPI -> Job/Application/Resume/Interview/Feedback
Chrome Extension --/                            |
                                                 v
                         runtime-data/jobpilot.db (SQLite + AutofillProfile)

React Web -- explicit analysis click ------------\
React Web -- explicit Resume disclosure/confirm --> FastAPI -- optional --> configured LLM provider

BOSS/Nowcoder current rendered DOM -- user click/read-only --> Chrome Extension
Current application form -- user Scan/Confirm/Fill --> Chrome Extension -- no Submit
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

JD 分析与 Evidence Map 是可选增强。要启用它们，只在启动 FastAPI 的本地进程环境中设置
`JOBPILOT_LLM_BASE_URL`、`JOBPILOT_LLM_API_KEY`、`JOBPILOT_LLM_MODEL`；三项不完整或非法时
Web 显示“AI 服务未配置”，API 与本地核心仍正常启动。真实 Key 不得写入 `.env.example`、Git、
Web 或 Extension。

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

在 Chrome/Chromium 扩展管理页开启 Developer mode，选择 **Load unpacked**，并指向 `apps/extension/dist`。Popup 打开时只检查精确的 `http://127.0.0.1:8000/health`；用户随后明确点击时，才会读取当前 BOSS/牛客岗位详情，或扫描当前招聘申请表并生成填写预览。扫描不改页面，填写后仍由用户自己检查并提交。

Manifest 提交的 `key` 只是可公开的扩展公钥，不包含私钥或 secret；它让 GitHub 源码用户通过
**Load unpacked** 得到固定 ID `lgchonbleblfegkckndaaandoaekmgjf`。如果此前加载过不含该 key
的旧构建，应先在扩展管理页移除旧项，再重新 Load unpacked，并核对显示的 ID。

Extension 通过 manifest 中精确的 `http://127.0.0.1:8000/*` host permission 直接读取 health。
API 写入 gate 只为 `POST /api/v1/jobs` 额外接受精确 Origin
`chrome-extension://lgchonbleblfegkckndaaandoaekmgjf` 与 `Sec-Fetch-Site: none` 的组合；其他
合法或畸形 Extension ID 均拒绝。该 Origin 不加入 CORS；API CORS 仍仅服务精确的 loopback
Web origin。Extension 读取 `GET /api/v1/autofill-profile` 也要求同一精确 Origin、
`Sec-Fetch-Site: none` 与 loopback Host；Profile 的 PUT 仍只允许合法 Web origin。

## Local configuration

- `VITE_API_BASE_URL`：Web 与 Extension 共用的 build-time loopback API base；同时构建 Extension 时必须保持精确 `http://127.0.0.1:8000`，Web 单独运行才可接受 `localhost` 或 `[::1]`；
- `JOBPILOT_API_BIND_HOST`：API 监听地址，只接受 IP-literal loopback；
- `JOBPILOT_CORS_ORIGINS`：逗号分隔的精确 loopback Web origins；
- `JOBPILOT_LLM_BASE_URL`：可选 OpenAI-compatible `/v1` base URL；
- `JOBPILOT_LLM_API_KEY`：只存在于 API 进程环境的可选 secret；
- `JOBPILOT_LLM_MODEL`：可选模型名；三项必须同时有效才启用 JD 分析与 Evidence Map。

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
- [招聘页面采集 Adapter](docs/technical/JOB_CAPTURE_ADAPTER.md)
- [JD 结构化 AI 分析](docs/technical/JD_AI_ANALYSIS.md)
- [简历版本](docs/technical/RESUME_VERSION.md)
- [简历证据映射](docs/technical/EVIDENCE_MAP.md)
- [面试记录](docs/technical/INTERVIEW_RECORD.md)
- [事实反馈闭环](docs/technical/FEEDBACK_LOOP.md)
- [求职资料与安全自动填写](docs/technical/AUTOFILL.md)
- [本地 PDF / DOCX 简历导入](docs/technical/RESUME_IMPORT.md)
- [自动填写第三方研究与许可](docs/technical/THIRD_PARTY_AUTOFILL_RESEARCH.md)
- [JD 分析评测状态](docs/evaluation/JD_ANALYSIS_RESULTS.md)
- [自动填写 Bad Cases](docs/evaluation/AUTOFILL_BAD_CASES.md)
- [架构决策记录](docs/DECISIONS/README.md)

本地产品边界由 [ADR-008](docs/DECISIONS/ADR-008-local-first-single-user-no-authentication.md) 固定，SQLite 存储由 [ADR-009](docs/DECISIONS/ADR-009-local-sqlite-storage.md) 固定，BOSS/牛客共享采集合同由 [ADR-012](docs/DECISIONS/ADR-012-nowcoder-shared-capture-contract.md) 固定，可选 JD 分析由 [ADR-013](docs/DECISIONS/ADR-013-jd-structured-ai-analysis.md) 固定，Resume Version 与 grounded Evidence Map 由 [ADR-014](docs/DECISIONS/ADR-014-resume-version-evidence-map.md) 固定，本地面试记录与事实反馈由 [ADR-015](docs/DECISIONS/ADR-015-interview-record-feedback-loop.md) 固定，Profile Vault 与安全表单自动填写由 [ADR-016](docs/DECISIONS/ADR-016-profile-vault-safe-autofill.md) 固定，本地 PDF/DOCX 导入由 [ADR-017](docs/DECISIONS/ADR-017-local-resume-import.md) 固定。被移除的历史认证实现和 ADR 可从 annotated tag `pre-local-first-cleanup` 恢复；它们不是当前产品文档。
