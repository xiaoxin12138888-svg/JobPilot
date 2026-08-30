# JobPilot Roadmap

> 当前状态：Phase 0–2A 已获得项目负责人明确批准；当前处于 **Phase 2B — Authentication Implementation & User Boundary**，ADR-006 已 Accepted。Task 6 Web server-backed session 已完成确定性实现并等待负责人验收，Task 7 尚未开始。
>
> 本文是实施计划；Task 6 的完成不表示整个 Phase 2B 或后续业务功能已经完成。

## 1. 里程碑边界

### MVP：Phase 1–4

MVP 的验收终点是一条可运行的个人求职管理闭环：

认证与用户隔离 → 当前岗位主动捕获或人工录入 → 岗位库 → 申请跟踪 → ResumeVersion 关联

MVP 不包含 AI、RAG、模拟面试、Evidence Map，也不要求五个平台 Adapter 全部完成。

### V1：Phase 5–11

V1 在 MVP 稳定基础上完成五个平台 Adapter，并逐步加入结构化 AI 分析、文档/RAG、面试工作流、基础 Evidence Map、反馈闭环、分析与发布加固。

### 全局阶段门禁

每个 Phase 必须依次完成：

实现 → 测试 → 代码/架构审查 → 简化 → 文档更新

阶段验收失败、关键风险未处理或文档与实现不一致时，不进入下一 Phase。每个阶段只实现当期交付物；后续能力只保留必要接口和扩展点，不创建假实现。

## 2. 依赖顺序

Phase 0 规格基线  
→ Phase 1 工程基础  
→ Phase 2A 认证架构门禁<br>
→ Phase 2B 认证实现与用户边界<br>
→ Phase 3 岗位捕获垂直切片  
→ Phase 4 申请与简历版本（MVP）  
→ Phase 5 五平台覆盖  
→ Phase 6 AI 分析与匹配  
→ Phase 7 文档与 RAG  
→ Phase 8 面试准备与真实面试复盘  
→ Phase 9 模拟面试工作流  
→ Phase 10 Evidence Map 与反馈闭环  
→ Phase 11 分析、加固与 V1 发布

## Phase 0 — Specification & Architecture

### Objective

在不实现正式业务功能的前提下，固定产品边界、模块职责、核心契约、数据模型、工程规则和分期计划，建立后续开发的共同事实来源。

### Deliverables

- README.md：产品、当前阶段、技术栈和架构速览；
- docs/PRODUCT_SPEC.md：用户、问题、边界、MVP、V1 和非目标；
- docs/ARCHITECTURE.md：Web、Extension、API、AI、RAG 与 Adapter 边界及 Mermaid 图；
- docs/ENGINEERING_PRINCIPLES.md：模块职责、依赖、代码、测试和阶段门禁规则；
- docs/API_CONTRACT.md：仅覆盖 Phase 1–4 所需的核心 REST API 草案；
- docs/DATA_MODEL.md：User、Job、Application、ResumeVersion 及少量未来实体预留；
- docs/ROADMAP.md：Phase 0–11 的阶段计划；
- docs/DECISIONS/ 下四份起始 ADR：monorepo、FastAPI/PostgreSQL、用户触发采集、不提前采用 Agent Framework。

### Acceptance Criteria

- 所有文档对产品范围、术语、核心资源和技术边界的表述一致；
- MVP 与 V1 边界明确，未把计划中能力描述为已实现；
- API 草案只覆盖 Phase 1–4，数据模型没有扩展成未来功能全集；
- 明确记录用户触发采集、数据库事实来源、AI 结构化输出和 Simple architecture first；
- 本阶段没有新增业务代码、正式依赖或用于占位的大量目录；
- 项目负责人完成 Phase 0 评审并明确批准后，方可进入 Phase 1。

### Explicit Non-goals

