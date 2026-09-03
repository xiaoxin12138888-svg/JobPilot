# Architecture Decision Records

本目录保存会长期影响架构、公共契约、数据、安全或开发方式的决策。ADR 解释“为什么”，不替代产品规格、API contract 或实施计划。

## When to create an ADR

以下变更必须在实现前新增 ADR：

- 改变应用、模块、数据或部署边界；
- 改变本地优先、loopback、single-user 或 no-proxy 约束；
- 引入核心 runtime dependency、远程服务或数据出站；
- 改变公共 API、持久化或长期安全承诺；
- 推翻已经 Accepted 的决定。

## Numbering and status

- 文件名使用 `ADR-NNN-short-kebab-title.md`，编号只增不复用；
- `Proposed`：正在评审，不能作为实现依据；
- `Accepted`：已批准，后续实现必须遵守；
- `Superseded`：已被后续 ADR 取代；
- `Deprecated`：决定不再适用且没有直接替代。

## Historical checkpoint

ADR-008 完全取代了旧远程身份方向。ADR-006、ADR-007 及其实现/验证材料已按项目负责人指令从 active working tree 删除，避免误导当前产品；原始文件完整保存在 annotated tag `pre-local-first-cleanup`（commit `9a3e79a7e134142d800bf94a78ecafcad0cf9302`）。

缺少 006/007 文件是有意的，不表示编号可复用。Git history 是历史证据，当前目录只列仍有用的决定。

## Current records

- [ADR-001：采用 Monorepo 与模块化单体](ADR-001-monorepo.md) — Accepted
- [ADR-002：采用 FastAPI 与 PostgreSQL 作为后端基础](ADR-002-fastapi-postgresql.md) — Partially Superseded（PostgreSQL storage 由 ADR-009 取代；FastAPI 决定保留）
- [ADR-003：岗位采集必须由用户主动触发](ADR-003-user-triggered-job-capture.md) — Accepted
- [ADR-004：早期不引入 Agent Framework](ADR-004-no-early-agent-framework.md) — Accepted
- [ADR-005：采用 pnpm 与 uv 作为单一包管理工具链](ADR-005-pnpm-uv-toolchains.md) — Accepted
- [ADR-008：采用 Local-first Single-user 无认证架构](ADR-008-local-first-single-user-no-authentication.md) — Accepted
- [ADR-009：采用本地 SQLite 作为唯一 Runtime Database](ADR-009-local-sqlite-storage.md) — Accepted
- [ADR-010：Job 与 Application 领域基础](ADR-010-job-application-domain-foundation.md) — Accepted
- [ADR-011：BOSS 直聘当前岗位页主动采集](ADR-011-boss-direct-job-capture.md) — Accepted

当前 runtime storage 只能按 ADR-009 理解为 SQLite。ADR-002 标题和正文中的 PostgreSQL 是被保留的历史决策记录，不是兼容模式、安装要求或未来默认承诺。
