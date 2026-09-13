# AI Copilot Bad Case Review

## 当前状态

Provider：`NOT_CONFIGURED`。真实 Provider run：`NOT RUN`。因此当前没有真实 observed output，
也没有可登记为真实 Bad Case 的样本；以下四项是预注册审查类别和已存在的确定性回归门禁，不能
冒充真实模型失败。

## BC-01 — 无证据优势

- ID：BC-01
- Input：真实 run 未执行；预注册条件为模型输出 Resume 原文中不存在的 strength quote。
- Observed：`NOT OBSERVED — PROVIDER NOT CONFIGURED`。
- Expected：每条 strength 必须引用所选 Resume 中存在的原文。
- Root Cause：真实 root cause 尚不可得；常见风险是模型把建议或岗位要求误写成候选人事实。
- Fix：当前 parser 在持久化前校验 source type/id/quote，不满足时返回 `AI_INVALID_RESPONSE`。
- Regression：自动化覆盖 unsupported Resume quote 被拒绝；真实样本待 Provider run 后补充。

## BC-02 — 把“未发现”写成“不具备”

- ID：BC-02
- Input：真实 run 未执行；预注册条件为 gap 断言“用户不会/不具备”。
- Observed：`NOT OBSERVED — PROVIDER NOT CONFIGURED`。
- Expected：只能描述“当前资料/简历未发现…”，不能判断用户能力。
- Root Cause：真实 root cause 尚不可得；风险来自模型把证据缺失升级为能力结论。
- Fix：Prompt 与 parser 同时约束缺口语言，违规返回 `AI_INVALID_RESPONSE`。
- Regression：自动化覆盖能力断言和缺少“未发现”的 gap 被拒绝。

## BC-03 — 生成不存在经历

- ID：BC-03
- Input：真实 run 未执行；预注册条件为模型把不存在的项目/经历作为已有事实。
- Observed：`NOT OBSERVED — PROVIDER NOT CONFIGURED`。
- Expected：事实型经历只能通过 RESUME/INTERVIEW 真实 quote 表达；无证据内容只能作为明确的
  `AI建议`。
- Root Cause：真实 root cause 尚不可得；风险来自模型根据岗位需要补全候选人背景。
- Fix：grounded 字段验证真实 source；UI 把非事实建议单独标记为 `AI建议`。
- Regression：自动化覆盖不存在 source/quote 被拒绝；建议语义仍须在真实 run 中人工检查。

## BC-04 — 面试问题过度确定

- ID：BC-04
- Input：真实 run 未执行；预注册条件为问题使用“必问/一定会问/面试官会问”等确定性表达。
- Observed：`NOT OBSERVED — PROVIDER NOT CONFIGURED`。
- Expected：只表达“可能关注方向”，每题引用真实 JOB 证据。
- Root Cause：真实 root cause 尚不可得；风险来自模型把准备建议表述为招聘方确定行为。
- Fix：Prompt 与 parser 拒绝确定性措辞，UI 标题固定为“可能关注方向”。
- Regression：自动化覆盖确定性问题被拒绝与错误 JOB source/quote 被拒绝。

## 后续更新规则

Provider 配置后只运行冻结的 20 条 dataset。只有 `real-run.json` 中真实输出与人工复核事实可以新增
Observed、Root Cause 和 Fix；不得依据 Fake Provider、schema fixture 或预期风险虚构 Bad Case。
