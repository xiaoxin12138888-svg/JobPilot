# ADR-011：BOSS 直聘当前岗位页主动采集

- **Status**：Accepted
- **Date**：2026-09-03
- **Decision owner**：JobPilot 项目负责人

## Context

Phase 3 已提供统一 Job create service、规范化 URL 去重、SQLite 岗位库和原平台链接，但岗位
只能在 Web 手动录入。Phase 4 需要验证第一条真实招聘平台链路，同时继续遵守 local-first、
no-proxy、用户主动触发、最小权限和不自动投递边界。

## Decision

1. Phase 4 只支持 BOSS 直聘，Job source 新增 `boss`；其他招聘平台保持不支持。
2. Extension 仅在用户打开 Popup 后再次点击“读取当前岗位”时，使用 `activeTab` 与
   `scripting` 对当前 tab 执行一次只读 `BossAdapter`。不注册 content script/background，
   不申请 BOSS host permission、`tabs` permission 或 `<all_urls>`。Manifest 使用仅含公开公钥
   的 `key` 固定 Extension ID；API 只允许该精确 Extension Origin 与 `Sec-Fetch-Site: none`
   组合写入现有 `POST /api/v1/jobs`，不信任任意格式合法的 Extension ID，也不把 Extension
   Origin 加入 CORS。
3. Adapter 必须同时验证精确 BOSS hostname、Job detail URL 形状和页面岗位详情结构，只读取
   当前页面已呈现的 title、company、location、salary 与 description 纯文本。它不访问网络、
   script、Cookie、storage、内部业务对象或隐藏 API，也不修改页面。
4. Adapter 产出沿用现有 Job 字段的 `JobCaptureDraft` 和仅供 Popup 显示的 warnings。用户必须
   在可编辑预览中确认 title/company 后才能保存。
5. 保存复用 `POST /api/v1/jobs`、现有 Job service 和服务端 URL normalization。重复 URL 继续
   返回 `409 DUPLICATE_JOB_URL`；error envelope 可选返回现有本地 Job 的 `resourceId`，用于
   打开 JobPilot 详情，不返回招聘平台或账号数据。
6. `jobs.source` CHECK 通过可逆 migration 从只允许 `manual` 扩展到 `manual|boss`。不新增表；
   migration 只在临时数据库和真实数据库副本上验证。
7. BOSS source URL 必须是当前 active tab 的 HTTP/HTTPS Job detail URL。Extension 与 API 都将
   其收敛为 scheme、精确 hostname 与 Job detail path，不保存 tracking/session query 或 fragment。
   所有采集字段按不可信外部纯文本处理，执行长度限制与控制字符清理；不保存 HTML。
8. 保存或打开原平台均不创建 Application、不标记 applied，也不自动操作 BOSS 页面。
9. 只有真实 Chrome 与关闭 VPN/系统/浏览器代理的完整链路全部通过，BOSS 状态才能标为
   `SUPPORTED — V1`；否则 Phase 4 必须报告 BLOCKED。

## Consequences

- JobPilot 获得第一条 BOSS 页面到本地 SQLite 的受控数据入口，但不成为爬虫或投递工具。
- DOM selector 需要基于真实页面观察并由最小脱敏 fixture 回归；页面变化可能产生 warning 或
  手动添加 fallback，而不是猜测并静默保存。
- Extension manifest 增加两个窄权限，安全审查必须证明没有常驻脚本、远端运行依赖、凭据读取
  或招聘网站网络调用。
- Manifest 公钥可以随源码公开；仓库和构建产物不得包含对应私钥或其他 secret。旧的无 key
  unpacked 安装需要移除后重新加载，才能切换到固定 ID。
- 固定 Origin 排除普通网页和其他 Extension ID，但公开 key 不是抵御本机恶意进程，或用户主动
  加载复用同一公钥的其他 unpacked 代码的秘密认证；本机安装代码与操作系统账户仍是信任边界。
- Phase 5 的多平台 Adapter 仍需负责人另行批准；本 ADR 不建立通用 Adapter framework。
