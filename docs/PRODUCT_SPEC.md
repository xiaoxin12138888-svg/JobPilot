# JobPilot 产品规格

> 状态：Phase 2.5 Local Runtime Foundation Finalization 已完成，等待负责人验收。Phase 3 尚未开始；未来能力只描述产品边界，不代表已经实现。

## 1. 产品定位

JobPilot 是个人求职者安装在自己电脑上的本地优先工作台。它计划把用户从多个招聘平台主动带入的信息整理到一个本机 workspace，形成可检查的求职工作流：

```text
岗位捕获 -> 岗位整理 -> 申请跟踪 -> 简历版本关联 -> 准备与复盘
```

JobPilot 不替代招聘网站。岗位发现、账号登录、HR 沟通和正式投递仍在原招聘平台完成。

## 2. 目标用户与本地边界

核心用户是同时使用多个招聘平台、希望在自己的电脑管理求职材料的个人求职者。

- 一个安装实例对应一个本地 workspace；
- 不创建 JobPilot 账号，不要求云登录或 “JobPilot Cloud”；
- 不支持团队、组织、招聘方、猎头或多人协作；
- 未来岗位、申请、简历和文档数据只保存在用户本机；
- 本地数据边界由操作系统账户、文件权限和 loopback 网络共同构成。

若以后要加入公网部署、多用户、远程同步或团队能力，必须先新增 ADR、威胁模型和明确授权，不能直接放宽本地默认值。

## 3. 产品原则

### 3.1 用户触发、用户确认

未来 Extension 只在用户主动点击后读取当前已打开的具体岗位页。标准流程是：

```text
用户点击 -> 读取当前已呈现 DOM -> 预览 -> 用户确认或修正 -> 保存到本地 workspace
```

自动解析不足时，可以依次提供手动选择当前页面内容和手动粘贴 JD。任何结果在用户确认前都不是正式岗位记录。

### 3.2 本地 API 是事实边界

未来岗位、申请和简历版本的状态由本机 FastAPI/domain 与本地数据库统一定义。Web 和 Extension 只消费同一套契约，不各自维护业务事实。

### 3.3 简单架构优先

V1 保持 Web、Chrome Extension、单体 FastAPI 和一个本地 SQLite 文件。当前没有业务表；只在获得明确 Phase 授权后增加当期真实需要的模型和接口。

### 3.4 AI 不是核心运行依赖

未来 AI 必须是显式启用、可替换、可降级的辅助能力。核心岗位与申请工作流不能因为远端模型不可达而停止，也不得把模型输出当作事实。

## 4. P0 no-proxy runtime

安装后的日常核心流程必须在中国大陆普通网络、关闭 VPN、系统/浏览器代理和特殊 DNS 时工作。

目标招聘平台是 BOSS 直聘、牛客、实习僧、猎聘和国聘。平台支持状态只能基于对应 Adapter 的真实验收，不能因为出现在目标清单中就提前宣称支持。

- 核心不依赖 Auth0、Logto Cloud、Google APIs/reCAPTCHA、Cloudflare Turnstile、GitHub runtime API/raw、jsDelivr、unpkg、cdnjs、远程字体/脚本、境外 AI、telemetry/analytics 或 update API；
- Extension 不执行远程 JavaScript，不下载运行时代码，不修改代理；
- 招聘网站流量由用户浏览器直接访问，不经过 JobPilot API 或中转服务器；
- 未来每个招聘平台 Adapter 使用单独批准的精确 host permission；
- Adapter 只能由用户主动触发并读取当前页面已呈现 DOM；
- 每个 Adapter 必须完成无代理真实网络验收，不能用 synthetic probe 或一次偶然成功代替完整路径。

## 5. 当前实现范围

当前只实现工程与本地连接基线：

- Web 本地服务状态；
- Extension 本地 health Popup；
- FastAPI `GET /health`；
- health shared type 与 loopback API client；
- `runtime-data/jobpilot.db` 中的本地 SQLite、SQLAlchemy/Alembic 空 schema 基础；
- 测试、lint、format、typecheck 和 build 门禁。

当前没有 Job、Application、ResumeVersion、LocalProfile、Adapter、content script、AI、RAG、对象存储或上传。

## 6. 未来核心能力

以下能力必须按 Roadmap 分阶段批准后实施：

1. 用户主动触发的当前岗位捕获与人工兜底；
2. 本地岗位库、去重和编辑；
3. Application 状态与事件记录；
4. ResumeVersion 保存及与 Application 的关联；
5. 更多平台 Adapter；
6. 可选的结构化分析、文档检索、面试准备和复盘。

单用户模型不需要 `user_id`。若未来确有本机偏好资料需求，可以另行设计 `LocalProfile`；当前不预建伪 User。

## 7. 明确非目标

- JobPilot 公网账号、云同步、SaaS、多用户、团队或 RBAC；
- 后台爬虫、自动翻页、列表扫描、隐藏接口采集；
- 绕过招聘平台登录、验证码、风控或访问限制；
- 自动投递、自动联系 HR 或代替用户决策；
- 把采集结果建设成对外职位数据库；
- 远程可执行代码、强制 telemetry 或代理/VPN 功能；
- 在 Phase 3 批准前实现任何业务资源。

## 8. 成功标准

当前 Phase 2.5 完成标准：

- Web、Extension 和 API 在无账号、无 provider 配置下启动；
- 客户端只连接精确 loopback API；
- supported API launcher 首次运行自动初始化 SQLite，重启复用同一文件，`/health` 请求本身不查询数据库或远程服务；
- Extension bundle 不含远程代码、后台、content script、代理或额外 host；
- Extension 通过精确 loopback host permission 直连 API，不复制 Extension ID 到 CORS；
- canonical docs 不再把历史认证系统或 PostgreSQL 描述为当前能力；
- 全部自动化门禁通过，并在进入 Phase 3 前停止。

未来 MVP 成功标准将在 Phase 3/4 规格中冻结，至少覆盖用户确认、本地保存、状态可追溯、无代理真实网络和数据不离开本机的默认行为。
