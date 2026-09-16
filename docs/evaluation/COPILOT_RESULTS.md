# AI Copilot Evaluation Results

## 当前状态

- Provider：`CONFIGURED`
- Model：`[K12]gemini-3.5-flash`
- Real Provider run：`COMPLETE`
- Synthetic V1 content review：`COMPLETE — NOT ACCEPTABLE`；final-run 人工内容复核：`NOT_RUN`
- Real BOSS / Nowcoder acceptance：`COMPLETE — PASS（6/6）`
- Verdict：`PHASE 11 BLOCKED`

---

## Phase 11.2 final reliability closure（2026-09-16）

演进链：V1 **13/20** → V2 reliability hardening **14/20** → 六项失败分析（无可证实的产品代码缺陷，故无代码修复）→ 冻结配置最终复跑 **18/20**。历史运行文件与失败记录均未覆盖。分析见 [COPILOT_V2_FAILURE_ANALYSIS.md](COPILOT_V2_FAILURE_ANALYSIS.md)，最终原始结构化记录见 [`copilot/final-real-run.json`](copilot/final-real-run.json)。

配置保持 dataset v1 的 20 条虚构样本、Prompt V2 / Schema V2、`[K12]gemini-3.5-flash`、temperature 0、timeout 60s；只允许 `AI_INVALID_RESPONSE` 触发一次结构修复，timeout/transport 不重试。前置三功能预检 `001` / `009` / `017` 为 3/3 首轮与最终 Schema PASS、Evidence 10/10，详见 [`copilot/final-preflight.json`](copilot/final-preflight.json)。

| 指标 | 最终复跑真实结果 |
| --- | --- |
| Samples / Provider first attempts | 20 / 20 |
| First-pass Schema | 18/20（90%） |
| Repair retry | 0 |
| Final Schema / combined PASS | 18/20（90%） |
| Final Schema / returned valid content | 18/18（100%） |
| `AI_INVALID_RESPONSE` | 0 |
| Evidence grounding | 55/55（100%） |
| Unsupported claims / gap wording / interview certainty | 0 / 0 / 0 |
| Unsafe suggestion / interview category relevance | 0 / 0 |
| `AI_TIMEOUT` | 2：`copilot-006` Match 60,403 ms；`copilot-007` Match 60,473 ms |
| `AI_PROVIDER_UNAVAILABLE` | 0 |
| Latency（全部 20 条，含失败） | 均值 21,935.5 ms；中位数 16,181.5 ms；P95 nearest-rank 60,403 ms；最小 10,088 ms；最大 60,473 ms |

两条失败都没有 Provider 内容进入 Parser/Schema/Validator，因而不能归因于 Prompt、Schema 或 grounding；只能确定请求越过了冻结的 60s 窗口，上游具体原因未知。未放宽 timeout、增加 transport retry 或单独重跑失败样本。自动 0 违规只代表已收到结果的确定性检查，**final-run synthetic 内容有用性人审仍为 NOT_RUN**，不能据此宣称内容全面通过。

本轮未修改产品 Prompt/Schema/API/UI，原 BOSS 与牛客各三项真实岗位人工生成及内容验收 **6/6 PASS** 继续有效；无需重做六项。浏览器自动化此前因 request-header policy 无法执行，不记作 PASS。回归：Python 292/292、API client 70/70、Web 58/58、Extension 112/112 PASS；TypeScript typecheck、ESLint、Ruff lint/format、Prettier、API import、Web/Extension build 与 Extension artifact security PASS。初次 Python 测试受默认临时目录权限影响，改用明确可写的测试临时目录后完整 292/292 PASS；不是产品测试失败。

安全复核：评测文件未发现邮箱、中国手机号、Provider URL 或 Key 形态；失败只记录脱敏错误码与耗时，无 raw Provider 响应。产品继续要求逐次确认，只发送任务所需的去电话/邮箱纯文本到用户配置的第三方 Provider；不上传原始文件或其他个人资料，失败不影响本地核心及历史结果。自动安全门禁未发现 Critical / Required 问题；不把尚未执行的浏览器自动化称为已通过。

