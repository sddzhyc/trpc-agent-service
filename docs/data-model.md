# 数据模型设计

## 1. 核心关系

一个 `tenant` 拥有多个 `agent_app`、`channel_binding`、`storage_profile` 和 `policy`；一个 Agent App 产生多个 `session`；Session 追加 `message/event`，并异步产生 `summary`、长期 `memory` 和 `artifact`；所有外部入口和操作写入 `audit_log`。生产 SQL 的每张业务表都以 `tenant_id` 作为第一列和复合索引前缀。

## 2. 最小表结构

```sql
tenant(tenant_id PK, name, status, active_version, created_at)
agent_app(tenant_id, app_id, name, instruction, model_json, tool_policy_json,
          PRIMARY KEY(tenant_id, app_id))
channel_binding(tenant_id, channel, account_id, verify_token_ref, secret_ref,
                enabled, PRIMARY KEY(tenant_id, channel, account_id))
session(tenant_id, session_id, app_id, user_id, version, state_json, updated_at,
        PRIMARY KEY(tenant_id, session_id))
session_event(tenant_id, session_id, sequence, event_id, event_type, payload_json,
              trace_id, created_at, PRIMARY KEY(tenant_id, session_id, sequence),
              UNIQUE(tenant_id, event_id))
memory(tenant_id, user_id, memory_id, content, embedding_version, projection_status,
       created_at, PRIMARY KEY(tenant_id, memory_id))
summary(tenant_id, session_id, source_version, content, updated_at,
        PRIMARY KEY(tenant_id, session_id))
audit_log(tenant_id, audit_id, channel, user_id, session_id, agent_name, tool_name,
          decision, latency_ms, error_type, cost, trace_id, detail_json, created_at,
          PRIMARY KEY(tenant_id, audit_id))
```

`knowledge_item/chunk` 的正文和 embedding 放向量库，`artifact` 的 bytes 放对象存储、checksum 和 URI 放 SQL；`inbound_message` 以 `(tenant_id, channel, account_id, external_message_id)` 唯一，`outbound_message` 记录每次分段发送与状态。

## 3. JSON 示例

```json
{
  "tenant_id": "acme",
  "app_id": "default",
  "session_id": "hmac-opaque-id",
  "event": {"sequence": 4, "type": "assistant_message", "text": "已完成"},
  "memory": {"memory_id": "m-1", "content": "用户偏好中文", "version": 1},
  "summary": {"source_version": 4, "content": "本轮已完成工单查询"},
  "channel_binding": {"channel": "wecom", "account_id": "acme-bot", "secret_ref": "env://WECOM_SECRET"},
  "audit": {"decision": "allow", "latency_ms": 182, "cost": 0.003, "trace_id": "t-1"}
}
```

## 4. 生命周期

Session event 是事实记录，按保留周期归档；state 是可重建快照；summary/memory/knowledge 是可重放投影；Artifact 先 staging 上传并校验 checksum，后提交 metadata。删除租户时先冻结入口，再按 tenant 范围删除 SQL、缓存、向量和对象，审计按合规策略保留或加密归档。
