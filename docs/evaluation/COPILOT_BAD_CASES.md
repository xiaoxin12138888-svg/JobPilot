# AI Copilot Bad Case Review

## 当前状态

本文件只记录 2026-09-14 的真实 Provider preflight 与冻结 20-sample run 中实际观察到的问题。
没有用 Fake Provider、schema fixture 或预期风险冒充真实 Bad Case。失败响应只保存脱敏错误码，
因此不能观察到的内容明确标为 unknown，不推测 Provider raw response。

## BC-01 — Resume Advice 大面积 invalid response

- **Feature**：Resume Advice
- **Input Summary**：`copilot-009`、`010`、`011`、`012`、`014`，覆盖交互设计、科技内容运营、
  嵌入式、医学事务与经营分析岗位。
- **Observed**：5 条均收到 Provider 响应，但被产品 parser 拒绝为 `AI_INVALID_RESPONSE`；该功能
  只有 `copilot-013` 成功，Schema success 为 1/6。
- **Expected**：全部输出严格包含 `highlight`、`possibleImprovement`、`interviewFocus`，事实 evidence
  必须来自声明的 Resume/Job source。
- **Root Cause**：`UNKNOWN`。invalid raw response 按安全约束未持久化，仅凭统一错误码不能判断是
  JSON、字段、类型、source type/id 还是 quote 不匹配。Feature 聚集说明 Prompt/model 格式遵循存在
  系统性风险，但不是精确 root cause 证据。
- **Severity**：Required。
- **Prompt / Code Fix**：建议在获批的 Prompt V2 中减少结构歧义，或在 Provider 支持时采用严格
  JSON schema；如需定位，应增加不保存 raw text 的脱敏诊断分类并进行一次获批 retry。本轮未实施。
- **Regression Result**：NOT RUN；初始失败已完整保留，没有自动 retry。

## BC-02 — preflight 重复 sourceId 被评测器误计数

- **Feature**：Evaluation runner
- **Input Summary**：`copilot-001` 的两段 Job source 共用 `job-001`。
- **Observed**：Provider 输出先通过产品 parser，但旧评测器把三条正确 evidence 计为 2/3。
- **Expected**：与产品 parser 一致，对同一 type/id 下的每段原文逐一匹配，结果为 3/3。
- **Root Cause**：评测器使用 `(sourceType, sourceId) -> text` 字典，后一段文本覆盖前一段。
- **Severity**：Required。
- **Prompt / Code Fix**：`8174a45` 将每个 type/id 映射到全部来源文本，不改 Grounding 定义。
- **Regression Result**：PASS；先由新测试稳定复现 3/2，再修复为 3/3；Copilot 专项 26/26 PASS，
  Ruff 与 format PASS。

## BC-03 — 建议可能诱导补写不存在经历

- **Feature**：Job Match / Suggestions
- **Input Summary**：`copilot-008`；Resume 只包含 scikit-learn 新闻分类实验，JD 要求 PyTorch。
- **Observed**：建议写“补充使用 PyTorch 训练文本分类模型的项目经历或相关代码示例”，没有“若
  属实/如有”条件，也没有区分新建练习项目与已有经历。
- **Expected**：只能建议核实已有资料，或明确建议未来学习、练习、创建可验证的新项目；不能暗示
  用户把输入中不存在的经历直接补进简历。
- **Root Cause**：Prompt V1 约束“不虚构”，但没有强制无 evidence 的补充建议使用条件式措辞。
- **Severity**：Required。
- **Prompt / Code Fix**：Prompt V2 方向应要求：无 Resume evidence 时只能写“如属实再补充”，否则
  改为“学习/练习/创建后再记录”；不得宣称已有。本轮保持 Prompt V1 冻结，未实施。
- **Regression Result**：NOT RUN；真实问题保留，等待负责人批准 Prompt V2。

## BC-04 — 非 AI 岗位被强制生成 AI 问题

- **Feature**：Interview Prep
- **Input Summary**：`copilot-015` 企业软件销售、`016` 软件项目经理、`020` 用户研究员；JD 没有
  明确 AI 要求。
- **Observed**：三条结果仍生成 AI 类问题。`copilot-016` 的 PRODUCT 与 AI 字段写成“当前资料未
  发现……建议准备……”的陈述/建议，不是可直接练习回答的面试问题。
- **Expected**：问题与岗位证据直接相关、可回答，不为了满足类别而制造弱相关方向。
- **Root Cause**：Prompt/产品 parser 强制每次必须同时包含 PRODUCT、AI、PROJECT 三类，与非 AI
  岗位的“全部问题均应岗位相关”目标冲突。
- **Severity**：Required。
- **Prompt / Code Fix**：Prompt V2 / Schema 方向应允许不适用类别为空，或把 AI 改为可选类别；
  这涉及冻结 contract，本轮未实施。
- **Regression Result**：NOT RUN；等待负责人决定是否允许 contract 级通用调整。

