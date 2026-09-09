"""Framework integration seam for tenant-specific agents."""

from __future__ import annotations

from ..tenant.models import TenantConfig
from .runner import AgentExecutor, EchoExecutor


def create_executor(config: TenantConfig) -> AgentExecutor:
    """Return the configured executor.

    Week 1-3 uses a deterministic executor.  A deployment can inject a
    tRPC-Agent Runner per app without changing gateway, storage or channels.
    """
    _ = config
    return EchoExecutor()
