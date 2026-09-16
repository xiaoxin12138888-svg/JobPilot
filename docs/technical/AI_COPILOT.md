# AI Job Copilot 技术契约

## 范围

Phase 11 P0 包含岗位匹配、简历准备和面试准备。它是 Job Detail 中按需生成的辅助内容，不是聊天、
自动决策或自动操作。Phase 6 JD prompt/schema 与 Phase 7 Evidence Map prompt/schema 不变。

## 输入与隐私

- Match / Resume Advice：当前非 stale JD Analysis 的六类 requirement、Job title、用户明确选择的
  Resume Version 正文。
- Interview Prep：同一 Job 的当前 requirement 与 Application 下已有 Interview rounds/questions。
- email 与 phone 在 Provider data 构造前确定性删除；不发送 Profile、Application 状态、文件名或
  无关记录。
- Provider data 中每个 source 都带本地 ID，模型只能把它当作不可信文本。

## 输出契约

Match：`summary`、`strengths[]`、`gaps[]`、`suggestions[]`。strength 必须引用 RESUME；gap 必须引用
JOB。Resume Advice：`highlight[]` 引用 RESUME，`possibleImprovement[]` 是 string[] AI 建议，
`interviewFocus[]` 引用 JOB。Interview Prep：`possibleQuestions[]` 可使用 PRODUCT、AI、PROJECT、
TECHNICAL、BEHAVIORAL、DOMAIN，但只能根据 JD 选择相关类别，非 AI 岗位不强制 AI；问题引用
JOB。有面试记录时 `review.strengths[]/weaknesses[]` 引用 INTERVIEW，`nextActions[]` 为 string[]
建议。

Grounded item wire shape：

```json
{
  "text": "结论或准备方向",
  "sourceEvidence": {
    "text": "来源中的连续原文",
    "sourceType": "RESUME",
    "sourceId": "本地资源 ID"
  }
}
```

Source type 是 `RESUME | JOB | INTERVIEW`；INTERVIEW 仅用于复盘。所有字段 exact-key、长度和条数
有界。source type/id/quote 任一不匹配，本次结果以 `AI_INVALID_RESPONSE` 失败且不持久化。
当前生成使用 schema 2 与 `match-v2` / `resume-advice-v2` / `interview-prep-v2`；历史 schema 1
结果仍可读。V2 将当次允许的 source IDs 显式加入 system instruction，不接受模型自创 ID。
要求增加简历经历/成果的建议必须有“如果你确实有”类条件，否则只能建议学习、准备或核实。

## 有界结构修复

首次 content 只有在严格 Copilot parser 返回 `AI_INVALID_RESPONSE` 时才允许修复。最多一次、仍使用
同一 Provider/模型/Prompt，并在单独 user repair message 中携带白名单 validator code，明确禁止新增
claim 或 evidence。首次无效响应只在该请求内存中传回同一 Provider，不写数据库、文件或日志。
首次 `AI_TIMEOUT` 现在允许用完全相同的脱敏输入自动重试一次；每次 Provider request 仍为 60s，
总 Provider 调用最多 2 次。首次结构错误仍最多修复一次；若超时重试后又出现结构错误，不允许第
三次调用。`AI_PROVIDER_UNAVAILABLE` 和 provider envelope 失败不重试；第二次仍超时返回脱敏
`AI_TIMEOUT`。Copilot Web 整次请求等待窗口为 130s，仅为容纳两次 60s Provider 尝试，
不改变 Provider 或其他 API timeout。评测 runner 只持久化每次尝试的脱敏状态与耗时、重试原因
和总耗时，不保存 raw Provider content 或错误。此改动后的冻结 20 条真实复跑已完成，
20/20 均首轮成功，未触发重试。

## Persistence 与 stale

`copilot_records` 是 append-only。相同 context 重新生成会创建新 ID，GET context endpoint 返回最新
记录，GET `/api/v1/copilot/{id}` 可读取历史记录。API 根据当前最小 Provider data 重新计算 SHA-256
fingerprint；不同即 `isStale: true`。来源缺失、JD Analysis 缺失或 stale 时历史记录仍可读但 stale。

