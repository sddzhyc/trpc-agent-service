"""Stateless worker coordinator around tRPC-Agent-Python or a local fallback."""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

from ..channels import ChannelDispatcher
from ..log import redact
from ..metrics import MetricsRegistry, TraceContext
from ..tenant import (
    AuditStore,
    IdempotencyStore,
    InboundMessage,
    MemoryStore,
    SessionStore,
    TenantRegistry,
)
from ..tool import TenantPolicyFilter


class AgentExecutor(Protocol):
    async def reply(self, message: InboundMessage, memory: list[str], instruction: str) -> str:
        ...


class EchoExecutor:
    """Deterministic executor for local development and acceptance tests."""

    async def reply(self, message: InboundMessage, memory: list[str], instruction: str) -> str:
        if not message.text.strip():
            return "请发送文字消息，我会继续协助。"
        suffix = f"（已关联 {len(memory)} 条长期记忆）" if memory else ""
        return f"已收到：{message.text.strip()}{suffix}"


class TRPCAgentExecutor:
    """Adapter for a pre-built tRPC-Agent ``Runner``.

    The platform owns routing and persistence; the framework still owns agent
    orchestration, model calls, Tool/MCP and event generation.
    """

    def __init__(self, runner: object, user_id: str = "") -> None:
        self.runner = runner
        self.user_id = user_id

    async def reply(self, message: InboundMessage, memory: list[str], instruction: str) -> str:
        try:
            from trpc_agent_sdk.types import Content, Part
        except ImportError as exc:
            raise RuntimeError("trpc-agent-py is required for TRPCAgentExecutor") from exc
        content = Content(parts=[Part.from_text(text=message.text)])
        chunks: list[str] = []
        async for event in self.runner.run_async(
            user_id=self.user_id or message.external_user_id,
            session_id=message.session_id,
            new_message=content,
        ):
            if not getattr(event, "content", None):
                continue
            for part in getattr(event.content, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    chunks.append(text)
        return "".join(chunks) or "已完成处理。"


class AgentService:
    """Gateway-to-worker runtime with at-least-once queue semantics."""

    def __init__(
        self,
        registry: TenantRegistry,
        dispatcher: ChannelDispatcher,
        executor: AgentExecutor | None = None,
        queue_size: int = 1000,
        sessions: SessionStore | None = None,
        memories: MemoryStore | None = None,
        audits: AuditStore | None = None,
    ) -> None:
        self.registry = registry
        self.dispatcher = dispatcher
        self.executor = executor or EchoExecutor()
        self.queue: asyncio.Queue[InboundMessage] = asyncio.Queue(maxsize=queue_size)
        self.idempotency = IdempotencyStore()
        self.sessions = sessions or SessionStore()
        self.memories = memories or MemoryStore()
        self.audits = audits or AuditStore()
        self.metrics = MetricsRegistry()

    @staticmethod
    def idempotency_key(message: InboundMessage) -> str:
        return f"{message.tenant_id}:{message.channel}:{message.account_id}:{message.external_message_id}"

    async def enqueue(self, message: InboundMessage) -> bool:
        """Claim the external message and queue it; duplicate delivery is a no-op."""
        key = self.idempotency_key(message)
        if not await self.idempotency.claim(key):
            self.metrics.inc("inbound_duplicate", tenant=message.tenant_id, channel=message.channel)
            return False
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            await self.idempotency.complete(key, {"status": "queue_full"})
            self.metrics.inc("inbound_rejected", tenant=message.tenant_id, channel=message.channel)
            raise RuntimeError("agent queue is full")
        self.metrics.inc("inbound_accepted", tenant=message.tenant_id, channel=message.channel)
        return True

    async def process_one(self) -> list[object]:
        message = await self.queue.get()
        try:
            return await self.process(message)
        finally:
            self.queue.task_done()

    async def process(self, message: InboundMessage) -> list[object]:
        start = time.perf_counter()
        with TraceContext(message.trace_id):
            config = self.registry.revision_for_session(message.tenant_id, message.session_id)
            policy = TenantPolicyFilter(config)
            user_decision = policy.check_user(message.external_user_id)
            input_decision = policy.check_input(message.text)
            if not user_decision.allowed or not input_decision.allowed:
                text = "当前消息未通过租户安全策略。"
                await self.audits.write(self._audit(message, "deny", input_decision.reason or user_decision.reason, start))
                return await self.dispatcher.reply(message, text)

            async with self.sessions.lock(message.tenant_id, message.session_id):
                snapshot = await self.sessions.get_or_create(message.tenant_id, message.session_id, message.app_id, message.external_user_id)
                memory = await self.memories.list(message.tenant_id, message.external_user_id)
                app = config.apps.get(message.app_id) or next(iter(config.apps.values()))
                reply = await self.executor.reply(message, memory, app.instruction)
                events = await self.sessions.append_turn(snapshot, message.text, reply, message.trace_id)
                await self.memories.add(message.tenant_id, message.external_user_id, message.text)
                deliveries = await self.dispatcher.reply(message, reply)
            await self.audits.write(self._audit(message, "allow", "ok", start, len(events)))
            await self.idempotency.complete(self.idempotency_key(message), {"status": "completed", "text": reply})
            self.metrics.inc("agent_turn_completed", tenant=message.tenant_id, channel=message.channel)
            return deliveries

    @staticmethod
    def _audit(message: InboundMessage, decision: str, reason: str, start: float, event_count: int = 0) -> dict[str, object]:
        return redact({
            "tenant_id": message.tenant_id,
            "channel": message.channel,
            "user_id": message.external_user_id,
            "session_id": message.session_id,
            "agent_name": message.app_id,
            "tool_name": None,
            "decision": decision,
            "reason": reason,
            "event_count": event_count,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            "error_type": None,
            "cost": 0,
            "trace_id": message.trace_id,
        })

    async def worker_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(self.process_one(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