- 不实现 UI、认证、数据库、插件解析、LLM、RAG 或模拟面试；
- 不创建五个平台 Adapter 的假实现；
- 不确定所有未来 endpoint、表结构或部署细节；
- 不为了“完整架构”引入微服务、消息队列或复杂代码生成系统。

## Phase 1 — Engineering Foundation

### Objective

建立最小但可持续演进的 monorepo 工程骨架，让 Web、Extension 和 API 都能独立启动、构建和测试，同时不提前实现业务功能。

### Deliverables

- apps/web：React、TypeScript、Vite 的最小应用壳；
- apps/extension：Manifest V3、TypeScript 的最小可加载扩展壳；
- Extension 的初始权限预算：以 `activeTab`、用户手势和按需注入为默认，不申请无理由的广域常驻 host 权限；
- apps/api：FastAPI 的应用入口、最小 CORS 配置边界和唯一的 `GET /health` 探针；
- packages/shared-types 与 packages/api-client：仅加入当前真实需要的稳定共享契约；
- 根级环境变量示例；PostgreSQL 在 Phase 2B 出现首个真实持久化消费者时再建立开发配置；
- 统一的开发、构建、格式化、静态检查和测试命令；
- 各应用/共享 package 就地维护的最小行为测试，以及 `AGENTS.md` 中的工程约束。

### Acceptance Criteria

- 新开发者按文档可在本地启动 Web、API，并加载 Extension；
- Web 与 Extension 通过 production build、TypeScript strict typecheck 和最小 smoke test；API 通过导入/启动验证、Ruff 与 Pytest；
- Extension manifest 通过最小权限审查，空壳不会在后台读取页面或访问招聘平台；
- `GET /health` 不依赖数据库、业务表、对象存储、LLM 或招聘平台；
- 配置中不提交密钥，开发环境缺少必要变量时给出明确错误；
- 工程边界与 Phase 0 架构文档一致，未创建没有消费者的 package。

### Explicit Non-goals

- 不实现登录、用户表或任何岗位业务；
- 不制作正式视觉设计系统或复杂页面；
- 不加入 pgvector、对象存储、Sentry 或 GitHub Actions 的完整生产配置；
- 不引入 Kubernetes、Kafka、微服务或多套状态管理方案。

## Phase 2A — Authentication Architecture Decision Gate

### Objective

在写认证代码前决定 Web、Chrome Extension 与 FastAPI 如何共享同一安全、可维护的用户身份，并冻结最小 Phase 2B contract、session 生命周期、授权、账号删除、数据导出与保留边界。

### Deliverables

- Managed、self-hosted 与 OAuth/OIDC-centric 方案的定性比较矩阵；
- `ADR-006-authentication-strategy.md`：推荐 Auth0 managed OIDC、双 transport、风险与迁移路径；
- `AUTH_ARCHITECTURE.md`：Identity Model、Web/Extension sequence diagram、FastAPI boundary、session、revocation、deletion、authorization 与 threats；
- `DATA_MODEL.md` 中最小 `(identity_issuer, identity_subject) -> User.id` 更新；
- `API_CONTRACT.md` 中 provider-owned operation 与 Phase 2B JobPilot endpoint 的最小边界；
- 账号与个人数据生命周期政策：分阶段数据导出、live deletion deadline、backup/log retention、restore ledger 和未来敏感资源删除责任；
- Phase 2A/2B 路线、任务、README/AGENTS 与 ADR index 同步；
- 独立架构、安全与契约审查结论。

### Acceptance Criteria

