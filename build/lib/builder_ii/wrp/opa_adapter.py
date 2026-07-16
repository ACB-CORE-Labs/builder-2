"""W3 / P2.3 — optional OPA/Rego surface over MSDA declarative gates.

Pure-Python evaluation is the reference implementation (parity with
``governance_router.evaluate_msda_gate``). Rego export is a deterministic
Governor review artifact. The optional ``OpaEvalAdapter`` invokes an external
``opa`` binary when present; it is never required at runtime or in CI.

Promotion honesty:
- Export and eval produce review / decision data only.
- Nothing here grants model, shell, MCP, or gateway execution authority.
- Not wired into model_execution_gateway or tool_invocation_gateway (M-LEAD).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from builder_ii.wrp.governance_router import evaluate_msda_gate

# Package path used in exported Rego and in documented ``opa eval`` queries.
REGO_PACKAGE = "builder_ii.wrp.msda"
REGO_QUERY = f"data.{REGO_PACKAGE}.decision"

_OPA_BINARY = "opa"


class BackendUnavailableError(RuntimeError):
    """Raised when an optional backend (e.g. ``opa``) is not available."""


def _rego_string(value: str) -> str:
    """Escape a string for a Rego double-quoted literal."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _policy_rules(policy: dict[str, Any]) -> list[dict[str, Any]]:
    rules = policy.get("rules") if isinstance(policy, dict) else None
    if not isinstance(rules, list):
        return []
    return [r for r in rules if isinstance(r, dict)]


def export_msda_to_rego(policy: dict[str, Any]) -> str:
    """Export MSDA JSON policy to deterministic Rego-like text for Governor review.

    Semantics mirror ``evaluate_msda_gate``:
    - default deny
    - first matching deny wins
    - allow only if an allow rule matches and no deny matches
    - tool/domain patterns: exact match or ``*``

    Output is byte-stable for a given policy dict content (rule order preserved;
    list members sorted only where order is not policy-significant for matching
    within a single rule's tool/domain lists — we preserve input order).
    """
    if not isinstance(policy, dict):
        raise TypeError("policy must be a dict")

    policy_name = str(policy.get("policy_name") or "msda")
    default_effect = str(policy.get("default_effect") or "deny")
    rules = _policy_rules(policy)
    digest = policy.get("digest")
    digest_s = str(digest) if digest is not None else ""

    lines: list[str] = [
        "# MSDA → Rego export (Governor review surface)",
        f"# policy_name: {policy_name}",
        f"# default_effect: {default_effect}",
        f"# policy_digest: {digest_s}",
        "# semantics: first matching deny wins; else last matching allow; else default deny",
        "# not authority — validation/review only",
        f"package {REGO_PACKAGE}",
        "",
        "import rego.v1",
        "",
        'default effect := "deny"',
        'default rule_id := "default_deny"',
        "default allow := false",
        "",
        "tool_match(pattern) if {",
        '    pattern == "*"',
        "}",
        "",
        "tool_match(pattern) if {",
        "    pattern == input.tool",
        "}",
        "",
        "domain_match(pattern) if {",
        '    pattern == "*"',
        "}",
        "",
        "domain_match(pattern) if {",
        "    pattern == input.data_domain",
        "}",
        "",
    ]

    deny_ids: list[str] = []
    allow_ids: list[str] = []

    for rule in rules:
        rule_id = str(rule.get("rule_id") or "unnamed")
        effect = str(rule.get("effect") or "deny")
        tools = [str(t) for t in (rule.get("tools") or [])]
        domains = [str(d) for d in (rule.get("data_domains") or [])]
        tools_lit = "[" + ", ".join(_rego_string(t) for t in tools) + "]"
        domains_lit = "[" + ", ".join(_rego_string(d) for d in domains) + "]"

        lines.append(f"# rule_id={rule_id} effect={effect}")
        if effect == "deny":
            deny_ids.append(rule_id)
            lines.append(f"deny_match[{_rego_string(rule_id)}] if {{")
            lines.append(f"    tools := {tools_lit}")
            lines.append(f"    domains := {domains_lit}")
            lines.append("    some t in tools")
            lines.append("    tool_match(t)")
            lines.append("    some d in domains")
            lines.append("    domain_match(d)")
            lines.append("}")
            lines.append("")
        elif effect == "allow":
            allow_ids.append(rule_id)
            lines.append(f"allow_match[{_rego_string(rule_id)}] if {{")
            lines.append(f"    tools := {tools_lit}")
            lines.append(f"    domains := {domains_lit}")
            lines.append("    some t in tools")
            lines.append("    tool_match(t)")
            lines.append("    some d in domains")
            lines.append("    domain_match(d)")
            lines.append("}")
            lines.append("")
        else:
            lines.append(f"# skipped unknown effect for rule {rule_id!r}")
            lines.append("")

    # First-matching deny: encode ordered rule_ids so review can reconstruct order.
    deny_order_lit = "[" + ", ".join(_rego_string(r) for r in deny_ids) + "]"
    allow_order_lit = "[" + ", ".join(_rego_string(r) for r in allow_ids) + "]"
    # Full rule order as declared in MSDA (deny-first walk order in Python evaluator).
    full_order = [str(r.get("rule_id") or "unnamed") for r in rules]
    full_order_lit = "[" + ", ".join(_rego_string(r) for r in full_order) + "]"

    lines.extend(
        [
            f"deny_rule_order := {deny_order_lit}",
            f"allow_rule_order := {allow_order_lit}",
            f"rule_order := {full_order_lit}",
            "",
            "# decision object for `opa eval` query",
            "# documented invocation (when opa is on PATH):",
            f"#   opa eval -f json -d policy.rego -i input.json '{REGO_QUERY}'",
            "# input.json shape: {\"tool\": \"...\", \"data_domain\": \"...\", \"risk\": \"...\"}",
            "",
            "first_deny := rid if {",
            "    some i",
            "    rid := rule_order[i]",
            "    deny_match[rid]",
            "    not earlier_deny(i)",
            "}",
            "",
            "earlier_deny(i) if {",
            "    some j",
            "    j < i",
            "    deny_match[rule_order[j]]",
            "}",
            "",
            "last_allow := rid if {",
            "    some i",
            "    rid := rule_order[i]",
            "    allow_match[rid]",
            "    not later_allow(i)",
            "}",
            "",
            "later_allow(i) if {",
            "    some j",
            "    j > i",
            "    allow_match[rule_order[j]]",
            "}",
            "",
            "effect := \"deny\" if {",
            "    first_deny",
            "}",
            "",
            "effect := \"allow\" if {",
            "    not first_deny",
            "    last_allow",
            "}",
            "",
            "rule_id := first_deny if {",
            "    first_deny",
            "}",
            "",
            "rule_id := last_allow if {",
            "    not first_deny",
            "    last_allow",
            "}",
            "",
            "allow if {",
            '    effect == "allow"',
            "}",
            "",
            "decision := {",
            '    "effect": effect,',
            '    "rule_id": rule_id,',
            '    "allow": allow,',
            "}",
            "",
        ]
    )

    return "\n".join(lines)


