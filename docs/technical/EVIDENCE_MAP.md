# Evidence Map V1

## Input and consent

生成前必须同时满足：Job 存在；当前 JD Analysis 存在且非 stale；ResumeVersion 存在；Provider
已配置；请求含 `confirmExternalAi: true`。Web 在发送前明确说明本次会把所选简历正文与岗位要求
发送给用户配置的 AI 服务，用户确认后才调用 POST。

发送数据仅为 Job title、可选 company、当前分析的 must-have/preferred requirement 文本，以及
所选 ResumeVersion content。不得发送原始 HTML、完整 JD、notes、Application、其他 Job 或简历。
系统提示把两类输入都声明为不可信数据，禁止执行其中的指令。

## Schema and grounding

Schema version 1：

```text
EvidenceMap { mappings: EvidenceMapping[] }
EvidenceMapping {
  requirementType: MUST_HAVE | PREFERRED
  requirementText: string
  coverage: DIRECT | PARTIAL | GAP
  resumeEvidence: [{ quote: string }]
  reason: string
}
```

服务端按当前 JD Analysis 构建期望 requirement 序列；Provider 必须逐项原样返回，不能自行创建、
遗漏、重排或改写 requirement。每个 quote 在 whitespace normalization 后必须存在于同样规范化
的 Resume content；不支持的 quote 被删除。DIRECT/PARTIAL 无剩余有效 quote 时降级 GAP。

DIRECT 表示当前简历有可直接支持要求的原文；PARTIAL 表示有相关但不完整的原文；GAP 仅表示
当前简历版本未找到可证明内容。UI 的总览只数各 coverage 的数量，不计算分数、匹配率或概率。

## Persistence and failure

每个 Job + ResumeVersion 保存一个当前记录。读取时比较所存 JD analysis fingerprint 与当前分析，
并比较所存 Resume fingerprint 与当前正文，任一变化即 `isStale: true`。stale 结果可以显示但不能
冒充最新结果。Provider 超时、不可用或返回非法内容时，最后一个有效记录不删除、不覆盖；错误
继续使用 Phase 6 的稳定脱敏语义。