- Extension credential 的获取、可信存储、access/refresh lifetime、rotation、reuse、revoke、logout 和 MV3 worker 边界明确；
- Web 明确采用 opaque HttpOnly session cookie，并记录 XSS、CSRF、CORS、SameSite 与本地开发约束；
- FastAPI 将 cookie/bearer 统一为本地 User context，且业务查询强制同时使用 resource ID 和 authenticated user ID；
- 账号 create/login/logout/expire/revoke/delete 和未来 Job/Application/Resume/Interview/Document 删除责任可测试；
- 数据导出 owner/里程碑明确，生产 backup 最大保留窗口、日志窗口和 restore 前 deletion-ledger 重放规则可测试；
- ADR 记录 provider 成本、可达性、锁定、迁移与 rejected alternatives；
- Git diff 只包含 Phase 2A 文档/规划，没有依赖、schema、Auth UI、token code、provider account 或 middleware；
- 项目负责人明确批准 ADR-006 后，才能进入 Phase 2B。

### Explicit Non-goals

- 不安装 auth SDK、ORM 或 Alembic，不创建 migration/User/session table；
- 不创建 Auth0 tenant/application/API，不写 provider secret 或 production config；
- 不实现 login/register UI、password/JWT/refresh code、Extension login 或 FastAPI auth middleware；
- 不设计组织、团队、RBAC、管理员矩阵或自建 OAuth Server；
- 不进入 Phase 2B。

## Phase 2B — Authentication Implementation & User Boundary

### Objective

在 ADR-006 获批且 Auth0 tenant/config/依赖范围单独批准后，实现最小可用认证闭环和强制用户级数据边界，为后续个人求职数据提供统一身份基础。

### Deliverables

- User 与最小 Web session/revocation state 的数据库迁移、领域模型和 API 表达模型；
- 独立 dev Auth0 tenant 下的 Web confidential client、Extension public client 与 JobPilot API audience 配置；
- Auth0 provider-managed email/password、验证/恢复与 Web Universal Login 接入；
- Web Authorization Code/BFF、opaque HttpOnly cookie、CSRF、session rotation/revocation；
- Extension `launchWebAuthFlow` + PKCE/state/nonce、signed ID-token nonce validation/discard、exact API/Auth0 host permissions、trusted token storage、single-flight rotating refresh 与 logout；
- FastAPI cookie/bearer adapters、OIDC/JWT/JWKS 验证和统一 `AuthenticatedUser`；
- `/api/v1/auth/session`、current-user profile、Web CSRF 与 local logout 的批准 contract；recent reauthentication、revoke-all 与 account deletion 保留 Accepted design，但不在当前最小闭环实现；
- `resource_id + authenticated_user_id` repository/service ownership pattern 和跨用户负向 fixture；
- 认证错误、CORS、限流、敏感日志脱敏、本地 fake issuer/JWKS 与 provider outage 测试；
- 账号删除、write-ahead restore marker、backup replay/quarantine 与 provider cutoff policy 继续由认证架构约束，但只在后续单独批准的 account-lifecycle task 实现；当前不发布不安全的缩减版 endpoint；
- `/api/v1/auth/me` 提供当前 User profile 的机器可读表达；完整账户导出 contract 在首个业务数据 Phase 冻结并随资源增量扩展；

### Acceptance Criteria

- 用户可以通过 hosted flow 创建/登录账号，Web 刷新后保持批准的会话并安全退出；JobPilot 不保存或接收密码；
- Extension 通过用户手势和 PKCE 取得同一 identity 的短期 access context，调用 `/api/v1/auth/me`，并正确处理 worker 重启、rotation、reuse、过期与退出；
- 未认证、错误 issuer/audience/algorithm/signature/time/token type、未验证 email 和撤销会话返回统一安全错误；
- Web unsafe request 通过 CSRF + Origin 门禁，Web/Extension CORS 只有精确 allowlist；
- 集成测试证明用户 A 无法读取、更新、引用或删除用户 B 的受保护资源；
- 日志不记录密码、code、verifier、cookie、token、session secret 或 provider 原始 payload；
- revoke/logout 明确测试短期 JWT 的残余 `exp` 窗口，不虚报瞬时失效；
- 所有 Web logout 均有 Origin/Fetch gate；Extension rotation 在 worker termination/不确定结果时 fail closed；unknown `kid` 不能放大 JWKS fetch；
- 当前 OpenAPI 不暴露 recent reauthentication、revoke-all 或 account deletion 的半实现；其 Accepted lifecycle invariants 留给单独批准的后续 task，不能被当前 local logout 结果替代或虚报；
- Router 只处理请求、校验、service 与响应，认证业务规则不进入 React、popup、content script 或路由大函数。

