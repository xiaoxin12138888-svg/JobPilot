# JobPilot 产品规格

> 状态：Phase 3、Phase 4 与 Phase 5 已通过，BOSS 与牛客均为 `SUPPORTED — V1`。
> Phase 6 — JD Structured AI Analysis 已获批并实现本地核心；真实 V1/V2 评测尚未通过。

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
`confirmApplied: true`；首次进入时记录 `applied_at`。

## 5. 原平台行为

“去原平台查看/投递”只是一个安全的新窗口链接：

- 只打开该 Job 已保存的 `source_url`；
- 不自动填写、点击或申请；
- 不创建 Application；
- 不改变任何 Application 状态；
- 没有 URL 时不显示该动作。

## 6. Web

Phase 3 Web 包含：

- 本地 API checking/unavailable/retry 状态；
- 岗位库 loading/error/empty/list 状态；
- 手动岗位表单与前后端校验；
- 岗位详情、编辑和明确确认删除；
- Application 建立、显式已投递确认和状态更新；
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

## 8. 本地与 no-proxy 边界

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

## 9. Phase 6 非目标

智联、实习僧、猎聘、国聘 Adapter、通用 AI/Adapter framework、ResumeVersion、Evidence Map、
JD×Resume matching、匹配/推荐/Offer 分数、RAG、embedding、vector DB、upload、Agent/LangChain、
模拟面试、自动投递、云同步、账号、认证和多用户均不属于 Phase 6。

## 10. 成功标准

Phase 6 必须通过自动 schema/provider/persistence/stale/API/UI/security 测试，并在同一套至少 20
条、经人工审核的脱敏 gold 数据上真实运行 Prompt V1、记录 Bad Cases、据此修改 V2 并复跑。
还需对一个真实 BOSS Job 和一个真实牛客 Job 完成人工忠实度验收，同时完整回归采集、
Job/Application、SQLite restart 与 no-proxy core。没有 Provider 或人工 gold 审核时必须报告
BLOCKED，不得伪造指标。
