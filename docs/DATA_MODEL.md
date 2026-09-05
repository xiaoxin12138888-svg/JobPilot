# JobPilot Local Data Model

> 状态：`0001_job_application` 创建 `jobs`/`applications`，`0002`/`0003` 扩展 Job source，
> `0004_jd_analysis_records` 新增单 Job 当前分析，`0005_resume_versions` 与
> `0006_evidence_map_records` 新增 Phase 7 本地简历版本、Application 关联和当前 Evidence Map。

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
| `source` | String(32), NOT NULL, CHECK IN (`manual`, `boss`, `nowcoder`) |
| `source_url` | String(2048), nullable |
| `normalized_source_url` | String(2048), nullable, UNIQUE |
| `description` | Text, nullable |
| `notes` | Text, nullable |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

索引：`updated_at`、`source`。SQLite UNIQUE 允许多个 NULL，因此无 URL Job 不做去重。
规范化 URL 只接受 HTTP/HTTPS、无 userinfo；lowercase scheme/host、去默认端口和 fragment。
`manual` 保留 path/query，原始 `source_url` 供用户打开。`boss` 来源要求 URL 属于精确
`www.zhipin.com/job_detail/{id}.html`；`nowcoder` 来源要求 URL 属于精确
`www.nowcoder.com/jobs/detail/{numeric-id}`。两个平台来源都会把 `source_url` 与去重字段收敛到
scheme、host、path，不保存 tracking/session query 或 fragment。所有招聘页面字段只作为有
长度边界、去明显控制字符的纯文本保存。

## 3. `applications`

| 列 | 类型/约束 |
| --- | --- |
| `id` | String(36), PK |
| `job_id` | String(36), NOT NULL, FK jobs.id ON DELETE CASCADE, UNIQUE |
| `status` | String(32), NOT NULL, CHECK 正式状态集合 |
| `resume_version_id` | String(36), nullable, FK resume_versions.id ON DELETE RESTRICT |
| `applied_at` | DateTime, nullable |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

索引：`(status, updated_at)`。唯一 `job_id` 固定一岗一个 Application。
`applied_at` 在首次确认进入 applied 时写入，后续用户更正状态不抹除首次投递时间。
`resume_version_id` 创建时为 null，只由用户明确设置、更换或清空；不由 Job save、Application create
或 Evidence Map 自动推断。

## 4. `jd_analysis_records`

| 列 | 类型/约束 |
| --- | --- |
| `id` | String(36), PK |
| `job_id` | String(36), NOT NULL, FK jobs.id ON DELETE CASCADE, UNIQUE |
| `schema_version` | Integer, NOT NULL, CHECK = 1 |
| `result_json` | Text, NOT NULL，canonical structured JSON |
| `source_fingerprint` | String(64), NOT NULL，分析输入 SHA-256 |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

每个 Job 至多一个分析；reanalysis 保留 id/created_at 并更新 result、指纹和 updated_at。指纹只覆盖
实际发送的 title/company/description/location/salaryText，不包含 notes 或 Application。GET 用当前
指纹计算 `isStale`，该布尔值不持久化。正式结果始终是 schema version 1 JSON，不拆 skill 表。

## 5. `resume_versions`

| 列 | 类型/约束 |
| --- | --- |
| `id` | String(36), PK |
| `name` | String(200), NOT NULL |
| `content` | Text, NOT NULL，untrusted plain text |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

索引：`updated_at`。版本彼此独立；duplicate 复制正文并创建新 id/时间。Repository 查询动态计算
`application_count`，不持久化冗余计数。Application 引用存在时 service 返回
`RESUME_VERSION_IN_USE`，数据库 RESTRICT 作为完整性后盾。

## 6. `evidence_map_records`

| 列 | 类型/约束 |
| --- | --- |
| `id` | String(36), PK |
| `job_id` | String(36), NOT NULL, FK jobs.id ON DELETE CASCADE |
| `resume_version_id` | String(36), NOT NULL, FK resume_versions.id ON DELETE CASCADE |
| `schema_version` | Integer, NOT NULL, CHECK = 1 |
| `result_json` | Text, NOT NULL，canonical structured JSON |
| `job_analysis_fingerprint` | String(64), NOT NULL |
| `resume_content_fingerprint` | String(64), NOT NULL |
| `created_at` | DateTime, NOT NULL |
| `updated_at` | DateTime, NOT NULL |

唯一约束：`(job_id, resume_version_id)`。每组只保留当前记录；成功重新生成保留 id/created_at 并
更新 result、两份指纹与 updated_at。GET 与当前 JD Analysis/Resume content 指纹比较后计算
`isStale`，不持久化该布尔值。生成失败不更新或删除旧行。`result_json` 只保存 schema version 1
的 requirement mappings，不拆 Evidence/score 表。

## 7. Application state machine

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

## 8. Deletion and deferred models

Web 明确确认后真实删除 Job，SQLite 级联其 Application、JD analysis 与 Evidence Map；当前无
archive/restore。被 Application 引用的 Resume Version 不可删除；未引用版本删除时级联其
Evidence Map。

Phase 7 不创建 Resume 文件/文档、Interview、Recommendation、Score、Embedding、Vector、User、
Identity、Session 或 LocalProfile。任何新表必须在对应 Phase 获批后设计 migration 与生命周期。