def _request_fields(request: dict[str, Any]) -> tuple[str, str, str]:
    if not isinstance(request, dict):
        raise TypeError("request must be a dict")
    tool = str(request.get("tool") or "")
    data_domain = str(request.get("data_domain") or "")
    risk = str(request.get("risk") or "local_offline")
    return tool, data_domain, risk


def eval_msda_python(policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Pure-Python MSDA gate decision; equivalent to governance_router rules.

    Reuses ``evaluate_msda_gate`` so decisions cannot drift from the reference
    router. Returns a compact decision dict (not a full WRP envelope):

    ``{"effect", "rule_id", "reasons", "allow", "request", "policy_digest"}``
    """
    if not isinstance(policy, dict):
        raise TypeError("policy must be a dict")
    tool, data_domain, risk = _request_fields(request)

    artifact = evaluate_msda_gate(
        tool=tool,
        data_domain=data_domain,
        policy=policy,
        risk=risk,
    )
    decision = artifact.get("decision") if isinstance(artifact, dict) else None
    if not isinstance(decision, dict):
        effect = "deny"
        rule_id = "default_deny"
        policy_digest = policy.get("digest")
    else:
        effect = str(decision.get("effect") or "deny")
        rule_id = str(decision.get("matched_rule") or "default_deny")
        policy_digest = decision.get("policy_digest")

    allow = effect == "allow"
    if allow:
        reasons = [
            f"matched allow rule {rule_id!r}",
            f"tool={tool!r} data_domain={data_domain!r}",
            "no deny rule matched before allow",
        ]
    elif rule_id == "default_deny":
        reasons = [
            "default deny (no allow rule matched)",
            f"tool={tool!r} data_domain={data_domain!r}",
        ]
    else:
        reasons = [
            f"matched deny rule {rule_id!r}",
            f"tool={tool!r} data_domain={data_domain!r}",
        ]

    return {
        "effect": effect,
        "rule_id": rule_id,
        "reasons": reasons,
        "allow": allow,
        "request": {
            "tool": tool,
            "data_domain": data_domain,
            "risk": risk,
        },
        "policy_digest": policy_digest,
        "backend": "python_msda",
    }


def build_opa_eval_argv(
    *,
    opa_bin: str,
    policy_path: Path | str,
    input_path: Path | str,
    query: str = REGO_QUERY,
) -> list[str]:
    """Documented argv for optional external OPA evaluation (no shell)."""
    return [
        opa_bin,
        "eval",
        "-f",
        "json",
        "-d",
        str(policy_path),
        "-i",
        str(input_path),
        query,
    ]


class OpaEvalAdapter:
    """Optional OPA backend for MSDA review eval.

    Availability is ``shutil.which("opa")`` (or an explicit binary path).
    When unavailable, ``eval`` raises ``BackendUnavailableError``.
    When available, writes exported Rego + input JSON and runs:

        opa eval -f json -d <policy.rego> -i <input.json> 'data.builder_ii.wrp.msda.decision'

    CI must not require a real ``opa`` binary — unit tests mock ``subprocess.run``.
    """

    def __init__(self, *, opa_path: str | None = None) -> None:
        resolved = opa_path if opa_path is not None else shutil.which(_OPA_BINARY)
        self._opa_path: str | None = resolved if resolved else None

    @property
    def available(self) -> bool:
        return self._opa_path is not None

    @property
    def opa_path(self) -> str | None:
        return self._opa_path

    def eval(self, policy: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
        """Evaluate request against policy via external ``opa`` (or raise)."""
        if not self.available or self._opa_path is None:
            raise BackendUnavailableError(
                "opa binary not found on PATH; pure-Python eval_msda_python is the "
                "reference backend. Install Open Policy Agent or use eval_msda_python."
            )

        tool, data_domain, risk = _request_fields(request)
        rego_text = export_msda_to_rego(policy)
        input_obj = {"tool": tool, "data_domain": data_domain, "risk": risk}

        with tempfile.TemporaryDirectory(prefix="builder_ii_opa_") as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "msda_policy.rego"
            input_path = tmp_path / "input.json"
            policy_path.write_text(rego_text, encoding="utf-8")
            input_path.write_text(
                json.dumps(input_obj, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            argv = build_opa_eval_argv(
                opa_bin=self._opa_path,
                policy_path=policy_path,
                input_path=input_path,
            )
            completed = subprocess.run(  # noqa: S603 — fixed argv, shell=False
                argv,
                check=False,
                capture_output=True,
                text=True,
                shell=False,
            )

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(
                f"opa eval failed (exit {completed.returncode}): {stderr or completed.stdout}"
            )

        return self._parse_opa_json(
            completed.stdout or "",
            request={"tool": tool, "data_domain": data_domain, "risk": risk},
            policy_digest=policy.get("digest") if isinstance(policy, dict) else None,
        )

    @staticmethod
    def _parse_opa_json(
        stdout: str,
        *,
        request: dict[str, Any],
        policy_digest: Any,
    ) -> dict[str, Any]:
        """Parse ``opa eval -f json`` output into the compact decision dict."""
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"opa eval returned non-JSON stdout: {exc}") from exc

        # OPA JSON shape: {"result": [{"expressions": [{"value": {...}}]}]}
        value: Any = None
        if isinstance(payload, dict):
            result = payload.get("result")
            if isinstance(result, list) and result:
                first = result[0]
                if isinstance(first, dict):
                    exprs = first.get("expressions")
                    if isinstance(exprs, list) and exprs and isinstance(exprs[0], dict):
                        value = exprs[0].get("value")
            if value is None and "effect" in payload:
                value = payload

        if not isinstance(value, dict):
            raise RuntimeError("opa eval result missing decision object")

        effect = str(value.get("effect") or "deny")
        rule_id = str(value.get("rule_id") or "default_deny")
        allow = bool(value.get("allow")) if "allow" in value else effect == "allow"
        reasons = [
            f"opa backend decision effect={effect!r} rule_id={rule_id!r}",
            f"tool={request.get('tool')!r} data_domain={request.get('data_domain')!r}",
        ]
        return {
            "effect": effect,
            "rule_id": rule_id,
            "reasons": reasons,
            "allow": allow,
            "request": dict(request),
            "policy_digest": policy_digest,
            "backend": "opa",
        }
