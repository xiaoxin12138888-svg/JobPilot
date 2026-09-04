# ADR-013：可选的 JD 结构化 AI 分析

- **Status**：Accepted
- **Date**：2026-09-04
- **Decision owner**：JobPilot 项目负责人

## Context

Phase 3 已提供本地 Job/Application，Phase 4 与 Phase 5 已验证 BOSS、牛客的用户主动采集。
现有岗位描述仍是非结构化纯文本。产品负责人批准 Phase 6 纵向增加可选的 JD 结构化分析，
并暂停新的招聘平台；本决定不授权 Resume、Evidence Map、匹配度、RAG、Agent 或模拟面试。

外部模型不是核心运行依赖。模型可能未配置、超时、不可达、限流或返回不可信内容，任何一种
情况都不能阻断 Job/Application、采集、SQLite、原始 JD 或原平台链接。

## Decision

1. 分析调用链只能是 `Web → FastAPI → JDAnalysisService → JDAnalysisProvider`。Web 与
   Extension 不接触 API Key；Extension 本阶段保持不变。
2. FastAPI 只从进程环境读取可选的 `JOBPILOT_LLM_BASE_URL`、
   `JOBPILOT_LLM_API_KEY`、`JOBPILOT_LLM_MODEL`。三项未完整、非法或缺失时 AI 视为未配置，
   FastAPI 和全部核心能力仍正常启动。Key 不进入 Git、日志、错误、SQLite、Web 或 Extension。
3. 唯一 infrastructure adapter 调用 OpenAI-compatible `POST {baseUrl}/chat/completions`，使用
   明确超时和 JSON structured output。业务层只认识 `JDAnalysisProvider`，不建立 factory、
   registry、router、SDK framework、LangChain、LangGraph 或 Agent。
4. 提交给 Provider 的输入仅包含 `title`、`company`、`description`，以及可选 `location`、
   `salaryText`。不得发送 notes、Application、其他 Job、浏览器 metadata、本地文件或未来
   Resume 数据。
5. 正式 schema version 为 `1`：`summary: string`；`responsibilities`、
   `mustHaveRequirements`、`preferredRequirements`、`experienceRequirements`、
   `educationRequirements`、`interviewFocus` 为 `EvidenceItem[]`；`skills`、
   `domainKeywords` 为 `string[]`。`EvidenceItem` 只有 `text` 与 `evidence: string|null`。
   缺失信息规范化为空字符串/空数组，正式存储不得使用 Markdown。
6. JD 是不可信数据而非指令。系统提示与 JD 数据分离，要求忽略 JD 内指令式文本，只依据输入
   提取，不补全学历、经验或技能，不把公司介绍/福利当要求，不重复同义项，并严格输出 schema。
7. Provider 内容必须依次经过 `parse → strict schema validation → normalization → deterministic
   evidence check → persist`。Evidence 在空白规范化后必须是 JD description 的子串，否则置
   `null`；非法结果绝不写入 SQLite。
8. 新增 `jd_analysis_records`，每个 Job 最多一个当前分析。保存 schema version、结构化 JSON、
   非秘密的输入指纹及时间；重新分析原位更新。删除 Job 通过 FK cascade 删除分析。
9. 输入指纹只覆盖实际发送的五个 Job 字段，不覆盖 notes、Application 或浏览器数据。读取时将
   当前输入指纹与存储值比较得到 `isStale`；旧结果保留但必须显式显示过期，不得静默当成最新。
10. API 仅新增 `GET /api/v1/jobs/{jobId}/analysis` 与
    `POST /api/v1/jobs/{jobId}/analysis`。GET 对存在的 Job 始终返回 `200`，包含
    `isConfigured` 与 nullable `analysis`，从而区分未配置、未分析、ready/stale；不存在 Job
    仍为 `404`。POST 接受严格空 JSON，创建或覆盖分析并返回同一资源形状。
11. 稳定错误为 `AI_NOT_CONFIGURED`（503）、`AI_PROVIDER_UNAVAILABLE`（503）与
    `AI_INVALID_RESPONSE`（502）。响应不包含 provider traceback、raw response、URL、Key 或
    transport 细节。
12. Job Detail 新增聚焦的“AI 岗位分析”区，呈现未配置、未分析、分析中、成功、失败与 stale，
    以及摘要、职责、硬性要求、加分项、技能、经验、学历、领域词和面试重点。Evidence 轻量显示；
    原始 JD 永远可见且不被替换。
13. 自动测试只用 Fake Provider。真实 Provider 验收和 V1/V2 评测只有在负责人提供可用配置时
    执行；不可用时必须如实标记 BLOCKED，禁止伪造结果。评测 gold label 由人工检查。

## Consequences

- JobPilot 核心继续 local-first、loopback-only、SQLite、no account、no credentials、no proxy、
  no telemetry；仅用户主动点击分析时，最小 JD 字段才可能发往显式配置的 Provider。
- 单表 JSON 与一个 Provider seam 足以支持本阶段，同时保留 schema、证据、stale 和错误边界。
- 模型品牌切换只改变环境配置和单个 adapter，不把 provider 对象传播到产品代码。
- Phase 7 与其他招聘平台仍需项目负责人另行批准。
