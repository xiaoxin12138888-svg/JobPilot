# JobPilot Roadmap

> 当前阶段：Phase 3 — Job & Application Domain Foundation 已获批准并完成实现/验收。
> Phase 4 尚未获项目负责人批准。

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

## 4. Candidate next phase

### Phase 4 — First Recruitment Site Adapter & Job Capture

**Not started / not authorized.** 候选范围是首个招聘网站 Adapter、精确 host permission、
用户主动触发的当前页面 DOM 读取、预览确认、人工修正与保存到现有 Job contract。

进入前必须冻结第一个平台、DOM fixture、错误/降级、权限和无代理真实验收。不得自动申请、
后台爬取、列表扫描、隐藏 API、绕过登录/验证码/风控或修改 Application 状态。

## 5. Later phases

ResumeVersion、更多 Adapter、结构化 JD 分析、可选 AI、文档/RAG、Evidence Map、面试准备、
复盘与发布加固均在更晚阶段单独评审。远程能力必须显式启用、可替换、可降级，不能成为
本地 Job/Application 核心依赖。

## 6. P0 no-proxy gate

installed runtime 不访问远程身份、公共 CDN、远程字体/脚本、GitHub runtime/raw、telemetry、
update 或强制境外 AI。未来每个 Adapter 必须分别记录招聘页、Extension、识别、解析、
确认保存和岗位库的真实关闭代理结果；任一核心步骤依赖代理就不能标为支持。

## 7. Stop boundary

Phase 3 完成后只等待项目负责人验收。不得自动创建 Phase 4 分支、权限或实现。
