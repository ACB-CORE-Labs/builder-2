from __future__ import annotations

from builder_ii.wrp.governance_router import (
    create_default_msda_policy,
    evaluate_msda_gate,
    validate_msda_gate_decision,
    validate_msda_policy,
)

_GATE_FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("repo_map", "local_workspace", "allow"),
    ("context_pack", "artifact_store", "allow"),
    ("artifact_validate", "local_workspace", "allow"),
    ("pytest_local", "local_workspace", "allow"),
    ("shell", "local_workspace", "deny"),
    ("bash", "local_workspace", "deny"),
    ("mcp_call", "external_network", "deny"),
    ("network_fetch", "external_network", "deny"),
    ("repo_map", "secrets", "deny"),
    ("unknown_tool", "local_workspace", "deny"),
    ("pytest_local", "credentials", "deny"),
    ("subprocess_open", "artifact_store", "deny"),
)


def test_msda_policy_valid_deny_default() -> None:
    pol = create_default_msda_policy()
    assert validate_msda_policy(pol) == []
    assert pol["default_effect"] == "deny"


def test_all_gate_fixtures_validated_before_execution() -> None:
    pol = create_default_msda_policy()
    for tool, domain, expected in _GATE_FIXTURES:
        decision = evaluate_msda_gate(tool=tool, data_domain=domain, policy=pol)
        assert validate_msda_gate_decision(decision) == []
        assert decision["execution_permitted"] is False
        assert decision["decision"]["effect"] == expected
        assert decision["audit"]["logged"] is True
