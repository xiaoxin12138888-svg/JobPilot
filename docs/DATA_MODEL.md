# JobPilot Local Data Model

> 状态：Alembic revision `0001_job_application` 已创建 Phase 3 的 `jobs` 与
> `applications`。Phase 4 contract 由 `0002_boss_job_source` 仅扩展 Job source CHECK；没有
> 新业务表。

## 1. Storage rules

- 唯一 runtime database：`runtime-data/jobpilot.db`；
- 一个安装实例隐含一个 workspace，不使用 `user_id`、tenant 或 owner；
- SQLAlchemy transaction + Alembic migration；
- 每个连接 `foreign_keys=ON`、`busy_timeout=5000`，当前 rollback journal；
- 时间由应用按 UTC 写入，API 返回 ISO 8601；
- test/clean/build/format 不得读写或删除真实 runtime database。

## 2. `jobs`

| 列 | 类型/约束 |
| --- | --- |
| `id` | String(36), PK |
| `title` | String(200), NOT NULL |
| `company` | String(200), NOT NULL |
| `location` | String(300), nullable |
| `salary_text` | String(300), nullable |
| `source` | String(32), NOT NULL, CHECK IN (`manual`, `boss`) |
| `source_url` | String(2048), nullable |
| `normalized_source_url` | String(2048), nullable, UNIQUE |
| `description` | Text, nullable |
| `notes` | Text, nullable |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

索引：`updated_at`、`source`。SQLite UNIQUE 允许多个 NULL，因此无 URL Job 不做去重。
规范化 URL 只接受 HTTP/HTTPS、无 userinfo；lowercase scheme/host、去默认端口和 fragment，
保留 path/query。原始 `source_url` 供用户打开。`boss` 来源还要求 URL 属于受支持的 BOSS
岗位详情页；所有招聘页面字段只作为有长度边界、去明显控制字符的纯文本保存。

## 3. `applications`

| 列 | 类型/约束 |
| --- | --- |
| `id` | String(36), PK |
| `job_id` | String(36), NOT NULL, FK jobs.id ON DELETE CASCADE, UNIQUE |
| `status` | String(32), NOT NULL, CHECK 正式状态集合 |
| `applied_at` | DateTime, nullable |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

索引：`(status, updated_at)`。唯一 `job_id` 固定一岗一个 Application。
`applied_at` 在首次确认进入 applied 时写入，后续用户更正状态不抹除首次投递时间。

## 4. State machine

显式允许表（同状态更新为 no-op）：

- planned → applied / withdrawn / closed
- applied → planned / screening / assessment / interviewing / rejected / withdrawn / closed
- screening → applied / assessment / interviewing / rejected / withdrawn / closed
- assessment → screening / interviewing / rejected / withdrawn / closed
- interviewing → assessment / offer / rejected / withdrawn / closed
- offer → interviewing / closed
- rejected → interviewing / closed
- withdrawn → applied / closed
- closed → offer / rejected / withdrawn

任何目标为 applied 的流转都要求显式确认。不创建 event sourcing 或 audit table。

## 5. Deletion and deferred models

Web 明确确认后真实删除 Job，SQLite 级联其 Application；当前无 archive/restore。

Phase 3 不创建 ResumeVersion、Interview、Document、Evidence、AI result、User、Identity、
Session 或 LocalProfile。任何新表必须在对应 Phase 获批后设计 migration 与生命周期。
