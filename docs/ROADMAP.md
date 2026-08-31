# JobPilot Roadmap

> 当前阶段：Local-first Single-user Repository Cleanup。Phase 3 尚未开始，必须等待项目负责人单独批准。

## 1. Global gates

每个阶段依次完成：

```text
规格/ADR -> failing behavior test -> minimal implementation -> verification
-> code review -> simplification -> documentation -> explicit acceptance
```

任何阶段都必须保持：

- single-user、single local workspace；
- Web/Extension 对 JobPilot API 的连接、API bind 与数据库工具仅使用 loopback；未来招聘页面访问只能使用逐个平台批准的 exact host、用户手势和当前 DOM；
- 无 JobPilot 账号、云租户或强制远程 runtime；
- P0 中国大陆普通网络 no-proxy 可用；
- 不提前实现后续 Phase。

## 2. Completed foundations

### Phase 0 — Product and architecture baseline

产品边界、用户触发采集、monorepo、模块化单体、FastAPI/PostgreSQL 和工程工具链已形成初始决定。

### Phase 1 — Engineering foundation

Web、Extension、API、共享 package、测试、lint、format、typecheck 与 build 骨架已建立。

### Local-first architecture reset

ADR-008 将产品固定为本地优先、单用户、无账号架构。旧远程身份实验只保存在 Git checkpoint `pre-local-first-cleanup`，不属于当前工作树。

## 3. Current cleanup slices

### Slice 1 — API and persistence cleanup

完成：删除历史身份实现与表，恢复 `/health`-only API，强制 API/PostgreSQL loopback，保留空 SQLAlchemy/Alembic 骨架。

### Slice 2 — Shared health and Web

完成：health client 使用精确 shape 和 credential-free GET；Web 状态为 `checking / ready / unavailable`，并在 unavailable 时提供 retry。

### Slice 3 — Extension local health Popup

完成：删除远程凭据 lifecycle、background 和 credential storage；manifest 只允许精确 `127.0.0.1` health origin。

### Slice 4 — Documentation and repository cleanup

完成：删除过时验证材料，重写 canonical docs、环境样例、ignore 与 agent rules，并完成 link/stale-reference/runtime/tracked-artifact 扫描。

### Slice 5 — Clean install and complete validation

完成：清理可重建产物，重新 frozen/locked install，并通过全部测试、lint、format、typecheck、build、API 和安全扫描。

### Slice 6 — Mandatory review and simplification

完成：`code-review-and-quality` 达到 Critical 0 / Required 0；`code-simplification` 删除确认的死 wrapper、DTO、fixture、配置和说明。

完成 Slice 6 后必须停止并等待 Phase 3 授权。

## 4. Future product phases

### Phase 3 — Job capture and local job library

**Not started / not authorized.** 候选范围仅包括用户主动触发的当前页面读取、预览确认、人工兜底、本地 Job 保存与 Web 岗位库。

进入前必须冻结：第一个平台、精确 host permission、DOM fixture、write API 安全、Job schema、去重和完整无代理验收。

### Phase 4 — Application and ResumeVersion foundation

在本地 Job 稳定后增加 Application 状态事件、ResumeVersion 与本地关联。模型不使用 `user_id`。

### Later phases

后续才评估更多 Adapter、结构化 JD 分析、可选 AI、文档/RAG、面试工作流、Evidence Map、反馈闭环和发布加固。远程能力必须可选、可降级，不能成为本地核心依赖。

## 5. P0 no-proxy gate

当前与未来所有 Phase 都必须证明：

- installed runtime 不访问境外身份、公共 CDN、远程字体/脚本、GitHub runtime/raw、telemetry、update 或强制境外 AI；
- Extension bundle 不含远程 executable code 或代理能力；
- JobPilot API 不代理招聘网站流量；
- 未来 Adapter 只使用单独批准的精确 host、用户手势和当前已呈现 DOM；
- 每个 Adapter 在 VPN、系统/浏览器代理和特殊 DNS 关闭时完成真实端到端验收。

每个 BOSS 直聘、牛客、实习僧、猎聘或国聘 Adapter 都必须单独记录：

- 招聘平台页面：`PASS / FAIL`
- Extension Popup：`PASS / FAIL`
- 页面识别：`PASS / FAIL`
- 岗位解析：`PASS / FAIL`
- 保存到 JobPilot：`PASS / FAIL`
- JobPilot 岗位库：`PASS / FAIL`

任一核心步骤只有打开代理才能完成时，该 Adapter 不得标记为支持。不得提前申请尚未实现的平台权限，也不得使用 `<all_urls>`。

## 6. Current next step

Local-first cleanup Slices 0–6 已完成。当前下一步只有项目负责人评审 cleanup 结果并决定是否批准 Phase 3；不得自动创建 Job/Application/ResumeVersion、Adapter、content script、AI 或 RAG 实现。
