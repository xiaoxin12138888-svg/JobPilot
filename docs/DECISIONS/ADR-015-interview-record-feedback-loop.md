# ADR-015：本地面试记录与事实反馈闭环

- **Status**：Accepted
- **Date**：2026-09-06
- **Decision owner**：JobPilot 项目负责人

## Context

JobPilot 已能保存岗位、投递和实际使用的简历版本，但 Application 进入面试后没有轮次、真实题目、
手动复盘与结果原因的可追溯记录。Phase 7 的 Evidence Map 已实现但语义验收因外部 Provider 延迟而
暂停；负责人决定不继续阻塞本地产品闭环，并批准一个完全不依赖 AI 的独立 Phase 8。

## Decision

1. 新增 `InterviewRound` 与 `InterviewQuestion` 两个本地实体。一个 Application 有 0~N 轮面试，
   一轮有 0~N 道实际题目；不创建通用 Feedback/Insight/Analytics/Event 表。
2. Round 类型固定为 `PHONE|VIDEO|ONSITE|OTHER`，状态固定为
   `PLANNED|COMPLETED|CANCELLED`。创建、完成或取消 Round 不自动改变 Application 状态或结果。
3. Round 保存名称、可选时间、面试官备注，以及用户手填的做得好、需改进、需学习和其他备注。
   Question 保存实际问题、七类手选 category、用户自己的回答摘要、四档自评和可选备注。
4. Application 只增加 nullable `outcome_note` 与 `rejection_reason`。`outcome_note` 同时承载最小
   Offer 说明；不建立第二套 Outcome/Offer 状态机。淘汰原因是用户记录，不是系统判断。
5. Round 删除级联 Question；Application 删除级联 Round/Question；Job 的现有 Application cascade
   继续生效。Web 在删除 Round 前明确确认。无软删除、历史事件或自动状态同步。
6. API 使用现有 camelCase、统一错误信封、分页、loopback/Host/Origin/Fetch Metadata 与 JSON-only
   写入边界。面试内容不得进入日志、telemetry、Extension、Git 或真实测试 fixture。
7. Feedback Summary 在请求时直接查询现有 SQLite，返回事实 counts、funnel、题型、自评、拒绝
   原因、来源和简历版本分组；不持久化派生结果，不调用 Provider，不产生评分、推荐或因果结论。
8. 面试岗位数定义为“至少有一轮 InterviewRound 的不同 Application 数”。Funnel 为保存岗位、
   Application、面试岗位、当前 Offer；相邻阶段分母为零时 rate 为 null，Web 不展示 0% 假象。
   如果用户漏记中间阶段，导致后一阶段事实数量大于前一阶段，rate 同样为 null；各阶段原始数量
   保持不变，不显示超过 100% 的误导转化率，也不截断或推断缺失记录。
9. 高频薄弱类别只按 `OK + POOR` 计数，按弱项数、该类总题数和固定 enum 顺序确定性排序。
10. 整个功能在所有 `JOBPILOT_LLM_*` 未配置时完整工作。Phase 6/7 Provider、Prompt、Schema、Gold
    Dataset 和评测算法不变；Phase 7 保持 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。

## Consequences

- 用户可以把真实面试事实、本人的回答与复盘留在本机，并从投递、来源和简历版本维度查看可追溯
  数量，为以后另行批准的策略分析打基础。
- 统计只描述已有样本；缺少数据时显示引导文案，不展示误导性成功率。
- Phase 8 不实现 AI 总结、AI 评分、Mock Interview、RAG/Embedding、Agent、录音/转写、日历同步、
  自动答案、自动投递或新的招聘平台。
