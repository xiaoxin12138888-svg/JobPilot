# JobPilot 产品规格

> 状态：Phase 3 已通过。Phase 4 — BOSS Direct Job Capture 已获负责人批准，contract 已冻结，
> 正在 `phase/4-boss-job-capture` 实现。

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

Phase 4 新增一条受控入口：

```text
用户主动打开具体 BOSS 岗位页 -> Popup 中点击读取 -> 当前可见 DOM 纯文本解析
-> 确认/编辑预览 -> POST /api/v1/jobs -> SQLite -> 岗位库/详情
```

Popup 打开时只检查本地 API，不自动读取页面。采集失败可打开 JobPilot 手动添加。

## 3. Job

Job 是用户主动保存的岗位快照，包含职位、公司、地点、薪资文本、来源、原平台 URL、
JD、备注和本地时间。来源允许 `manual` 与 Phase 4 的 `boss`。

- title 与 company 必填，输入统一去除首尾空白；
- source URL 只接受不带凭据的 HTTP/HTTPS；
- URL 规范化 scheme、host、默认端口并移除 fragment，规范化结果在本地唯一；
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

## 7. 本地与 no-proxy 边界

- Web、Extension 与 API 只通过精确 loopback 通信；
- installed runtime 不依赖账号、云服务、CDN、远程字体/脚本、telemetry、update 或境外 AI；
- JobPilot API 不请求或代理招聘网站；
- Extension 使用 `activeTab` + `scripting` 在用户点击后对当前 tab 执行一次只读解析；没有
  BOSS host permission、`tabs` permission、background 或常驻 content script；
- 测试只使用显式临时数据库，不读取、替换或删除 `runtime-data/jobpilot.db`。

## 8. Phase 4 非目标

牛客、实习僧、猎聘、国聘 Adapter、通用 Adapter framework、后台/批量爬取、隐藏 API、
ResumeVersion、Evidence Map、AI/RAG/LLM/Agent、推荐、自动投递、自动联系 HR、云同步、账号、
认证和多用户均不属于 Phase 4。

## 9. 成功标准

Phase 4 必须在关闭 VPN/系统/浏览器代理时，从真实 BOSS 岗位详情页完成读取、预览编辑、保存、
岗位库/详情、原链接、重复识别与重启持久化；保存不能创建或改变 Application。自动化、真实
Chrome、manifest/CSP/network/privacy、loopback/security、代码审查和简化门禁必须全部通过。
