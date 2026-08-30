# JobPilot 工程原则

## 1. 目的与适用范围

本文定义 JobPilot 从第一天起必须遵守的工程约束。它适用于 Web、浏览器扩展、API、AI/RAG、测试、基础设施和文档。任何阶段若需偏离，应先新增或更新 ADR，并在实现前获得评审。

## 2. 总体原则

1. **Simple architecture first**：在模块化单体能够满足需求时，不引入微服务、Kafka、Kubernetes、Elasticsearch、MongoDB 或独立向量数据库。
2. **单一职责**：一个模块只负责一类变化原因；目录和文件边界按领域与职责划分，而非按“以后可能有用”划分。
3. **契约优先**：公共接口先定义输入、输出、错误和兼容规则，再实现。
4. **数据库是业务事实来源**：持久化状态及其语义由 API/domain 统一管理，Web 与 Extension 只消费契约。
5. **显式优于魔法**：先使用清晰的 service、port、adapter 和显式 workflow；只有证据表明必要时才增加框架或泛化层。
6. **阶段门禁**：未完成本阶段的验收、评审、简化和文档更新，不进入下一阶段。

## 3. 模块与依赖边界

### 3.1 Web

- React Component 负责渲染、交互编排和局部 UI 状态。
- 业务规则、状态迁移、权限判断和 API 数据转换不得写入 Component。
- 远端业务状态以 API 响应为准；不得另建一套 Application 状态定义。
- 一个状态管理方案足够时，不引入第二套框架。

### 3.2 Chrome Extension

- Content Script 只读取用户当前主动打开页面的 DOM，并产出候选 `JobCapture`。
- Content Script 不承载持久化、去重、业务状态迁移、长 prompt 或跨页面采集逻辑。
- 平台差异只存在于独立 `JobSiteAdapter` 中，不得将 `if boss ... else if ...` 散落到 UI、网络或存储代码。
- 保存前必须展示用户确认；自动解析失败时依次支持手动选择和手动粘贴。
- 禁止后台批量爬取、自动翻页、扫描列表、绕过验证码或登录限制、调用隐藏接口以及高频访问招聘平台。

### 3.3 API

FastAPI Router 仅负责：

1. 接收请求；
2. 边界校验与认证上下文；
3. 调用 application service；
4. 将结果映射为稳定响应。

业务规则进入 application/domain；持久化细节进入 repository adapter；外部 AI、对象存储等进入 infrastructure adapter。ORM model 不得直接作为公共 API 响应。

源码依赖方向保持向内：

```text
transport/router ------> application service ------> domain
infrastructure adapters ------> application/domain-owned ports
```

运行时可以由 service 经 port 调用 adapter；源码层仍由 adapter 依赖 core-owned port。Domain 不依赖 FastAPI、具体数据库驱动、LLM SDK 或对象存储 SDK。

### 3.4 AI 与 RAG

- Router 不直接拼接长 prompt 或调用模型。
- 调用链必须经过 application service、AI service port、provider adapter、结构化结果校验，再进入 domain。
- 至少保留 `JDAnalyzer`、`ResumeMatcher`、`InterviewEvaluator` 三个职责独立的 port，但在需求到达相应阶段前不实现。
- LLM 原始文本、provider 异常和内部 prompt 不直接暴露给客户端。
- RAG 索引属于可重建派生数据；原始 Document 元数据与文件引用仍由核心数据库/对象存储负责。
- 模拟面试优先显式 workflow/state machine；没有可验证的编排复杂度前不引入 Agent Framework。

## 4. 契约与业务状态

- 公共业务 REST API 使用 `/api/v1` 主版本前缀，统一资源命名、分页和错误结构；无业务语义的 `GET /health` 是明确的运维探针例外。
- 破坏性契约变更必须通过 ADR、迁移方案和新主版本；同一主版本优先增加可选字段。
- Application 状态的权威定义位于后端 domain/API 契约。Web 与 Extension 共用一个 TypeScript 镜像，且通过 OpenAPI/契约测试检查漂移。
- Python 与 TypeScript 之间暂不建立复杂代码生成系统；仅当手工同步已产生可量化维护成本时再评估轻量生成。
- 所有第三方响应均视为不可信输入，必须在系统边界验证。

