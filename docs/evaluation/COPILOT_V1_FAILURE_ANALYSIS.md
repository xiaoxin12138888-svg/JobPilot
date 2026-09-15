# Copilot V1 Provider Failure Analysis

## Scope and provenance

- Baseline：`docs/evaluation/copilot/real-run.json`，dataset v1，20 synthetic samples。
- Provider：`[K12]gemini-3.5-flash`，temperature 0，timeout 60 seconds。
- Frozen Prompt：`match-v1`、`resume-advice-v1`、`interview-prep-v1`。
- Diagnostic replay：2026-09-15，仅重放 baseline 中七个 `AI_INVALID_RESPONSE`，每条一次。
- Privacy：只持久化 failure type、预期 Schema、字段类型 shape、validator issue 与 latency；没有持久化
  Provider 原文、Provider URL、API Key 或有效结果正文。

V1 原始 invalid response 按既有安全策略没有落盘，因此无法事后恢复第一次运行的逐字段错误。以下
分类来自同一 Provider、同一 V1 Prompt、同一 synthetic input 的单次 diagnostic replay；其中未复现
项必须明确标记，不能把 replay 结果伪装成第一次运行的原文。

## Classification summary

| Failure type | Count | Samples |
| --- | ---: | --- |
| A. Non JSON | 0 | — |
| B. Markdown code fence | 0 | — |
| C. Missing field | 0 | — |
| D. Wrong field type | 5 | 009, 010, 011, 012, 019 |
| E. Invalid enum | 0 | — |
| F. Evidence structure | 1 | 017 |
| G. Truncated output | 0 | — |
| H. Other | 0 | — |
| Failure not reproduced | 1 | 014 |

所有七次 replay 都在 60 秒内收到 Provider 内容。`response_format: {"type":"json_object"}` 对当前
Provider 至少能稳定得到 JSON object，但没有保证字段元素类型或 Evidence 内容满足产品 Schema；它
不是 JSON Schema enforcement 的证据。

## copilot-009

- **Feature**：Resume Advice；交互设计师 synthetic sample。
- **Failure Type**：D — Wrong field type。
- **Expected Schema**：`highlight: GroundedItem[]`、`possibleImprovement: string[]`、
  `interviewFocus: GroundedItem[]`。
- **Actual Shape**：三个顶层字段都是 array；`possibleImprovement` 的元素不是 string。
- **Root Cause**：V1 示例只写 `"possibleImprovement":[]`，没有显式声明 array item type。Provider
  选择了结构化 item，而产品 parser 只接受可直接展示的行动建议字符串。
- **Candidate Fix**：Resume Advice V2 明确 `possibleImprovement` 必须是 JSON string array，提供一个
  字符串示例；首次错误时只发送 validator issue 做一次结构修复，不在代码中静默提取或补写语义。

## copilot-010

- **Feature**：Resume Advice；科技内容运营实习生 synthetic sample。
- **Failure Type**：D — Wrong field type。
- **Expected Schema**：同 copilot-009。
- **Actual Shape**：三个顶层字段都是 array；`possibleImprovement` 的元素不是 string。
- **Root Cause**：与 copilot-009 相同，且跨岗位重复，说明这是 Prompt/输出契约的系统性歧义，不是
  单一输入异常。
- **Candidate Fix**：采用同一通用 Resume Advice V2 string-array 契约，不做 sample-specific 指令。

## copilot-011

- **Feature**：Resume Advice；嵌入式软件工程师 synthetic sample。
- **Failure Type**：D — Wrong field type。
- **Expected Schema**：同 copilot-009。
- **Actual Shape**：三个顶层字段都是 array；`possibleImprovement` 的元素不是 string。
- **Root Cause**：与 copilot-009 相同；技术岗位同样触发，进一步排除职位领域特例。
- **Candidate Fix**：同一 V2 item-type 指令与一次结构修复；Evidence 要求不变。

## copilot-012

- **Feature**：Resume Advice；医学事务专员 synthetic sample。
- **Failure Type**：D — Wrong field type。
- **Expected Schema**：同 copilot-009。
- **Actual Shape**：三个顶层字段都是 array；`possibleImprovement` 的元素不是 string。
- **Root Cause**：与 copilot-009 相同；四个不同领域连续重现，确认为 V1 contract ambiguity。
- **Candidate Fix**：同一 V2 item-type 指令；不需要为此改变产品语义或放宽 parser。

## copilot-014

