# ADR-002：采用 FastAPI 与 PostgreSQL 作为后端基础

- **Status**：Accepted
- **Date**：2026-08-30

## Context

JobPilot 需要稳定的 REST 契约、关系型业务数据、后续 AI/RAG 能力以及适合小团队的简单运维。核心实体之间关系明确，投递状态和版本数据需要事务一致性；当前没有多数据库或独立向量服务的规模证据。

## Decision

- 使用 Python + FastAPI 构建模块化单体 API。
- 使用 PostgreSQL 作为业务事实来源。
- RAG 到达对应阶段后，在同一 PostgreSQL 中启用 pgvector；向量和 chunk 是可重建的派生数据。
- 文件通过 S3-compatible object storage port 管理，数据库只保存稳定引用和元数据。
- 不在早期引入 MongoDB、Elasticsearch、独立向量数据库或分布式消息系统。

## Consequences

- FastAPI/Pydantic 适合明确请求、响应和 Structured Output 校验，也便于接入 Python AI 生态。
- PostgreSQL 以一个事务边界覆盖核心业务，减少同步和运维复杂度。
- 数据库 schema 变更必须使用迁移并经过评审。
- pgvector 会增加索引与查询调优工作，但避免早期维护第二套数据系统。
- FastAPI schema 与 TypeScript 客户端类型需通过 OpenAPI/契约测试保持一致。
- 如果未来搜索或向量负载出现可测量瓶颈，再基于性能数据评估专用系统。