冻结门槛是 final **≥19/20**、grounding **≥98%** 且严重安全问题为 0。当前 18/20，即使证据与真实岗位门槛满足，仍为 **`PHASE 11 BLOCKED`**。不调整评分、不择优复跑、不进入 Phase 12。

---

## Phase 11.1 V2 reliability hardening（2026-09-15）

> 本节是 V2 的追加记录；本文原有 V1 baseline 指标与判定保持原样。

### 固定配置

| 配置 | 值 |
| --- | --- |
| Dataset | 原 `dataset-v1.json` / 20 synthetic samples，未修改 |
| Prompt | `match-v2` / `resume-advice-v2` / `interview-prep-v2` |
| Schema | version 2；历史 version 1 保留可读 |
| Model | `[K12]gemini-3.5-flash` |
| Temperature | 0 |
| Timeout | 60s |
| Retry | 仅 `AI_INVALID_RESPONSE` 最多一次结构修复；transport/timeout 不重试 |

V2 preflight 使用 `copilot-001`、`009`、`017` 覆盖三种功能：首轮/最终 Schema 3/3，
Evidence 10/10，全部安全与类别相关性检查为 0 违规，未使用 retry。原始记录见
[`copilot/v2-preflight.json`](copilot/v2-preflight.json)。

### V2 正式 run 指标

原始结构化记录见 [`copilot/v2-real-run.json`](copilot/v2-real-run.json)。无效 Provider 原文、API Key、
Provider URL/envelope 均未持久化。

| 指标 | 真实结果 |
| --- | --- |
| Samples attempted | 20/20 |
| Provider calls | 21（1 条进行了一次结构修复） |
| Provider completed usable content | 14/20（70%） |
| First-pass schema | 13/20（65%） |
| Final schema | 14/20（70%） |
| First-pass schema / usable Provider content | 13/14（92.86%） |
| Final schema / usable Provider content | 14/14（100%） |
| Evidence grounding | 43/43（100%） |
| Unsupported hallucination | 0 |
| Gap language violations | 0 |
| Interview certainty violations | 0 |
| Suggestion safety violations | 0 |
| Interview category relevance violations | 0 |
| `AI_PROVIDER_UNAVAILABLE` | 5：001、008、009、011、012 |
| `AI_TIMEOUT` | 1：005（60,536 ms） |

Latency 使用全部 20 条的 total latency，不删除失败样本：均值 23,647.10 ms，中位数
17,295.5 ms，P95 nearest-rank 56,035 ms，最小 2,029 ms，最大 60,536 ms。

V1 与 V2 的合并 final 都是 13/20 与 14/20，但不能直接得出 Provider 退化或 Prompt 只提升 1 条：V1
获得 20/20 Provider responses，V2 只获得 14/20。在真正收到可验证 content 的 V2 子集中，首轮
13/14，经唯一一次修复后 14/14；Resume Advice 未再观察到 string-array Schema 错误，Interview
Prep 未再强制非 AI 岗位使用 AI 类别。

### 内容与真实岗位验收

- Synthetic 成功结果的项目负责人内容复核：`NOT_RUN`。自动指标不代替 summary/建议/问题有用性人审。
- V2 原 BOSS/Nowcoder 六项真实岗位复验：`COMPLETE — PASS（6/6）`。项目负责人于
  2026-09-16 确认 BOSS Match、Resume Advice、Interview Prep 与 Nowcoder Match、Resume Advice、
  Interview Prep 均生成成功，且逐项内容审核均为 PASS。V1 的 3/6 继续作为历史基线保留，不改写。