- **Feature**：Resume Advice；经营分析专员 synthetic sample。
- **Failure Type**：Failure not reproduced。
- **Expected Schema**：同 copilot-009。
- **Actual Shape**：三个顶层字段都是 array，并通过冻结 V1 parser。
- **Root Cause**：第一次 invalid raw response 未保存，本轮无法复现，因此根因不可证明。事实只支持
  “当前 Provider 在相同 temperature 0 输入下仍可能产生非确定性结构结果”。
- **Candidate Fix**：V2 提高字段类型明确度并记录 first-pass/final 指标；若 first pass 失败，允许一次
  结构修复。不得为该样本硬编码，也不得把本轮通过回写为 V1 baseline PASS。

## copilot-017

- **Feature**：Interview Prep；安全运营工程师 synthetic sample，JD 只有安全告警/事件响应、Web
  攻击与 Linux 要求。
- **Failure Type**：F — Evidence structure。
- **Expected Schema**：`possibleQuestions: Question[]`；每题必须有 non-empty JOB Evidence；review
  strengths/weaknesses 使用 INTERVIEW Evidence，`nextActions: string[]`。
- **Actual Shape**：顶层结构正确，但 `possibleQuestions[1].sourceEvidence` 至少一个字段为空。
- **Root Cause**：直接原因是必填 Evidence 为空。V1 同时强制 PRODUCT/AI/PROJECT 三类，而该非 AI
  安全岗位没有支持 AI 类问题的 JD source，这一不匹配很可能诱发空 Evidence；由于未保存正文，不能
  进一步断言空的是哪一个字段或问题类别。
- **Candidate Fix**：Interview Prep V2 按 JD 选择小而稳定的 category enum，不强制 AI；Prompt 显式
  提供 `ALLOWED_SOURCE_IDS`，要求只复制对应 JOB source 的连续原文。Validator 继续 fail closed。

## copilot-019

- **Feature**：Interview Prep；产品经理实习生 synthetic sample。
- **Failure Type**：D — Wrong field type。
- **Expected Schema**：同 copilot-017。
- **Actual Shape**：顶层 `possibleQuestions` array 与 `review` object 正确；`review.nextActions` 的元素
  不是 string。
- **Root Cause**：V1 示例只写 `"nextActions":[]`，没有显式声明 item type，和 Resume Advice 的
  `possibleImprovement` 歧义同源。
- **Candidate Fix**：Interview Prep V2 明确 `nextActions` 是 string array 并给出字符串示例；不在
  parser 中自动抽取对象字段或生成缺失行动。

## Resume Advice schema decision

当前 Resume Advice 产品需要的三个概念足够简单：已有简历亮点、行动建议、岗位面试关注点。四个
重现失败都发生在 string-array item type，而不是顶层嵌套过深、缺字段或 Evidence ownership 冲突。
因此暂不简化产品 Schema；优先修 Prompt 的类型歧义并增加一次结构修复。若 V2 preflight 仍不能稳定
输出，再用真实证据重新评估 Schema，不为技术美观提前改动。

## BC-06 unsupported evidence attribution

V1 baseline 只保存聚合 `69/70`，没有保存逐样本 evidence count 或 invalid raw response，所以现有
证据无法定位第一次运行中的唯一 unsupported evidence。Diagnostic replay 新发现 copilot-017 有一条
空 Evidence，但不能证明它就是 V1 baseline 的同一条。V2 evaluator 必须记录每个 sample 的
`provided/grounded` 数量和脱敏 failure path，才能在不保存正文的前提下完成归因。

## V2 direction approved by evidence

1. 三个独立 V2 Prompt 都明确 `RETURN JSON ONLY`、禁止 Markdown/code fence/解释、列出严格字段名与
   字段类型。
2. Resume Advice 和 Interview Prep 明确所有 string-array item type；不通过 parser coercion 放宽。
3. Prompt 显式提供 allowed source IDs；source ownership、ID existence 与 quote grounding继续严格。
4. Interview category 由 JD 决定，不再强制非 AI 岗位生成 AI 问题。
5. Suggestion 必须使用条件句区分“简历未体现”和“用户不会”，禁止建议虚构经历。
6. `AI_INVALID_RESPONSE` 最多一次结构修复；只传脱敏 validator issue，要求保持同一语义且不得新增
   claims/evidence。
7. V2 评测分别记录 first-pass 与 final schema、retry、per-sample evidence 和 attempt/total latency。

## Gate

V1 failure analysis is complete. Prompt/Schema V1、dataset v1、`COPILOT_RESULTS.md` V1 baseline 与
`COPILOT_BAD_CASES.md` BC-01 至 BC-07 均未覆盖或修改。下一步可以开始 RED/GREEN V2；仍不得进入
Phase 12。
