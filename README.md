# 基于 tRPC-Agent-Python 的多租户节点化 Agent 服务

本仓库是四周交付方案的完整代码基线。它把 tRPC-Agent-Python 的 Agent 编排能力包装成可服务多个企业租户的 Gateway/Worker 平台，支持企业微信、Telegram、飞书、租户级主备模型配置、Session/Memory 隔离、工具治理、审计、观测和后端可替换。默认 InMemory 模式用于本地演示；生产使用 PostgreSQL + Redis，并按 Gateway、Worker、Admin、Migration 四类角色部署。

## 1. 上游能力与复用边界

tRPC-Agent-Python 当前 README 提供：`LlmAgent` 与 `Runner`、Chain/Parallel/Cycle/Graph/Team 编排、FunctionTool/MCP、Skills、Session（InMemory/Redis/SQL）、Memory、Knowledge、Filter、FastAPI 服务化和 OpenTelemetry。平台直接复用这些能力，新增租户控制面、Channel Adapter、路由/幂等、Storage Router、治理策略、审计和部署层。`trpc_service/agent/runner.py` 的 `TRPCAgentExecutor` 是 Runner 适配点。


## 2. 快速运行

运行环境：Python 3.10+。项目依赖包含 `fastapi`、`uvicorn`、`cryptography` 和 `trpc-agent-py`；推荐使用 `uv sync` 安装完整环境。

```bash
uv run trpc-service demo
python -m trpc_service._cli serve
```

服务地址：`GET /health/live`、`GET /health/ready`、`POST /webhook/{tenant_id}/{channel}`、`GET /admin/tenants`。开发租户为 `acme`、`globex`，配置位于 `trpc_service/web/app.py`，生产环境应通过 Admin API/SQL 和 SecretRef 管理，不能使用示例 token。

Telegram JSON 示例（开发 binding）：

```bash
curl -X POST http://127.0.0.1:8080/webhook/acme/telegram \
  -H 'Content-Type: application/json' \
  -H 'X-Telegram-Bot-Api-Secret-Token: acme-telegram-secret' \
  -d '{"account_id":"acme-telegram","update_id":1,"message":{"message_id":7,"from":{"id":42},"chat":{"id":42,"type":"private"},"text":"你好"}}'
```

企业微信支持普通/加密 XML 回调、EncodingAESKey 解密、URL 校验、应用消息发送和临时素材下载；Telegram 支持 Bot API 文本/图片/文件发送、媒体下载及 429/5xx 重试。

企业微信智能机器人长连接使用 `Bot ID + Secret`，无需公网回调地址。将凭证写入 `.env`：

```dotenv
TRPC_SERVICE_WECOM_BOT_ID=你的BotID
TRPC_SERVICE_WECOM_BOT_SECRET_REF=env://WECOM_BOT_SECRET
WECOM_BOT_SECRET=你的Secret
TRPC_SERVICE_WECOM_BOT_TENANT_ID=acme
TRPC_SERVICE_IM_DRY_RUN=false
```

然后运行 `uv sync`、`uv run trpc-service serve`。通过 `GET /health/ready` 查看
`wecom_connections` 状态。长连接不使用 `/webhook/{tenant_id}/wecom`，该接口保留给旧的 Corp 应用回调模式。
当前 Bot 长连接要求 `TRPC_SERVICE_ROLE=all`，因为同一机器人只能保持一条有效 WebSocket，
接收消息和发送 Agent 回复必须由同一进程完成。

飞书通道支持 HTTP Webhook 和官方 SDK 长连接。长连接只需 App ID/App Secret 且无需公网域名；两种模式均通过 Open API 回复。完整配置见 [docs/feishu-setup.md](docs/feishu-setup.md)。

## 3. 设计交付物

- 架构、拓扑、时序和复用边界：[docs/architecture.md](docs/architecture.md)
- 数据模型：[docs/data-model.md](docs/data-model.md)
- 一致性、同步、幂等和迁移：[docs/consistency.md](docs/consistency.md)
- 企业微信/Telegram 接入：[docs/im-channels.md](docs/im-channels.md)
- 飞书机器人接入与使用：[docs/feishu-setup.md](docs/feishu-setup.md)
- 治理、监控、OTel 和安全：[docs/security.md](docs/security.md)
- 故障、容量、灰度和部署：[docs/operations.md](docs/operations.md)
- 风险清单（16 项）：[docs/risks.md](docs/risks.md)
- 四周时间计划与完成状态：[docs/implementation-plan.md](docs/implementation-plan.md)
- 完整实现进展与剩余环境验收：[docs/progress-report.md](docs/progress-report.md)
- 生产角色、配置、死信恢复和上线步骤：[docs/production-runbook.md](docs/production-runbook.md)

## 4. 四周计划摘要

| 周期 | 里程碑 | 状态 |
|---|---|---|
| 第 1 周 | 需求冻结、租户/Agent/Binding/Session/Event/Memory/Summary/Audit 模型、revision 与隔离 key | 已完成 |
| 第 2 周 | 无状态 Worker、幂等队列、Session lock、Memory、Filter、审计、脱敏、trace/metrics | 已完成 |
| 第 3 周 | 企业微信/Telegram Adapter、签名校验、Session ID、分段、FastAPI webhook/health/admin、demo | 已完成 |
| 第 4 周 | Redis Streams + PostgreSQL outbox/SQL Session、真实模型/IM、向量/对象存储、OTel/Prometheus、部署与恢复 | 代码完成；真实凭据、集群故障演练和压测待执行 |

完整验收口径见 [docs/implementation-plan.md](docs/implementation-plan.md)。InMemory 队列和存储仅用于单进程演示；生产启动会强制 PostgreSQL/Redis、强 Session HMAC key、真实模型凭据、独立迁移和非 dry-run IM 发送。

## 5. 目录结构（与题目 README 一致）

```text
|-- README.md
|-- build.sh / clean.sh / coverage.sh
|-- data
|-- docs
|-- format.sh / lint_flake8.sh
|-- start.sh / stop.sh
`-- trpc_service
    |-- _cli.py
    |-- agent       # Runner 适配与无状态 Worker
    |-- channels    # 企业微信、Telegram、飞书 Adapter 和分段/派送
    |-- config      # 环境设置与 SecretRef
    |-- log         # 日志与敏感信息脱敏
    |-- metrics     # trace context 和低基数指标
    |-- queue       # Redis Streams、pending reclaim、DLQ、Outbox
    |-- storage     # PostgreSQL、Redis、pgvector、S3、迁移
    |-- skill       # 预留 Skill 装载入口
    |-- tenant      # 租户模型、revision、Session/Memory/Audit 存储
    |-- tool        # 租户级工具 Filter
    |-- version.py
    |-- web         # FastAPI Gateway/Admin/health
    `-- workspace   # 本地/容器沙箱约定
```