## UX

Job Detail 的 AI Copilot 区域含“岗位理解 / 匹配分析 / 简历准备 / 面试准备”。每个生成命令有独立
确认、loading、错误、重试和 stale 状态；请求进行中禁用重复点击。事实明确标为 `[来自简历]`、
`[来自岗位]` 或 `[来自面试]`，建议标为 `[AI建议]`，整个结果标记“AI 生成内容”。失败不清空上次
有效结果，也不阻塞原始岗位、简历、投递和面试数据。

## Security 与错误

沿用 loopback-only、exact Origin/Host/fetch metadata、JSON-only、no credentials、no redirect、no
system proxy 与脱敏错误。稳定错误包括 `AI_NOT_CONFIGURED`、`AI_TIMEOUT`、`AI_INVALID_RESPONSE`；
既有非 timeout transport failure 为 `AI_PROVIDER_UNAVAILABLE`。日志不得包含 source text、raw model
response、Provider URL 或 API Key。

不存在后台或整份文件上传：JobPilot 不保存/上传原始 Resume 文件，也不把资料同步到 JobPilot
远端。用户点击生成并再次确认后，当前任务所需的最小简历/面试纯文本会发送到用户自行配置的
第三方 Provider；这是功能所需的显式外发，不能表述为“从不发送到第三方”。Provider 未配置或
失败时，本地核心与历史结果仍可用。

## Phase 11.1 安全复核

- **Prompt Injection / 恶意 JD**：system instruction 与不可信 Job/Resume/Interview JSON 分离；输入中要求
  改规则、泄露信息、编造经历或输出其他格式的文字仍按数据处理。虚构 injection 样本没有改变
  contract 或生成匹配分。
- **简历隐私**：Provider input 构造前移除 phone/email，不发送 Profile、其他简历、Application 状态、
  文件名、Cookie 或账号数据。用户明确选中的最小简历文本仍会发给其配置的第三方 Provider，
  不用“不上传简历”误导用户。
- **Provider 失败**：timeout/unavailable/invalid 只返回稳定脱敏错误，不含 URL、Key、envelope 或 raw
  response；失败不覆盖上次有效 Analysis，Job/Application/Resume/Interview 本地功能继续可用。
- **AI 结果泄露**：只有经 exact schema、source ownership 和 quote grounding 验证的结果写入本地 SQLite；
  无 telemetry、无远程同步、无 raw-response 日志。
- **Remote upload**：不上传 PDF/DOCX 原文件，不访问招聘网站隐藏 API；仅在用户当次确认后向已配置
  Provider 发送任务所需的脱敏纯文本。传输继续禁止系统代理和 redirect。

## 当前验收状态

20 条 BOSS/牛客风格虚构 dataset 与 real-output-only runner 的演进链：V1 13/20、V2 14/20、
变更前最终复跑 18/20，后两条 Match 因 Provider 60s 超时失败。负责人批准一次 `AI_TIMEOUT`
有界重试后，对**同一冻结 20 条**完整复跑：首轮/最终 Schema 20/20、Evidence 62/62、retry 0、
自动安全/相关性违例 0。全部在第一次请求成功；不能把结果改善归因于重试。Synthetic 内容有用性
人审仍为 NOT_RUN；原 BOSS/牛客各三项真实岗位人工生成与内容验收 6/6 PASS，Prompt/Schema/模型
未变，结果保持有效。按冻结 ≥19/20 及 evidence/safety/真实岗位门槛，**`PHASE 11 PASS`**。
Phase 7 状态不变，Phase 12 未开始。

## 前端入口收敛

2026-09-16，项目负责人批准隐藏岗位详情中的旧 Evidence Map 面板，以 Copilot“匹配分析”作为唯一
简历匹配入口。该变更仅影响 Web 可见入口：Evidence Map 历史数据、数据库迁移、后端/API client
兼容契约均保留，不删除用户数据，也不改变 Phase 7 状态。
