"""Outbound channel dispatcher with a testable delivery sink."""

from __future__ import annotations

from typing import Callable

from ..tenant.models import InboundMessage, OutboundMessage
from .base import ChannelAdapter


class ChannelDispatcher:
    def __init__(self, adapters: dict[str, ChannelAdapter], sink: Callable[[OutboundMessage], None] | None = None) -> None:
        self.adapters = adapters
        self.sink = sink
        self.deliveries: list[OutboundMessage] = []

    async def reply(self, inbound: InboundMessage, text: str) -> list[OutboundMessage]:
        adapter = self.adapters[inbound.channel]
        messages = adapter.to_outbound(inbound, text)
        for message in messages:
            adapter.send(message)
            self.deliveries.append(message)
            if self.sink:
                self.sink(message)
        return messages
