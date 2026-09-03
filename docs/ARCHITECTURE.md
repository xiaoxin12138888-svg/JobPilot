# JobPilot 总体架构

> 状态：ADR-008 至 ADR-011 Accepted。Phase 4 contract 已冻结并保持 local-first、
> single-user、no-account、SQLite。

## 1. 运行时

```mermaid
flowchart LR
    U[用户]
    W[React Web]
    E[Chrome Extension BOSS capture Popup]
    C[packages/api-client]
    A[FastAPI 127.0.0.1:8000]
    S[(runtime-data/jobpilot.db)]
    R[原招聘平台]

    U --> W
    U --> E
    W --> C
    E --> C
    C --> A
    A --> S
    R -. 当前可见 DOM 只读解析 .-> E
    W -. 仅打开 source_url .-> R
```

受支持 launcher 在 Uvicorn 前把 SQLite migration 升级到 head。业务请求通过 FastAPI 访问
SQLite；`GET /health` 仍不连接数据库。Web 与 Extension 永不直连 SQLite，API 不访问招聘网站。

## 2. Monorepo 边界

```text
apps/web                 岗位库、手动录入、详情与投递跟踪
apps/extension           BOSS 页面识别、一次性只读 Adapter、确认编辑 Popup
apps/api/domain          Job/Application 值、校验与状态规则
apps/api/application     use-case service 与业务 repository port
apps/api/infrastructure  SQLAlchemy repository 与 SQLite/Alembic
apps/api/api             FastAPI schema、router、安全和错误映射
packages/shared-types    camelCase transport 类型与状态中文
packages/api-client      loopback-only、credential-free、响应校验
```

Router 只处理 request、validation、service 与 response。状态流转不写在 Router，ORM 不泄漏到
API 或 Web。两个业务 repository 保持专用，不建立 generic CRUD/factory。

## 3. Persistence

唯一 runtime database 是 `runtime-data/jobpilot.db`。SQLAlchemy 2.x 管理 transaction，
每个连接启用 foreign keys 和 5000 ms busy timeout；当前单进程继续使用 rollback journal。

Alembic revision `0001_job_application` 只创建 `jobs` 和 `applications`。Application 的
`job_id` 唯一并在 Job 删除时级联。自动化测试必须显式传入临时数据库路径。

## 4. API 与 localhost 写入边界

- bind 只接受 IP-literal loopback；客户端 base URL 只接受 loopback；
- CORS 只允许精确配置的 Web origin、无 credentials、无 wildcard/regex；
- 写请求 Host 必须是 loopback；
- 浏览器 cross-site Origin 或 `Sec-Fetch-Site: cross-site` 写入被拒绝；
- POST/PATCH 只接受 `application/json`；
- SQLite locked/busy 映射为不泄漏内部信息的 `503 DATABASE_BUSY`；
- request ID 与统一错误信封覆盖 validation、domain 和 framework error。

CORS/Host 不是对同一操作系统账户下恶意进程的认证。若以后允许 LAN/public/multi-user，
必须先有新 ADR 与威胁模型。

## 5. Web architecture

Web 不引入路由或状态框架。App 只协调 health 和 library/create/detail 三种视图；岗位库、
表单、详情和 Application 控件为聚焦组件。所有业务 I/O 经过 api-client，不自行拼 HTTP。

“去原平台查看/投递”使用 `target="_blank"` 与 `rel="noreferrer"`，没有关联 mutation。

## 6. Local-first 与后续边界

installed runtime 不依赖远程身份、CDN、字体/脚本、telemetry、update、对象存储或 AI。
Extension 只新增 `activeTab` 与 `scripting`；没有 background、常驻 content script、`tabs`
permission 或招聘网站 host permission。一次性 `BossAdapter` 只能在明确用户手势后读取当前
已呈现的必要 DOM 纯文本，随后由用户确认并通过共享 api-client 调用现有 Job service。

真实 BOSS、Extension、解析、保存与 Web 链路必须单独通过 no-proxy 验收，不得改变 Phase 3
的本地事实边界或 Application 状态。
