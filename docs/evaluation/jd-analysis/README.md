# JD 分析评测集

`dataset-v1.json` 包含 20 条写成真实 BOSS/牛客风格的合成脱敏 JD，不含账号数据、联系人、
Cookie、URL 或页面 HTML。每条样本包含人工审核的职责、硬性要求、加分项、技能、经验与学历
Gold 标签。

项目负责人已于 2026-09-05 完成逐条审核。数据集与每条样本的 `goldReviewStatus` 均为
`human-reviewed`，`reviewedSampleCount` 为 20；`GOLD_REVIEW_PACK.md` 保存中文审核包和历史。
Evaluator 会校验这三类信号，部分审核或只修改顶层状态时会阻止运行。

## Prompt V1 真实产物

`prompt-v1-run.json` 是冻结 Prompt V1 在同一 20 条数据集上的真实 Provider 运行记录，包含：

- 数据集、Prompt、Schema、模型、temperature 和 timeout 版本信息；
- 20/20 validated structured results；
- 每条样本 latency；
- 冻结的聚合指标与逐样本 exact-match 差异；
- 不包含 API Key、Provider envelope 或无效 raw response。

从仓库根目录执行相同 runner 的命令为：

```text
uv run --project apps/api python apps/api/scripts/evaluate_jd_analysis.py \
  --dataset docs/evaluation/jd-analysis/dataset-v1.json \
  --output docs/evaluation/jd-analysis/prompt-v1-run.json
```

Runner 使用产品同一份 Prompt V1 和 Provider adapter。文本比较只做空白/大小写规范化后
exact-match；`unsupportedHallucinationCount` 则保守统计模型 evidence 是否为规范化 JD 的原文
子串。Schema failure 与 evidence 不支持分别统计。

V1 正式指标见 `../JD_ANALYSIS_RESULTS.md`，真实 Bad Cases 与尚未实施的 V2 建议见
`../JD_ANALYSIS_BAD_CASES.md`。Prompt V2 必须经过项目负责人后续批准；本次没有创建、修改或
运行 V2，也没有进入 Phase 7。
