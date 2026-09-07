# JobPilot 产品规格

> 状态：Phase 3 至 Phase 6 已通过，BOSS 与牛客均为 `SUPPORTED — V1`。Phase 7 — Resume
> Version & Evidence Map 为 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。Phase 8 — Interview
> Record & Feedback Loop 已于 2026-09-07 完成并通过自动化、隔离浏览器、真实 runtime、重启
> 持久化、既有回归和安全验收。Phase 9 — Profile Vault & Safe Job Form Autofill 已完成实现与
> 自动化验证，真实 ATS 的人工映射与页面结果验收仍待完成。

## 1. 产品定位

JobPilot 是个人求职者安装在自己电脑上的本地优先求职工作台。招聘平台继续负责岗位发现、
账号登录、沟通和正式投递；JobPilot 负责保存用户确认过的本地岗位快照与真实求职进度。

一个安装实例就是一个本地 workspace：无 JobPilot 账号、无云租户、无认证、无多用户，
业务数据只写入本机 SQLite。

## 2. 当前用户流程

```text
手动添加岗位 -> 岗位库 -> 岗位详情 -> 建立计划投递
-> 用户确认已在原平台投递 -> 跟踪筛选/测评/面试/结果
```

即使没有任何招聘网站 Adapter，用户也能完成整个本地管理流程。

Phase 4/5 新增两条共享同一产品流程的受控入口：

```text
用户主动打开具体 BOSS 或牛客岗位页 -> Popup 中点击读取 -> 对应 Adapter 解析当前可见 DOM 纯文本
-> 确认/编辑预览 -> POST /api/v1/jobs -> SQLite -> 岗位库/详情
```

Popup 打开时只检查本地 API，不自动读取页面。采集失败可打开 JobPilot 手动添加。

Phase 6 在保存后增加一条可选流程：

```text
岗位详情 -> 用户点击“AI 分析此岗位” -> FastAPI -> 显式配置的 Provider
-> strict schema/evidence 校验 -> SQLite -> 岗位详情结构化结果
```

不点击、未配置或分析失败时，原 Job/Application/采集与 JD 查看流程不受影响。

Phase 7 在结构化 JD 后增加可解释证据链：

```text
创建纯文本 Resume Version -> 选择一个已有有效 JD Analysis 的 Job
-> 选择一个 Resume Version -> 当次确认外部 AI 数据发送
-> Requirement -> Resume 原文证据 -> DIRECT / PARTIAL / GAP
-> 用户在 Application 中另行记录本次实际使用的 Resume Version
```

Evidence Map 选择不会自动改写 Application，Application 的简历选择也不会自动触发 AI。

Phase 8 增加完全本地的面试与事实复盘链路：

```text
已有 Application -> 添加面试轮次 -> 记录实际问题/回答摘要/自评 -> 手动复盘并标记轮次完成
-> 用户另行更新 Application 状态与结果说明 -> 求职复盘读取 SQLite 当前事实统计
```

Interview 行为不自动改变 Application；Feedback Summary 不调用 Provider、不保存派生结果。

Phase 9 增加不依赖 Provider 的本地资料与安全填写流程：

```text
Web 维护本机 AutofillProfile -> 用户打开招聘申请表 -> 点击 Extension 扫描
-> 确定性 Resolve -> Preview 中确认/取消 -> 点击填写已确认字段
-> 用户检查页面 -> 用户自己点击招聘网站 Submit
```

`Scan != Fill != Submit` 是 P0 边界。扫描不读取字段当前值、不修改页面；填写只处理 Preview 中
被用户确认的非敏感字段；JobPilot 永不自动 Submit、Continue、勾选协议、上传文件或改变
Application。

## 3. Job

Job 是用户主动保存的岗位快照，包含职位、公司、地点、薪资文本、来源、原平台 URL、
JD、备注和本地时间。来源允许 `manual`、`boss` 与 `nowcoder`。

- title 与 company 必填，输入统一去除首尾空白；
- source URL 只接受不带凭据的 HTTP/HTTPS；
- URL 规范化 scheme、host、默认端口并移除 fragment，规范化结果在本地唯一；手动来源保留有意义的 query，BOSS 与牛客来源只保存经过严格 hostname/path 校验的岗位详情 URL，并移除 tracking/session query；
- 没有 URL 时不做 company/title 模糊去重，允许保存相似岗位；
- description 是本地快照，原岗位下架后仍保留；
- 删除必须由 Web 明确确认，并同时删除该 Job 的 Application；当前没有归档/恢复系统。

