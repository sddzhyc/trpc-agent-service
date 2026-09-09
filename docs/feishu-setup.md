# 飞书机器人接入与使用

当前飞书通道支持 HTTP Webhook 和飞书官方 SDK 长连接两种接收模式。Webhook 支持 URL challenge、Verification Token、Encrypt Key 回调签名和 AES-256-CBC 解密；两种模式都支持 `im.message.receive_v1` 文本事件、机器人自消息过滤、单聊/群聊 Session、事件幂等、App Secret 换取并缓存 `tenant_access_token`，以及调用飞书 Open API 回复原消息。

## 1. 飞书开放平台配置

1. 在飞书开放平台创建“企业自建应用”，记录 **App ID** 和 **App Secret**。
2. 在应用能力中添加“机器人”。
3. 为应用申请消息相关权限，至少包含接收消息和“以应用身份发送消息”；具体权限名称以开放平台当前控制台为准，常见权限为 `im:message`、`im:message:send_as_bot`。
4. 在“事件与回调”中选择“将事件发送至开发者服务器”，添加事件 `im.message.receive_v1`。
5. 设置请求地址：`https://<公网域名>/webhook/<tenant_id>/feishu`。示例租户地址为 `https://agent.example.com/webhook/acme/feishu`。
6. 记录事件配置中的 **Verification Token**，建议同时设置 **Encrypt Key**。
7. 发布应用版本，并将机器人加入测试群或授权给测试用户。群聊通常需要 `@机器人` 才会触发事件。

回调必须使用公网可访问的 HTTPS 地址。开发机可以通过受控的反向代理或隧道暴露 `127.0.0.1:8080`，但不要把 App Secret 放在 URL、日志或代理配置中。

如果没有公网域名，可在“事件与回调 > 回调配置”中改选“使用长连接接收事件”。长连接只支持企业自建应用，保存该配置前需要先按第 3 节启动本服务并成功建立连接。

## 2. 安装依赖

推荐使用 uv：

```powershell
uv sync
```

也可以使用 pip：

```powershell
python -m pip install -e .
```

`cryptography` 用于飞书加密回调解密；`fastapi/uvicorn` 用于 webhook 服务；`trpc-agent-py` 用于真实 Agent 对话。

`lark-oapi` 是飞书官方 Python SDK，用于长连接鉴权、加密传输、事件派发和自动重连。

## 3. 配置飞书凭据

服务启动时会自动读取当前工作目录下的 `.env`。项目根目录已经提供本地 `.env`，填写以下配置即可：

```dotenv
TRPC_SERVICE_FEISHU_TENANT_ID=acme
TRPC_SERVICE_FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
TRPC_SERVICE_FEISHU_APP_SECRET_REF=env://FEISHU_APP_SECRET
TRPC_SERVICE_FEISHU_VERIFICATION_TOKEN_REF=env://FEISHU_VERIFICATION_TOKEN
TRPC_SERVICE_FEISHU_ENCRYPT_KEY_REF=env://FEISHU_ENCRYPT_KEY

FEISHU_APP_SECRET=开放平台中的 App Secret
FEISHU_VERIFICATION_TOKEN=事件订阅中的 Verification Token
FEISHU_ENCRYPT_KEY=事件订阅中的 Encrypt Key
TRPC_SERVICE_SESSION_HMAC_KEY=至少 32 字节的随机字符串
```

上述配置默认是 HTTP Webhook。无公网地址时，最小长连接配置如下：

```dotenv
TRPC_SERVICE_FEISHU_CONNECTION_MODE=websocket
TRPC_SERVICE_FEISHU_TENANT_ID=acme
TRPC_SERVICE_FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
TRPC_SERVICE_FEISHU_APP_SECRET_REF=env://FEISHU_APP_SECRET
FEISHU_APP_SECRET=开放平台中的 App Secret
```

长连接由服务启动时自动建立，仅需 App ID 和 App Secret；不需要 `Verification Token`、`Encrypt Key` 或公网回调 URL。SDK 收到事件后会先写入本地有界缓冲区并立即确认，主事件循环再完成解析和 Agent 入队，因此模型响应时间不会占用飞书要求的 3 秒回调窗口。缓冲区容量与 `TRPC_SERVICE_MAX_QUEUE_SIZE` 一致。

