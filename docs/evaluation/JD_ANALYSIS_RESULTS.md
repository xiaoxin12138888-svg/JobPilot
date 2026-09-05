# JD 分析评测结果

## Prompt V1 真实运行

- 运行日期：2026-09-05
- 数据集：`dataset-v1.json`，版本 1，20 条人工审核完成的脱敏样本
- Prompt：v1（冻结，未修改）
- Schema：版本 1（冻结，未修改）
- Provider 模型：`[K12]gemini-3.5-flash`
- Temperature：0
- Provider timeout：60 秒
- 完成样本：20/20
- 原始评测记录：`jd-analysis/prompt-v1-run.json`

本次结果由冻结的 evaluator 对 validated result 进行确定性比较。除大小写和空白规范化外，
职责、硬性要求与加分项均按字符串集合精确比较；同一语义的拆分、合并或改写因此可能同时产生
一条 omission 和一条或多条 false extraction。这是冻结评分算法的既定行为，本次没有修改。

## 冻结 Evaluation Metrics

| 指标 | V1 真实结果 |
| --- | ---: |
| Schema Success | 20/20（100%） |
| Responsibilities Omissions | 4 |
| Responsibilities False Extractions | 8 |
| Must-have Omissions | 18 |
| Must-have False Extractions | 19 |
| Preferred Omissions | 16 |
| Preferred False Extractions | 16 |
| Must-have Misclassified as Preferred | 0 |
| Preferred Misclassified as Must-have | 0 |
| Evidence Grounding | 183/183（100%） |
| Unsupported Hallucination Count | 0 |

`skillsOmissions` 和 `skillsFalseExtractions` 保留在逐样本记录中，但不属于当前冻结的顶层聚合
指标，因此没有加入或改变正式评分。作为非评分诊断，20 条样本合计记录了 15 条 skills omission
和 53 条 skills false extraction。

## 延迟观察

| 统计项 | 真实结果 |
| --- | ---: |
| 最小值 | 10,969 ms |
| 中位数 | 14,561.5 ms |
| 平均值 | 15,275.3 ms |
| P95（nearest-rank） | 19,028 ms |
| 最大值 | 21,584 ms |
| 20 条总耗时 | 305,506 ms |

切换 Provider 后的单样本 Smoke Test 为 13,955 ms。Baseline 首条为全组最慢的 21,584 ms，
其余 19 条平均 14,943.3 ms；该序列与 Provider 侧都没有可验证的 cold-start 标志，因此只能记录
“首条较慢”，不能把差异确定归因为 cold start，也不能据此改变评测结果。

## 结论

- Schema、evidence grounding 与注入/福利等安全边界表现稳定。
- 精确文本忠实度仍有明显问题：条目粒度不一致、改写原文，以及加分项限定词丢失是主要来源。
- 学历/经验专用字段还存在负向描述和可选经历的边界问题；这些是人工复核发现，不追加到冻结指标。
- 真实案例、原因及只读的 Prompt V2 建议见 `JD_ANALYSIS_BAD_CASES.md`。
- Prompt V2 未创建、未修改、未运行；Phase 7 未进入。
