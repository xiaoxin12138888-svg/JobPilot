# JobPilot Roadmap

> 当前阶段：Phase 6 已于 2026-09-05 完成并通过。Phase 7 — Resume Version & Evidence Map
> 保持 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。Phase 8 — Interview Record & Feedback Loop
> 已于 2026-09-07 完成并通过自动化、隔离浏览器、真实 runtime、重启持久化、既有回归和安全验收。
> Phase 9 — Profile Vault & Safe Job Form Autofill 已于 2026-09-07 完成实现、自动化验证和真实
> 中国移动校招表单人工验收并标记 PASS。BOSS 与牛客保持 `SUPPORTED — V1`。
> Phase 10 — Local Resume Import 已完成实现、自动化门禁和虚构文件隔离浏览器验收，等待真实
> DOCX/PDF 人工内容与合并验收；此前不得标记 PASS。
> Phase 7 Evidence Map 的独立 Web 面板已于 2026-09-16 隐藏，历史数据/API 兼容保留，Phase 7
> 仍为 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`；当前匹配入口统一为 Copilot。
> Phase 11 — AI Job Copilot P0/V2 已完成技术实现、三样本预检和真实 20 条虚构集评测。Provider
> 完成 14/20，收到的 14 条结果最终均通过 Schema/Evidence，但合并结果未达 19/20 门槛。V2
> BOSS/牛客人工生成与内容验收已于 2026-09-16 达到 6/6 PASS；synthetic 门槛仍阻止 Phase 11
> 标记 PASS 或进入 Phase 12。

## 1. Global gates

每个阶段依次完成：

```text
规格/ADR -> failing behavior test -> minimal implementation -> verification
-> code review -> simplification -> documentation -> explicit acceptance
```

所有阶段保持 single-user、single local workspace、loopback API、SQLite、no-account、
no-cloud-default、P0 中国大陆普通网络 no-proxy，并且不提前实现后续 Phase。

## 2. Completed foundations

- Phase 0：产品和架构基线；
- Phase 1：Web/Extension/API/共享包与工程门禁；
- Local-first reset：ADR-008 移除远程身份方向并保留历史 checkpoint；
- Phase 2.5：ADR-009、SQLite launcher、health timeout、Extension health Popup、真实 Chrome
  与 no-proxy 基线。

## 3. Phase 3 — Job & Application Domain Foundation

负责人批准的新方向用 ADR-010 取代旧 Roadmap 中“Phase 3 先做 Adapter、Phase 4 再做
Application”的排序。本阶段交付：

- `jobs` / `applications` migration、约束、repository 与 service；
- Job CRUD、URL 规范化去重、keyword/source/Application status 筛选和 limit/offset；
- 一岗一个 Application、显式 applied 确认和有限状态更正；
- shared types 与严格校验的 loopback api-client；
- Web 岗位库、手动录入、详情、编辑/删除和投递状态；
- 自动化、真实浏览器、重启持久化、no-proxy、安全、审查与简化门禁。

Extension 在本阶段保持 health-only；没有 Adapter、content script、`activeTab` 或招聘站点权限。

## 4. Phase 4 — BOSS Direct Job Capture

状态：Completed（2026-09-04）。

只实现 BOSS 直聘：`activeTab` + `scripting` 用户主动触发当前岗位页 DOM 读取、可编辑确认预览、
复用 Job API 保存、重复岗位处理、Web source 展示和真实 no-proxy 验收。没有 BOSS host
permission、常驻 content script、background、后台爬取、列表扫描、隐藏 API、登录/验证码/
风控绕过或 Application mutation。

## 5. Phase 5 — Nowcoder Adapter & Shared Capture Contract

状态：Completed（2026-09-04）。

只新增牛客具体岗位详情页 Adapter，并与 BOSS 共用 `JobCaptureDraft/JobCaptureResult`、Popup
预览编辑、Job API、duplicate 和 source label。当前 tab 使用显式两平台分派，没有 factory、
registry、持久 content script、招聘网站 host permission、隐藏 API 或 Application mutation。
平台 detection、selectors 与 DOM helpers 继续留在自包含注入函数内。真实无代理牛客完整流程和
BOSS 回归均已通过。

## 6. Phase 6 — JD Structured AI Analysis

状态：Completed（2026-09-05）。

暂停横向 Adapter 扩展。对已保存 Job 增加用户主动触发的可选结构化分析、strict schema、
evidence grounding、单条 SQLite 持久化、stale/reanalysis 与 Job Detail 状态展示。Provider 未配置
或失败不影响本地核心。Resume、Evidence Map、matching、RAG、Agent 与模拟面试不进入本阶段。

自动实现、Fake Provider 回归、20 条脱敏 gold 人工审核、真实 Prompt V1/V2 与 Bad Cases
对比，以及真实 BOSS/牛客 Web AI 人工验收均已完成。牛客结果保留一条非阻塞的 `and` 中英
混排 Bad Case；未修改冻结指标，也未创建 Prompt V3。Phase 6 标记为 PASS。

## 7. Phase 7 — Resume Version & Evidence Map

状态：`IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`（Phase 7C 语义证据修正已实现；负责人暂停
真实 BOSS/牛客语义质量结论）。

只交付本地纯文本 Resume Version、Application 显式记录本次实际使用版本，以及当前 JD
requirements 到所选 Resume 原文的 Evidence Map。新生成的 schema 2 综合硬性要求、加分项、
职责、技能、经验和学历六类条件；旧 schema 1 继续可读。Coverage 固定为 DIRECT/PARTIAL/GAP，
quote 必须 grounded，每项先显示明确结论，总览只做确定性计数、待确认项和主要证据缺口。真实
简历仅在用户当次 UI 确认后发送到 Phase 6 的同一可选 Provider；失败不影响本地 CRUD、
Application、已存分析或最后一个有效 Evidence。

Phase 7C 冻结 Semantic Match, Grounded Evidence：Prompt 必须理解条件含义并扫描完整简历，允许
从不同 section 组合一至三条真实原文，不因措辞不同判 GAP；同时禁止用外部常识补全未写的能力、
年限、学历、毕业年份或项目事实。真实人工验收发现旧结果过度字面化，因此 Phase 7 不能在新的
BOSS 与牛客语义结果由负责人确认前标记 PASS。

不做文件解析/OCR、简历生成/整份改写、分数/推荐、RAG/embedding/vector DB、Agent、模拟面试、
自动投递或新招聘平台。只有真实 BOSS/牛客 Evidence 质量、Application 关联与重启持久化均由
项目负责人确认后，Phase 7 才能标记 PASS。

## 8. Phase 8 — Interview Record & Feedback Loop

状态：PASS（2026-09-07）。

只交付完全本地的 Interview Round/Question、手动回答与自我复盘、Application 结果说明/用户记录的
淘汰原因，以及请求时从 SQLite 计算的事实 Feedback Summary。面试行为不自动改变 Application，
结果说明不建立第二套 Offer/Outcome 模型，Feedback 不持久化派生结果、不调用 Provider、不产生
AI 评分、建议或因果结论。

漏斗原始数量保持事实；相邻分母为零或因漏记中间阶段而出现后一阶段大于前一阶段时，转化率为
null，不显示 0% 假象或超过 100% 的结果。题目分类、自评、弱项、淘汰原因、来源和简历版本分组
均为确定性计数。整个 Phase 在所有 `JOBPILOT_LLM_*` 缺失时完整工作，且不读取简历正文。

自动化与隔离验收覆盖源码、临时 migration/API/Web 重启、浏览器录入一轮三题、手动复盘、
Application 结果、Feedback 数量与 320/768/1024/1440 布局。真实验收将 8001 安全恢复到当前
API，并以标准 Alembic migration 升级原有 `runtime-data/jobpilot.db`；旧数据数量保持不变。
验收复用了现有 Nowcoder Application，没有创建重复记录；轮次创建、三题创建与编辑、四项自我
复盘、完成/取消状态边界、确定性 Feedback、重启持久化、PATCH null 422、既有功能与安全回归均
通过，Application 状态未被面试操作隐式改变。

## 9. Phase 9 — Profile Vault & Safe Job Form Autofill

状态：`PASS`（2026-09-07）。

交付 single-user 本地 `AutofillProfile`、Web“求职资料”、Extension 当前表单 Scanner、有限规则
Resolver、遮罩 Preview、用户勾选确认与 Safe Fill Executor。Extension 继续只有 `activeTab`、
`scripting` 和精确 loopback host；不增加 storage、background、常驻 content script 或招聘网站
host permission。Profile 与 Resume/Application 独立，只存 SQLite 并在 Extension 中保持当次
Popup 内存。

`Scan != Fill != Submit`：Scanner 不读字段现值、不改页面；Resolver 只把精确/规范化结果设为
READY，fuzzy 必须人工确认，敏感/文件/勾选/未知项不自动填；Executor 复核 URL/ref/signature，
只使用 DOM 原生 setter 与标准事件，无法唯一确认 option 时失败关闭。它不调用 LLM、私有框架
API、form.submit/requestSubmit、Submit/Continue，也不创建或更新 Application。

自动实现、单元/组件/安全产物门、本地 fixture 浏览器验证和全部仓库回归已完成。真实中国移动
校招表单检测 37 个字段（READY 1、REVIEW_REQUIRED 2、MANUAL 26、UNMAPPED 8），仅选择并成功
填写 1 个姓名字段；attempts/success/failure 为 1/1/0，`Submit triggered: NO`。负责人确认映射、
建议值、页面结果和无意外动作，Phase 9 标记 PASS。Phase 10 随后由负责人另行明确批准，不改变
当时的 Phase 9 验收事实。

## 10. Phase 10 — Local Resume Import

状态：`IMPLEMENTED — REAL RESUME ACCEPTANCE REQUIRED`（2026-09-07）。

只交付用户选择的 10 MiB 内文字型 PDF/DOCX → 本地 Parse → 可编辑 Preview → 显式 Confirm →
Resume Version / selected-only Profile merge。Parse 不保存、不使用 filename；原文件不保留。PDF
无文字/加密和 DOCX ZIP/XML 风险稳定拒绝，不使用 OCR、LLM 或远端 parser。

Profile 冲突显示 Current vs Imported，scalar 逐字段选、数组逐条追加；deterministic equality 只
提示可能重复。Resume + Profile 使用一个 SQLite transaction，失败回滚。Extension、Job、
Application、Evidence Map 和 Phase 9 Autofill 保持不变。

全量自动化与虚构文件隔离浏览器链路已完成；仍必须由负责人分别检查一份脱敏 DOCX/PDF 的原文
顺序、section、候选字段，以及真实保存/合并/重启结果。此前只能报告
`USER ACTION REQUIRED — REAL RESUME IMPORT ACCEPTANCE`。

## 11. Phase 11 — AI Job Copilot

状态：`IMPLEMENTED — PROVIDER EVALUATION AND HUMAN ACCEPTANCE REQUIRED`。

P0 只在 Job Detail 交付岗位匹配、简历准备与面试准备；岗位理解复用 JD Analysis。用户逐次确认
后，系统才把当前任务需要的最小 Job/Resume/Interview 文本发送到其配置的 Phase 6 Provider，
并在发送前移除 phone/email。所有事实结论必须引用真实本地 source；非法 quote、能力断言、
虚构经历或确定性面试问题稳定拒绝。结果 append-only、fingerprinted、stale-aware；失败保留上次
有效结果且不影响任何本地核心。

20 条 BOSS/牛客风格虚构数据已使用 `[K12]gemini-3.5-flash`、temperature 0 和 60s timeout
完成 V1/V2 真实评测。V2 预检 3/3；正式 run 的 Provider availability 为 14/20，first-pass schema
为 13/20，一条经结构修复后 final schema 为 14/20。有效结果 evidence 43/43，自动检出的 unsupported、
错误 gap、虚构建议、过度确定和错误 AI category 均为 0。由于合并 final 未达 19/20 且 V2 真实
BOSS/牛客验收待完成，Phase 11 继续 `BLOCKED`。

Phase 11 不包含 P1 求职策略、Chat Agent、长期记忆、RAG/embedding/vector DB、评分/Offer 概率、
自动改写简历、自动投递、自动消息或招聘网站操作。

## 12. Later phases

模拟面试、Personal Knowledge Base、其余招聘平台、P1 策略建议与发布加固必须由负责人
另行明确批准。远程能力必须显式启用、可替换、可降级，不能成为本地
Job/Application/Resume/Interview 核心依赖。

## 13. P0 no-proxy gate

installed runtime 不访问远程身份、公共 CDN、远程字体/脚本、GitHub runtime/raw、telemetry、
update 或强制境外 AI。未来每个 Adapter 必须分别记录招聘页、Extension、识别、解析、
确认保存和岗位库的真实关闭代理结果；任一核心步骤依赖代理就不能标为支持。

## 14. Stop boundary

不得把暂停中的 Phase 7 或未完成真实验收的 Phase 11 写成 PASS，也不得进入 Phase 12、实现 AI
Autofill、OCR/AI Resume Parser、Resume Builder/Tailoring、模拟面试、策略推荐或
智联/实习僧/猎聘/国聘等其他平台。
