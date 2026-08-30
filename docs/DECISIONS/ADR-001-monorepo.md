# ADR-001：采用 Monorepo 与模块化单体

- **Status**：Accepted
- **Date**：2026-08-30

## Context

JobPilot 包含 React Web、Chrome Extension、FastAPI API 和少量跨 TypeScript 客户端契约。项目由小团队持续迭代，需要明确边界、统一评审与测试，又没有独立部署多个后端服务的现实需求。

## Decision

采用一个独立 monorepo。目标结构为：

```text
apps/
  web/
  extension/
  api/
packages/
  shared-types/
  api-client/
docs/
tests/
infra/
```

后端采用按业务能力划分的模块化单体。只有 Web 与 Extension 确实共享的稳定 TypeScript 契约进入 `shared-types`；统一 API 调用能力进入 `api-client`。Phase 0 不创建这些空目录。

## Consequences

- 产品、契约和测试可以原子演进，跨端变更更容易审查。
- Web 与 Extension 能共享少量稳定类型，避免各自定义业务状态。
- Python 与 TypeScript 仍存在语言边界，需要契约测试控制漂移。
- 多工具链会增加根级命令设计成本，但低于多仓库协调成本。
- 不因采用 monorepo 而允许跨模块任意导入；模块边界仍由依赖规则和评审保证。
- 若未来出现独立扩缩容、隔离或团队所有权证据，再用新 ADR 评估服务拆分。