### Explicit Non-goals

- 不实现企业组织、RBAC、管理员后台、团队邀请、MFA 产品或 enterprise SSO；
- 不同时接入多个身份 provider；Google connection 最多作为后续单独批准的可选入口；
- 不实现岗位、申请或简历业务；
- 不在当前最小 Phase 2B closure 中实现 recent reauthentication、revoke-all、KMS/backup restore ledger 或 account deletion；这些能力必须作为完整 account-lifecycle task 另行批准，不能拆成不安全的部分实现；
- 不自建 password database、OAuth authorization server 或通用 IAM 平台。

## Phase 3 — Job Capture & Job Library Vertical Slice

### Objective

完成第一条跨 Extension、API、数据库和 Web 的岗位垂直切片，验证“用户主动触发并确认后保存当前岗位”的核心假设。

### Deliverables

- Job 与 JobCapture 的领域模型、迁移、请求/响应模型；
- 版本化岗位 API：保存、读取、列表和必要的基础编辑；
- Extension 内统一 JobSiteAdapter 接口、注册机制和错误语义；
- generic/manual Adapter 与一个 V1 平台的参考 Adapter；
- 当前页提取、确认/修正、保存和失败兜底的轻交互；
- `activeTab`/按需注入、optional host permission 及 Extension 消息 sender/tab/frame/schema 校验的实现与安全测试；
- Web 岗位库的最小可用列表和详情；
- 机器可读账户导出 contract，以及 User profile 和全部用户自有 Job 的导出；后续资源按所属 Phase 增量纳入；
- 参考 Adapter 的保存 HTML fixture、契约测试、API 集成测试和主流程浏览器测试；
- 重复来源链接或重复保存的行为规则及测试。

### Acceptance Criteria

- 只有用户点击后才读取当前标签页，保存前必须展示确认步骤；
- 权限与消息边界测试证明：未触发时不读取页面，非预期页面/frame 的消息不能启动采集或保存；
- 用户能通过参考 Adapter 或人工兜底保存岗位，并在 Web 岗位库中查看；
- 解析输出统一通过 JobCapture 校验，Content Script 不包含持久化或业务决策；
- Adapter 自动化测试只使用本地 fixture，不访问真实招聘平台；
- 不同用户的岗位记录严格隔离；
- 账户导出只包含当前用户的 User/Job 数据，不包含 credential、provider/session 内部字段或其他用户数据；
- 无法识别或字段缺失时进入可理解的兜底流程，不静默伪造字段。

### Explicit Non-goals

- 不完成其余四个平台 Adapter；
- 不扫描职位列表、不自动翻页、不后台爬取、不调用隐藏批量接口；
- 不正式投递、不联系 HR；
- 不实现 JD 分析、匹配评分、申请跟踪或推荐。

## Phase 4 — Application Tracking & ResumeVersion Foundation

### Objective

在岗位库之上完成申请跟踪和简历版本关联，使 MVP 形成可运行、可审计的基础求职工作流。

### Deliverables

