# Factual Feedback Loop V1

## Purpose and boundary

`GET /api/v1/feedback-summary` 为本机求职复盘提供可追溯事实。它在请求时直接聚合 SQLite，
不保存 Feedback/Insight/Analytics/Event 行，不调用 Provider，不读取 Resume content，也不返回
AI 评分、建议、预测或因果结论。

## Facts

Totals 包含：

- saved Jobs；
- Applications；
- 至少有一轮 InterviewRound 的不同 Applications；
- InterviewRounds 与 InterviewQuestions；
- 当前 status 为 Offer 或 rejected 的 Applications。

其他分组包括题目 category、自评 performance、淘汰原因、未记录淘汰原因、Resume Version 与 Job
source。简历版本和来源组只报告 Applications、interview Applications 与 offers 数量，不比较优劣。

## Deterministic rules

漏斗固定为：

```text
SAVED_JOBS -> APPLICATIONS -> INTERVIEW_APPLICATIONS -> OFFERS
```

每个 `conversionRate` 使用紧邻前一阶段 count 为分母。首阶段 rate 为 null；分母为零时为 null。
如果缺少中间事实导致后一阶段 count 大于前一阶段，rate 也为 null。原始 counts 永不截断、补齐或
反推，Web 不显示 0% 假象或超过 100% 的误导结果。

弱项只把 `OK + POOR` 计入 `weakCount`，忽略 `GOOD` 与 `NOT_SURE`。只返回 weakCount 大于零的
分类，排序依次为 weakCount 降序、questionCount 降序、固定 enum 顺序。所有规则均在 domain 中
确定性执行，不由 UI 或模型解释。

## UX

`?view=feedback` 提供 loading、error/retry、empty 与 populated 状态。页面明确说明数据来自本机
记录且不包含 AI 评分或建议。统计卡、漏斗、分类、自评、弱项、淘汰原因、简历版本和来源在
320/768/1024/1440 下保持可读；表格只在自身容器内滚动，不制造页面横向溢出。

## Privacy and failure

聚合查询只读取计数、枚举、Resume Version 名称和 Job source，不读取问题/回答/复盘正文或简历
正文。Provider 未配置、不可达或失败均不影响本 endpoint。数据库 busy、统一 request ID 与脱敏
错误语义沿用现有 API 边界。
