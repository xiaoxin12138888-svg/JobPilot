# ADR-016：本地求职资料与安全表单自动填写

- **Status**：Accepted
- **Date**：2026-09-07
- **Decision owner**：JobPilot 项目负责人

## Context

JobPilot 已能管理岗位、投递、简历版本、面试与事实复盘，但招聘申请表仍反复要求用户填写相同的
结构化个人事实。项目负责人批准 Phase 9，以本地 Profile Vault、当前表单扫描、确定性字段映射、
填写预览和用户确认后的安全填写减少重复劳动。该功能辅助填写，不代表投递成功，也不授权自动
Submit、自动下一步、招聘平台私有 API、AI 字段识别或 Resume 解析。

Profile 含姓名、联系方式、教育与经历等私密信息；招聘页面及其 DOM 均为不可信输入。因此必须
把读取资料、扫描页面、填写页面和最终提交拆成明确边界，并在歧义或敏感场景中保守失败。

## Decision

1. 新增一个 single-user singleton `AutofillProfile`，与 `ResumeVersion`、`Application` 完全独立。
   Profile 只含 `personal`、`education[]`、`experience[]`、`links`：姓名、电话、邮箱、当前城市，
   学校/专业/学历/起止月，公司/职位/起止月/描述，以及 GitHub/作品集/主页。V1 不含身份证、护照、
   银行卡、民族、婚姻、政治面貌、家庭、详细地址、身体/宗教/残疾等低必要性敏感资料。
2. Profile 只写入 `runtime-data/jobpilot.db`。`0009_autofill_profile` 新增一个固定 singleton 行的
   `autofill_profiles` 表，以 canonical JSON 保存四个 section 与本地时间。不开 profile list、
   ownership、sync、history、Resume 导入或内容解析。migration 可逆，自动测试只用临时 SQLite。
3. API 固定为 `GET /api/v1/autofill-profile` 与 `PUT /api/v1/autofill-profile`。GET 返回
   `{profile: null}` 或当前 Profile；PUT 通过现有 Web 写安全边界原位创建/替换并返回同一 wrapper。
   Extension 只读 GET，不能写 Profile。所有字段在 API/domain 做纯文本、长度、日期与结构校验。
4. Extension manifest 权限继续只有 `activeTab`、`scripting` 与精确 loopback host；不增加
   `<all_urls>`、招聘站 host、content script、background、storage、cookies、webRequest、proxy、
   history 或远程 runtime。Profile 仅在本次 Popup 内存中存在，关闭即丢弃。
5. 扫描只能由用户点击“扫描当前表单”触发，且绝不修改页面。Scanner 只返回当前可见、未 disabled
   的必要控件描述：`ref`、label、kind、type、name、id、required、placeholder、autocomplete 与
   select options；不返回 HTML、DOM 对象、现有输入值、Cookie、storage、网络响应或页面私有状态。
6. Scanner 忽略 hidden、submit/button/reset/image、password、验证码/CAPTCHA、不可见/disabled
   控件和 JobPilot 自身 UI。FILE 可被识别但不可填写。`ref` 在一次 scan session 内优先唯一 id，
   其次唯一 name，否则使用可 round-trip 的 DOM path；无法唯一解析时不得填写。
7. Resolver 只识别批准的有限 canonical keys。Tier 1 exact alias 与 Tier 2 唯一 normalized/regex
   结果为 `READY`；Tier 3 唯一 fuzzy candidate 只能为 `REVIEW_REQUIRED`；其余为 `UNMAPPED`。
   缺少 Profile value、FILE、radio/checkbox 以及敏感/法律/协议/EEO/工作授权等字段为 `MANUAL`。
   不展示数字置信度。多条教育/经历只按页面现有同类字段的 DOM 顺序对应 Profile 数组，不点击
   “添加经历”；数量或结构不清晰时保持人工处理。
8. Scan 后在 Popup 生成内存态 `FillPlanItem`。READY 默认选中，REVIEW_REQUIRED 默认不选中且
   只有用户明确勾选后才可填写；MANUAL/UNMAPPED 不可选。手机号和邮箱只在预览中遮罩，Executor
   仍使用内存中的真实值。用户可以取消任何可填写项。
9. Fill 需要第二个明确按钮“填写已确认字段”。Executor 先校验同一页面 URL、稳定 ref 与扫描时
   字段签名；唯一 id/name 是字段主身份，动态框架可改写另一个辅助标识及 required/placeholder/
   autocomplete，但 kind 与 input type 必须不变。失效字段跳过，重渲染恢复使用所有字段共享的
   最长 1 秒有界预算，大量失效返回脱敏的重新扫描提示。Text/Textarea/原生日期
   使用 native prototype setter 与最小 `focus → input → change → blur` 标准事件；不访问 React/Vue
   私有对象。原生 Select 仅接受唯一 exact/normalized/contains option。
10. Combobox V1 仅在标准 DOM 中保守尝试：输入值后等待可见 options，仅唯一明确匹配时选择；
    零个或多个候选即恢复原值并报告失败。复杂第三方日期、普通 radio/checkbox、FILE 与任何敏感
    控件均保持 MANUAL，不建立框架专属引擎或平台 Adapter。
11. Executor 永远不调用 `form.submit()`、`requestSubmit()`、submit button click 或等价提交/下一步
    行为，也不点击协议。完成后只提示用户检查并自行 Submit。Fill 不创建 Application，也不改变
    Application 状态；只有用户在 JobPilot 中另行明确记录投递事实。
12. Phase 9 全链路不调用 `JOBPILOT_LLM_*` 或其他远程服务；Provider 未配置时必须完整工作。
    Profile/建议值不进入日志、console、errors、Git、docs、真实 fixture、Extension storage 或
    telemetry。生产诊断只允许非敏感状态与计数。
13. 真实验收至少使用一个由用户打开的真实招聘/ATS 表单，记录检测与填写计数，人工复核 mapping
    和页面结果，并证明 `Submit Triggered = NO`。在负责人确认前只能报告
    `USER ACTION REQUIRED — REAL AUTOFILL ACCEPTANCE`，不能自动宣布 Phase 9 PASS。
14. JobFill（MIT）只作为研究参考；若实质复制必须逐文件记录来源并满足 MIT notice。
    jobApplier 未确认显式 License，只能学习分层、状态机与安全原则，禁止复制源码。JobFill 的
    React Fiber/Phoenix 等私有组件调用不采用。

## Consequences

- 用户获得 `Profile → Scan → Resolve → Preview → Confirm → Fill → Human Submit` 的本地辅助链路，
  同时明确保留扫描、填写和投递三个独立动作。
- 单表 singleton、四个聚焦 Extension 模块和现有 Web/API patterns 足够支持 V1；不建立
  AutofillEngineBase、AdapterRegistry、Plugin、DSL、Profile repository interface hierarchy 或
  AI mapper framework。
- 保守规则会让部分复杂控件保持手填，这是避免敏感误填、错误 DOM 和意外提交的有意取舍。
- Phase 7 保持 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。任何 Resume Import/Builder、
  AI Autofill、平台专用 Autofill Adapter 或 Phase 10 都必须另行批准。

## Acceptance evidence

2026-09-07，真实 Chrome 中国移动校招表单检测 37 个字段（READY 1、REVIEW_REQUIRED 2、
MANUAL 26、UNMAPPED 8），用户只选择姓名并成功填写。attempts/success/failure 为 1/1/0，
`Submit triggered: NO`；未点击 Continue、协议、上传或其他字段。项目负责人确认映射、建议值、
页面结果和无意外动作，Phase 9 标记 PASS，并停止在 Phase 10 之前。
