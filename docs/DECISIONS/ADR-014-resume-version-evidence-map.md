# ADR-014：简历版本与可追溯证据映射

- **Status**：Accepted
- **Date**：2026-09-05
- **Decision owner**：JobPilot 项目负责人

## Context

Phase 6 已把用户保存的 JD 转换为严格、可追溯的结构化要求，但仍不能回答“当前简历中的哪段
真实经历能够证明这项要求”。项目负责人批准 Phase 7，以纯文本简历版本、投递所用版本记录和
逐要求 Evidence Map 完成这条纵向链路。目标是可解释和可追溯，不是产生匹配分或自动改写简历。

简历包含敏感个人信息，JD 与简历文本也都可能包含 prompt injection。外部 Provider 仍是可选
增强，任何失败都不得阻断 Job、Application、简历版本管理、已存结果或本地 SQLite。

## Decision

1. 新增 `ResumeVersion`，字段固定为 `id`、`name`、`content`、`createdAt`、`updatedAt`。
   V1 只允许用户手动录入或粘贴纯文本，并提供创建、查看、编辑/重命名、复制和删除；不支持
   PDF、DOCX、图片、OCR、上传、模板、富文本或版本树。
2. `Application` 增加 nullable `resumeVersionId`。只有用户显式保存选择、更换或清空时更新；
   保存 Job、创建 Application、生成 Evidence Map 都不会自动选择或创建 Application。
3. 被任何 Application 引用的简历版本不能删除，返回稳定 `RESUME_VERSION_IN_USE`（409）。
   未引用版本可删除，关联 Evidence Map 通过 FK cascade 清理。
4. 新增 `EvidenceMapRecord`；一个 `(job_id, resume_version_id)` 只有一个当前记录，保存 schema
   version、严格 JSON、JD analysis fingerprint、Resume content fingerprint 与时间。重新生成原位
   更新；删除 Job 或未被 Application 引用的 Resume 时级联。
5. Evidence Map schema version 1 只有 `mappings`。每项只有 `requirementType`（`MUST_HAVE` 或
   `PREFERRED`）、`requirementText`、`coverage`（`DIRECT`、`PARTIAL` 或 `GAP`）、
   `resumeEvidence: [{quote}]` 和 `reason`。不包含任何 numeric score、推荐或 Offer 概率。
6. Requirement 集合和顺序只能来自当前、非 stale JD Analysis 的 `mustHaveRequirements` 与
   `preferredRequirements`。Provider 不能新增、删除、合并、改写或改变类型；缺失或 stale 分析
   必须拒绝生成，并保留已有记录。
7. Provider quote 经 whitespace normalization 后必须是所选 `ResumeVersion.content` 的子串。
   无效 quote 删除；DIRECT/PARTIAL 最终没有有效 quote 时确定性降级为 GAP。GAP 只表示当前简历
   未找到证据，不表示用户没有能力。coverage 按多段 grounded facts 的语义关系综合判断，不要求
   关键词逐字相等；明确事实无需假设即可完整成立时为 DIRECT，需要假设或证据不完整时为
   PARTIAL。允许简单、透明的日期推理；教育入学时间、明确学历层次与通常学制可支持毕业届别
   推算，但没有明确毕业/结束时间时最多为 PARTIAL，reason 必须披露所用事实、假设和结论。
8. 对 Provider 的输入仅包含 Job title、可选 company、当前 JD Analysis 的两类要求，以及用户
   明确选择的一个 Resume content；不发送原始招聘页 HTML、完整 JD、notes、Application、其他
   Job/Resume、浏览数据或本地文件。JD requirement 与 Resume 都作为不可信数据放在 user data，
   不进入 system instruction。
9. Evidence Map 复用 Phase 6 的三个环境变量、一个 OpenAI-compatible adapter、60 秒后端请求
   timeout、redirect rejection、no system proxy 和稳定脱敏错误；不建立第二套 Provider 配置、
   registry、framework、RAG、embedding、vector DB 或 Agent。
10. `GET /api/v1/jobs/{jobId}/evidence-map?resumeVersionId=...` 只读本地结果并计算 stale；
    `POST /api/v1/jobs/{jobId}/evidence-map` 要求明确的 `resumeVersionId` 和 `confirmExternalAi:true`。
    第一次及每次真实发送都必须由 UI 当次明确确认，不建立隐式或永久 consent。
11. stale 由当前 JD Analysis fingerprint 与 Resume content fingerprint 确定。输入改变后旧结果保留
    但明确标为 stale；重新生成失败绝不覆盖最后一个有效结果。
12. Web 新增最小“简历版本”页面、Job Detail“简历证据匹配”区和 Application 简历选择器。
    UI 必须覆盖未选择、JD 缺失/stale、未配置、生成中、成功、失败与 Evidence stale；纯文本仅按
    文本渲染，不使用 `dangerouslySetInnerHTML`。总览仅由 mappings 确定性统计三类数量。
13. 自动测试只使用虚构/脱敏简历。真实外部 AI 验收前，负责人必须在 UI 粘贴脱敏简历并主动
    确认；Codex 不读取其他本地简历文件，也不替代 BOSS/牛客人工忠实度结论。

## Consequences

- JobPilot 获得 `Requirement → Resume Evidence → Coverage → Application Resume Version` 的
  本地可追溯闭环，同时继续保持 single-user、local-first、no-auth、loopback-only。
- 两个新增表和一个 nullable FK 是本阶段全部持久化增量；不建立历史、评分或内容解析系统。
- Provider 不可用只影响 Evidence Map 生成；本地简历 CRUD、关联、已有 JD/证据结果和全部既有
  功能继续可用。
- Phase 8 及任何简历生成、Tailoring、文件解析、推荐、面试或自动投递必须另行批准。
