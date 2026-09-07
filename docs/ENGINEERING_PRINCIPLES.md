# JobPilot 工程原则

> 当前 Phase 10 Local Resume Import 已完成实现、自动化门禁与虚构文件隔离浏览器验证，等待真实
> 简历人工验收；Phase 7 保持 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`，Phase 11 未开始。

## 1. Scope

本文约束 Web、Chrome Extension、FastAPI、共享 packages、数据库工具、测试、文档和未来业务模块。偏离长期边界前必须新增或更新 ADR。

## 2. Core principles

1. **Local-first**：一个安装实例、一个本地 workspace，业务数据默认不离开用户电脑。
2. **No account**：当前不创建账号、登录、session、token、User 或多用户 ownership。
3. **Loopback only**：API 与客户端只接受 loopback；不提供公网/LAN fallback。
4. **One fact source**：未来持久业务状态由本机 API/domain 与 SQLite 定义。
5. **User trigger and confirmation**：招聘页面读取必须由用户主动触发并在保存前确认；真实简历
   发往可选 Provider 前必须在当次 Web 操作中明确告知并确认；表单 Scan、Fill 与 Submit 必须
   分离，只有用户确认的字段可以 Fill，Submit 永远由用户执行；本地简历导入必须保持
   `Parse != Save`，只有最终确认才可写 Resume/Profile。
6. **No remote core dependency**：已安装核心不依赖境外服务、CDN、远程代码、telemetry 或 update API。
7. **Simple architecture first**：只实现当前已批准、已有消费者的最小边界。

## 3. Module boundaries

### Web

- 负责路由、表单、展示、可访问性和本地服务状态；
- 通过 api-client 调用本机 API；
- 不承载 domain 状态机、数据库访问或外部 provider 逻辑。
- Resume content 只按纯文本渲染，不使用 `dangerouslySetInnerHTML`；Evidence 每项先显示明确结论，
  全图总览只做确定性计数、待确认项和主要证据缺口。
- Interview 问题、回答、复盘和 Application 结果只按纯文本渲染；面试操作不得隐式推进投递状态。
- Feedback 只呈现本地事实计数、nullable 漏斗率和分组，不输出评分、建议或因果结论。
- Resume Import 只渲染不可信纯文本；Parse/Preview 不保存，Current vs Imported 与逐项选择必须
  在 Confirm 前可见，phone/email 默认遮罩。

### Extension

- Phase 5 提供本地 health 与 BOSS/牛客当前岗位读取/确认 Popup；
- Phase 9 在同一 Popup 增加用户触发的 Scanner、deterministic Resolver、Preview 与 Safe Fill；
- bundle 不执行远程 JavaScript，不下载 CDN 资源，不发送 telemetry，不修改代理；
- 仅使用 `activeTab`、`scripting` 与精确 loopback host；没有 background、常驻 content
  script、`tabs` permission、storage、identity 或 recruitment host permission；
- Manifest `key` 只能包含可公开公钥以固定 Extension ID；不得提交私钥或 secret。API 只精确
  接受该 JobPilot Extension Origin 与安全 Fetch Metadata，不信任其他合法 Extension ID；
- page capture 必须是明确用户手势、当前页面、一次性只读 DOM parser 和最小返回 schema。
- Scanner 不返回当前值或完整 DOM；Profile/Fill Plan 只在 Popup 内存。READY 默认选中，fuzzy
  只能 REVIEW_REQUIRED，敏感/文件/勾选/缺值不得进入写入计划。
- Executor 必须重新校验 URL/ref/signature，使用原生 setter 与标准事件，并且不得调用
  form.submit/requestSubmit、Submit/Continue、框架私有状态或招聘网站私有 API。

### API

- Router 只负责 request、validation、application service 和 response；
- 业务规则进入 domain/application，持久化进入 repository adapter；
- supported launcher 在服务启动前升级 SQLite migration；`/health` 请求不查询数据库；
- 写接口强制 loopback Host、安全 Origin/Fetch Metadata 与 JSON boundary；CORS 不替代本机进程认证。
- Resume Parse 是唯一 Web-only multipart 例外且不持久化；请求体在 multipart 解析前受有界
  Content-Length 保护，文件读取后再执行精确上限校验；Confirm 仍为 JSON-only，并用一个
  transaction 写可选 Resume Version 与 selected-only Profile patch。

### Shared packages

- `shared-types` 只保存两个 TypeScript 应用真实共享的稳定 wire types；
- `api-client` 统一 URL 构造、credential-free transport 和不可信响应校验；
- 不把 Python domain/ORM 模型复制进 TypeScript。

## 4. Data and security

- 当前业务数据只含 `jobs`、`applications`、`jd_analysis_records`、`resume_versions`、
  `evidence_map_records`、`interview_rounds`、`interview_questions` 与 singleton
  `autofill_profiles`；所有表不含 `user_id` 或
  身份字段；
- 数据库只使用本地 SQLite file URL；默认 `runtime-data/jobpilot.db` 属于用户数据，自动化不得触碰；
- SQLite connections 启用 foreign keys 与有界 busy timeout；当前保留 rollback journal，WAL 必须由实测需要驱动；
- 操作系统账户与文件权限保护本地静态数据；
- CORS 是浏览器边界，不是本机恶意进程认证；
- Extension Origin 不加入 Web CORS allowlist；扩展写入身份由固定 ID 的精确 Origin gate 约束；
- DOM、粘贴文本、URL、文件和所有外部响应均为不可信输入；
- 日志不得记录简历正文、完整 JD、文件内容、本机 secret 或未脱敏外部 payload。
- 面试问题、回答摘要、复盘、面试官备注与 Application 结果不得写日志、telemetry、Extension、
  Git 或真实数据 fixture；Feedback Summary 不读取简历正文。
- AI invalid-response 诊断只能记录固定白名单分类码，不记录 Job/Resume ID、外部响应或输入片段。
- Resume content 默认只写本地 SQLite；Evidence Map 只发送用户当次选择的一个版本和当前非
  stale JD requirements，不发送原始 HTML、完整 JD、notes、Application、其他 Job/Resume 或文件。
- Evidence requirement 必须保持当前 JD Analysis 六类条件的类型、文本和顺序；旧 schema 1 只读
  兼容，新生成使用 schema 2。quote 必须能在空白规范化后回溯到所选 Resume，DIRECT/PARTIAL
  每项最多组合三条跨 section 的真实原文，无有效 quote 时降级 GAP。允许语义支持，不要求关键
  词相同；但不允许使用外部常识补全或升级简历未写的能力、年限、学历、毕业年份或项目事实。
  禁止匹配/ATS/Offer 分数。
- Feedback 的面试岗位只按至少存在一轮的不同 Application 计数；漏斗率只在前一阶段分母非零且
  后一阶段不超过前一阶段时计算。原始计数不截断、不推断缺失记录，派生统计不持久化。
- AutofillProfile 默认不收集证件、银行卡、婚姻、民族、政治面貌等低价值敏感事实；Profile 不进
  日志、Git、测试真实数据、Extension storage 或远端。Autofill 完整链路不得调用 LLM。
- Resume 文件名、文件正文和解析候选不进入日志/Git/Extension/Provider。原文件不永久保存；
  PDF/DOCX parser 必须验证格式并限制文件、页数、文本、ZIP/XML 与耗时资源。

## 5. P0 no-proxy rule

核心运行必须在中国大陆普通网络、关闭 VPN、代理和特殊 DNS 时工作。开发依赖下载可以使用 registry/mirror，但已安装 runtime 不得调用 GitHub API/raw、公共 CDN、远程字体/脚本、境外身份、强制境外 AI、telemetry 或 update API。

未来每个招聘平台 Adapter 都要单独通过真实无代理端到端验收；没有实际证据时只能报告 BLOCKED 或 NOT VERIFIED。

## 6. Dependencies

- TypeScript 只使用 pnpm，Python 只使用 uv；
- TypeScript tests 使用 Vitest，Python tests 使用 Pytest；
- Python lint/format 只使用 Ruff；
- 优先标准库与现有依赖；新 runtime 依赖必须说明必要性、维护、许可、体积和远程行为；
- 禁止远程 executable code 和为了未来猜测引入的框架。

## 7. TDD and incremental delivery

- 行为变更先写 failing test，确认 RED 后做最小 GREEN；
- 多文件变更按可构建、可回滚的 slice 交付；
- 每个 increment 运行受影响 tests、typecheck、lint、format 和 build；
- 测试断言行为，不绑定无意义实现细节；
- 外部服务在自动化中使用 fixture/fake，CI 不访问真实招聘网站或付费服务；
- 测试数量随产品删除而下降是允许的，但现有行为必须有证据。

## 8. Code quality

- Domain/Application 不依赖 React、FastAPI、ORM 或具体外部 SDK；
- 删除死 abstraction，不保留 compatibility shim、空 wrapper 或注释掉的旧实现；
- 重复达到稳定第三次前不抽象；
- 错误对外稳定且有界，内部堆栈不返回客户端；
- 不在 unrelated change 中顺手重构。

## 9. Git and documentation

- 不提交 secret、`.env`、runtime data、日志、cache、build 或 browser artifacts；
- lockfile、migration、`.env.example` 和源 fixture 在需要时必须跟踪；
- 关键架构改变使用 ADR；旧实验由 Git history/tag 保存，不在 active docs 中伪装成当前能力；
- 每个 Phase 完成前同步 README、产品、架构、API、data、roadmap、AGENTS 和 task checklist。

## 10. Definition of Done

- scope 与当前 Phase 一致，未提前实现下一 Phase；
- tests、lint、format、typecheck、build 和 API gates 通过；
- loopback/CORS、secret、remote-runtime、manifest/CSP 和 tracked-artifact 扫描通过；
- browser/runtime 无法验证时明确报告 BLOCKED，不虚构 PASS；
- 全部 `JOBPILOT_LLM_*` 缺失时 Interview、Feedback、Profile 与 Autofill 仍完整可用；
- 全部 `JOBPILOT_LLM_*` 缺失时 Resume Import 仍完整可用；
- `code-review-and-quality` 为 Critical 0 / Required 0；
- `code-simplification` 后无确认的死代码；
- 文档与实现一致，工作树按任务要求交付。
