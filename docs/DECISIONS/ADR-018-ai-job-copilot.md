# ADR-018：基于本地求职上下文的可选 AI Copilot

- Status: Accepted
- Date: 2026-09-09

## Context

JobPilot 已保存 Job、结构化 JD Analysis、Resume Version、Application 与 Interview Record。用户需要
围绕一个岗位理解自身证据、准备简历表达和面试，而不是一个脱离本地数据的聊天机器人。简历和
面试文本属于私密、不可信输入；模型输出也不能直接作为事实。

## Decision

1. Phase 11 只实现三个用户触发的 P0 command：Job Match、Resume Advice、Interview Prep。求职策略
   是 P1，本阶段不实现；不引入 Chat Agent、长期记忆、自动行动、RAG、Embedding、向量库或 Agent
   framework。
2. 继续复用 Phase 6 OpenAI-compatible Provider 与三个 `JOBPILOT_LLM_*` 环境变量。AI 未配置时
   本地 Job、Resume、Application、Interview 等功能保持可用。
3. 三个 POST 都要求 `confirmExternalAi: true`。Match/Resume Advice 还要求明确的
   `resumeVersionId`；Interview Prep 使用当前 Job 的现有 Interview rounds，不自动创建或修改任何
   业务数据。
4. Provider 输入只包含当前非 stale 的结构化岗位条件、必要的岗位标题，以及对应功能所需的简历
   或面试文本。发送前删除 email 和 phone；不发送 Profile、Application 状态、原始文件、联系方式
   或其他无关字段。JD、Resume、Interview 全部放在明确的不可信 data envelope 中。
5. Match 的 strengths 只接受 Resume quote，gaps 只接受 Job requirement quote；Resume Advice 的
   highlight 只接受 Resume quote，interviewFocus 只接受 Job quote；Interview questions 只接受 Job
   quote，复盘 strengths/weaknesses 只接受 Interview quote。`sourceId` 必须等于实际来源 ID，quote
   经空白标准化后必须存在于该次发送的来源。任何不满足条件的生成结果整体返回
   `AI_INVALID_RESPONSE`，不会写入数据库。
6. gap 文案必须使用“当前资料/当前简历未发现……”语义，不得断言用户不会或没有能力；面试区域
   固定显示“可能关注方向”，不得声称面试官一定会问；建议不得新增用户经历、指标或事实。
7. 使用一个 `copilot_records` 表保存 append-only 结果：`id`、Job/Resume 上下文 ID、kind、schema
   version、result JSON、input fingerprint、model、prompt version 和 created time。每次重新生成新增
   记录；失败不覆盖旧记录。JD/Resume/Interview 输入变化时旧记录计算为 stale，但不自动删除。
8. 公开 API 为：
   - `GET|POST /api/v1/jobs/{jobId}/copilot/match`
   - `GET|POST /api/v1/jobs/{jobId}/copilot/resume-advice`
   - `GET|POST /api/v1/jobs/{jobId}/copilot/interview-prep`
   - `GET /api/v1/copilot/{id}`
9. GET 返回对应上下文最新记录；POST 返回新记录。Provider 未配置、超时、响应无效分别保留稳定
   `AI_NOT_CONFIGURED`、`AI_TIMEOUT`、`AI_INVALID_RESPONSE`；其他既有 sanitized transport failure
   继续使用 `AI_PROVIDER_UNAVAILABLE`。
10. loopback、exact Host/Origin/fetch metadata、JSON-only mutation、no credentials、redirect rejection、
    no system proxy、响应大小限制、无 raw Provider response 与 content-free logging 全部沿用。

## Consequences

- 追加式记录比 upsert 多占少量 SQLite 空间，但能真实保留重新生成历史和 stale 状态。
- 严格 quote grounding 会拒绝部分语义合理但无法追溯的模型输出；这是避免虚构的有意取舍。
- Phase 11 不是自动决策系统，不产生匹配分、Offer 概率，也不改变 Job/Application/Resume/Interview。