## BC-05 — Interview Prep invalid response

- **Feature**：Interview Prep
- **Input Summary**：`copilot-017` 安全运营、`copilot-019` 产品经理实习生，均包含面试复盘。
- **Observed**：两条 Provider 响应均为 `AI_INVALID_RESPONSE`，该功能 Schema success 为 4/6。
- **Expected**：返回 PRODUCT/AI/PROJECT 问题与 grounded INTERVIEW review，且不使用确定性措辞。
- **Root Cause**：`UNKNOWN`。原始 invalid response 未保存，不能从统一错误码确定具体失败字段。
- **Severity**：Required。
- **Prompt / Code Fix**：与 BC-01 一样，先增加脱敏诊断分类或在获批后单样本 retry，再决定是否是
  Prompt V2 的通用格式问题；本轮未实施。
- **Regression Result**：NOT RUN；初始失败已保留，没有自动 retry。

## BC-06 — 一条 unsupported evidence 无法归因到具体失败样本

- **Feature**：Evaluation observability / Grounding
- **Input Summary**：20 条全量 run；7 条 invalid response 未保存 raw result。
- **Observed**：评测器在 parse 前扫描到 70 条 evidence，其中 69 条能在声明来源中匹配；13 条产品
  接受结果自身为 38/38，因此唯一不匹配 evidence 来自某条被拒绝响应，但现有记录无法定位 ID。
- **Expected**：Grounding 70/70；若不匹配，应保留非敏感的 sample-level evidence 计数和诊断类别。
- **Root Cause**：Provider 至少输出了一条无法按 type/id/quote 匹配的 evidence；runner 只持久化
  汇总计数与错误码，缺少 per-sample 非敏感诊断，具体样本与语义不可得。
- **Severity**：Required。
- **Prompt / Code Fix**：后续可仅记录每个 sample 的 `provided/grounded` 计数和稳定 diagnostic enum，
  不保存 raw invalid content。需要先批准评测工具变更；本轮未实施。
- **Regression Result**：NOT RUN；没有为了定位而重发失败样本。

## 未观察到的风险

- 没有 gap “用户不会/没有能力”违规：0。
- 没有“必问/一定会问/面试官会问”确定性措辞：0。
- 没有发现输入中不存在的经历被直接陈述为用户既有事实；BC-03 是建议措辞风险。
- Prompt injection sample 没有改变输出 contract，也没有生成匹配分。

## BC-07 — 真实岗位生成成功率不足

- **Feature**：Real BOSS / Nowcoder Copilot generation
- **Input Summary**：百度 BOSS 岗位与 OPPO 牛客岗位，各运行 Match、Resume Advice、Interview Prep
  一次；Match/Resume Advice 使用所选真实简历，联系方式由产品边界移除。
- **Observed**：BOSS Resume Advice、BOSS Interview Prep、Nowcoder Match 成功并由负责人确认 PASS；
  BOSS Match 没有创建记录，Nowcoder Resume Advice 与 Interview Prep 返回
  `AI_INVALID_RESPONSE`。总成功率 3/6。额外的华勤 BOSS Resume Advice 页面也显示脱敏失败提示，
  但不计入正式六项指标。
- **Expected**：六项都应在 60 秒内生成可持久化、可复核的 grounded 结果；失败时 UI 明确提示且
  核心 Job/Resume/Application 功能保持可用。
- **Root Cause**：Nowcoder 两项只能确定为 Schema/grounding validation failure；invalid raw
  response 未保存。BOSS Match 的终端包装器没有保留精确状态，不能推断具体错误码。
- **Severity**：Required。
- **Prompt / Code Fix**：结合 BC-01、BC-04、BC-05，需先获批通用 Prompt V2 / optional interview
  category contract 或更强结构化输出策略；不得为具体 BOSS/Nowcoder 样本硬编码。本轮未实施。
- **Regression Result**：FAIL；初始结果全部保留，没有自动 retry。成功结果持久化且失败没有覆盖
  结果的产品行为 PASS。

## 后续门禁

当前 Bad Cases 含 Required 问题，不能通过 Phase 11。真实 BOSS/Nowcoder 验收已经完成，成功输出的
项目负责人人审为 3/3 PASS，但生成成功率只有 3/6。不得自动继续调 Prompt 或进入 Phase 12；项目
负责人需要另行决定是否批准通用 Prompt V2 / optional interview category contract 修复。

---

## Phase 11.1 V2 追加记录

> BC-01 至 BC-07 是冻结 V1 原始记录，不改写。以下只记录 V2 正式 run 中真实观察到的新结果。

## BC-08 — Provider unavailable 批量中断

