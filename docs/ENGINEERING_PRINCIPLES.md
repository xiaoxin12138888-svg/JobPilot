# JobPilot 工程原则

## 1. Scope

本文约束 Web、Chrome Extension、FastAPI、共享 packages、数据库工具、测试、文档和未来业务模块。偏离长期边界前必须新增或更新 ADR。

## 2. Core principles

1. **Local-first**：一个安装实例、一个本地 workspace，业务数据默认不离开用户电脑。
2. **No account**：当前不创建账号、登录、session、token、User 或多用户 ownership。
3. **Loopback only**：API 与客户端只接受 loopback；不提供公网/LAN fallback。
4. **One fact source**：未来持久业务状态由本机 API/domain 与 SQLite 定义。
5. **User trigger and confirmation**：招聘页面读取必须由用户主动触发并在保存前确认。
6. **No remote core dependency**：已安装核心不依赖境外服务、CDN、远程代码、telemetry 或 update API。
7. **Simple architecture first**：只实现当前已批准、已有消费者的最小边界。

## 3. Module boundaries

### Web

- 负责路由、表单、展示、可访问性和本地服务状态；
- 通过 api-client 调用本机 API；
- 不承载 domain 状态机、数据库访问或外部 provider 逻辑。

### Extension

- 当前只提供本地 health Popup；
- bundle 不执行远程 JavaScript，不下载 CDN 资源，不发送 telemetry，不修改代理；
- 当前没有 background、content script、storage、identity 或 recruitment host；
- 未来 page capture 必须精确 host、用户手势、当前页面、最小消息 schema。

### API

- Router 只负责 request、validation、application service 和 response；
- 业务规则进入 domain/application，持久化进入 repository adapter；
- supported launcher 在服务启动前升级 SQLite migration；`/health` 请求不查询数据库；
- 写接口强制 loopback Host、安全 Origin/Fetch Metadata 与 JSON boundary；CORS 不替代本机进程认证。

### Shared packages

- `shared-types` 只保存两个 TypeScript 应用真实共享的稳定 wire types；
- `api-client` 统一 URL 构造、credential-free transport 和不可信响应校验；
- 不把 Python domain/ORM 模型复制进 TypeScript。

## 4. Data and security

- 当前 metadata 只含 Phase 3 的 `jobs` 与 `applications`；所有表不含 `user_id` 或身份字段；
- 数据库只使用本地 SQLite file URL；默认 `runtime-data/jobpilot.db` 属于用户数据，自动化不得触碰；
- SQLite connections 启用 foreign keys 与有界 busy timeout；当前保留 rollback journal，WAL 必须由实测需要驱动；
- 操作系统账户与文件权限保护本地静态数据；
- CORS 是浏览器边界，不是本机恶意进程认证；
- DOM、粘贴文本、URL、文件和所有外部响应均为不可信输入；
- 日志不得记录简历正文、完整 JD、文件内容、本机 secret 或未脱敏外部 payload。

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
- `code-review-and-quality` 为 Critical 0 / Required 0；
- `code-simplification` 后无确认的死代码；
- 文档与实现一致，工作树按任务要求交付。
