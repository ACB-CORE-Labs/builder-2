import pytest

from builder_ii.role_gates import (
    CAPABILITY_DIRECT_ASK,
    CAPABILITY_FILE_EDITING,
    CAPABILITY_GOOSE_TOOL_EXECUTION,
    CAPABILITY_HEAVY_MODEL_ROUTING,
    CAPABILITY_RUNTIME_SWITCH,
    DEFAULT_CAPABILITIES,
    gate_for,
    is_capability_allowed,
    role_capability_gates,
    validate_role_gates,
)
from builder_ii.roles import role_names


def test_every_role_has_complete_capability_coverage() -> None:
    for role_name in role_names():
        gates = role_capability_gates(role_name)
        assert {gate.capability for gate in gates} == set(DEFAULT_CAPABILITIES)
        assert all(gate.reason for gate in gates)


def test_direct_ask_is_allowed_for_all_roles() -> None:
    for role_name in role_names():
        assert is_capability_allowed(role_name, CAPABILITY_DIRECT_ASK)


def test_goose_tool_execution_is_unsupported_for_all_roles() -> None:
    for role_name in role_names():
        gate = gate_for(role_name, CAPABILITY_GOOSE_TOOL_EXECUTION)
        assert gate.status == "UNSUPPORTED"


def test_failure_reviewer_cannot_edit_files() -> None:
    gate = gate_for("failure_reviewer", CAPABILITY_FILE_EDITING)

    assert gate.status == "FORBIDDEN"
    assert "diagnostic" in gate.reason


def test_patch_planner_file_edits_remain_operator_only() -> None:
    gate = gate_for("patch_planner", CAPABILITY_FILE_EDITING)

    assert gate.status == "OPERATOR_ONLY"


def test_lane_router_cannot_switch_runtime_or_route_heavy_models() -> None:
    assert gate_for("lane_router", CAPABILITY_RUNTIME_SWITCH).status == "FORBIDDEN"
    assert gate_for("lane_router", CAPABILITY_HEAVY_MODEL_ROUTING).status == "FORBIDDEN"


def test_role_gate_validation_is_clean() -> None:
    assert validate_role_gates() == ()


def test_unknown_role_or_capability_raise_clear_errors() -> None:
    with pytest.raises(ValueError, match="unknown role"):
        role_capability_gates("missing")

    with pytest.raises(ValueError, match="unknown capability"):
        gate_for("patch_planner", "missing")
