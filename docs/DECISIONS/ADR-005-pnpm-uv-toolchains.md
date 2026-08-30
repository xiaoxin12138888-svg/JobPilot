# ADR-005：采用 pnpm 与 uv 作为单一包管理工具链

- **Status**：Accepted
- **Date**：2026-08-30

## Context

JobPilot monorepo 同时包含多个 TypeScript workspace 与一个 Python API。Phase 1 需要可复现安装、锁文件和清晰根级命令，同时必须避免 npm/Yarn/pnpm 或 pip/Poetry/uv 多套方案并存。

## Decision

- TypeScript workspace 统一使用 pnpm，并提交根级 `pnpm-lock.yaml`。
- Python API 统一使用 uv，并提交 `apps/api/uv.lock`；不提交 requirements、Poetry 或 Pipenv 锁文件。
- TypeScript 使用 strict mode；ESLint 与 Prettier 负责静态规范，Vitest 负责测试。
- Python 使用 Ruff 同时承担 lint 与 format，Pytest 负责测试；不重复引入 Black 或 isort。
- Phase 1 Python 代码极少，暂不引入 mypy。领域逻辑和跨模块类型边界出现后再依据实际收益评估。
- 不引入 Turborepo、Nx 或其他任务运行器；根级 pnpm scripts 足以协调当前命令。

## Consequences

- 两个生态各自只有一套安装和锁定路径，新开发者能够复现已验证版本。
- pnpm workspace 支持 Web、Extension 与共享包的原子演进，uv 为 API 提供隔离虚拟环境。
- 贡献者需要安装 pnpm 与 uv，但无需维护重复的格式化或依赖配置。
- 若未来工具无法满足有证据的需求，应通过新 ADR 评估替代，而不是并行加入第二套方案。

