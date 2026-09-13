# AI Copilot Evaluation Results

## 当前状态

- Dataset：20 条 synthetic samples，PASS
- Provider configured in evaluation terminal：NO
- Real Provider run：NOT RUN
- Human content review：NOT RUN
- Real BOSS / Nowcoder acceptance：NOT RUN

2026-09-13 的评测终端未配置 `JOBPILOT_LLM_BASE_URL`、`JOBPILOT_LLM_API_KEY` 与
`JOBPILOT_LLM_MODEL` 的完整组合。为遵守“真实输出才可计分”，本文件不填写模型、latency、成功率
或内容质量分数，也不把 API 进程中可能存在的环境变量复制到评测终端。

## 冻结指标

| 指标 | 结果 |
| --- | --- |
| Schema success | NOT RUN |
| Evidence grounding | NOT RUN |
| Unsupported hallucination count | NOT RUN |
| Gap language violations | NOT RUN |
| Interview certainty violations | NOT RUN |
| Summary / suggestion / question human review | NOT RUN |

## 技术验收记录（非内容评测）

- Python：274/274 PASS；其中 migration/Copilot 隔离复核 19/19 PASS。
- API client：69/69 PASS；Web：62/62 PASS；Extension：112/112 PASS。
- TypeScript typecheck、ESLint、Prettier、Ruff、API import、Web build、Extension build 与 Extension
  artifact security gate：PASS。
- 真实 Chrome 使用隔离临时 SQLite 与虚构 Job/Resume，依次检查岗位理解、匹配分析、简历准备、
  面试准备；Provider 未配置提示和核心功能降级正常。未触发任何 AI POST。
- Chrome console warning/error：0；请求 320/768/1024/1440 四档 viewport 后，页面和 Copilot
  tabs 均无横向 overflow，临时 viewport 已恢复。
- 五轴代码审查：Critical 0 / Required 0。审查中发现的 stale 历史结果可读性、runner 异常字段
  健壮性、ESM 开发启动路径与 React effect 状态问题均已修复并有回归验证。

## Bad Cases

当前没有真实 Provider 输出，因此没有伪造“真实 Bad Case”。产品 parser 与自动化回归已覆盖以下
预注册失败类别：

- BC-01：strength 使用简历中不存在的 quote → `AI_INVALID_RESPONSE`；
- BC-02：gap 写成“用户不会/没有能力”而非“当前资料未发现” → `AI_INVALID_RESPONSE`；
- BC-03：以不存在的经历作为 grounded evidence → `AI_INVALID_RESPONSE`；无 evidence 的建议仍
  必须由真实输出人审确认没有把建议写成既有事实；
- BC-04：问题写成“一定会问/必问/面试官会问” → `AI_INVALID_RESPONSE`。

真实 run 完成后，只能根据 `real-run.json` 中的实际结果补充样本 ID、原因和人工结论。
完整状态见 [COPILOT_BAD_CASES.md](COPILOT_BAD_CASES.md)。

## 阻断项

Phase 11 不能标记 PASS，直到同一冻结 Prompt/Schema 完成 20 条真实 Provider 输出评测，并由项目
负责人分别确认真实 BOSS 与牛客岗位的匹配、简历建议和面试准备内容。不得因此进入 Phase 12。

当前人工门禁：`USER ACTION REQUIRED — CONFIGURE PROVIDER, RUN FROZEN 20-SAMPLE EVALUATION,
AND REVIEW REAL BOSS/NOWCODER OUTPUTS`。