- Application 与 ResumeVersion 的领域模型、迁移和 API 模型；
- 有限且统一的申请状态集合、合法转换规则和必要的变更记录；
- 状态事件分别保留可空的现实发生时间和可靠的服务端录入时间，统计不得混淆二者；
- ResumeVersion 关联锁定规则：`planned` 阶段可调整，进入后续状态后只允许空值补录一次；
- 创建申请、更新状态、查看申请及关联岗位的 API 与 Web 流程；
- ResumeVersion 的基础创建、查看、版本标识及与申请的关联；
- 文件存储采用 S3 兼容抽象；本阶段只实现简历版本所需的最小能力；
- 对象存储安全与一致性规格：私有对象、服务端 key、流式限长、类型验证、恶意文件隔离策略、配额/并发、失败补偿和孤儿对象回收；
- 用户隔离、状态转换、对象所有权/内部字段不泄露、上传失败补偿和端到端 MVP 测试；
- 将 Application、ResumeVersion 元数据和原始文件纳入账户导出；导出产物保持私有、授权访问并按批准的短期 TTL 清理；
- MVP 操作说明和已知限制。

### Acceptance Criteria

- 用户可从自己的岗位创建申请、更新合法状态，并看到当前状态及必要历史；
- 状态事件能够区分 `occurredAt` 与 `recordedAt`；缺少实际发生时间时，界面和后续统计不得伪装成精确阶段耗时；
- Web、Extension 与 API 不维护互相冲突的申请状态定义；
- 用户能保存可区分的简历版本，并明确知道某次申请关联了哪个版本；
- 申请离开 `planned` 后不能静默替换已绑定的简历版本；空值补录和非法替换均有契约测试；
- 非法状态转换、跨用户 Job/ResumeVersion 关联及对象所有权违规均被拒绝且返回统一错误；普通 API 响应不泄露 object key、内部 URL 或内容哈希；
- 对象写入或数据库提交任一失败时不产生可访问的半成品；回收流程能识别并处理孤儿对象；
- MVP 主流程从登录到岗位保存、申请更新和简历关联通过端到端测试；
- 删除确认前可取得包含 User、Job、Application、ResumeVersion 元数据和原始文件的完整 MVP 账户导出，且不导出 credential、内部 object key 或安全 ledger；
- Phase 1–4 文档、实现和测试一致，完成 MVP 阶段评审。

### Explicit Non-goals

- 不解析简历语义，不做 JD 匹配或自动改写；
- 不实现文档知识库、向量索引或 RAG；
- 不实现复杂审批、提醒自动化或招聘平台状态同步；
- 不宣称 MVP 已支持全部五个平台。

## Phase 5 — Five-platform Adapter Completion

### Objective

在不改变用户触发与确认边界的前提下，完成 BOSS 直聘、牛客、实习僧、猎聘和国聘五个平台的独立 Adapter 覆盖。

### Deliverables

- boss、nowcoder、shixiseng、liepin、iguopin 五个独立 Adapter；
- Adapter 注册表、统一 JobCapture 契约与跨平台字段归一化规则；
- 每个平台的代表性 HTML fixtures、异常 fixture 和回归测试；
- generic/manual 兜底在所有平台场景中保持可达；
- 有限的真实浏览器人工验证清单、兼容性矩阵和维护说明；
- 平台 DOM 变化时的故障识别与用户提示。

### Acceptance Criteria

- 五个 Adapter 均通过同一契约测试，平台特定逻辑只存在于各自模块；
- 代表性 fixture 的必填字段提取和校验通过，异常 fixture 能得到明确失败类型；
- 解析失败时用户可以选择页面内容或粘贴 JD 并继续保存；
- 自动化测试及 CI 不访问真实招聘平台；
- 人工验证确认插件只处理用户当前打开页面，不产生后台高频请求；
- 各平台上线前完成当期访问规则和合规边界复核。

### Explicit Non-goals

- 不承诺覆盖每个平台的所有历史页面或永久兼容；
- 不实现列表扫描、批量导入、自动翻页、验证码绕过或登录绕过；
- 不从平台隐藏接口同步岗位或申请状态；
- 不为了共享少量代码过早抽象所有 Adapter 细节。

## Phase 6 — JD Analysis & Resume Matching

### Objective

提供与核心业务解耦、可验证且可追溯的结构化 JD 分析和简历匹配辅助，不把模型输出当作领域事实。

