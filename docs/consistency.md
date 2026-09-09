# 数据同步、幂等与多后端一致性

## 权威与一致性分层

第 4 周生产实现以 PostgreSQL 为配置、Inbox、Session event、audit 的权威；Redis Streams 只作至少一次通知，丢失后可由 outbox/reconciler 重建；Redis 适合低延迟 Session/lock/cache；向量库、外部 Memory 和对象存储是带 `source_version`/checksum 的最终一致投影。MVP 的 InMemory 只用于单进程开发和单元测试。

| 数据 | 推荐后端 | 一致性与恢复 |
|---|---|---|
| 配置、binding、audit | SQL | 事务强一致、revision/ETag CAS |
| Session event/state、幂等 | SQL + Redis | 同 Session 串行，version CAS；Redis 可重建 |
| 队列与短锁 | Redis Streams | at-least-once、pending reclaim、TTL lease |
| Memory/Summary | SQL 事实 + Redis 缓存 | 事实强一致，缓存失效或按版本回退 |
| Knowledge embedding | pgvector/Qdrant | 最终一致，记录 embedding_version 和 lag |
| Artifact bytes | S3/MinIO | staging + checksum + metadata 事务 |

## 同 Session 写入顺序

`claim writer lease → append user/tool/assistant events → version-CAS 更新 state → commit → 异步 summary → memory/vector projection → outbound delivery`。事件 sequence 连续；summary 只接受 `source_version >= current`；投影落后时回答回退到 SQL 事实或显式提示。生产实现不在模型执行期间持有 SQL 事务，提交时校验 lease_owner/epoch，旧 Worker 只能得到 fencing conflict。

## 幂等策略

1. IM 入口使用 `(tenant_id, channel, account_id, external_message_id)` inbox 唯一键；重复回调直接 2xx，若已有结果只重试 outbound。
2. Queue task 使用 `task_id`，消费端允许重复但 Claim 只成功一次。
3. 有副作用工具必须接收 `tenant_id:session_id:event_id:tool_name` 的 execution key；未知结果不自动重放，进入人工确认。
4. Outbound 记录 `in_reply_to + part`，超时标记 ambiguous，不能盲目发送整段两次。

## 迁移

Redis→SQL 或本地向量库→远端向量库遵循 `prepare → backfill → checksum → dual-write/outbox → shadow-read → tenant cutover → observe → rollback/cleanup`。全量复制按租户和游标分批，固定序列化与 embedding 版本；shadow-read 比对 event count、checksum、Recall@K；只切换一个租户，保留回滚窗口。
