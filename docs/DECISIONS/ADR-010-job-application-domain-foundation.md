# ADR-010：Job 与 Application 领域基础

- Status: Accepted
- Date: 2026-09-03

## Context

Phase 2.5 已固定 local-first、single-user 与 SQLite 基线，但尚无业务表。项目负责人批准
Phase 3 同时交付可手动使用的岗位库和投递跟踪；旧 Roadmap 中“Phase 3 先做 Adapter、
Phase 4 再做 Application”的顺序不再适用。

## Decision

- Phase 3 只创建 `jobs` 与 `applications` 两张表，不创建 Adapter、ResumeVersion、事件流或 AI 数据。
- Job 是用户主动保存的本地岗位快照；当前唯一可创建来源为 `manual`。
- HTTP/HTTPS `source_url` 规范化后唯一；没有 URL 时不做模糊去重。
- Job 使用显式确认后的真实删除，并级联删除其 Application；当前不引入归档系统。
- 一个 Job 最多一个 Application。Application 初始状态为 `planned`，状态流转由小型显式领域规则控制。
- 任何进入 `applied` 的流转都要求 `confirmApplied: true`；打开原平台链接永不修改本地状态。
- Router 仅负责传输验证和映射；领域规则位于 domain/application service，持久化使用两个非泛型 repository。
- 列表使用 `limit`/`offset`（默认 50、最大 100），JSON 使用 camelCase。
- 首个写接口保持 loopback、credential-free 精确 CORS，并增加 Host、unsafe Origin/Fetch Metadata 与 JSON 边界检查。

## Consequences

用户无需招聘网站 Adapter 即可手动录入岗位、创建投递并跟踪状态。后续 Phase 4 可以在不改变
本阶段数据所有权和用户确认原则的前提下增加第一个招聘网站 Adapter；一岗多投、状态事件、
ResumeVersion、自动投递与云同步仍需另行批准。