岗位库默认按最近更新时间排序，支持职位/公司/地点关键字、来源和投递状态筛选。

## 4. Application

Application 表示一个 Job 的真实求职进度。一个 Job 最多一个 Application，建立时为
`planned`。正式状态及中文文案：

| 状态 | 中文 |
| --- | --- |
| `planned` | 计划投递 |
| `applied` | 已投递 |
| `screening` | 筛选中 |
| `assessment` | 笔试/测评 |
| `interviewing` | 面试中 |
| `offer` | Offer |
| `rejected` | 淘汰 |
| `withdrawn` | 已放弃 |
| `closed` | 岗位关闭 |

状态使用小型显式流转表，并允许少量相邻状态更正。每次进入 `applied` 都要求
`confirmApplied: true`；首次进入时记录 `applied_at`。`resumeVersionId` 默认为 null，只有用户在
已有 Application 上明确选择并保存时才设置，也可明确清空或更换。

`outcomeNote` 是用户手动填写的结果说明，在 `offer`、`rejected`、`withdrawn` 或 `closed` 时
显示，也可为空；它同时承载最小 Offer 说明，不创建第二套 Offer 模型。`rejectionReason` 只在
`rejected` 时允许使用，分类来自固定枚举，离开淘汰状态时自动清空。界面必须明确说明淘汰原因是
用户记录的已知情况或自我判断，不是系统判定。

## 5. 原平台行为

“去原平台查看/投递”只是一个安全的新窗口链接：

- 只打开该 Job 已保存的 `source_url`；
- 不自动填写、点击或申请；
- 不创建 Application；
- 不改变任何 Application 状态；
- 没有 URL 时不显示该动作。

## 6. Web

当前 Web 包含：

- 本地 API checking/unavailable/retry 状态；
- 岗位库 loading/error/empty/list 状态；
- 手动岗位表单与前后端校验；
- 岗位详情、编辑和明确确认删除；
- Application 建立、显式已投递确认和状态更新；
- 纯文本 Resume Version 新建、查看、编辑/重命名、复制和受引用保护的删除；
- Application 实际使用 Resume Version 的显式选择、保存和清空；
- 面试轮次创建、编辑、完成、取消/删除，实际问题 CRUD、回答摘要、表现自评和手动复盘；
- Application 结果说明与用户填写的淘汰原因；
- `求职复盘` 的 loading/error/retry/empty/populated 状态和事实统计；
- `求职资料` 的 loading/error/empty/edit/save、多教育/经历条目和本机隐私说明；
- Job Detail 的 JD Analysis 与 Evidence Map 前置、确认、loading、success、stale、error/retry；
- 320/768/1024/1440 响应式布局与键盘可访问控件。

不建设复杂 Dashboard 或拖拽看板。

## 7. AI 岗位分析

分析结果包含岗位摘要、核心职责、硬性要求、加分项、技能关键词、经验要求、学历要求、
业务/领域关键词与面试准备重点。缺失信息为空，不允许补全匹配度、Offer 概率或其他伪精确分数。

只发送 title、company、description 与可选 location/salaryText。JD 是不可信数据；其中的指令式
文本不能改变系统任务。结果必须通过 strict JSON schema 与 evidence 子串检查，非法结果不持久化。
每个 Job 保存一个当前分析；分析输入发生变化时旧结果保留但显示 stale，重新分析原位更新。

Web 必须覆盖未配置、未分析、分析中、成功、失败和 stale。Evidence 可轻量展开；原始 JD 始终
可见。Provider 未配置、超时、限流、不可达或 malformed 只影响本区块。

## 8. Resume Version

Resume Version 是保存在本机 SQLite 的独立纯文本版本，字段只有名称、正文和本地时间；不读取
PDF/DOCX/图片，不提供 OCR、富文本、模板、版本树、自动生成或整份改写。用户可新建、查看、
编辑/重命名和复制。若任何 Application 正在引用该版本，删除返回稳定
`RESUME_VERSION_IN_USE`；未引用版本可删除并级联对应 Evidence Map。

简历正文按不可信纯文本处理，不写日志、Extension、telemetry、Git、文档或真实测试 fixture。

