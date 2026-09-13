# AI Copilot 评测集

`dataset-v1.json` 包含 20 条完全虚构、无个人数据的 BOSS/牛客风格样本：8 条岗位匹配、6 条简历
准备和 6 条面试准备。它只包含评测所需的最小 Job sources、Resume 与 Interview 文本，不包含账号、
联系人、URL、Cookie、页面 HTML 或真实求职资料。

`evaluate_copilot.py` 只调用当前显式配置的真实 Provider，不含 canned output、mock result 或默认
分数。Provider 未配置时以退出码 2 停止，并且不创建输出文件。运行命令：

```text
uv run --project apps/api python apps/api/scripts/evaluate_copilot.py \
  --dataset docs/evaluation/copilot/dataset-v1.json \
  --output docs/evaluation/copilot/real-run.json
```

真实输出只记录模型名、Prompt/Schema 版本、timeout、逐样本 latency、通过严格产品 parser 后的
结构化结果和脱敏错误码；不记录 API Key、Provider URL/envelope 或无效 raw response。冻结的自动
指标包括：

- schema success；
- source type/id/quote 全部正确的 evidence grounding；
- unsupported evidence/hallucination count；
- gap 是否错误断言“用户不会/没有能力”；
- interview question 是否声称“一定会问/必问”。

summary、建议有用性和问题相关性仍需人工内容审核，runner 不用伪造分数代替人审。真实运行状态与
Bad Cases 见 `../COPILOT_RESULTS.md`。