- **ID**：`copilot-001`、`008`、`009`、`011`、`012`。
- **Input**：原 dataset v1 的 3 条 Match 与 3 条 Resume Advice 中的 5 条；未改 Prompt/Schema/model/timeout。
- **Observed**：2,029～13,587 ms 内返回脱敏 `AI_PROVIDER_UNAVAILABLE`，每条只发送一次，无结构修复。
- **Expected**：Provider 在 60s 内返回可交给严格 parser 的 content。
- **Root Cause**：Provider/transport 未可用；公开错误按安全边界脱敏，无法从本次记录判定上游 HTTP
  状态或内部原因，不做猜测。
- **Fix**：不应使用 Schema retry；由项目负责人决定更换/稳定 Provider，或接受当前可用性。本阶段不改 retry/
  timeout，不重跑挑选结果。
- **Regression**：PASS；transport failure 不重试，错误脱敏，上一次有效结果保留。产品验收门槛未达。

## BC-09 — 60s Provider timeout

- **ID**：`copilot-005`。
- **Input**：测试开发工程师 Match 虚构样本。
- **Observed**：60,536 ms 后返回 `AI_TIMEOUT`，没有第二次 Provider 请求。
- **Expected**：60s 内返回并通过结构/evidence 验证。
- **Root Cause**：真实 Provider 请求超过已冻结 60s 产品窗口；无证据表明业务 Schema 出错。
- **Fix**：不自动增加 timeout，不对 timeout retry；如需变更 Provider 或 timeout，必须另行批准。
- **Regression**：PASS；稳定 `AI_TIMEOUT`、不泄露 raw error，本地 Job/Resume/Application 仍可用。

## BC-10 — Interview Prep 首轮结构失败被单次修复

- **ID**：`copilot-017`。
- **Input**：安全运营工程师 JD 与一条面试复盘。
- **Observed**：首轮 29,274 ms 被 `AI_INVALID_RESPONSE` 拒绝；唯一修复后总计 43,520 ms，最终 Schema
  PASS、Evidence 4/4，TECHNICAL 类别与非 AI JD 匹配。
- **Expected**：最好首轮直接成功；若只有结构问题，允许一次不增加 claim/evidence 的修复。
- **Root Cause**：首轮无效 raw 按安全边界未持久化，只能确认为严格 parser 拒绝，不猜测具体字段。
- **Fix**：V2 单次 structure-only repair 已生效；不增加第三次请求。
- **Regression**：PASS；每样本记录 first/final status、attempt/retry 和 latency，不保存无效原文。

## V2 结论

V1 的 string-array 错误和非 AI 岗位强制 AI 类别在已收到的 V2 有效 content 中未再出现；但新的
Provider availability 失败使合并 final 只有 14/20，低于 19/20 门槛。未生成的 6 条不能进行 summary/
建议/问题内容审核，不得用 0 违规冒充内容质量 PASS。

2026-09-16 的 V2 真实岗位复验中，BOSS 与 Nowcoder 的 Match、Resume Advice、Interview Prep
共六项均生成成功，项目负责人内容审核 6/6 PASS；本次没有观察到新的真实岗位 Bad Case，因此不
虚构新增编号。该结果满足真实岗位门槛，但不覆盖 BC-08/BC-09，也不能替代冻结 synthetic run 的
19/20 门槛。Phase 11 保持 `BLOCKED`。

---

## Phase 11.2 最终复跑新增真实 Bad Case

> V1 的 BC-01～07 与 V2 的 BC-08～10 均保留为历史事实。本节只记录 [`copilot/final-real-run.json`](copilot/final-real-run.json) 中实际观察到的两条新失败，不将未发生的结构或内容错误写成 Bad Case。

## BC-11 — 两条 Match 请求越过冻结的 60s 窗口

- **ID**：`copilot-006`、`copilot-007`。
- **Input**：冻结 dataset v1 中两条虚构 Match 样本；Prompt V2、Schema V2、Provider、model、temperature 0 与 timeout 60s 未变。
- **Observed**：两条分别在 60,403 ms、60,473 ms 返回脱敏 `AI_TIMEOUT`；均为一次请求、retry 0、无可验证 Provider 内容。最终 Schema 为 18/20，而其余 18 条均通过；Evidence 55/55。
- **Expected**：两条应在 60s 产品窗口内返回可供严格结构和证据验证的结果，使冻结 20 条评测至少 19/20。
- **Root Cause**：已观察到的直接原因是 Provider 请求超时。上游负载、网络或具体服务内部原因没有可验证记录；Parser、Schema、Validator 和结构修复均未被这两条触达，不能把超时归因于它们。
- **Fix**：本轮没有可证实且在授权范围内的产品代码修复。不自动增加 timeout 或 transport retry，不更换 Provider，不单独复跑失败样本以挑选结果。后续如需改变这些冻结条件，须由负责人另行批准并重新定义可比较的评测。
- **Regression**：产品 timeout 返回稳定脱敏 `AI_TIMEOUT`，不保存 raw response、不覆盖历史有效结果；Python 292/292、API client 70/70、Web 58/58、Extension 112/112 与静态/构建门禁 PASS。验收数字仍为 18/20，故 `PHASE 11 BLOCKED`。