## 9. Evidence Map

生成前要求 Job、当前非 stale JD Analysis、用户所选 Resume Version、已配置 Provider，以及
本次操作的明确外发确认。发送数据只含必要岗位上下文、当前硬性要求、加分项、岗位职责、技能、
经验、学历六类条件和所选简历正文；不发送摘要、领域关键词、面试重点、原始页面 HTML、完整 JD、
notes、Application、其他 Job/Resume 或文件。

每条 mapping 保留原 requirement 类型/文本，并只使用 `DIRECT`、`PARTIAL`、`GAP`：DIRECT 是
简历中存在可直接支持要求的原文，PARTIAL 是存在相关但不完整的原文，GAP 只表示当前所选简历
未找到证据。quote 经空白规范化后必须是简历正文子串；无有效 quote 的 DIRECT/PARTIAL 确定性
降级为 GAP。新生成记录使用 schema version 2；已有 schema version 1 的 must-have/preferred
记录仍可读取，并在六类条件指纹下显示 stale，成功重新生成后原位升级。六类条件分组展示；每项
先给出“直接证据”“部分支持 / 待确认”或“当前无法证明”，再显示判断依据和 grounded quote。总览只
做全图确定性计数，并列出有限的主要待确认项和证据缺口，不产生匹配率、ATS/Offer 分数或推荐。

coverage 按多段事实之间的语义关系综合判断，不要求岗位文字与简历关键词逐字相等。一项要求可由
完整简历不同 section 中一至三条各自可追溯的 quote 共同支持；这些事实无需补充用户事实即可完整
证明时为 DIRECT，存在明显相关事实但缺少关键组成部分或需用户确认时为 PARTIAL，扫描完整简历
仍无合理支持事实时才为 GAP。不得通过外部知识补全或升级能力等级、工作年限、学历、毕业年份、
项目规模、经历连续性或其他未写事实。只有明确毕业年份、预计毕业时间或培养年限才能支持届别；
仅有入学时间和在读状态时最多为 PARTIAL，reason 必须指出缺少的毕业信息，不能推导目标毕业年份。

每个 Job + Resume Version 只保留一个当前结果。JD Analysis 或 Resume content 变化后旧结果保留
但标为 stale；重新生成失败保留最后一个有效结果及 stale 状态，不暴露 Provider 原始错误。

## 10. Interview Record

每个 Application 可以有多轮面试。轮次包含名称、`PHONE|VIDEO|ONSITE|OTHER` 类型、可选计划
时间、`PLANNED|COMPLETED|CANCELLED` 状态、面试官备注，以及“做得好的地方”“没答好的地方”
“需要补充学习”“其他备注”四个可选自我复盘字段。创建、完成、取消或删除轮次都不推断或修改
Application 状态。

每轮可记录多道实际问题。问题包含七类手动分类、用户自己的回答摘要、
`GOOD|OK|POOR|NOT_SURE` 自评和备注。轮次删除前必须明确确认，并级联删除该轮问题；全部内容
按不可信纯文本处理，只保存在本机 SQLite，不进入 Extension、日志、Provider 或真实测试 fixture。

## 11. Factual Feedback Summary

`求职复盘` 每次直接查询 SQLite，展示已保存岗位、Application、至少有一轮面试的岗位、轮次、
题目、Offer 与淘汰数量，并按题目分类、自评、弱项类别、淘汰原因、简历版本和岗位来源分组。
高频薄弱类别只把 `OK + POOR` 计为弱项，并按弱项数、该类题目总数和固定 enum 顺序排序。

漏斗固定为保存岗位 → Application → 有面试记录的 Application → 当前 Offer。转化率以前一个
阶段为分母；分母为零或由于用户漏记中间事实而出现后一阶段大于前一阶段时返回 null，界面不
显示 0% 假象或超过 100% 的误导值。原始计数不截断、不补推缺失事实。统计不产生评分、推荐、
策略或不同来源/简历版本之间的因果结论。

## 12. Profile Vault 与安全自动填写

`AutofillProfile` 是 single-user singleton 本地资源，与 Resume Version 和 Application 独立。
字段仅包含 name/phone/email/currentCity，多条 education 与 experience，以及 GitHub/作品集/
个人主页链接；默认不收集身份证、护照、银行卡、婚姻、民族、政治面貌、家庭地址等低价值敏感
事实。Web 可查看、编辑并完整替换，Extension 不持久化 Profile。