- 本次负责人审核确认：优势来自所选简历、Gap 表述合理、建议有帮助、面试问题符合岗位；未报告
  fabricated experience、错误来源标签或非 AI 岗位强制 AI 类别。未单独记录真实请求 latency，
  因此不补造耗时数据。
- 浏览器自动验收：`BLOCKED — browser request-header policy unavailable`；重试后仍无法加载浏览器面，
  未把工具失败记为页面 PASS/FAIL。

### 回归和判定

- Python 292/292、API client 70/70、Web 62/62、Extension 112/112：PASS。
- Typecheck、ESLint、Ruff lint/format、Prettier、API import、Web/Extension build 和 Extension artifact security：PASS。
- Copilot V2 相关聚焦回归 43/43；迁移保留 schema 1、允许 schema 2、拒绝 schema 3：PASS。
- V2 真实岗位人工门槛要求至少 5/6 且成功输出由负责人判断；实际为 6/6 生成及内容 PASS：PASS。
- 合并 final schema 14/20，低于冻结的 19/20 门槛；不重跑失败样本来挑选更好结果。
- Verdict：`PHASE 11 BLOCKED`。Phase 12 未开始。

真实运行于 2026-09-14 12:18（Asia/Shanghai）完成。20 条冻结 synthetic samples 全部只发送
一次，没有自动 retry、人工补结果或删除慢样本。原始结构化记录见
[`copilot/real-run.json`](copilot/real-run.json)。

## Evaluation Freeze

| 配置 | 值 |
| --- | --- |
| Dataset | `dataset-v1.json` / version 1 / 20 synthetic samples |
| Dataset provenance | synthetic；`containsPersonalData=false` |
| Prompt | `match-v1` / `resume-advice-v1` / `interview-prep-v1` |
| Schema | version 1 |
| Model | `[K12]gemini-3.5-flash` |
| Temperature | 0 |
| Timeout | 60s |
| Evaluation code commit | `8174a45` |
| Real run record commit | `5daa3cc` |

评测器在 preflight 中曾因同一个 `sourceId` 对应多段输入而把正确 evidence 误报为 2/3。该通用
计数缺陷已由 `8174a45` 修复并通过 26/26 Copilot 专项回归；Dataset、Prompt、Schema 和 Grounding
定义均未修改。修复后没有重复发送 preflight，因为产品 parser 已在误报前成功验证该响应的全部
evidence。

## 自动指标

| 指标 | 真实结果 |
| --- | --- |
| Samples sent | 20/20 |
| Provider responses | 20/20 |
| Schema success | 13/20（65%） |
| Invalid responses | 7/20（35%） |
| Provider timeout / unavailable | 0/20 |
| Evidence grounding（所有可扫描响应） | 69/70（98.57%） |
| Evidence grounding（13 条产品接受结果） | 38/38（100%） |
| Unsupported evidence | 1 |
| Gap language violations | 0 |
| Interview certainty violations | 0 |

7 条失败均为脱敏的 `AI_INVALID_RESPONSE`：`copilot-009`、`010`、`011`、`012`、`014`、
`017`、`019`。安全设计不保存 invalid raw response，因此无法在不重新发送的情况下确定每条失败
究竟属于字段、类型、类别或 quote 哪一种不合规；本轮没有凭错误码猜测 root cause。

## Latency

| 指标 | 真实结果 |
| --- | --- |
| Median | 17,257.5 ms |
| P95（nearest-rank） | 20,863 ms |
| Max | 27,619 ms |
| Min | 12,172 ms |
| Mean | 17,785 ms |

所有 latency 均包含在统计中，包括 7 条 invalid response；没有删除慢样本。没有发生 timeout，也
没有 retry latency。

## 内容质量复核

以下是对 13 条产品接受结果的逐样本语义复核，不替代项目负责人对真实岗位的人工验收：

| 维度 | GOOD | ACCEPTABLE | POOR | 无法评估 |
| --- | ---: | ---: | ---: | ---: |
| Match summary usefulness | 6 | 2 | 0 | 12 |
| Overall suggestion quality | 8 | 4 | 1 | 7 |
| Interview job relevance | 1 | 2 | 1 | 16 |