### Deliverables

- AI Service abstraction 与首个 LLM Provider；
- 仅服务 ResumeVersion 的版本化 PDF/DOCX 文本提取、处理状态和失败边界，为 ResumeMatcher 提供 provider-neutral 文本输入；
- JDAnalyzer 和 ResumeMatcher 的输入、结构化输出、校验与版本策略；
- 分析/匹配 Application Service，以及与 Job、ResumeVersion 的明确关联；
- 最小 API 动作和 Web 展示，区分原文事实、模型判断和建议；
- 超时、限流、无效结构、提供方不可用和重试边界；
- 固定评估样例、结构化结果契约测试及服务集成测试；
- 成本、延迟和提示/模型版本的基础记录；
- AI 数据出站与 Provider 隐私评审：用户告知、最小化、留存/训练政策、区域/子处理方、删除传播和密钥隔离。

### Acceptance Criteria

- Router 与 React Component 中不存在长 prompt 或模型编排业务逻辑；
- 每次结果都能追溯到输入岗位、简历版本、模型/提示版本和生成时间；
- ResumeMatcher 只接收已成功提取并绑定到指定 ResumeVersion 的版本化文本；提取失败不会退化为让 Provider 直接读取不受控文件；
- 无效或不完整模型输出不能直接写成有效领域结果；
- API 不向客户端暴露 Provider 原始响应或密钥；
- 测试证明 Provider 请求只包含当前用户、当前用例所需的最小字段；用户能识别 AI 数据用途，留存/训练边界已有记录；
- 评估样例验证关键字段、失败路径和结果展示，不以单一匹配分替代证据说明；
- UI 明确提示 AI 结果的辅助性质。

### Explicit Non-goals

- 不做精准岗位推荐、成功率预测或自动求职决策；
- 不自动投递，不自动改写并覆盖用户简历；
- 不引入 LangGraph 或复杂 Agent Framework；
- 不同时接入多个 Provider 只为展示技术复杂度。

## Phase 7 — Documents & RAG

### Objective

建立用户私有文档知识库，为后续证据检索和面试准备提供带来源、受用户边界约束的检索能力。

### Deliverables

- Document 的元数据、对象存储键、处理状态和用户所有权；
- 文件上传、读取授权、删除及最小支持格式规则；
- 文本提取、切分、embedding 和 pgvector 索引流水线；
- 检索服务接口、来源片段定位和最小 RAG 回答能力；
- 可测试的处理/检索预算：文件与用户配额、最大页数/chunk 数、embedding 并发、`topK`、上下文 token 和代表性延迟目标；
- 失败重试、重复处理、删除后的索引清理和日志脱敏；
- 用户隔离、检索质量样例、集成测试和文件生命周期测试。

### Acceptance Criteria

- 文件本体通过 S3 兼容抽象访问，数据库保存权威元数据与向量索引；
- 用户 A 的上传、检索和回答上下文绝不包含用户 B 的内容；
- 每个 RAG 回答能返回可定位的来源片段，缺乏证据时明确说明；
- 文档处理失败具有可观察状态，不产生看似成功的空索引；
- 删除文档后，本体、元数据和派生索引按既定策略一致处理；
- PostgreSQL/pgvector 满足 V1 需求，没有引入独立向量数据库；
- 代表性 V1 数据集下，处理与检索不超过批准预算；超限请求得到明确错误或可恢复状态，而非无界占用资源。

### Explicit Non-goals

- 不建设全网知识搜索或共享公共语料库；
- 不支持无限文件类型、无限文件大小或复杂协同编辑；
- 不把检索片段自动认定为真实或最新事实；
- 不引入 Elasticsearch、MongoDB 或独立向量数据库。

## Phase 8 — Interview Preparation & Real Interview Log

### Objective

把岗位、简历、用户证据和授权文档转化为可编辑、可追溯的面试准备材料，并建立真实面试事件与复盘的人工录入入口，为模拟面试和后续反馈闭环提供可靠输入。

