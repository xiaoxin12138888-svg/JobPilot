# ADR-002：采用 FastAPI 与 PostgreSQL 作为后端基础

- **Status**：Accepted
- **Date**：2026-08-30

> **Local-first amendment（2026-09-01）**：[ADR-008](ADR-008-local-first-single-user-no-authentication.md) 保留 FastAPI + PostgreSQL 决定，但将其限定为本机 loopback/self-hosted 基础。本文对 pgvector 和 S3-compatible object storage 的表述只是未来候选，不是当前 runtime、云存储或远程服务授权；任何对象存储必须重新审批，并且不能成为本地核心的强制远程依赖。

## Context

JobPilot 需要稳定的 REST 契约、关系型业务数据、后续 AI/RAG 能力以及适合小团队的简单运维。核心实体之间关系明确，投递状态和版本数据需要事务一致性；当前没有多数据库或独立向量服务的规模证据。

## Decision

- 使用 Python + FastAPI 构建模块化单体 API。
- 使用 PostgreSQL 作为业务事实来源。
- 若未来 RAG Phase 另行获批，优先评估在本机 PostgreSQL 中启用 pgvector；当前不预承诺该扩展，向量和 chunk 必须是可重建派生数据。
- 若未来文件存储 Phase 另行获批，先设计本地文件/object-storage port，数据库只保存稳定引用和元数据。远程 S3-compatible 实现需要新的明确批准，且不得成为本地核心的强制依赖。
- 不在早期引入 MongoDB、Elasticsearch、独立向量数据库或分布式消息系统。

## Consequences

- FastAPI/Pydantic 适合明确请求、响应和 Structured Output 校验，也便于接入 Python AI 生态。
- PostgreSQL 以一个事务边界覆盖核心业务，减少同步和运维复杂度。
- 数据库 schema 变更必须使用迁移并经过评审。
- 若未来采用 pgvector，会增加索引与查询调优工作，但可避免维护第二套数据系统。
- FastAPI schema 与 TypeScript 客户端类型需通过 OpenAPI/契约测试保持一致。
- 如果未来搜索或向量负载出现可测量瓶颈，再基于性能数据评估专用系统。