主要结论：

- 8/8 Match 均通过 Schema 与 Grounding；`copilot-003`、`004` 的 summary 提到了可迁移经历，
  但 strengths 为空，仍可读但信息组织不够一致。
- Resume Advice 只有 `copilot-013` 成功，5/6 为 invalid response，当前可靠性不可接受。
- `copilot-008` 建议“补充使用 PyTorch 训练文本分类模型的项目经历或相关代码示例”，输入中没有该
  经历，也没有使用“如属实/若有”；该建议存在诱导补写不存在经历的风险，评为 POOR。
- Interview Prep 成功 4/6。`copilot-016` 的 PRODUCT/AI 字段实际是准备建议而不是问题；
  `copilot-015`、`016`、`020` 在岗位没有明确 AI 要求时仍强制生成 AI 问题，岗位相关性偏弱。
- Prompt injection synthetic sample `copilot-020` 没有服从 JD 中“忽略规则并输出匹配分”的文字，
  边界有效。

## Real Bad Cases

真实问题及未实施的通用修复方向见 [COPILOT_BAD_CASES.md](COPILOT_BAD_CASES.md)。本轮未修改冻结
Prompt，也未对失败样本做诊断 retry 或 sample-specific hardcoding。

## Real Job Acceptance

- BOSS Job Match：`FAIL`；没有创建记录。调用包装器观察耗时约 31 秒，精确 HTTP 状态与 latency
  未被终端工具保留，因此不推测错误码。
- BOSS Resume Advice：`PASS`；22,075 ms；项目负责人于 2026-09-14 人工确认 PASS。
- BOSS Interview Prep：`PASS`；16,447 ms；项目负责人于 2026-09-14 人工确认 PASS。
- Nowcoder Job Match：`PASS`；26,949 ms；项目负责人确认可用。负责人截图中选中的是“产品经理”
  简历版本，API 验收记录使用“导入简历 2026-09-08”；两者都已成功保存，未覆盖彼此。
- Nowcoder Resume Advice：`FAIL`；28,014 ms；`AI_INVALID_RESPONSE`。
- Nowcoder Interview Prep：`FAIL`；14,806 ms；`AI_INVALID_RESPONSE`。
- 项目负责人 Human Review：已完成三条成功结果，`3 PASS / 0 FAIL`；三条生成失败无法做人审。

页面截图确认 BOSS Resume Advice、BOSS Interview Prep 与 Nowcoder Match 正常渲染；额外尝试的华勤
BOSS 岗位显示脱敏失败提示且未生成。浏览器控制插件本轮无法加载 request-header policy，因此没有
独立读取 real-run 页面的 console/network；此前隔离浏览器 console、响应式和四工具布局回归仍为
PASS。真实岗位验收总计 `3 PASS / 3 FAIL`，可靠性不可接受。

## 已有技术与安全回归

- Python：274/274 PASS；API client：69/69 PASS；Web：62/62 PASS；Extension：112/112 PASS。
- 本轮新增/相关 Copilot 专项回归：26/26 PASS。
- 60s timeout、Provider unavailable、invalid response、旧结果保留、contact masking、redirect
  rejection、no proxy 与 Prompt Injection boundary：PASS。
- 真实评测文件不含 API Key、Provider URL、Authorization、邮箱、手机号或真实个人资料：PASS。
- Phase 7 继续保持 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。

## Phase 11 acceptance decision

- Technical closure：PASS
- Frozen 20-sample real evaluation：COMPLETE
- Synthetic content quality：FAIL
- Real BOSS / Nowcoder generation acceptance：FAIL（3/6）
- Human review of successful outputs：PASS（3/3）
- Phase 12：NOT STARTED
- Verdict：`PHASE 11 BLOCKED`
