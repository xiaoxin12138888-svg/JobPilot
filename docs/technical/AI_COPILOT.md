# AI Job Copilot 技术契约

## 范围

Phase 11 P0 包含岗位匹配、简历准备和面试准备。它是 Job Detail 中按需生成的辅助内容，不是聊天、
自动决策或自动操作。Phase 6 JD prompt/schema 与 Phase 7 Evidence Map prompt/schema 不变。

## 输入与隐私

- Match / Resume Advice：当前非 stale JD Analysis 的六类 requirement、Job title、用户明确选择的
  Resume Version 正文。
- Interview Prep：同一 Job 的当前 requirement 与 Application 下已有 Interview rounds/questions。
- email 与 phone 在 Provider data 构造前确定性删除；不发送 Profile、Application 状态、文件名或
  无关记录。
- Provider data 中每个 source 都带本地 ID，模型只能把它当作不可信文本。

## 输出契约

Match：`summary`、`strengths[]`、`gaps[]`、`suggestions[]`。strength 必须引用 RESUME；gap 必须引用
JOB。Resume Advice：`highlight[]` 引用 RESUME，`possibleImprovement[]` 是 AI 建议，
`interviewFocus[]` 引用 JOB。Interview Prep：`possibleQuestions[]` 分类固定为 PRODUCT、AI、PROJECT
并引用 JOB；有面试记录时 `review.strengths[]/weaknesses[]` 引用 INTERVIEW，`nextActions[]` 为建议。

Grounded item wire shape：

```json
{
  "text": "结论或准备方向",
  "sourceEvidence": {
    "text": "来源中的连续原文",
    "sourceType": "RESUME",
    "sourceId": "本地资源 ID"
  }
}
```

Source type 是 `RESUME | JOB | INTERVIEW`；INTERVIEW 仅用于复盘。所有字段 exact-key、长度和条数
有界。source type/id/quote 任一不匹配，本次结果以 `AI_INVALID_RESPONSE` 失败且不持久化。

## Persistence 与 stale

`copilot_records` 是 append-only。相同 context 重新生成会创建新 ID，GET context endpoint 返回最新
记录，GET `/api/v1/copilot/{id}` 可读取历史记录。API 根据当前最小 Provider data 重新计算 SHA-256
fingerprint；不同即 `isStale: true`。来源缺失、JD Analysis 缺失或 stale 时历史记录仍可读但 stale。

## UX

Job Detail 的 AI Copilot 区域含“岗位理解 / 匹配分析 / 简历准备 / 面试准备”。每个生成命令有独立
确认、loading、错误、重试和 stale 状态；请求进行中禁用重复点击。事实明确标为 `[来自简历]`、
`[来自岗位]` 或 `[来自面试]`，建议标为 `[AI建议]`，整个结果标记“AI 生成内容”。失败不清空上次
有效结果，也不阻塞原始岗位、简历、投递和面试数据。

## Security 与错误

沿用 loopback-only、exact Origin/Host/fetch metadata、JSON-only、no credentials、no redirect、no
system proxy 与脱敏错误。稳定错误包括 `AI_NOT_CONFIGURED`、`AI_TIMEOUT`、`AI_INVALID_RESPONSE`；
既有非 timeout transport failure 为 `AI_PROVIDER_UNAVAILABLE`。日志不得包含 source text、raw model
response、Provider URL 或 API Key。
