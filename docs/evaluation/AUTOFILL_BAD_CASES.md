# Autofill Bad Cases

> 状态：真实 ATS 验收完成。本文只记录真实观察，不把 synthetic fixture 或推测写成真实 Bad
> Case。

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

### AF-BC-001：唯一主引用稳定但辅助标识变化导致安全误拒绝

| 字段 | 内容 |
| --- | --- |
| BC ID | `AF-BC-001` |
| Platform | 中国移动校招表单 |
| Field label | 姓名 |
| Control type | text input |
| Expected canonical key | `name` |
| Actual result | Preview 映射正确，但 Fill 被错误报告为字段结构变化；未写入其他字段，未 Submit |
| Status | P2 |
| Observed problem | 页面保留唯一主 ref 与 text 类型，但框架改写辅助字段标识后，旧签名校验持续拒绝填写 |
| Root cause | Executor 在已有唯一 id/name 主引用之外仍要求另一个辅助 id/name 完全不变，动态表单因此产生 false stale |
| Fix | 唯一 id/name 作为主身份；仍严格核对 URL、唯一性、kind/type，并为重渲染提供所有字段共享的最长 1 秒恢复预算 |
| Regression result | PASS；真实 attempts/success/failure 1/1/0，`Submit triggered: NO` |
