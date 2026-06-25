from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from builder_ii.roles import builder_roles, role_names

GateStatus = Literal["ALLOWED", "OPERATOR_ONLY", "UNSUPPORTED", "FORBIDDEN"]

CAPABILITY_DIRECT_ASK = "direct_ask"
CAPABILITY_GOOSE_PLANNING = "goose_planning"
CAPABILITY_GOOSE_TOOL_EXECUTION = "goose_tool_execution"
CAPABILITY_FILE_EDITING = "file_editing"
CAPABILITY_RUNTIME_SWITCH = "runtime_switch"
CAPABILITY_HEAVY_MODEL_ROUTING = "heavy_model_routing"

DEFAULT_CAPABILITIES = (
    CAPABILITY_DIRECT_ASK,
    CAPABILITY_GOOSE_PLANNING,
    CAPABILITY_GOOSE_TOOL_EXECUTION,
    CAPABILITY_FILE_EDITING,
    CAPABILITY_RUNTIME_SWITCH,
    CAPABILITY_HEAVY_MODEL_ROUTING,
)


@dataclass(frozen=True)
class RoleCapabilityGate:
    role: str
    capability: str
    status: GateStatus
    reason: str


_DEFAULT_GATES: dict[str, tuple[GateStatus, str]] = {
    CAPABILITY_DIRECT_ASK: ("ALLOWED", "direct local chat is validated for review and planning prompts"),
    CAPABILITY_GOOSE_PLANNING: ("ALLOWED", "governed Goose planning and review sessions are allowed"),
    CAPABILITY_GOOSE_TOOL_EXECUTION: ("UNSUPPORTED", "local MLX Goose tool execution is not validated"),
    CAPABILITY_FILE_EDITING: ("OPERATOR_ONLY", "file edits require explicit operator action and verification"),
    CAPABILITY_RUNTIME_SWITCH: ("OPERATOR_ONLY", "runtime and model switching must remain explicit via operator command"),
    CAPABILITY_HEAVY_MODEL_ROUTING: ("FORBIDDEN", "heavy and candidate lanes are explicit opt-in and cannot be selected automatically"),
}

_ROLE_OVERRIDES: dict[str, dict[str, tuple[GateStatus, str]]] = {
    "failure_reviewer": {
        CAPABILITY_FILE_EDITING: ("FORBIDDEN", "failure review is diagnostic only"),
    },
    "invariant_auditor": {
        CAPABILITY_FILE_EDITING: ("FORBIDDEN", "invariant audit may block or advise but not edit"),
        CAPABILITY_RUNTIME_SWITCH: ("FORBIDDEN", "audit may recommend escalation but not switch runtimes"),
    },
    "diff_summarizer": {
        CAPABILITY_FILE_EDITING: ("FORBIDDEN", "diff summary must not mutate the reviewed change"),
    },
    "lane_router": {
        CAPABILITY_RUNTIME_SWITCH: ("FORBIDDEN", "lane routing recommends only; the operator switches explicitly"),
        CAPABILITY_HEAVY_MODEL_ROUTING: ("FORBIDDEN", "lane router must escalate heavy, candidate, and sidecar choices"),
    },
}


def role_capability_gates(role_name: str) -> tuple[RoleCapabilityGate, ...]:
    if role_name not in set(role_names()):
        valid = ", ".join(role_names())
        raise ValueError(f"unknown role {role_name!r}; expected one of: {valid}")

    merged = dict(_DEFAULT_GATES)
    merged.update(_ROLE_OVERRIDES.get(role_name, {}))
    return tuple(
        RoleCapabilityGate(role_name, capability, merged[capability][0], merged[capability][1])
        for capability in DEFAULT_CAPABILITIES
    )


def gate_for(role_name: str, capability: str) -> RoleCapabilityGate:
    gates = {gate.capability: gate for gate in role_capability_gates(role_name)}
    try:
        return gates[capability]
    except KeyError as exc:
        valid = ", ".join(DEFAULT_CAPABILITIES)
        raise ValueError(f"unknown capability {capability!r}; expected one of: {valid}") from exc


def is_capability_allowed(role_name: str, capability: str) -> bool:
    return gate_for(role_name, capability).status == "ALLOWED"


def validate_role_gates() -> tuple[str, ...]:
    problems: list[str] = []
    known_roles = {role.name for role in builder_roles()}

    for role_name in _ROLE_OVERRIDES:
        if role_name not in known_roles:
            problems.append(f"unknown role override {role_name}")

    for role in builder_roles():
        capabilities = {gate.capability for gate in role_capability_gates(role.name)}
        if capabilities != set(DEFAULT_CAPABILITIES):
            problems.append(f"{role.name}: capability coverage mismatch")
        for gate in role_capability_gates(role.name):
            if not gate.reason:
                problems.append(f"{role.name}:{gate.capability}: missing reason")

    return tuple(problems)
