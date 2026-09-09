"""Enterprise WeCom callback adapter (JSON and basic XML payloads)."""

from __future__ import annotations

import hashlib
import hmac
import xml.etree.ElementTree as ET
from typing import Any

from ..tenant.models import ChannelBinding, InboundMessage
from .base import ChannelAdapter


class WeComAdapter(ChannelAdapter):
    name = "wecom"
    max_message_size = 2048
    byte_limit = True

    def verify(self, binding: ChannelBinding, headers: dict[str, str], body: bytes) -> bool:
        signature = headers.get("x-wecom-signature") or headers.get("signature", "")
        timestamp = headers.get("x-wecom-timestamp") or headers.get("timestamp", "")
        nonce = headers.get("x-wecom-nonce") or headers.get("nonce", "")
        if not (signature and timestamp and nonce):
            return False
        value = "".join(sorted((binding.verify_token, timestamp, nonce)))
        return hmac.compare_digest(hashlib.sha1(value.encode()).hexdigest(), signature)

    def parse(self, tenant_id: str, binding: ChannelBinding, payload: Any, trace_id: str) -> InboundMessage:
        if isinstance(payload, bytes):
            root = ET.fromstring(payload)
            data = {child.tag: (child.text or "") for child in root}
        else:
            data = dict(payload)
        user_id = str(data.get("FromUserName") or data.get("user_id") or data.get("from_user", ""))
        chat_id = str(data.get("ChatId") or data.get("chat_id") or user_id)
        chat_type = "group" if data.get("ChatId") or data.get("chat_type") == "group" else "direct"
        message_id = str(data.get("MsgId") or data.get("message_id") or data.get("id", ""))
        return InboundMessage(
            tenant_id=tenant_id,
            channel=self.name,
            account_id=binding.account_id,
            external_message_id=message_id,
            external_user_id=user_id,
            chat_id=chat_id,
            chat_type=chat_type,
            text=str(data.get("Content") or data.get("text") or ""),
            app_id=str(data.get("app_id", "default")),
            trace_id=trace_id,
            raw=data,
        )
