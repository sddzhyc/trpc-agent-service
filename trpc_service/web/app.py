"""FastAPI gateway and an in-process runtime factory."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from ..agent import AgentService
from ..channels import ChannelDispatcher, TelegramAdapter, WeComAdapter, make_session_id
from ..config import ServiceSettings
from ..metrics import new_trace_id
from ..tenant import AgentApp, ChannelBinding, TenantConfig, TenantPolicy, TenantRegistry


class ServiceRuntime:
    def __init__(self, settings: ServiceSettings, registry: TenantRegistry, service: AgentService) -> None:
        self.settings = settings
        self.registry = registry
        self.service = service

    async def ingest(self, tenant_id: str, channel: str, payload: Any, headers: dict[str, str]) -> bool:
        account_id = str(payload.get("account_id") or payload.get("bot_id") or headers.get("x-channel-account", ""))
        config, binding = self.registry.resolve_binding(tenant_id, channel, account_id)
        adapter = self.service.dispatcher.adapters[channel]
        body = json.dumps(payload, ensure_ascii=False).encode()
        if not adapter.verify(binding, headers, body):
            raise PermissionError("invalid channel signature")
        trace_id = headers.get("x-trace-id") or new_trace_id()
        message = adapter.parse(tenant_id, binding, payload, trace_id)
        session_id = make_session_id(tenant_id, channel, message.chat_id, message.chat_type, self.settings.session_hmac_key)
        message = replace(message, session_id=session_id)
        # Do not trust an app_id supplied by an external platform unless it is
        # present in the tenant revision.
        if message.app_id not in config.apps:
            message = replace(message, app_id=next(iter(config.apps)))
        return await self.service.enqueue(message)


def build_demo_runtime(settings: ServiceSettings | None = None) -> ServiceRuntime:
    settings = settings or ServiceSettings.from_env()
    common_policy = TenantPolicy(allowed_tools=frozenset({"weather"}), dangerous_tools=frozenset({"delete_ticket"}))
    configs = [
        TenantConfig(
            tenant_id="acme",
            name="Acme 客服",
            apps={"default": AgentApp("default", "acme-assistant")},
            channels={
                "wecom": ChannelBinding("wecom", "acme-bot", "acme-dev-token"),
                "telegram": ChannelBinding("telegram", "acme-telegram", "acme-telegram-secret"),
            },
            policy=common_policy,
        ),
        TenantConfig(
            tenant_id="globex",
            name="Globex 研发",
            apps={"default": AgentApp("default", "globex-assistant")},
            channels={"telegram": ChannelBinding("telegram", "globex-telegram", "globex-telegram-secret")},
            policy=TenantPolicy(allowed_tools=frozenset()),
        ),
    ]
    registry = TenantRegistry(configs)
    dispatcher = ChannelDispatcher({"wecom": WeComAdapter(), "telegram": TelegramAdapter()})
    service = AgentService(registry, dispatcher, queue_size=settings.max_queue_size)
    return ServiceRuntime(settings, registry, service)


def create_app(runtime: ServiceRuntime | None = None) -> Any:
    """Create the HTTP app; FastAPI remains an optional dependency."""
    try:
        from fastapi import FastAPI, HTTPException, Request
    except ImportError as exc:
        raise RuntimeError("install fastapi and uvicorn to run the HTTP gateway") from exc

    runtime = runtime or build_demo_runtime()
    app = FastAPI(title="tRPC-Agent multi-tenant service", version="0.1.0")
    stop = None
    workers: list[Any] = []

    @app.on_event("startup")
    async def startup() -> None:
        nonlocal stop, workers
        import asyncio

        stop = asyncio.Event()
        workers = [asyncio.create_task(runtime.service.worker_loop(stop)) for _ in range(runtime.settings.worker_count)]

    @app.on_event("shutdown")
    async def shutdown() -> None:
        if stop is not None:
            stop.set()
        if workers:
            import asyncio

            await asyncio.gather(*workers, return_exceptions=True)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> dict[str, Any]:
        return {"status": "ok", "queue_depth": runtime.service.queue.qsize()}

    @app.post("/webhook/{tenant_id}/{channel}")
    async def webhook(tenant_id: str, channel: str, request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception:
            raw = await request.body()
            try:
                payload = json.loads(raw.decode())
            except Exception as exc:
                raise HTTPException(status_code=400, detail="payload must be JSON in the prototype") from exc
        headers = {key.lower(): value for key, value in request.headers.items()}
        try:
            accepted = await runtime.ingest(tenant_id, channel, payload, headers)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"accepted": accepted, "duplicate": not accepted}

    @app.get("/admin/tenants")
    async def tenants(request: Request) -> list[dict[str, Any]]:
        expected = runtime.settings.admin_token
        if expected and request.headers.get("x-admin-token") != expected:
            raise HTTPException(status_code=403, detail="admin authentication required")
        return [{"tenant_id": item.tenant_id, "name": item.name, "version": item.version, "status": item.status} for item in runtime.registry.list_tenants()]

    return app
