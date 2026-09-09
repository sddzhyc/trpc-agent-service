# IM Channel Adapter 设计

## 统一契约

每种通道实现 `verify(binding, headers, body)`、`parse(...)`、`to_outbound(...)` 和 `send(...)`。Adapter 输出统一 `InboundMessage`：`tenant_id/channel/account_id/external_message_id/external_user_id/chat_id/chat_type/text/session_id/trace_id`。平台限制只在 Adapter 内处理，Worker 不感知 XML、Update 或卡片协议。飞书的完整接入步骤见 [feishu-setup.md](feishu-setup.md)。

## 飞书

飞书 Adapter 支持 URL challenge、Verification Token、Encrypt Key 签名与 AES 解密、`im.message.receive_v1` 文本事件、App ID 校验、bot 消息过滤、App Secret 换取/缓存 tenant access token，以及 Open API 原消息回复。回复失败时会区分 token 失效、限流、服务端错误和不可重试错误；token 失效后刷新并重试一次。

## 企业微信与 Telegram 差异

| 项目 | 企业微信 | Telegram |
|---|---|---|
| 绑定 | corp/app/bot account、token、AES/secret 引用 | bot token、webhook secret header |
| 验签 | `token+timestamp+nonce` 排序后 SHA1；加密回调再解密 | `X-Telegram-Bot-Api-Secret-Token` 常量时间比较 |
| 入站 | XML 或 JSON，FromUserName/ChatId/MsgId | JSON Update，from.id/chat.id/message_id |
| 回复 | 文本/流式或分段，按 UTF-8 字节限制 | sendMessage/editMessageText，按字符限制 |
| 超时 | 回调快速 ACK，异步发送 | webhook 快速 ACK，API 退避重试 |

当前代码提供完整的 JSON/XML 解析、签名校验、企业微信 EncodingAESKey 解密与应用消息发送、Telegram Bot API 文本/图片/文件发送和 429/5xx 退避、飞书文本/图片/文件/卡片/撤回/主动消息及官方 SDK 长连接。

## Session 与身份隔离

单聊以 `(tenant, channel, user_id)` 生成 Session，群聊以 `(tenant, channel, chat_id)` 生成；如需群内私有上下文再追加 user_id。external user 只能通过已验证 binding 映射到内部 user，不能携带 tenant_id 跨租户访问。binding 的 token/secret 只保存 SecretRef。

## 限制与重试

回复前按平台上限分段，保留 part/total_parts；遇到 429/5xx 使用抖动指数退避和最大次数，永久 4xx 写 audit/DLQ；图片/文件先落 Artifact 再传给 Agent。流式中断时发送一次“生成中断”状态，不重放已发送片段。
