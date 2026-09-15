# AI Copilot 评测集

`dataset-v1.json` 包含 20 条完全虚构、无个人数据的 BOSS/牛客风格样本：8 条岗位匹配、6 条简历
准备和 6 条面试准备。它只包含评测所需的最小 Job sources、Resume 与 Interview 文本，不包含账号、
联系人、URL、Cookie、页面 HTML 或真实求职资料。

`evaluate_copilot.py` 只调用当前显式配置的真实 Provider，不含 canned output、mock result 或默认
分数。Provider 未配置时以退出码 2 停止，并且不创建输出文件。V2 必须先运行固定的
Match / Resume Advice / Interview Prep 三样本预检：

```text
uv run --project apps/api python apps/api/scripts/evaluate_copilot.py \
  --dataset docs/evaluation/copilot/dataset-v1.json \
  --preflight \
  --output docs/evaluation/copilot/v2-preflight.json
```

只有 `preflightPassed: true` 后才能运行 20 条 V2：

```text
uv run --project apps/api python apps/api/scripts/evaluate_copilot.py \
  --dataset docs/evaluation/copilot/dataset-v1.json \
  --preflight-from docs/evaluation/copilot/v2-preflight.json \
  --output docs/evaluation/copilot/v2-real-run.json
```

每个样本首轮结构验证失败时，最多向同一 Provider 发送一次仅修复结构的请求；超时、传输失败或
第二次仍无效时立即停止该样本，不进行第三次请求。真实输出只记录模型名、Prompt/Schema 版本、timeout、
首轮/总 latency、retry 次数、通过严格产品 parser 后的结构化结果和脱敏错误码；不记录 API Key、
Provider URL/envelope 或无效 raw response。自动指标包括：

- first-pass / final schema success；
- repair usage；
- source type/id/quote 全部正确的 evidence grounding；
- unsupported evidence/hallucination count；
- gap 是否错误断言“用户不会/没有能力”；
- interview question 是否声称“一定会问/必问”；
- 建议是否要求编造简历经历；
- 非 AI 岗位是否被错误归为 AI 面试类别。

summary、建议有用性和问题相关性仍需人工内容审核，runner 不用伪造分数代替人审。真实运行状态与
Bad Cases 见 `../COPILOT_RESULTS.md`。

## V1 failure diagnostic replay

Phase 11.1 的定向诊断模式从冻结 V1 run 自动选择 `AI_INVALID_RESPONSE` 样本，仍使用 V1 Prompt，
不会覆盖 baseline，也不会持久化 Provider 原文或有效结果正文。它只记录 A–H failure type、预期
Schema、脱敏后的字段类型形状、validator issue 与 latency：

```text
uv run --project apps/api python apps/api/scripts/evaluate_copilot.py \
  --dataset docs/evaluation/copilot/dataset-v1.json \
  --diagnose-failures-from docs/evaluation/copilot/real-run.json \
  --output docs/evaluation/copilot/v1-failure-diagnostics.json
```

必须在与 V1 相同的已配置 Provider 终端中执行。该文件只用于编写
`../COPILOT_V1_FAILURE_ANALYSIS.md`；在七条真实分类完成前不得修改 V2 Prompt 或 Schema。
