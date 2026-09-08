# Profile Vault 与安全表单自动填写

> 状态：PASS；实现、自动化验证和真实中国移动校招表单人工验收均已完成。
> Phase 7 继续保持 `IMPLEMENTED — SEMANTIC ACCEPTANCE PAUSED`。

## 产品边界

Phase 9 只解决招聘申请表中高频事实的重复输入：

```text
本机 Profile -> 用户点击 Scan -> deterministic Resolve -> Preview
-> 用户确认/取消 -> 用户点击 Fill -> 人工检查 -> 用户自己 Submit
```

`Scan != Fill != Submit` 是实现边界。扫描不修改页面；填写不代表投递；JobPilot 不点击 Submit、
Continue、协议或隐私授权，不创建 Application，也不改变 Application 状态。完整流程不依赖 LLM。

## Profile Vault

`AutofillProfile` 是一个与 Resume Version、Job、Application 独立的 single-user singleton：

- `personal`：name、phone、email、currentCity；
- `education[]`：school、major、degree、start、end；
- `experience[]`：company、position、start、end、description；
- `projects[]`：name、role、start、end、description；
- `links`：github、portfolio、homepage。

教育、工作/实习和项目经历各最多 20 条，月份使用 `YYYY-MM`，链接只接受无 userinfo 的 HTTP(S)。整个 Profile
至少有一个事实；空经历条目拒绝。默认不收集身份证、护照、银行卡、民族、婚姻、政治面貌、
家庭成员、详细住址等没有高频 Autofill 价值的敏感事实。

Web 的“求职资料”页面支持查看、编辑、保存和多条教育、工作/实习及项目经历。Phase 10 的本地
Resume Import 只有在用户预览并明确勾选后才会追加所选资料。Profile 只写本机 SQLite 的
`autofill_profiles` row 1；不写 Extension storage，不同步云端。

## API 与浏览器安全

- `GET /api/v1/autofill-profile` 返回 `{profile: null}` 或当前 Profile；
- `PUT /api/v1/autofill-profile` 是 Web 的完整替换；
- Web 继续使用精确 loopback CORS、`credentials: omit`、JSON-only mutation；
- Extension GET 只允许固定 Origin
  `chrome-extension://lgchonbleblfegkckndaaandoaekmgjf` + `Sec-Fetch-Site: none` + loopback Host；
- Extension 不可 PUT Profile；其他 Extension ID、cross-site Web 和非 loopback target 均拒绝。

Manifest 权限保持 `activeTab`、`scripting` 和 `http://127.0.0.1:8000/*`。没有 `<all_urls>`、
background、content script、storage、cookies、webRequest、proxy、history 或招聘网站 host。

## Scanner

用户点击“扫描当前表单”后，`scanApplicationForm` 通过一次 `chrome.scripting.executeScript`
注入。函数自包含，不依赖 page private state。它最多返回 250 个字段、每字段最多 200 个 option：

```text
FormFieldDescriptor {
  ref, label, kind, type, name, id,
  required, placeholder, autocomplete, options
}
```

kind 只允许 TEXT、TEXTAREA、SELECT、COMBOBOX、DATE、RADIO、CHECKBOX、FILE、UNKNOWN。Scanner
忽略 password、验证码、hidden、submit/button/reset/image、不可见、disabled/aria-disabled 和
`data-jobpilot-ui` 控件。不读取或返回当前 value、HTML、Cookie、Web Storage 或页面私有对象。

Label 依次使用显式 label、aria-labelledby、aria-label、closest label、placeholder、name、id、
有界 form-item/preceding text 和 data label。所有语义文本均有长度上限，不读取大块父 DOM。

Ref 在当前扫描中唯一：优先唯一 id，其次唯一 name，否则使用可被 `querySelector` 唯一回溯的
tag/nth-of-type DOM path。扫描会话只保留在 Popup 内存，并记录 tab、page URL 与 scan token。

## Resolver 与 Preview

Resolver 只使用有限 canonical keys：name、phone、email、current_city、school、major、degree、
education_start/end、company、position、experience_start/end/description、github、portfolio、
homepage。匹配层级固定：

