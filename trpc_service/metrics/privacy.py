"""Bounded, opaque labels for telemetry."""

from __future__ import annotations

import hashlib


def tenant_label(tenant_id: str) -> str:
    return hashlib.blake2b(tenant_id.encode(), digest_size=10, person=b"trpc-label").hexdigest()


def sanitize_attributes(values: dict[str, object]) -> dict[str, object]:
    sensitive = {"token", "secret", "password", "api_key", "authorization"}
    return {key: ("[REDACTED]" if key.lower() in sensitive else value) for key, value in values.items()}
