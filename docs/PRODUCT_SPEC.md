# JobPilot 产品规格

> 状态：Phase 3 至 Phase 6 已通过，BOSS 与牛客均为 `SUPPORTED — V1`。Phase 7 — Resume
> Version & Evidence Map 已获批并完成本地实现/自动化；真实简历外发、BOSS/牛客结果质量与重启
> 持久化仍等待项目负责人在 UI 中确认和验收。Phase 8 未获批。

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
先给出“支持”“部分支持 / 待确认”或“当前无法证明”，再显示判断依据和 grounded quote。总览只
做全图确定性计数，并列出有限的主要待确认项和证据缺口，不产生匹配率、ATS/Offer 分数或推荐。

coverage 按多段事实之间的语义关系综合判断，不要求岗位文字与简历关键词逐字相等。一项要求可由
多条各自可追溯的 quote 共同支持；明确事实无需额外假设即可完整证明时为 DIRECT，需要假设或证据
不完整时为 PARTIAL，并在 reason 中说明推理和缺口。允许依据明确日期做简单、透明的时间推算；
例如可结合教育入学时间、明确学历层次和通常学制推算毕业届别，但未明确写出毕业/结束时间时最多
只能是 PARTIAL。不得据此推断工作年限、经历连续性或其他未写明事实。

每个 Job + Resume Version 只保留一个当前结果。JD Analysis 或 Resume content 变化后旧结果保留
但标为 stale；重新生成失败保留最后一个有效结果及 stale 状态，不暴露 Provider 原始错误。

## 10. 本地与 no-proxy 边界

- Web、Extension 与 API 只通过精确 loopback 通信；
- installed runtime 不依赖账号、云服务、CDN、远程字体/脚本、telemetry、update 或境外 AI；
- JobPilot API 不请求或代理招聘网站；
- Extension 使用 `activeTab` + `scripting` 在用户点击后对当前 tab 执行一次只读解析；没有
  招聘网站 host permission、`tabs` permission、background 或常驻 content script；
- Extension Manifest 通过可公开公钥固定 ID；API 只允许该精确 Extension Origin 与
  `Sec-Fetch-Site: none` 组合写入 Job create，其他资源和 Extension ID 不受信任，Extension
  Origin 不加入 CORS；
- 测试只使用显式临时数据库，不读取、替换或删除 `runtime-data/jobpilot.db`。
- 外部 LLM 只属于显式启用的可选增强，Key 仅存在 FastAPI 进程环境；Web/Extension 不持有 Key，
  本地核心不依赖 Provider，也不修改系统或浏览器代理。
- 简历默认只在本机 SQLite；任何 Evidence Map 外发都要求用户在当次 Web 操作中确认。

## 11. Phase 7 非目标

PDF/DOCX/图片/OCR、文件上传、简历生成/整份改写、ATS/匹配/Offer 分数、推荐、RAG、embedding、
vector DB、Agent/LangChain、模拟面试、自动投递、新招聘平台、云同步、账号、认证和多用户均不
属于 Phase 7。

## 12. 成功标准

Phase 7 必须通过 Resume/Application/Evidence schema、grounding、stale、persistence、API/UI、
privacy/security 自动测试及全部既有回归。项目负责人还需在 UI 粘贴一份脱敏真实简历，对一个
已有有效分析的 BOSS Job 和一个牛客 Job 分别确认外发并人工判断六类条件数量、逐项明确结论、
quote grounding、coverage/reason 质量、全图总览和无数字分数；随后验证 Application 关联与
API/Web 重启持久化。
缺少用户确认或人工判断时必须报告 BLOCKED，不得代替负责人宣称 PASS。
