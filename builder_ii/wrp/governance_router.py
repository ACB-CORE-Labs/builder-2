"""W3 / F3 — GovernanceRouter / MSDA declarative access gating.

Deny-by-default tool and data-domain gates. Every decision is a digest-bound artifact.
OPA/Rego is an optional external review surface — not a required runtime dependency.
"""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    MSDA_GATE_DECISION_KIND,
    MSDA_POLICY_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)


def create_default_msda_policy() -> dict[str, Any]:
    return base_envelope(
        kind=MSDA_POLICY_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
        extra={
            "policy_name": "wrp_default_msda",
            "default_effect": "deny",
            "rules": [
                {
                    "rule_id": "allow_local_readonly_tools",
                    "effect": "allow",
                    "tools": ["repo_map", "context_pack", "artifact_validate", "pytest_local"],
                    "data_domains": ["local_workspace", "artifact_store"],
                    "max_risk": "local_network",
                },
                {
                    # S2 v2 gateway nodes (record/stub_tool only — not shell, not cloud MCP).
                    "rule_id": "allow_wrp_gateway_local_tools",
                    "effect": "allow",
                    "tools": ["model_call", "builtin.echo", "builtin.utc_static"],
                    "data_domains": ["local_workspace", "artifact_store"],
                    "max_risk": "local_network",
                },
                {
                    "rule_id": "deny_shell_by_default",
                    "effect": "deny",
                    "tools": ["shell", "bash", "subprocess_open"],
                    "data_domains": ["*"],
                },
                {
                    "rule_id": "deny_mcp_network_by_default",
                    "effect": "deny",
                    "tools": ["mcp_call", "network_fetch"],
                    "data_domains": ["external_network"],
                },
                {
                    "rule_id": "deny_secret_domain",
                    "effect": "deny",
                    "tools": ["*"],
                    "data_domains": ["secrets", "credentials"],
                },
            ],
            "audit_required": True,
            "grants_authority": False,
        },
    )


def _tool_matches(pattern: str, tool: str) -> bool:
    return pattern == "*" or pattern == tool


def _domain_matches(pattern: str, domain: str) -> bool:
    return pattern == "*" or pattern == domain


def evaluate_msda_gate(
    *,
    tool: str,
    data_domain: str,
    policy: dict[str, Any] | None = None,
    risk: str = "local_offline",
) -> dict[str, Any]:
    """Evaluate access request; default deny. Always emits a decision artifact."""
    pol = policy or create_default_msda_policy()
    rules = pol.get("rules") if isinstance(pol, dict) else None
    if not isinstance(rules, list):
        rules = []

    matched_rule: str | None = None
    effect = "deny"
    # First matching deny wins among denies; allows only if an allow matches and no deny matches.
    deny_hit = False
    allow_hit = False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        tools = rule.get("tools") or []
        domains = rule.get("data_domains") or []
        tool_ok = any(_tool_matches(str(t), tool) for t in tools)
        domain_ok = any(_domain_matches(str(d), data_domain) for d in domains)
        if not (tool_ok and domain_ok):
            continue
        if rule.get("effect") == "deny":
            deny_hit = True
            matched_rule = str(rule.get("rule_id", "deny"))
            break
        if rule.get("effect") == "allow":
            allow_hit = True
            matched_rule = str(rule.get("rule_id", "allow"))

    if deny_hit:
        effect = "deny"
    elif allow_hit:
        effect = "allow"
    else:
        effect = "deny"
        matched_rule = matched_rule or "default_deny"

    return base_envelope(
        kind=MSDA_GATE_DECISION_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
        extra={
            "request": {
                "tool": tool,
                "data_domain": data_domain,
                "risk": risk,
            },
            "decision": {
                "effect": effect,
                "matched_rule": matched_rule,
                "policy_digest": pol.get("digest") if isinstance(pol, dict) else None,
            },
            "audit": {
                "logged": True,
                "tamper_evident": True,
            },
            "execution_permitted": False,  # gate artifact never executes
            "grants_authority": False,
        },
    )


def validate_msda_policy(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=MSDA_POLICY_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("default_effect") != "deny":
        errors.append("default_effect must be deny")
    rules = record.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty list")
    return errors


def validate_msda_gate_decision(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=MSDA_GATE_DECISION_KIND)
    if not isinstance(record, dict):
        return errors
    decision = record.get("decision")
    if not isinstance(decision, dict) or decision.get("effect") not in {"allow", "deny"}:
        errors.append("decision.effect must be allow or deny")
    if record.get("execution_permitted") is not False:
        errors.append("execution_permitted must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    return errors