`TRPC_SERVICE_FEISHU_CONNECTION_MODE` 可选值为：`webhook`（默认）、`websocket` 或 `both`。`both` 会同时启用两种接收入口，此时仍需配置 Webhook 的 Verification Token 和 Encrypt Key。长连接是集群消费而非广播，同一应用虽然最多可建立 50 条连接，但生产部署应按消费并发需求控制连接数量；本项目当前建议单进程单连接。

如果使用国际版 Lark，可以覆盖 Open API 地址：

```dotenv
TRPC_SERVICE_FEISHU_API_BASE_URL=https://open.larksuite.com
```

`.env` 已被 Git 忽略，不会提交凭据；`.env.example` 只保留字段模板。终端中显式设置的同名环境变量优先级高于 `.env`。如需使用其他文件，可在终端设置 `TRPC_SERVICE_ENV_FILE` 为对应路径。生产环境仍应使用 Kubernetes Secret、Vault 或 KMS 注入，不应依赖仓库目录中的明文凭据文件。

## 4. 配置真实 tRPC-Agent 对话

未配置模型时，机器人使用 `EchoExecutor` 返回“已收到：...”，便于先验证飞书链路。要启用真实模型对话，再设置：

```dotenv
TRPC_AGENT_MODEL_NAME=模型名称
TRPC_AGENT_API_KEY=模型 API Key
TRPC_AGENT_BASE_URL=OpenAI 兼容 API 地址
```

服务启动时会创建 `LlmAgent + Runner + InMemorySessionService`，飞书消息将转换为 tRPC-Agent `Content/Part` 并通过 `Runner.run_async` 执行。当前多节点生产环境仍应把 Session 后端替换为 Redis 或 SQL。

## 5. 启动与验证

```powershell
uv run trpc-service serve
```

默认监听 `0.0.0.0:8080`。先检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health/live
Invoke-RestMethod http://127.0.0.1:8080/health/ready
```

`/health/ready` 的 `feishu_connections` 会显示长连接状态：`starting` 表示正在启动，`running` 表示 SDK 已运行，`connected` 表示已建立 WebSocket，`failed` 表示启动失败。失败时检查日志以及 App ID、App Secret、企业自建应用类型和公网访问能力。

SDK 日志级别默认是 `WARNING`，避免 INFO 日志记录包含临时连接票据的 WebSocket URL。排障时可临时设置 `TRPC_SERVICE_FEISHU_LOG_LEVEL=INFO`，完成后应恢复并妥善处理调试日志。

把公网 HTTPS 地址填入飞书事件订阅后，飞书会发送 URL verification；服务校验 token/签名并返回：

```json
{"challenge":"飞书提供的 challenge"}
```

验证成功后，在飞书中向机器人发送文本。服务会快速接收入队，由 Worker 执行 Agent，再进行两次 Open API 调用：

```text
POST /open-apis/auth/v3/tenant_access_token/internal
POST /open-apis/im/v1/messages/{message_id}/reply
```

`tenant_access_token` 会按 App ID 和 SecretRef 缓存，并在过期前刷新；token 失效时会清除缓存并重试一次。429、5xx 和飞书可重试错误码采用有限指数退避；回复 body 带稳定 `uuid`，用于减少重复回复风险。

## 6. 消息映射

| 飞书字段 | 平台字段 |
|---|---|
| `header.app_id` | `ChannelBinding.account_id` |
| `header.event_id` | 回调追踪元数据 |
| `event.sender.sender_id.open_id` | `external_user_id` |
| `event.message.message_id` | `external_message_id` 和回复目标 |
| `event.message.chat_id` | `chat_id` |
| `event.message.chat_type=p2p` | 单聊 Session |
| 其他 `chat_type` | 群聊 Session |
| `event.message.content.text` | Agent 用户输入 |

Session ID 由服务端 HMAC 生成，包含 tenant、feishu 和 chat 范围；外部用户不能通过伪造 ID 访问其他租户。

## 7. 当前边界

当前实现已覆盖文本、图片、文件、富文本卡片、消息撤回、主动推送、资源上传下载和官方 SDK 长连接。开发默认使用 InMemory；多副本生产部署设置 `TRPC_SERVICE_BACKEND=postgres-redis`，由 PostgreSQL 保存 Inbox/Outbox、Session/Event/Memory/Audit，Redis Streams 提供 consumer group、pending reclaim 和 DLQ。
