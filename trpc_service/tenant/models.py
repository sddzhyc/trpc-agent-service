"""Tenant-scoped configuration and message models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ChannelBinding:
    channel: str
    account_id: str
    verify_token: str
    secret_ref: str | None = None
    enabled: bool = True
    allowed_users: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AgentApp:
    app_id: str
    name: str
    instruction: str = "You are a helpful enterprise assistant."
    model_name: str | None = None
    tools: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TenantPolicy:
    allowed_tools: frozenset[str] = frozenset()
    dangerous_tools: frozenset[str] = frozenset()
    max_input_chars: int = 8000
    daily_token_budget: int = 100_000
    redact_output: bool = True


@dataclass(frozen=True)
class StorageProfile:
    session: str = "inmemory"
    memory: str = "inmemory"
    audit: str = "inmemory"
    vector: str = "none"
    object_store: str = "none"


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    name: str
    apps: dict[str, AgentApp]
    channels: dict[str, ChannelBinding]
    policy: TenantPolicy = field(default_factory=TenantPolicy)
    storage: StorageProfile = field(default_factory=StorageProfile)
    version: int = 1
    status: str = "active"


@dataclass(frozen=True)
class InboundMessage:
    tenant_id: str
    channel: str
    account_id: str
    external_message_id: str
    external_user_id: str
    chat_id: str
    chat_type: str
    text: str
    app_id: str = "default"
    received_at: datetime = field(default_factory=utcnow)
    trace_id: str = ""
    session_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    tenant_id: str
    channel: str
    account_id: str
    external_user_id: str
    chat_id: str
    text: str
    in_reply_to: str
    trace_id: str
    part: int = 1
    total_parts: int = 1


@dataclass(frozen=True)
class SessionEvent:
    tenant_id: str
    session_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    trace_id: str
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class SessionSnapshot:
    tenant_id: str
    session_id: str
    app_id: str
    user_id: str
    state: dict[str, Any] = field(default_factory=dict)
    version: int = 0
    updated_at: datetime = field(default_factory=utcnow)