### Deliverables

- Interview 的基础模型及与 Job、Application、ResumeVersion 的关系，能够区分真实记录与后续模拟会话；
- 结构化准备计划、问题清单、回答要点和证据缺口；
- 从 JD 分析、匹配结果与 RAG 来源组装上下文的服务边界；
- 用户编辑、确认和保存准备材料的最小 Web 流程；
- 真实面试事件的人工记录与复盘入口：时间/轮次、真实问题、用户回答摘要、结果和复盘备注；
- 生成版本、来源标记、失败处理和评估样例；
- 单元、集成及关键交互测试。

### Acceptance Criteria

- 用户能为一个具体申请生成并编辑一份准备计划；
- 用户能为一个具体申请记录至少一次真实面试，保存真实问题、回答摘要和复盘备注，并在提交前确认内容；
- 每个建议明确区分原始岗位要求、用户证据、检索来源和 AI 生成内容；
- 更换 ResumeVersion 后不会静默覆盖旧准备结果，而是产生可识别的新版本或提示；
- 缺少证据时输出缺口提示，不编造用户经历；
- 关键生成结果通过结构校验并能用于 Phase 9 工作流输入。

### Explicit Non-goals

- 不实现实时模拟面试循环或自主 Agent；
- 不自动从招聘平台、通话或录音中采集真实面试内容；
- 不实现语音、视频、表情或情绪识别；
- 不保证生成问题与真实面试完全一致；
- 不自动替用户提交或公开面试材料。

## Phase 9 — Mock Interview Explicit Workflow

### Objective

使用显式 Workflow/State Machine 实现可检查、可中断和可恢复的模拟面试，而不是依赖不可控的自由 Agent 循环。

### Deliverables

- 模拟面试状态、事件、转换、终止和恢复规则；
- 创建会话、出题、提交回答、评价、继续/结束的应用服务与 API；
- InterviewEvaluator 的结构化结果、校验和版本信息；
- 最小 Web 会话界面、进度与错误恢复体验；
- 会话记录与岗位、简历、问题和回答的可追溯关系；
- 状态转换单元测试、服务集成测试及完整会话 E2E 测试。

### Acceptance Criteria

- 每个会话状态和允许动作都有显式定义，非法转换被拒绝；
- 页面刷新或短暂 Provider 故障不会使已提交回答和状态无故丢失；
- 评价结果经过结构校验，并明确为 AI 辅助反馈；
- 工作流可以在达到题数、用户结束或不可恢复错误时确定性终止；
- 核心流程不依赖 LangGraph 或开放式自主循环；
- 完整模拟面试可回放其题目、回答、评价及版本信息。

### Explicit Non-goals

- 不实现多 Agent 面试官团队；
- 不实现自动语音通话、视频分析或实时情绪判断；
- 不声称 AI 评价等同于招聘方结论；
- 不在没有明确需求时引入复杂 Agent Framework。

## Phase 10 — Evidence Map & Feedback Loop

### Objective

把岗位要求、用户证据、简历、作品材料、面试问题和回答表现连接为基础证据图，并让真实结果进入下一轮准备建议。

### Deliverables

- Requirement 与 Evidence 的有限数据模型，以及对现有资源的关联；
- Requirement → Evidence → Resume/Portfolio → Interview 的可追溯视图；
- 用户确认、修正和删除证据关联的能力；
- 面试问题、回答评价、申请结果与能力主题的反馈汇总；
- 缺口识别、客观统计和 LLM 辅助解释的分层输出；
- 版本、来源、冲突和无证据状态的处理规则；
- 典型证据链、跨用户隔离和解释边界测试。

### Acceptance Criteria

