"""Tenant-level tool authorization and budget guard."""

from __future__ import annotations

from dataclasses import dataclass

from ..tenant.models import TenantConfig


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_confirmation: bool = False


class TenantPolicyFilter:
    def __init__(self, config: TenantConfig) -> None:
        self.config = config

    def check_input(self, text: str) -> PolicyDecision:
        if len(text) > self.config.policy.max_input_chars:
            return PolicyDecision(False, "input_too_large")
        return PolicyDecision(True, "ok")

    def check_user(self, user_id: str) -> PolicyDecision:
        bindings = self.config.channels.values()
        restricted = [binding for binding in bindings if binding.allowed_users]
        if restricted and not any(user_id in binding.allowed_users for binding in restricted):
            return PolicyDecision(False, "user_not_allowed")
        return PolicyDecision(True, "ok")

    def check_tool(self, tool_name: str, confirmed: bool = False) -> PolicyDecision:
        policy = self.config.policy
        if tool_name not in policy.allowed_tools:
            return PolicyDecision(False, "tool_not_allowlisted")
        if tool_name in policy.dangerous_tools and not confirmed:
            return PolicyDecision(False, "confirmation_required", requires_confirmation=True)
        return PolicyDecision(True, "ok")