## 5. 代码组织与复杂度控制

- 禁止创建无明确领域含义的 `utils.ts`、`helpers.ts`、`common.ts` 或同类“杂物抽屉”。工具代码必须按领域或能力命名。
- 单文件接近 300–400 行时，必须检查是否存在多重职责；按职责拆分，不按行数机械拆分。
- 相同代码出现两次先观察；第三次出现且语义稳定后才评估抽象。
- 不为未知未来需求创建空 package、空 service、万能 repository 或十层抽象。
- 优先完成一个可测试的纵向切片，再扩展通用能力。

## 6. 依赖策略

未经批准不得增加新依赖。每个核心依赖提案必须记录：

- 它解决的具体问题；
- 标准库或现有依赖为何不足；
- 安全、体积、运行时和长期维护成本；
- 可替代方案与退出路径。

依赖版本应锁定并由自动化更新工具或定期维护流程审查。密钥、令牌、`.env` 和用户简历内容不得提交到版本库。

## 7. 测试策略

### 7.1 测试层级

- **Unit Test**：domain 规则、状态迁移、DTO 映射、Adapter 解析器和结构化 AI 结果校验。
- **Integration Test**：API + PostgreSQL、repository、对象存储 adapter、认证边界。
- **Browser/E2E Test**：关键 Web 流程、扩展确认与保存流程；数量保持小而关键。

### 7.2 招聘平台 Adapter

- 每个平台使用脱敏、版本化的 HTML fixture 做回归测试。
- fixture 计划放在 `tests/fixtures/job-pages/{boss,nowcoder,shixiseng,liepin,iguopin}/`。
- CI 不访问真实招聘平台，不依赖平台登录状态，也不尝试绕过反自动化机制。
- 真实页面仅用于有限的人工或 DevTools 验证，且必须由用户主动打开。

### 7.3 测试质量

- 测试验证外部行为和契约，不绑定无关实现细节。
- 不得删除、跳过或放宽失败测试来掩盖缺陷，除非变更需求已获批准且文档同步更新。
- 缺陷修复应先建立可复现测试；文档阶段使用结构、一致性、链接和 Mermaid 语法检查代替业务测试。

## 8. 可观测性与错误处理

- 使用结构化日志和请求关联 ID；不得记录密码、令牌、完整简历文本或敏感页面内容。
- 外部依赖错误映射为稳定的领域/API 错误，内部堆栈不返回客户端。
- JD、页面选区、用户备注和未来检索片段默认按纯文本数据渲染；禁止未经可信 allowlist 清洗就注入 HTML 或使用等价的非安全渲染入口。
- Sentry 等第三方可观测性工具在后续阶段按实际问题引入，不作为 Phase 0/1 前置条件。

## 9. Git 与变更管理

- 提交保持单一目的，使用清晰的 Conventional Commit 风格，例如 `feat(extension): add job capture contract`。
- 禁止以 `implement whole platform` 一次提交跨越多个模块和阶段。
- 架构、公共契约、数据库 schema、核心依赖和 CI 变更必须先评审。
- 不在同一提交中混入无关格式化、重构和功能修改。

## 10. Definition of Done

每个 Phase 或纵向切片只有在以下流程全部完成后才算完成：

```text
implementation -> tests -> review -> simplify -> docs update
```

验收清单：

- [ ] 交付物与批准的规格和明确非目标一致。
- [ ] 相关 unit/integration/browser 测试通过；无法自动化的检查有记录。
- [ ] 公共接口、状态和错误语义已进行契约评审。
- [ ] 没有业务逻辑泄漏到 React Component、Content Script 或 FastAPI Router。
- [ ] 没有新增未批准依赖、秘密信息或无用抽象。
- [ ] 代码已做职责和复杂度简化检查。
- [ ] README、规格、ADR、API 或运维文档已按变更同步。
- [ ] 本阶段 Acceptance Criteria 全部为 PASS，且 Explicit Non-goals 未被误实现。
