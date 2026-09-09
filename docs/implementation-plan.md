# 四周实施计划与完成状态

| 周期 | 目标 | 主要产出 | 状态 |
|---|---|---|---|
| 第 1 周 | 需求冻结与领域基线 | 架构图、租户/Agent/Binding/Session/Event/Memory/Summary/Audit 模型；`trpc_service/tenant` 注册表、revision、隔离 key | 已完成 |
| 第 2 周 | 核心运行链路 | `trpc_service/agent` 无状态 Worker、Session lock、Memory、幂等队列；`trpc_service/config` 设置和 SecretRef；`trpc_service/tool` Filter；`trpc_service/log` 脱敏；`trpc_service/metrics` trace/指标 | 已完成 |
| 第 3 周 | IM 与可运行入口 | `trpc_service/channels` 企业微信/Telegram Adapter、验签、Session ID、分段；`trpc_service/web` FastAPI webhook/health/admin；`_cli.py demo` 和 docs 全集 | 已完成 |
| 第 4 周 | 生产化联调与验收 | Redis Streams + PostgreSQL outbox/SQL Session、真实 tRPC Runner/模型、向量库/对象存储、OTel/Prometheus、Compose/K8s、恢复/迁移/灰度 | 代码完成；外部依赖联调、压测和故障演练待执行 |

## 第 1 周验收

- 两个租户可以配置不同 App、IM binding、工具策略和存储 profile。
- 相同外部 user/chat 在不同租户生成不同 HMAC Session ID。
- 配置发布使用单调 revision，支持 expected_version 冲突检测和回滚。

## 第 2 周验收

- 重复消息只产生一次队列任务；同 Session 的事件 sequence 连续。
- Worker 不保存路由状态，Session/Memory/Audit 均使用 tenant-scoped key。
- Filter 能拒绝超长输入、未授权用户和未 allowlist 的工具；日志不会暴露 token/password。

## 第 3 周验收

- 企业微信 SHA1 校验和 Telegram secret header 校验通过/失败均有明确结果。
- 消息归一化、群聊/单聊 Session 规则、平台长度分段和 outbound 记录可验证。
- `/health/live`、`/health/ready`、`/webhook/{tenant_id}/{channel}` 和受保护的 `/admin/tenants` 可运行；`python -m trpc_service._cli demo` 输出一条完整回复。

## 第 4 周退出标准

真实 Redis/SQL 写入后跨 Worker 可见；重复/乱序、节点终止、模型超时、工具失败、迁移和回滚演练均有证据；callback P95 < 500 ms、正常 IM 投递 ≥99.9%，并完成安全扫描和部署文档。

代码侧已经完成 PostgreSQL 权威 Inbox/Outbox/Session/Audit、Redis Streams consumer group、XAUTOCLAIM/heartbeat/DLQ、Session lease/fencing、Outbox 补偿扫描与人工重放、版本化 Summary/Knowledge/Vector 投影、S3 Artifact、真实 Runner/FunctionTool/MCP、模型 timeout/fallback、三种 IM、OTel/Prometheus、Admin CAS/RBAC 和 Compose/Kubernetes 清单。当前开发机缺少 Docker/Kubernetes 及真实平台凭据，因此 P95、99.9% 投递率、节点终止、真实 RLS、pgvector/MinIO 和平台回执属于部署环境验收项，不能由单元测试替代。
