# JobPilot Roadmap

> 当前阶段：Phase 6 — JD Structured AI Analysis 已批准并实现本地核心；真实评测与真实岗位 AI
> 验收仍待完成。BOSS 与牛客保持 `SUPPORTED — V1`。

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

## 4. Phase 4 — BOSS Direct Job Capture

状态：Completed（2026-09-04）。

只实现 BOSS 直聘：`activeTab` + `scripting` 用户主动触发当前岗位页 DOM 读取、可编辑确认预览、
复用 Job API 保存、重复岗位处理、Web source 展示和真实 no-proxy 验收。没有 BOSS host
permission、常驻 content script、background、后台爬取、列表扫描、隐藏 API、登录/验证码/
风控绕过或 Application mutation。

## 5. Phase 5 — Nowcoder Adapter & Shared Capture Contract

状态：Completed（2026-09-04）。

只新增牛客具体岗位详情页 Adapter，并与 BOSS 共用 `JobCaptureDraft/JobCaptureResult`、Popup
预览编辑、Job API、duplicate 和 source label。当前 tab 使用显式两平台分派，没有 factory、
registry、持久 content script、招聘网站 host permission、隐藏 API 或 Application mutation。
平台 detection、selectors 与 DOM helpers 继续留在自包含注入函数内。真实无代理牛客完整流程和
BOSS 回归均已通过。

## 6. Phase 6 — JD Structured AI Analysis

状态：In progress（2026-09-04）。

暂停横向 Adapter 扩展。对已保存 Job 增加用户主动触发的可选结构化分析、strict schema、
evidence grounding、单条 SQLite 持久化、stale/reanalysis 与 Job Detail 状态展示。Provider 未配置
或失败不影响本地核心。Resume、Evidence Map、matching、RAG、Agent 与模拟面试不进入本阶段。

自动实现、Fake Provider 回归与 20 条脱敏 gold 的人工审核已完成；真实 Prompt V1/V2、Bad
Cases、真实 BOSS/牛客 AI 人工验收必须完成后才可标记 Phase 6 PASS。

## 7. Later phases

如果 Phase 6 PASS，下一候选是 Phase 7 — Resume Version & Evidence Map；仍需负责人明确批准。
JD×Resume matching、RAG、模拟面试、其余招聘平台、复盘与发布加固均需更晚单独评审。远程能力
必须显式启用、可替换、可降级，不能成为本地 Job/Application 核心依赖。

## 8. P0 no-proxy gate

installed runtime 不访问远程身份、公共 CDN、远程字体/脚本、GitHub runtime/raw、telemetry、
update 或强制境外 AI。未来每个 Adapter 必须分别记录招聘页、Extension、识别、解析、
确认保存和岗位库的真实关闭代理结果；任一核心步骤依赖代理就不能标为支持。

## 9. Stop boundary

不得在真实评测/验收 blocker 存在时宣称 Phase 6 PASS。不得自动开始 Phase 7，也不得实现智联、
实习僧、猎聘、国聘等其他平台。
