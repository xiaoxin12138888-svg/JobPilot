# Autofill Bad Cases

> 状态：真实 ATS 验收待进行。本文只记录真实观察，不把 synthetic fixture 或推测写成真实 Bad
> Case；当前没有可报告的真实 BC。

## 优先级

- P0：填错敏感字段、自动 Submit、填到错误 DOM、隐私泄露；
- P1：错误 canonical mapping、错误 option、页面重渲染导致错填；
- P2：无法识别、需要手填、样式问题。

## 记录格式

| 字段 | 内容 |
| --- | --- |
| BC ID | `AF-BC-###` |
| Platform | 招聘平台或 ATS |
| Field label | 页面可见字段名 |
| Control type | input/select/combobox/date/... |
| Expected canonical key | 预期 canonical key 或 MANUAL/UNMAPPED |
| Actual result | 实际映射/填写结果 |
| Status | P0/P1/P2 |
| Observed problem | 只写真实观察 |
| Root cause | 经验证的根因 |
| Fix | 实际修复；未修则写 PENDING |
| Regression result | PASS/FAIL/NOT RUN |

## Real Bad Cases

尚无。完成真实表单的 Scan/Preview/Fill（不 Submit）并获得项目负责人确认后，在此追加事实记录。
