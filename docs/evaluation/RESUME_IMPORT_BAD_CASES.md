# Resume Import Bad Cases

> 状态：实现、自动化与虚构文件隔离浏览器验收已完成，等待真实简历人工验收。这里只记录真实
> 脱敏验收事实；synthetic fixtures 与推测不计为真实 Bad Case。

## Severity

- P0：已有数据覆盖、文件安全/隐私泄漏、远程上传或恶意 parser 行为；
- P1：大段缺失、Profile 字段错误、教育/经历错误合并；
- P2：section 标题遗漏、换行或格式质量。

## Record format

| Field | Meaning |
| --- | --- |
| ID | Stable Bad Case ID |
| Format | PDF / DOCX |
| Observed | 实际脱敏现象 |
| Expected | 期望行为 |
| Root Cause | 经验证的原因 |
| Fix | 实际修改 |
| Regression Result | 复测结果 |

## Real Bad Cases

尚无。完成项目负责人对一份脱敏 DOCX 和一份脱敏 PDF 的人工验收后，只追加真实观察。
