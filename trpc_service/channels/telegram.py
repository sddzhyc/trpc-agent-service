"""Telegram Bot API webhook adapter."""

from __future__ import annotations

import hmac
from typing import Any

from ..tenant.models import ChannelBinding, InboundMessage
from .base import ChannelAdapter


class TelegramAdapter(ChannelAdapter):
    name = "telegram"
    max_message_size = 4096

    def verify(self, binding: ChannelBinding, headers: dict[str, str], body: bytes) -> bool:
        expected = binding.verify_token
        supplied = headers.get("x-telegram-bot-api-secret-token", "")
        return bool(expected and supplied and hmac.compare_digest(expected, supplied))

    def parse(self, tenant_id: str, binding: ChannelBinding, payload: Any, trace_id: str) -> InboundMessage:
        update = dict(payload)
        message = dict(update.get("message") or update.get("edited_message") or {})
        chat = dict(message.get("chat") or {})
        user = dict(message.get("from") or {})
        chat_id = str(chat.get("id") or user.get("id") or "")
        user_id = str(user.get("id") or chat_id)
        chat_type = "group" if chat.get("type") in {"group", "supergroup"} else "direct"
        return InboundMessage(
            tenant_id=tenant_id,
            channel=self.name,
            account_id=binding.account_id,
            external_message_id=str(message.get("message_id") or update.get("update_id") or ""),
            external_user_id=user_id,
            chat_id=chat_id,
            chat_type=chat_type,
            text=str((message.get("text") or "")),
            trace_id=trace_id,
            raw=update,
        )
