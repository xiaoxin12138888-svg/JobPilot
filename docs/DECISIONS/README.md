# Architecture Decision Records

本目录保存 JobPilot 的 Architecture Decision Record（ADR），用于记录会长期影响架构、公共契约、数据、安全或开发方式的关键取舍。ADR 解释“为什么这样决定”，不替代产品规格、API 契约或实施文档。

## 何时创建 ADR

以下变更在实现前必须新增或更新 ADR：

- 改变应用、模块或部署边界；
- 改变数据库、对象存储、AI Provider 或关键基础设施策略；
- 引入核心依赖、Agent Framework 或跨语言代码生成；
- 对公共 API、认证、安全或数据保留作出长期承诺；
- 推翻已经 Accepted 的架构决定。

普通 bug 修复、局部实现细节和不影响长期边界的小重构不需要 ADR。

## 编号与状态

- 文件名：`ADR-NNN-short-kebab-title.md`，编号只增不复用。
- `Proposed`：正在评审，不能作为已批准实现依据。
- `Accepted`：已批准，后续实现必须遵守。
- `Superseded`：已被新 ADR 取代；旧文件保留并链接新编号。
- `Deprecated`：决定不再适用，但没有直接替代方案。

Accepted ADR 不应静默改写其历史结论。若事实变化，应新增 ADR，并把旧记录标为 Superseded。

## 最小模板

```markdown
# ADR-NNN：标题

- **Status**：Proposed
- **Date**：YYYY-MM-DD

## Context

需要解决的问题、约束和证据。

## Decision

选择的方案及明确边界。

## Consequences

正面影响、成本、风险和重新评估条件。
```

## 当前记录

- [ADR-001：采用 Monorepo 与模块化单体](ADR-001-monorepo.md) — Accepted
- [ADR-002：采用 FastAPI 与 PostgreSQL 作为后端基础](ADR-002-fastapi-postgresql.md) — Accepted
- [ADR-003：岗位采集必须由用户主动触发](ADR-003-user-triggered-job-capture.md) — Accepted
- [ADR-004：早期不引入 Agent Framework](ADR-004-no-early-agent-framework.md) — Accepted
- [ADR-005：采用 pnpm 与 uv 作为单一包管理工具链](ADR-005-pnpm-uv-toolchains.md) — Accepted
- [ADR-006：采用托管 OIDC 身份与双通道会话](ADR-006-authentication-strategy.md) — Accepted
- [ADR-007：以中国大陆普通网络可用性重选生产身份供应商](ADR-007-mainland-china-identity-provider.md) — Accepted (Provider Direction; production readiness and migration not authorized)
