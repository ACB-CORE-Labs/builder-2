"""MSDA preflight for tool/model/MCP entry points (P2 remainder / S2 prep).

When enabled, every invoke must pass MSDA allow before proceeding.
Default: off (gateways unchanged). Enable with BUILDER_II_WRP_MSDA_PREFLIGHT=1
or by calling assert_msda_preflight explicitly.

This module does not grant execution authority; it only fail-closes denials.
"""

from __future__ import annotations

import os
from typing import Any

from builder_ii.wrp.governance_router import create_default_msda_policy, evaluate_msda_gate

ENV_MSDA_PREFLIGHT = "BUILDER_II_WRP_MSDA_PREFLIGHT"


class MsdaPreflightDenied(PermissionError):
    """Raised when MSDA preflight denies an access request."""

    def __init__(self, message: str, *, decision: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.decision = decision or {}


def msda_preflight_enabled(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.getenv(ENV_MSDA_PREFLIGHT, "").strip().lower() in {"1", "true", "yes", "on"}


def run_msda_preflight(
    *,
    tool: str,
    data_domain: str = "local_workspace",
    risk: str = "local_offline",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate MSDA; return decision artifact. Does not raise."""
    pol = policy or create_default_msda_policy()
    return evaluate_msda_gate(tool=tool, data_domain=data_domain, policy=pol, risk=risk)


def assert_msda_preflight(
    *,
    tool: str,
    data_domain: str = "local_workspace",
    risk: str = "local_offline",
    policy: dict[str, Any] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    """If preflight enabled, require MSDA allow; else no-op.

    Returns decision when run; None when skipped.
    """
    if not msda_preflight_enabled(enabled):
        return None
    decision = run_msda_preflight(tool=tool, data_domain=data_domain, risk=risk, policy=policy)
    effect = (decision.get("decision") or {}).get("effect")
    # Gate artifacts set execution_permitted false always; effect is the authority signal for preflight.
    if effect != "allow":
        rule = (decision.get("decision") or {}).get("matched_rule")
        raise MsdaPreflightDenied(
            f"MSDA preflight denied tool={tool!r} domain={data_domain!r} rule={rule!r}",
            decision=decision,
        )
    return decision
