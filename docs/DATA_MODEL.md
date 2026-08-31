# JobPilot Local Data Model

> 状态：当前数据库 metadata 为空，没有业务表或 Alembic revision。以下未来概念不是已实现 schema。

## 1. Current baseline

- `Base.metadata` 不包含业务实体；
- `/health` 启动不创建 database engine；
- PostgreSQL URL 只允许 loopback host；
- migrations 与 integration tests 需要显式本地数据库 URL；
- 包含旧认证 revision 的预发布开发/测试数据库必须重建，不支持原地迁移。

一个安装实例隐含一个本地 workspace。当前没有 User、Identity、Session、Account 或 LocalProfile。

## 2. Modeling principles

- PostgreSQL 是未来本地业务事实来源；
- Web 与 Extension 不直接访问数据库；
- 单 workspace 模型不包含 `user_id`、tenant ID 或 owner ID；
- 时间统一保存为 UTC-aware timestamp；
- 枚举由 domain 与 API contract 共同固定；
- 外部 URL、页面文本和文件元数据都视为不可信输入；
- 只在对应 Phase 获批时创建表、约束和索引。

## 3. Future `Job`

Phase 3 的候选职责是保存用户确认后的岗位快照。概念字段可以包括：

- opaque `id`；
- source、source job ID、source URL；
- title、company、location、salary text；
- 用户确认后的 description；
- captured/saved/updated timestamps；
- 本地 dedupe key。

去重只发生在当前本地 workspace，不存在跨用户合并。JobPilot 后端不主动访问 source URL。

## 4. Future `Application`

Phase 4 的候选职责是记录一个 Job 的本地申请进度。概念字段可以包括：

- opaque `id`；
- `job_id`；
- status；
- note；
- applied/created/updated timestamps；
- append-only status event records。

Application、Job 和 ResumeVersion 的引用必须属于同一个本地数据库。由于只有一个 workspace，不需要 `user_id`。

## 5. Future `ResumeVersion`

Phase 4 的候选职责是标识用户本地保存的简历版本。概念字段可以包括：

- opaque `id`；
- label 与 version number；
- local object reference 或文件元数据；
- created timestamp。

文件保存、MIME/大小限制、恶意内容处理、导出和删除语义必须在上传功能获批前单独设计。

## 6. `LocalProfile` is not current scope

本机显示名、语言、时区或偏好只有出现真实产品需要时才进入 `LocalProfile` 设计。它不代表账号、远程身份或授权主体，也不能为了“以后可能需要”而提前建表。

## 7. Local data lifecycle

未来业务数据默认留在用户电脑。对应 Phase 必须提供可理解的本地备份、导出、删除和重建说明，不把云同步作为默认恢复路径。

操作系统账户和文件权限是本地静态数据边界；loopback 只限制网络暴露，不能防御同一操作系统账户下的恶意本机进程。

## 8. Future integrity gates

首次实现每个模型时至少重新评审：

- 主键、唯一约束和有界索引；
- 同 workspace 外键一致性；
- 删除/级联与文件一致性；
- 并发创建、去重和幂等；
- migration upgrade/downgrade；
- 本地备份与恢复；
- 不含 `user_id`、旧身份字段或 provider credential。
