# JobPilot API Contract

> 状态：当前公开 API 只有 `GET /health`。Phase 3 尚未开始，未来业务 endpoint 尚未冻结。

## 1. Runtime boundary

- API 默认 origin：`http://127.0.0.1:8000`；
- supported launcher 只接受 IP-literal loopback bind；
- Web health client 只接受 `localhost`、`127.0.0.1` 或 `[::1]`；
- Extension 当前只接受精确 `http://127.0.0.1:8000`；
- 不支持公网、LAN 或远端 API；
- 当前没有账号、登录、cookie、token、session 或用户资料 endpoint。

CORS 只允许精确配置的 loopback Web origin。不允许 `*`、regex、userinfo、path/query suffix、Extension origin 或 credential allowance。Extension 通过 manifest 中精确的 loopback host permission 直接发送请求，不需要复制 Extension ID。

## 2. `GET /health`

### Request

- Method：`GET`
- Path：`/health`
- Body：无
- Cookie/credential：不发送
- Purpose：确认本机 FastAPI 进程可导入、启动并响应

客户端必须使用：

```text
cache: no-store
credentials: omit
redirect: error
Accept: application/json
```

客户端在 5000 ms 后中止未完成的请求。失败后只提供用户触发的 retry，不进行后台轮询或自动重试。

### Success

`200 OK`，响应必须精确包含两个字段：

```json
{
  "status": "ok",
  "service": "jobpilot-api"
}
```

不允许额外字段。非 200、重定向、非 JSON、错误字段、缺失字段或额外字段都视为 unavailable。

### Dependency boundary

supported API launcher 在 Uvicorn 前初始化本地 SQLite 文件。`GET /health` 请求本身不创建 engine、不读取业务表，也不访问招聘网站、对象存储、模型服务、telemetry、update 或其他远程依赖。

## 3. Shared TypeScript contract

当前唯一共享传输类型是：

```typescript
interface ApiHealthResponse {
  status: 'ok';
  service: 'jobpilot-api';
}
```

`packages/api-client` 在消费响应前按不可信数据校验精确 shape。React 与 Extension Popup 不自行复制解析规则。

## 4. Error and request metadata

API 保留统一 request ID、错误响应和 access-query redaction 基础设施。当前 health 正常路径直接返回 `ApiHealthResponse`，不套 `data` envelope。

未来业务错误在所属 Phase 中冻结，至少满足：

- machine-readable `code`；
- 面向用户的有界 `message`；
- request ID；
- 不返回堆栈、数据库细节、文件路径、原始页面数据或外部供应商 payload。

## 5. Future business contract rules

Phase 3 获批前不得添加 `/api/v1/jobs` 或其他业务路由。未来 Job、Application、ResumeVersion contract 必须遵守：

- 单安装、单 workspace，不接受也不返回 `userId`；
- request/response DTO 与 ORM model 分离；
- 外部 DOM、粘贴文本、URL 和文件一律在边界校验；
- 列表从首次实现起有界；
- 写接口在实现前冻结 Origin、Host、Fetch Metadata、localhost CSRF、DNS-rebinding 与幂等策略；
- JobPilot API 不主动请求 `sourceUrl` 或招聘网站；
- 字段和 endpoint 只能由当期 Phase 规格批准，不能从旧草案恢复。

若未来需要 `LocalProfile`，它是本地产品数据，不是账号或认证主体，并须由新的明确需求驱动。

## 6. Acceptance

当前 API contract 的验收条件：

- OpenAPI path 只有 `/health`；
- health 响应与 TypeScript contract 一致；
- supported startup 初始化默认 SQLite，重启不覆盖文件；health request 不执行数据库查询；
- bind 与 client base URL 拒绝非 loopback host；数据库工具只接受显式的本地 SQLite file URL；
- CORS 精确、GET-only、credential-free；
- Web 对 `checking / ready / unavailable`、Extension 对 `checking / available / unavailable` 以及两端的 retry 动作有自动化测试；
- Phase 3 业务路由为零。
