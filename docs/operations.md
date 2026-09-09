# 故障恢复、容量与部署

## 故障策略

| 故障 | 策略 |
|---|---|
| Gateway/Worker 宕机 | 健康检查摘除；Redis pending reclaim；SQL lease 过期后接管 |
| IM 重复/乱序 | inbox 唯一键；Session accepted sequence；幂等 outbound |
| Redis/SQL 短暂不可用 | 有界退避、熔断；入口快速 ACK，任务保留在权威 outbox |
| 模型超时/限流 | 租户 fallback model、超时、预算门禁，失败话术可配置 |
| 工具失败 | 幂等工具有限重试；副作用工具未知结果进入人工处理 |
| 部分流式失败 | 关闭当前流，补发一次状态，不重复整段回答 |
| 配置发布错误 | immutable revision、tenant 级灰度、ETag 回滚 |

## 容量估算

先用压测测得单 Worker 稳态吞吐 `r_worker`、活跃 Runner 峰值内存 `m_runner`、模型并发 `c_model` 和 Redis/SQL QPS。`worker_count = ceil(peak_rate / r_worker × 1.3)`；并发上限取 `min(memory/m_runner, c_model, tool_pool)`。Gateway 以 callback P95 < 500 ms 为门禁，生产目标 IM 投递成功率 ≥99.9%。

## 部署分层

- 最小可运行：一个 FastAPI Gateway + 一个 Worker + InMemory（本仓库 `python -m trpc_service._cli demo`），用于离线演示。
- 联调 Compose：Gateway/Worker、Redis、PostgreSQL、OTel Collector，真实模型和 IM 通过环境变量注入。
- 生产 Kubernetes：Gateway/Worker/Admin 独立 Deployment/HPA，Redis/PostgreSQL HA，Vector/Object Storage、PDB、NetworkPolicy、Secret/KMS、Prometheus/OTel；队列恢复和投影任务独立扩容。

发布按租户 HMAC bucket 灰度；观察错误率、队列 lag、成本和 IM 投递指标，越阈值自动停止并将 active revision 回滚。
