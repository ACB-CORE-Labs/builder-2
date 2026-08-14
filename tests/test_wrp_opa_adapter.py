"""Tests for WRP OPA/MSDA adapter — pure Python parity + optional opa backend."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from builder_ii.wrp.governance_router import create_default_msda_policy, evaluate_msda_gate
from builder_ii.wrp.opa_adapter import (
    REGO_PACKAGE,
    REGO_QUERY,
    BackendUnavailableError,
    OpaEvalAdapter,
    build_opa_eval_argv,
    eval_msda_python,
    export_msda_to_rego,
)

# Fixture corpus shared with governance tests + extras for edge cases.
# (tool, data_domain, risk, expected_effect)
_PARITY_CORPUS: tuple[tuple[str, str, str, str], ...] = (
    ("repo_map", "local_workspace", "local_offline", "allow"),
    ("context_pack", "artifact_store", "local_offline", "allow"),
    ("artifact_validate", "local_workspace", "local_offline", "allow"),
    ("pytest_local", "local_workspace", "local_network", "allow"),
    ("shell", "local_workspace", "local_offline", "deny"),
    ("bash", "local_workspace", "local_offline", "deny"),
    ("subprocess_open", "artifact_store", "local_offline", "deny"),
    ("mcp_call", "external_network", "local_offline", "deny"),
    ("network_fetch", "external_network", "cloud_external", "deny"),
    ("repo_map", "secrets", "local_offline", "deny"),
    ("pytest_local", "credentials", "local_offline", "deny"),
    ("unknown_tool", "local_workspace", "local_offline", "deny"),
    ("repo_map", "external_network", "local_offline", "deny"),
    ("shell", "secrets", "local_offline", "deny"),
)


def _request(tool: str, data_domain: str, risk: str = "local_offline") -> dict[str, Any]:
    return {"tool": tool, "data_domain": data_domain, "risk": risk}


def test_export_msda_to_rego_deterministic() -> None:
    pol = create_default_msda_policy()
    a = export_msda_to_rego(pol)
    b = export_msda_to_rego(pol)
    assert a == b
    assert a.endswith("\n")
    assert f"package {REGO_PACKAGE}" in a
    assert "import rego.v1" in a
    assert 'default effect := "deny"' in a
    assert "allow_local_readonly_tools" in a
    assert "deny_shell_by_default" in a
    assert "deny_secret_domain" in a
    assert REGO_QUERY.split("data.")[-1] in a or "decision :=" in a
    # same content twice still stable
    assert export_msda_to_rego(dict(pol)) == a


def test_export_msda_to_rego_preserves_rule_order() -> None:
    pol = create_default_msda_policy()
    text = export_msda_to_rego(pol)
    positions = [
        text.index("allow_local_readonly_tools"),
        text.index("deny_shell_by_default"),
        text.index("deny_mcp_network_by_default"),
        text.index("deny_secret_domain"),
    ]
    assert positions == sorted(positions)


def test_eval_msda_python_shape() -> None:
    pol = create_default_msda_policy()
    result = eval_msda_python(pol, _request("repo_map", "local_workspace"))
    assert result["effect"] == "allow"
    assert result["allow"] is True
    assert result["rule_id"] == "allow_local_readonly_tools"
    assert isinstance(result["reasons"], list) and result["reasons"]
    assert result["backend"] == "python_msda"
    assert result["request"]["tool"] == "repo_map"
    assert result["policy_digest"] == pol.get("digest")


def test_parity_python_adapter_matches_governance_router() -> None:
    """For the fixture corpus, adapter decisions match evaluate_msda_gate."""
    pol = create_default_msda_policy()
    for tool, domain, risk, expected in _PARITY_CORPUS:
        router = evaluate_msda_gate(tool=tool, data_domain=domain, policy=pol, risk=risk)
        adapter = eval_msda_python(pol, _request(tool, domain, risk))
        assert adapter["effect"] == expected, f"{tool}/{domain}"
        assert adapter["effect"] == router["decision"]["effect"], f"{tool}/{domain}"
        assert adapter["rule_id"] == router["decision"]["matched_rule"], f"{tool}/{domain}"
        assert adapter["allow"] is (expected == "allow")
        assert adapter["policy_digest"] == router["decision"]["policy_digest"]


def test_parity_custom_policy() -> None:
    """Custom MSDA policy: deny-first and allow still agree across backends."""
    pol = create_default_msda_policy()
    # Mutate a copy of rules: insert a deny for pytest_local on local_workspace first.
    rules = list(pol["rules"])
    rules.insert(
        0,
        {
            "rule_id": "deny_pytest_local",
            "effect": "deny",
            "tools": ["pytest_local"],
            "data_domains": ["local_workspace"],
        },
    )
    custom = {**pol, "rules": rules}
    # drop digest so we are not claiming envelope integrity for this synthetic policy
    custom.pop("digest", None)

    router = evaluate_msda_gate(
        tool="pytest_local",
        data_domain="local_workspace",
        policy=custom,
    )
    adapter = eval_msda_python(custom, _request("pytest_local", "local_workspace"))
    assert router["decision"]["effect"] == "deny"
    assert adapter["effect"] == "deny"
    assert adapter["rule_id"] == router["decision"]["matched_rule"] == "deny_pytest_local"


def test_opa_adapter_unavailable_without_binary() -> None:
    with patch("builder_ii.wrp.opa_adapter.shutil.which", return_value=None):
        adapter = OpaEvalAdapter()
        assert adapter.available is False
        assert adapter.opa_path is None
        with pytest.raises(BackendUnavailableError, match="opa binary not found"):
            adapter.eval(create_default_msda_policy(), _request("repo_map", "local_workspace"))


def test_opa_adapter_available_when_path_set() -> None:
    path = "/usr/local/bin/opa"
    adapter = OpaEvalAdapter(opa_path=path)
    assert adapter.available is True
    assert adapter.opa_path == path


def test_opa_adapter_eval_mocks_subprocess() -> None:
    """Never require real opa in CI — mock subprocess.run and parse JSON."""
    opa_json = {
        "result": [
            {
                "expressions": [
                    {
                        "value": {
                            "effect": "allow",
                            "rule_id": "allow_local_readonly_tools",
                            "allow": True,
                        }
                    }
                ]
            }
        ]
    }
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = json.dumps(opa_json)
    completed.stderr = ""

    pol = create_default_msda_policy()
    mock_bin = "/mock/opa"
    with patch("builder_ii.wrp.opa_adapter.subprocess.run", return_value=completed) as run:
        adapter = OpaEvalAdapter(opa_path=mock_bin)
        result = adapter.eval(pol, _request("repo_map", "local_workspace"))

    assert result["effect"] == "allow"
    assert result["rule_id"] == "allow_local_readonly_tools"
    assert result["allow"] is True
    assert result["backend"] == "opa"
    run.assert_called_once()
    argv = run.call_args[0][0]
    assert argv[0] == mock_bin
    assert argv[1:4] == ["eval", "-f", "json"]
    assert REGO_QUERY in argv
    # shell must never be used
    assert run.call_args.kwargs.get("shell") is False


def test_opa_adapter_eval_nonzero_exit_raises() -> None:
    completed = MagicMock()
    completed.returncode = 1
    completed.stdout = ""
    completed.stderr = "rego_parse_error: boom"
    mock_bin = "/mock/opa"
    with patch("builder_ii.wrp.opa_adapter.subprocess.run", return_value=completed):
        adapter = OpaEvalAdapter(opa_path=mock_bin)
        with pytest.raises(RuntimeError, match="opa eval failed"):
            adapter.eval(create_default_msda_policy(), _request("shell", "local_workspace"))


def test_build_opa_eval_argv_documented_shape() -> None:
    argv = build_opa_eval_argv(
        opa_bin="/bin/opa",
        policy_path="/tmp/p.rego",
        input_path="/tmp/i.json",
    )
    assert argv == [
        "/bin/opa",
        "eval",
        "-f",
        "json",
        "-d",
        "/tmp/p.rego",
        "-i",
        "/tmp/i.json",
        REGO_QUERY,
    ]


def test_export_rejects_non_dict_policy() -> None:
    with pytest.raises(TypeError):
        export_msda_to_rego([])  # type: ignore[arg-type]


def test_eval_msda_python_rejects_non_dict_request() -> None:
    with pytest.raises(TypeError):
        eval_msda_python(create_default_msda_policy(), "nope")  # type: ignore[arg-type]
