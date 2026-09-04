# ADR-012：牛客当前岗位采集与共享采集合同

- **Status**：Accepted
- **Date**：2026-09-04
- **Decision owner**：JobPilot 项目负责人

## Context

Phase 4 已用一个用户主动触发的 `BossAdapter` 验证从当前招聘岗位详情页到本机 Job 库的完整
链路。Phase 5 只新增牛客，并用第二个真实 Adapter 判断哪些采集行为已经稳定到可以共享；它
不授权其他招聘平台、后台采集、自动投递、招聘平台私有 API、AI/RAG 或远程 runtime。

现有 `BossAdapter` 同时包含四类关注点：

- BOSS 专属：hostname/path/页面结构识别、BOSS selectors、`source = boss`；
- 平台无关：统一草稿与 warning 结果形状、可见纯文本清洗、必填/可选字段 warning 语义；
- Popup 专属：状态、预览编辑、来源标签、保存/duplicate/retry/manual fallback；
- API/domain 专属：字段上限、source/URL 可信边界、URL 规范化、SQLite 去重与持久化。

平台无关部分只有在 BOSS 与牛客实现后，才能通过 Shared Adapter Review 决定是否提取。

## Decision

1. Phase 5 只新增 `nowcoder` Job source，界面显示“牛客”；BOSS 继续为
   `SUPPORTED — V1`，其他招聘平台保持不支持。
2. `BossAdapter` 与 `NowcoderAdapter` 处于同一层级，统一返回现有 Job 字段组成的
   `JobCaptureDraft` 与 Extension-only `warnings`。不得创建牛客专属业务 DTO。
3. 当前 tab 只做清晰的 hostname/page 分派：BOSS 调用 `BossAdapter`，牛客调用
   `NowcoderAdapter`，未知页面返回 unsupported。不得引入 AdapterFactory、DI container、
   registry、plugin framework 或空平台实现。
4. Extension 权限保持 `activeTab`、`scripting` 与精确 loopback API host permission；不增加
   `tabs`、招聘网站 host permission、`<all_urls>`、content script、background worker、
   `webRequest`、cookie、history 或 proxy 权限。读取仍只发生在 Popup 内第二次明确点击以后。
5. Adapter 只读取当前已呈现的 title、company、location、salary、description 纯文本以及
   Chrome 提供的当前 tab URL。不得读取/保存 HTML、script、storage、Cookie、账号、简历、
   聊天、联系人、网络响应、HAR、token 或 credential，也不得修改招聘页面。
6. 牛客支持范围只包含真实验证过的具体招聘岗位详情页。selectors 必须来自负责人保持打开的
   当前真实页面；实现前不得凭旧资料猜测。首页、列表、公司页、专题、社区、面经、题库、登录
   与验证页必须 fail closed。
7. 保存继续复用 `POST /api/v1/jobs`、同一个 Job service 与 SQLite 唯一约束。FastAPI/domain
   仍是 URL 规范化、字段上限、纯文本和 source/URL 组合的权威边界；Adapter 不实现第二套
   URL normalizer。牛客 tracking query 与 fragment 不持久化。
8. `jobs.source` CHECK 通过最小可逆 migration 从 `manual|boss` 扩展为
   `manual|boss|nowcoder`；不新增表或 Job 字段。存在 `nowcoder` Job 时 downgrade 必须拒绝。
9. Popup 与 Web 复用现有体验。缺少 title/company 时禁止保存；可选字段缺失时提示确认；
   duplicate 仍打开已有本地 Job。保存或打开原平台永不创建/修改 Application。
10. 第二个 Adapter 完成后才执行 Shared Adapter Review。只允许提取已在两个 Adapter 中证明
    重复且更易读的合同或纯文本 helper；平台 detection、selectors 和页面结构仍各自保留。
11. 只有真实 Chrome、关闭 VPN/系统/浏览器代理后的牛客读取、预览、保存、duplicate、Web
    详情、原链接、零 Application、重启持久化及 BOSS 回归全部通过，牛客才可标记
    `SUPPORTED — V1`。否则保持 `NOT SUPPORTED` 并报告 blocker。

## Consequences

- Phase 5 会形成第一个双平台采集入口，同时保持清晰的小型条件分派和一个保存合同。
- 牛客 DOM 变化会以 unsupported、warning 或手动添加降级，不会通过扩大权限或调用隐藏 API
  规避。
- 共享代码只来自两个真实实现的重复证据，避免为尚未批准的平台建立推测性框架。
- 固定 Extension ID、精确 Origin、Sec-Fetch-Site、loopback Host、JSON-only、no credentials、
  no-proxy、no telemetry 和 no remote dependency 安全边界保持不变。
- Phase 6 与其他招聘平台仍需负责人另行批准。
