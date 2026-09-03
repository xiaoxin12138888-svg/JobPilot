# ADR-009：采用本地 SQLite 作为唯一 Runtime Database

- **Status**：Accepted
- **Date**：2026-09-01
- **Decision owner**：JobPilot 项目负责人
- **Supersedes**：[ADR-002](ADR-002-fastapi-postgresql.md) 与
  [ADR-008](ADR-008-local-first-single-user-no-authentication.md) 中选择 PostgreSQL 的部分

## Context

JobPilot 已确定为用户从 GitHub 获取并在个人电脑运行的 local-first、single-user workspace。
当前只有 `GET /health`，SQLAlchemy metadata 与 Alembic migration history 均为空，还没有任何
Job、Application、ResumeVersion 或其他业务数据需要迁移。继续要求用户安装 PostgreSQL、创建
database 并配置账号密码，会把尚不存在的规模需求转化为真实的首次运行障碍。

本决定只收敛当前本地持久化选择。FastAPI、SQLAlchemy 2.x、Alembic、single-user、loopback、
no-account 与 no-proxy 决策继续有效。

## Comparison

| Criterion | SQLite | PostgreSQL | Current finding |
| --- | --- | --- | --- |
| 安装复杂度 | Python 自带 driver，无独立服务 | 需要安装、启动和维护独立服务 | SQLite 明显更简单 |
| GitHub 用户首次运行体验 | 应用可自动创建一个本地文件 | 用户需创建 database、账号和密码 | SQLite 符合 download-and-run |
| 单用户场景 | 进程内、单 workspace 模型直接匹配 | client/server 能力在当前过剩 | SQLite 更合适 |
| 当前预计数据规模 | 足以承载个人岗位、申请和简历元数据 | 更适合更高并发和更大服务端负载 | 当前没有采用 PostgreSQL 的规模证据 |
| 事务能力 | 支持 ACID 事务与外键；写入串行 | 更强并发写入与隔离选项 | 当前单用户写入不构成阻塞 |
| 备份 | 停止写入后复制单文件，后续可增加 SQLite backup API | 通常需要 dump/restore 工具与服务知识 | SQLite 更易向个人用户解释 |
| SQLAlchemy 支持 | SQLAlchemy 2.x 原生支持 | SQLAlchemy 2.x 原生支持 | 两者都满足 |
| Alembic 支持 | 支持；复杂 ALTER 未来可能需要 batch migration | DDL 能力更完整 | 当前空 schema 无阻塞，未来逐 migration 评审 |
| 后续迁移可能 | 可通过 Alembic/schema + 显式数据导出迁移 | 可作为未来目标 | Git history 不需要当前保留双模式 |
| AI/RAG 未来影响 | 结构化事实仍可本地保存；派生向量可重建 | pgvector 等能力更丰富 | AI/RAG 未授权，不能驱动当前基础设施 |

## Decision

1. SQLite 是 JobPilot 当前唯一 runtime database；不保留 PostgreSQL runtime、driver、环境变量、
   URL validator、测试或双数据库抽象。
2. 默认数据库文件是 repository root 下的 `runtime-data/jobpilot.db`。受支持的 API launcher 在
   首次运行时自动创建目录和 database，后续启动复用同一文件。
3. 用户正常运行不需要设置 `DATABASE_URL`、安装 PostgreSQL、创建 database，或配置数据库账号
   密码。测试和工具可以显式传入临时 SQLite path，但不得触碰真实 runtime data。
4. 保留 SQLAlchemy 2.x 与 Alembic。所有数据库连接启用 `PRAGMA foreign_keys=ON`，使用有界
   busy timeout，并由调用方使用显式事务边界。
5. 当前没有并发写入或长事务证据，因此保持 SQLite 默认 rollback journal，不启用 WAL。未来若
   实测 Web/FastAPI 并发写入需要 WAL，再通过独立测试和评审启用。
6. 当前不创建业务表或 migration。Phase 3 获批后，第一批真实业务 schema 仍通过 Alembic 引入。
7. clean、build、test、format 与 repository cleanup 永远不能删除 `runtime-data/jobpilot.db`。
   数据库文件属于用户数据；备份与恢复说明必须在业务数据正式引入前完善。

## Consequences

- 首次运行路径不再依赖 Docker、PostgreSQL 服务、数据库账号密码或 `JOBPILOT_DATABASE_URL`。
- SQLite 文件与整个 `runtime-data/` 保持 Git ignored；测试数据库必须位于临时目录。
- SQLite 单 writer 模型是当前可接受约束。若未来出现可测量的并发、容量或查询阻塞，再新增 ADR
  评估 PostgreSQL；不能提前恢复双模式。
- 未来迁移到 PostgreSQL 会需要一次显式 schema/data migration，但当前空 schema 使现在切换的
  成本最低。
- AI/RAG 仍属于未授权的未来能力；任何向量方案都必须可选、可重建，且不能成为核心 runtime
  dependency。

## Acceptance

- clean temp directory 可首次创建 SQLite database；第二次初始化复用且不覆盖已有数据；
- 每个连接的 foreign keys 已启用，Alembic 可连接同一 SQLite URL；
- supported API launcher 使用默认 path 时正常启动且不要求数据库环境变量；
- psycopg、libpq/PGHOSTADDR、PostgreSQL-only config/tests/docs 从 active runtime 删除；
- 自动化测试不创建、替换或删除真实 `runtime-data/jobpilot.db`。

## Implementation evidence

Phase 2.5 已实现 default-path initialization、restart preservation、foreign keys、5000 ms busy timeout、hidden SQL parameters 与 Alembic temporary-file smoke test。真实 `runtime-data/jobpilot.db` 由 supported launcher 创建并保持 Git ignored；所有自动化数据库测试显式使用临时路径。
