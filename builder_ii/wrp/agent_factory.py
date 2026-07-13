"""AgentFactory (MoIRA reference) — lifecycle plans only, no free spawn."""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    AGENT_FACTORY_PLAN_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.spaces import AgentPoint


def plan_agent_lifecycle(
    *,
    agents: list[AgentPoint],
    action: str = "register_plan",
) -> dict[str, Any]:
    if action not in {"register_plan", "retire_plan"}:
        raise ValueError("action must be register_plan or retire_plan")
    return base_envelope(
        kind=AGENT_FACTORY_PLAN_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_plan_only",
        extra={
            "action": action,
            "agents": [a.to_jsonable() for a in agents],
            "spawn_permitted": False,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
        },
    )


def validate_agent_factory_plan(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=AGENT_FACTORY_PLAN_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("spawn_permitted") is not False:
        errors.append("spawn_permitted must be false")
    if record.get("runtime_binding") != "UNBOUND":
        errors.append("runtime_binding must be UNBOUND")
    return errors
