# Evidence Map V2

## Input and consent

生成前必须同时满足：Job 存在；当前 JD Analysis 存在且非 stale；ResumeVersion 存在；Provider
已配置；请求含 `confirmExternalAi: true`。Web 在发送前明确说明本次会把所选简历正文与岗位要求
发送给用户配置的 AI 服务，用户确认后才调用 POST。

发送数据仅为 Job title、可选 company、当前分析的 must-have、preferred、responsibility、skill、
experience、education 六类条件文本，以及所选 ResumeVersion content。summary、domain keywords
与 interview focus 不是匹配条件，不发送；也不得发送原始 HTML、完整 JD、notes、Application、
其他 Job 或简历。系统提示把 JD 条件和 Resume 都声明为不可信数据，禁止执行其中的指令。

## Schema and grounding

旧 schema version 1 保持可读，只允许 `MUST_HAVE | PREFERRED`。所有新生成使用 schema version 2：

```text
EvidenceMap { mappings: EvidenceMapping[] }
EvidenceMapping {
  requirementType: MUST_HAVE | PREFERRED | RESPONSIBILITY | SKILL | EXPERIENCE | EDUCATION
  requirementText: string
  coverage: DIRECT | PARTIAL | GAP
  resumeEvidence: [{ quote: string }]
  reason: string
}
```

服务端按硬性要求、加分项、岗位职责、技能、经验、学历的固定组顺序，以及各组原有顺序构建期望
requirement 序列；Provider 必须逐项原样返回，不能自行创建、遗漏、重排或改写 requirement。
每个 quote 在 whitespace normalization 后必须存在于同样规范化的 Resume content；不支持的
quote 被删除。DIRECT/PARTIAL 无剩余有效 quote 时降级 GAP。

DIRECT 表示当前简历有可直接支持要求的原文；PARTIAL 表示有相关但不完整的原文；GAP 仅表示
当前简历版本未找到可证明内容。每项 UI 先确定性显示“直接证据”“部分支持 / 待确认”或“当前无法
证明”，再显示判断依据和原文 quote。全图总览只数各 coverage 的数量，并按原映射顺序列出最多
三项主要待确认内容和证据缺口；不计算分数、匹配率或概率。

Provider 的 `reason` 也必须先写同一明确结论，再解释 grounded facts 如何共同支持判断，以及仍需
确认或缺少的内容。Web 不接受 Provider 自行生成的全局分数、摘要或推荐。

coverage 是对 grounded facts 的语义综合，不是关键词或字面相等。Provider 必须先理解每项条件，
再扫描完整 Resume；措辞不需要一致，证据也不局限于同名 section。新生成的 DIRECT/PARTIAL 每项
返回一至三条 quote，可用不同 section 的多段事实共同支持：组合后无需补充用户事实即可完整证明
为 DIRECT；明显相关但缺少关键组成部分或仍需用户确认为 PARTIAL；扫描完整简历仍无合理支持
事实才为 GAP。

语义推理只解释已写事实与 requirement 的关系，不得用外部知识补全或升级能力等级、工作年限、
学历、毕业年份、项目规模、成果或经历连续性。届别判断只接受简历明确写出的毕业年份、预计毕业
时间或培养年限；只有入学时间和在读状态时最多为 PARTIAL，reason 必须指出缺少毕业信息，不能
根据惯常培养长度推导目标年份。

## Persistence and failure

每个 Job + ResumeVersion 保存一个当前记录。读取时比较所存 JD analysis fingerprint 与当前分析，
并比较所存 Resume fingerprint 与当前正文，任一变化即 `isStale: true`。六类条件改变了分析
fingerprint，因此旧 schema 1 记录会成为 stale；成功重新生成保留同一记录 id/createdAt 并升级为
schema 2。SQLite migration `0007_evidence_map_schema_v2` 允许版本 1/2，存在版本 2 行时拒绝降级。
stale 结果可以显示但不能冒充最新结果。Provider 超时、不可用或返回非法内容时，最后一个有效
记录不删除、不覆盖；错误继续使用 Phase 6 的稳定脱敏语义。