- 用户能从一条岗位要求追溯到相关经历、简历/作品证据和面试记录；
- 系统能显示“无证据”或冲突证据，不用虚构内容补齐链路；
- 用户可以纠正 AI 建议的关联，后续展示保留明确来源与版本；
- 结果分析清楚区分原始事件、计算统计和 LLM 解释；
- 少量历史数据只生成带限制说明的策略建议，不生成可靠性声明不足的推荐模型；
- 数据删除或版本变更后，证据关系不会悬空或静默指向错误内容。

### Explicit Non-goals

- 不构建知识图谱平台或通用图数据库；
- 不自动断言用户胜任某岗位；
- 不做因果推断、精准岗位推荐或成功率预测；
- 不将用户证据用于未经授权的跨用户训练或比较。

## Phase 11 — Analytics, Hardening & Portfolio Release

### Objective

完成 V1 的客观求职分析、可靠性与安全加固、自动化发布门禁和作品集交付，使产品可稳定演示并可继续迭代。

### Deliverables

- 基于真实记录的岗位、申请、阶段转化和结果统计；
- 统计、LLM 解释和策略建议的分层展示及口径说明；
- 核心日志、关联 ID、错误监测；评估后按需接入 Sentry；
- GitHub Actions 的静态检查、测试、构建和必要的安全门禁；
- 性能、可访问性、隐私、授权、上传安全、备份/恢复和失败路径审查；
- 五平台 fixture 回归、API 集成和 V1 关键流程 E2E 测试套件；
- 部署/演示说明、架构与 ADR 更新、已知限制、作品集案例和演示数据策略。

### Acceptance Criteria

- 分析结果仅基于用户自己的可追溯记录，统计口径可解释且不宣称精准推荐；
- CI 对 Web、Extension、API、迁移和关键测试设置有效门禁；
- V1 核心流程通过：认证、岗位捕获、申请、简历、AI 分析、文档检索、面试准备、模拟面试、证据链和分析；
- 安全审查验证用户隔离、敏感日志、对象访问、上传和删除策略；
- 关键错误可定位，Provider 或外部存储故障有清晰降级和恢复方式；
- 发布文档不包含虚假功能、真实用户敏感数据或未说明的限制；
- Phase 0–11 文档与最终实现一致，完成 V1 评审。

### Explicit Non-goals

- 不为作品集数据伪造用户增长、推荐准确率或求职成功率；
- 不追求企业级多租户、全球多区域或超大规模基础设施；
- 不因发布而迁移到微服务、Kubernetes、Kafka 或独立向量数据库；
- 不在 V1 末尾临时加入未经过规格和测试的新功能。

## 3. 跨阶段风险与控制

| 风险                        | 影响阶段    | 控制方式                                                       |
| --------------------------- | ----------- | -------------------------------------------------------------- |
| 招聘平台 DOM 与访问规则变化 | Phase 3、5  | 独立 Adapter、本地 fixture、人工兜底、上线前合规复核           |
| 用户数据泄露                | Phase 2A–11 | 认证架构门禁、默认用户隔离、对象授权、日志脱敏、跨用户负向测试 |
| LLM 结果漂移或不可用        | Phase 6–10  | Provider 抽象、结构校验、版本记录、评估样例、清晰降级          |
| 过早抽象导致维护负担        | 所有阶段    | 只实现当期契约，第三次稳定重复后再抽象，阶段末简化             |
| 范围持续膨胀                | 所有阶段    | Explicit Non-goals、阶段审批、MVP/V1 门禁、规格先行            |
| 文档与实现偏离              | Phase 1–11  | 每阶段文档更新纳入验收，ADR 记录关键取舍                       |

## 4. 当前下一步

执行并验收 Phase 2B 的最小统一认证闭环。代码、依赖与 schema 实施已获授权；真实 Auth0 tenant/application、IDs、origins、redirects、capabilities 与 secrets 仍需项目负责人提供，不得猜测或擅自创建。Phase 2B 完成评审、简化和文档同步前不得进入 Phase 3。