用户点击“扫描当前表单”后，Scanner 只返回有界的 `FormFieldDescriptor`；password、验证码、
hidden、disabled、submit 与 JobPilot 自身控件被忽略。Ref 依次使用唯一 id、唯一 name 或可回溯
DOM path。Resolver 只使用有限 alias 与规范化规则：精确/规范化为 `READY`，唯一模糊候选为
`REVIEW_REQUIRED`，敏感/缺值/不可填写为 `MANUAL`，未知为 `UNMAPPED`。Preview 默认只勾选
READY，phone/email 仅显示遮罩值。

Fill Executor 再次核对 URL、唯一 ref、字段签名、可见性与禁用/只读/敏感策略。文本使用原生
setter 和 focus/input/change/blur；native select、month/date 与 combobox 只有唯一明确 option
时填写，否则失败关闭。FILE、radio/checkbox、协议、法律、隐私、薪资、证件和验证码不自动
填写。实现不调用框架私有状态、`form.submit()`、`requestSubmit()`、Submit/Continue 按钮，也不
创建或更新 Application。当前真实 ATS 人工验收完成前，Phase 9 不标记 PASS。

## 13. 本地与 no-proxy 边界

- Web、Extension 与 API 只通过精确 loopback 通信；
- installed runtime 不依赖账号、云服务、CDN、远程字体/脚本、telemetry、update 或境外 AI；
- JobPilot API 不请求或代理招聘网站；
- Extension 使用 `activeTab` + `scripting` 在用户点击后对当前 tab 执行一次只读解析；没有
  招聘网站 host permission、`tabs` permission、background 或常驻 content script；
- Phase 9 的 Fill 是另一次明确点击后的有界页面写入，只处理 Preview 已确认字段并在 Submit 前
  停止；它不改变 BOSS/牛客采集 Adapter 的只读边界；
- Extension Manifest 通过可公开公钥固定 ID；API 只允许该精确 Extension Origin 与
  `Sec-Fetch-Site: none` 组合写入 Job create，其他资源和 Extension ID 不受信任，Extension
  Origin 不加入 CORS；
- 测试只使用显式临时数据库，不读取、替换或删除 `runtime-data/jobpilot.db`。
- 外部 LLM 只属于显式启用的可选增强，Key 仅存在 FastAPI 进程环境；Web/Extension 不持有 Key，
  本地核心不依赖 Provider，也不修改系统或浏览器代理。
- 简历默认只在本机 SQLite；任何 Evidence Map 外发都要求用户在当次 Web 操作中确认。
- Autofill 不调用 LLM 或远程 parser；Profile 只从精确 loopback API 读取并保留在当次 Popup 内存。

## 14. Phase 9 非目标

PDF/DOCX/图片/OCR、自动上传简历、从 Resume 自动导入 Profile、开放题生成、AI 字段识别、
Resume Tailoring、通用 ATS Engine、平台专用 Autofill Adapter、自动 Submit/Continue/协议同意、
验证码绕过、批量投递、新招聘平台、云同步、账号、认证和多用户均不属于 Phase 9。

## 15. 成功标准

Phase 8 必须通过 Interview/Application/Feedback schema、CRUD、cascade、统计、API/UI、
provider-free、privacy/security 自动测试和全部既有回归。浏览器验收必须录入至少一轮、三道
虚构/历史问题、回答自评、手动复盘与 Application 结果，核对 Feedback 分类、表现、来源、简历
版本和重启持久化，并检查 320/768/1024/1440 与键盘焦点。

Phase 7 的真实语义质量验收保持独立暂停，Phase 8 不得把它改写为 PASS。Phase 8 已在加载最新
migration/API 的真实 runtime 中复用现有 Application 完成一轮三题、编辑、自我复盘、完成/取消
边界、确定性 Feedback、重启持久化、PATCH null 422、既有功能与安全验收；没有创建重复
Application，也没有由面试动作隐式改变 Application 状态。

Phase 9 只有在 Profile 持久化、Scanner/Resolver/Preview/Executor、Provider 未配置、全部安全与
既有回归、真实 ATS Scan/Fill（不 Submit）以及项目负责人对映射和页面结果的确认全部完成后，
才能标记 PASS。当前自动实现完成，真实 ATS 人工 Gate 仍待执行。
