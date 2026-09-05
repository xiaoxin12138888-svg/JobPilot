# JD 分析评测集

`dataset-v1.json` 包含 20 条写成真实 BOSS/牛客风格的合成脱敏 JD，不含账号数据、联系人、
Cookie、URL 或页面 HTML。每条样本包含人工审核的职责、硬性要求、加分项、技能、经验与学历
Gold 标签。

项目负责人已于 2026-09-05 完成逐条审核。数据集与每条样本的 `goldReviewStatus` 均为
`human-reviewed`，`reviewedSampleCount` 为 20；`GOLD_REVIEW_PACK.md` 保存中文审核包和历史。
Evaluator 会校验这三类信号，部分审核或只修改顶层状态时会阻止运行。

## Prompt V1/V2 真实产物

`prompt-v1-run.json` 与 `prompt-v2-run.json` 是冻结 Prompt V1/V2 在同一 20 条数据集上的
各一轮真实 Provider 运行记录，包含：

- 数据集、Prompt、Schema、模型、temperature 和 timeout 版本信息；
- 20/20 validated structured results；
- 每条样本 latency；
- 冻结的聚合指标与逐样本 exact-match 差异；
- 不包含 API Key、Provider envelope 或无效 raw response。

Runner 要求显式选择 Prompt 版本。V1 的可复现命令为：

```text
uv run --project apps/api python apps/api/scripts/evaluate_jd_analysis.py \
  --dataset docs/evaluation/jd-analysis/dataset-v1.json \
  --output docs/evaluation/jd-analysis/prompt-v1-run.json \
  --prompt-version v1
```

Runner 使用产品对应版本的 Prompt 和同一个 Provider adapter。文本比较只做空白/大小写规范化后
exact-match；`unsupportedHallucinationCount` 则保守统计模型 evidence 是否为规范化 JD 的原文
子串。Schema failure 与 evidence 不支持分别统计。

V1/V2 完整指标见 `../JD_ANALYSIS_RESULTS.md`，真实 Bad Cases 与逐项回归见
`../JD_ANALYSIS_BAD_CASES.md`。V2 仍有已记录错误，本轮不会自动创建 Prompt V3；真实 BOSS
和 Nowcoder Job AI 内容质量需由项目负责人确认，Phase 7 尚未进入。
