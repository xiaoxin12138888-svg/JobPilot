# ADR-004：早期不引入 Agent Framework

- **Status**：Accepted
- **Date**：2026-08-30

## Context

JobPilot 后续需要 JD 分析、简历匹配、面试评估和模拟面试。早期需求主要是边界清晰的单次结构化任务与可审计 workflow；目前没有动态工具选择、多智能体协作或复杂循环规划的证据。

## Decision

- 使用 application service 调用职责单一的 AI ports：`JDAnalyzer`、`ResumeMatcher`、`InterviewEvaluator`。
- Provider adapter 负责具体 LLM API；返回结果必须使用版本化 schema 校验并映射为领域结果。
- 模拟面试优先使用显式 workflow/state machine，明确状态、转移、重试和人工确认点。
- Phase 0 不实现 AI，不引入 LangGraph 或其他 Agent Framework。
- 只有当显式 workflow 出现可量化且持续的编排痛点时，才通过新 ADR 评估框架。

## Consequences

- prompt、provider 与业务规则解耦，失败更容易测试和定位。
- Structured Output 和校验会增加少量显式代码，但能阻止无效模型输出污染领域数据。
- 早期少一些“自动自治”能力，但换来可预测性、成本控制和审计能力。
- 如果未来确需复杂动态编排，迁移需要适配现有 ports；稳定业务契约不应随框架改变。

