# Interview Record V1

## Boundary

Interview Record 是已有 Application 下的本地事实记录。它不调用 LLM、不读取简历正文、不接触
Extension，也不代表 JobPilot 自动判断面试表现或推进投递状态。问题、回答、面试官备注和复盘均按
untrusted plain text 处理，只写入本机 SQLite。

## Model

一条 Application 可以有多轮 `InterviewRound`，一轮可以有多道 `InterviewQuestion`。

Round 包含：

- 必填 `roundName` 与 `PHONE|VIDEO|ONSITE|OTHER` 类型；
- 可选计划时间与 `PLANNED|COMPLETED|CANCELLED` 状态；
- 可选面试官备注；
- 用户手填的 `wentWell`、`couldImprove`、`learningNotes`、`otherNotes`。

Question 包含：

- 必填实际问题；
- 手选 `PRODUCT|AI|TECHNICAL|PROJECT|BEHAVIORAL|BUSINESS|OTHER` 分类；
- 可选用户回答摘要；
- `GOOD|OK|POOR|NOT_SURE` 自评；
- 可选备注。

文本统一换行、删除受限控制字符、裁剪首尾空白并执行长度上限。API 和 Web 不使用 HTML 渲染。

## Lifecycle and independence

- 创建轮次默认为 `PLANNED`，用户可编辑或显式标记完成/取消。
- 创建、完成、取消或删除轮次不会改变 Application status。
- Application status、`outcomeNote` 与 `rejectionReason` 仍由投递区单独显式保存。
- 删除轮次前 Web 必须确认；数据库级联该轮全部问题。
- 删除 Application 级联其所有轮次/问题；Job 删除继续通过 Application 级联。
- 不创建软删除、事件流、自动摘要、推荐、评分或第二套结果状态机。

## API and client

Application 下的轮次列表使用 limit/offset，并在每轮响应中包含完整 questions，避免 Web 产生
N+1 请求。轮次和问题写入复用现有 loopback Host、Origin/Fetch Metadata、JSON-only、
no-credentials 与统一错误信封。shared-types 与 api-client 对 enum、nullable 字段和嵌套响应进行
运行时校验。

## Privacy and verification

自动化只使用虚构内容。日志、错误、telemetry、Extension、Git 和真实 fixture 都不得包含面试
内容。Phase 8 浏览器验收必须在 Provider 未配置时录入至少一轮、三道虚构/历史问题、回答自评和
手动复盘，标记完成并在 API/Web 重启后确认持久化；不得人工改数据库。
