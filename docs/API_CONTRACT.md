# JobPilot API Contract

> 状态：`GET /health`、Job/Application 与 Phase 4 BOSS capture 所复用的 Job contract 已冻结。
> JSON 字段使用 camelCase。

## 1. Runtime boundary

默认 API origin 为 `http://127.0.0.1:8000`，只支持 loopback。没有账号、cookie、token、
session 或用户 endpoint。客户端请求使用 `credentials: omit`、`cache: no-store`、
`redirect: error` 和 5000 ms timeout。

写入还要求 loopback Host、安全的 Origin/Fetch Metadata 与 `application/json`。
CORS 只列精确 Web origin 和 `GET, POST, PATCH, DELETE`，不允许 credentials。
JobPilot Extension 只可写入 `POST /api/v1/jobs`，并要求精确 Origin
`chrome-extension://lgchonbleblfegkckndaaandoaekmgjf` 与 `Sec-Fetch-Site: none`；该 Origin
不属于 CORS allowlist，其他 Chrome Extension ID 即使格式合法也不受信任。

## 2. Health

`GET /health` 返回：

```json
{"status":"ok","service":"jobpilot-api"}
```

该请求不查询数据库或远程服务。

## 3. Job endpoints

### `POST /api/v1/jobs`

```json
{
  "title": "AI 产品经理实习生",
  "company": "测试公司",
  "location": "上海",
  "salaryText": "200-300 元/天",
  "source": "manual",
  "sourceUrl": "https://example.com/jobs/1",
  "description": "JD 快照",
  "notes": "本地备注"
}
```

`title`、`company` 必填；其他字段可为 null/省略，source 可为 `manual` 或 `boss`。`boss`
必须携带属于受支持 BOSS 岗位详情页的 HTTP/HTTPS `sourceUrl`。成功为 201。Web 手动录入与
Extension BOSS capture 均进入此 endpoint 和同一个 Job service；不存在 capture 专用保存接口。
服务端会把 BOSS `sourceUrl` 规范化为 scheme、精确 `www.zhipin.com` hostname 与岗位详情 path，
不保存 query 或 fragment；因此同一岗位的不同 tracking/session query 返回相同的 409 重复结果。
`manual` URL 继续保留有意义的 query。

### `GET /api/v1/jobs`

Query：

- `keyword`：title/company/location 简单包含匹配，最多 200 字符；
- `source=manual|boss`；
- `applicationStatus`：正式 Application status；
- `limit`：默认 50，1–100；
- `offset`：默认 0，非负。

按 `updatedAt` 倒序。响应：

```json
{"items":[],"total":0,"limit":50,"offset":0}
```

item 是 Job response，并增加 `applicationStatus`（可为 null）。

### `GET /api/v1/jobs/{jobId}`

返回 Job 或 404。

### `PATCH /api/v1/jobs/{jobId}`

接受 create 字段的非空 patch（可使用 null 清空可选字段），返回更新后的 Job。

### `DELETE /api/v1/jobs/{jobId}`

成功为 204；真实删除 Job 并由数据库级联 Application。Web 必须在调用前明确确认。

Job response 字段为：`id`、`title`、`company`、`location`、`salaryText`、
`source`、`sourceUrl`、`description`、`notes`、`createdAt`、`updatedAt`。
`normalizedSourceUrl` 是持久化去重字段，不公开。

## 4. Application endpoints

### `POST /api/v1/jobs/{jobId}/application`

JSON body 固定为空对象 `{}`。创建 `planned` Application，成功为 201。Job 不存在为 404；
该 Job 已有关联 Application 为 409。

### `GET /api/v1/applications`

支持 `jobId`、`status`、`limit`、`offset`；岗位详情使用 `jobId` 精确读取其至多一条
Application。列表 item 除 Application 字段外增加 `jobTitle` 与 `company`。

### `GET /api/v1/applications/{applicationId}`

返回 Application 或 404。

### `PATCH /api/v1/applications/{applicationId}`

```json
{"status":"applied","confirmApplied":true}
```

状态必须符合领域流转表。任何进入 `applied` 的请求都要求 `confirmApplied: true`。

Application response 字段为：`id`、`jobId`、`status`、`appliedAt`、
`createdAt`、`updatedAt`。

## 5. Errors

所有公开错误保持：

```json
{
  "error": {
    "code": "DUPLICATE_JOB_URL",
    "message": "该岗位链接已经保存",
    "requestId": "req_...",
    "resourceId": "existing-local-job-id"
  }
}
```

`resourceId` 仅在能安全标识相关本地资源时出现。BOSS 重复 URL 的 409 使用它指向已有 Job，
便于 Extension 打开本机详情；其他错误保持原有三字段 envelope。

主要状态：

- 404：Job/Application 不存在；
- 409：重复 normalized URL 或一个 Job 已有 Application；
- 422：request/domain validation 或非法状态流转；
- 503：SQLite 暂时 locked/busy；
- 403/415：localhost 写安全边界；
- 500：统一未知错误，不返回 exception、SQL 或 traceback。

响应均带 `X-Request-Id`，其值与 error envelope 一致。
