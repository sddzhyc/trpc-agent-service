"""Environment-backed service settings and secret references."""

from __future__ import annotations

import os
from dataclasses import dataclass


class SecretResolutionError(ValueError):
    pass


def resolve_secret(reference: str | None, environ: dict[str, str] | None = None) -> str | None:
    if reference is None:
        return None
    values = environ if environ is not None else os.environ
    if reference.startswith("env://"):
        name = reference[6:]
        if not name or name not in values:
            raise SecretResolutionError(f"secret environment variable is missing: {name}")
        return values[name]
    if reference.startswith("literal://"):
        # Useful only for local tests; production policy should reject it.
        return reference[10:]
    raise SecretResolutionError("secret must use env:// or literal:// reference")


@dataclass(frozen=True)
class ServiceSettings:
    host: str = "0.0.0.0"
    port: int = 8080
    admin_token: str | None = None
    session_hmac_key: str = "development-only-change-me"
    max_queue_size: int = 1000
    worker_count: int = 1
    environment: str = "development"

    @classmethod
    def from_env(cls) -> "ServiceSettings":
        return cls(
            host=os.getenv("TRPC_SERVICE_HOST", "0.0.0.0"),
            port=int(os.getenv("TRPC_SERVICE_PORT", "8080")),
            admin_token=resolve_secret(os.getenv("TRPC_SERVICE_ADMIN_TOKEN_REF")),
            session_hmac_key=os.getenv("TRPC_SERVICE_SESSION_HMAC_KEY", "development-only-change-me"),
            max_queue_size=int(os.getenv("TRPC_SERVICE_MAX_QUEUE_SIZE", "1000")),
            worker_count=max(1, int(os.getenv("TRPC_SERVICE_WORKER_COUNT", "1"))),
            environment=os.getenv("TRPC_SERVICE_ENV", "development"),
        )
