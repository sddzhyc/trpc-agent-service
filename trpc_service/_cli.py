"""Command line entry point for local development."""

from __future__ import annotations

import argparse
import asyncio
import json

from .channels import make_session_id
from .config import ServiceSettings
from .metrics import new_trace_id
from .tenant import InboundMessage
from .web import build_demo_runtime, create_app


async def demo() -> None:
    runtime = build_demo_runtime(ServiceSettings())
    message = InboundMessage(
        tenant_id="acme",
        channel="telegram",
        account_id="acme-telegram",
        external_message_id="demo-1",
        external_user_id="u-1",
        chat_id="chat-1",
        chat_type="direct",
        text="你好，介绍一下这个服务",
        trace_id=new_trace_id(),
        session_id=make_session_id("acme", "telegram", "chat-1", "direct", "development-only-change-me"),
    )
    await runtime.service.enqueue(message)
    await runtime.service.process_one()
    print(json.dumps([item.__dict__ for item in runtime.service.dispatcher.deliveries], ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="tRPC-Agent multi-tenant service")
    parser.add_argument("command", choices=("demo", "serve"), nargs="?", default="demo")
    args = parser.parse_args()
    if args.command == "demo":
        asyncio.run(demo())
        return
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("serve requires: pip install fastapi uvicorn") from exc
    uvicorn.run(create_app(), host=ServiceSettings.from_env().host, port=ServiceSettings.from_env().port)


if __name__ == "__main__":
    main()