| 结果 | 状态 | 默认选择 |
| --- | --- | --- |
| exact alias / normalized exact | READY | 是 |
| 唯一 substring fuzzy candidate | REVIEW_REQUIRED | 否 |
| 敏感、文件、radio/checkbox、缺 Profile 值 | MANUAL | 否且不可填 |
| 未知或多候选歧义 | UNMAPPED | 否且不可填 |

不显示数字置信度，不调用 LLM。页面已有多组同类教育/经历字段时，同一 canonical key 按 DOM
顺序取 Profile 对应条目；Extension 不点击“添加教育/经历”。Preview 只把 phone/email 显示为
遮罩值，真实值仅保留在内存 Fill Plan。用户可取消 READY，也可明确勾选 REVIEW_REQUIRED。
`projects[]` 不属于 Resolver canonical keys；Extension 不扫描、映射或填写项目字段。

## Fill Executor

Fill 前 Extension 再次确认活动 tab id 和 URL。页面内 Executor 再次确认：

- URL 与扫描时完全一致；
- ref 仍唯一指向目标元素；唯一 id/name 是主身份，另一个辅助标识和表单提示允许被框架改写；
- kind 与 input type 未变化；DOM path ref 继续核对完整 name/id/required/placeholder/autocomplete；
- 控件仍可见、非 disabled/aria-disabled、非 readonly；
- 控件和语义不属于 password、验证码、证件、薪资、法律/协议/隐私等敏感策略。

Text/textarea/date/month 使用对应原生 prototype value setter，再触发 focus、input、change、blur。
Native select 按 value exact、label exact、normalized exact、唯一包含逐层选择；任何层出现多个候选
都不猜。Combobox 只支持 input/textarea + aria-controls + 唯一安全 role=option；模糊多候选时恢复
原文本并返回失败。FILE、radio、checkbox 和复杂第三方 calendar 保持手动。

实现不访问 React Fiber、Vue 私有状态或 Phoenix 私有 API，不调用 `form.submit()`、
`requestSubmit()` 或 Submit/Continue 按钮。页面变化或大量 ref/signature 失效时返回 PAGE_CHANGED；
其他失败按字段返回不含值的固定 code。生产代码不记录 Profile、建议值或页面 payload。

## 测试与验收

本地 fixture 覆盖 label/ARIA/placeholder、textarea、select、month、combobox、unknown、checkbox、
radio、file 及禁止字段。自动测试覆盖 Scanner、Resolver、Preview、native setter/event、select/
combobox 歧义、URL/ref/signature stale、敏感字段二次拒绝与 no-submit。

Extension build artifact 会检查权限、公钥 ID、CSP、remote URL、storage/cookie/history/webRequest/
proxy、telemetry、private framework API、auto-submit 与 secret-bearing 配置。

2026-09-07 自动质量门结果：222 条 TypeScript 与 224 条 Python 测试全部通过；其中真实 ATS
修复后 Extension 独立套件为 112 条。TypeScript
typecheck、ESLint、Prettier、Ruff、Web/Extension build、artifact security、API import/start 及
`0009` upgrade -> downgrade -> upgrade 均通过。Python runtime 和 migration 只使用显式临时
SQLite，且 LLM 配置为空。隔离 Web 浏览器使用虚构资料验证了两条教育、两条经历的保存与刷新
持久化；本地 fixture 验证了 UTF-8 中文、语义 DOM、无横向溢出和无 console error/warning。
真实 ATS 修复同时覆盖稳定 Popup 宽度、动态表单提示变化、辅助字段标识变化和最长 1 秒的全局
有界重渲染恢复；URL、唯一主 ref、kind/type、敏感字段和 no-submit 安全边界保持不变。

2026-09-07 在用户打开的真实中国移动校招表单完成 Scan → Preview → Confirm → Fill → 人工检查：
detected 37、READY 1、REVIEW_REQUIRED 2、MANUAL 26、UNMAPPED 8、selected 1；
attempts/success/failure 为 1/1/0，`Submit triggered: NO`。只填写姓名字段，未点击 Continue、协议、
上传或其他字段；项目负责人确认映射、建议值、页面结果和无意外操作。Phase 9 标记 PASS。
