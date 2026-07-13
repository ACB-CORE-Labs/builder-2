from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.model_client_registry import (
    ALLOWED_RISK_CLASSIFICATIONS,
    KNOWN_CLIENT_IDS,
    KNOWN_MODEL_IDS,
    KNOWN_PROVIDER_IDS,
    MODEL_CLIENT_REGISTRY_KIND,
    validate_model_client_registry,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

MODEL_ROUTING_POLICY_KIND = "builder_ii.model_routing_policy"
MODEL_ROUTING_POLICY_SCHEMA_VERSION = 1

MODEL_ROUTING_RECOMMENDATION_KIND = "builder_ii.model_routing_recommendation"
MODEL_ROUTING_RECOMMENDATION_SCHEMA_VERSION = 1

_RISK_HIERARCHY = {
    "local_offline": 1,
    "local_network": 2,
    "cloud_external": 3,
}


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_routing_rules() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": "coding_local_default",
            "task_intent": "coding",
            "max_risk_classification": "local_network",
            "requires_tool_use": True,
            "preferred_model_family": "qwen2.5",
            "preferred_model_id": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            "rationale": "Default coding tasks prefer local offline tool-capable Qwen 2.5 Coder.",
        },
        {
            "rule_id": "reasoning_local_default",
            "task_intent": "reasoning",
            "max_risk_classification": "local_network",
            "requires_tool_use": False,
            "preferred_model_family": "phi4",
            "preferred_model_id": "mlx-community/Phi-4-mini-reasoning-4bit",
            "rationale": "Reasoning tasks prefer local offline Phi 3.5 Mini.",
        },
    ]


def create_model_routing_policy(*, require_wrp_binding: bool = False) -> dict[str, Any]:
    """Create a passive routing policy.

    ``require_wrp_binding`` defaults False for backward compatibility. S1 promotion
    may set it True on operator-selected policies so recommendations must carry a
    digest-bound WRP classification binding (still RECOMMENDATION_ONLY — not live exec).
    """
    return {
        "kind": MODEL_ROUTING_POLICY_KIND,
        "schema_version": MODEL_ROUTING_POLICY_SCHEMA_VERSION,
        "policy_name": "passive_model_routing_policy",
        "policy_state": "RECOMMENDATION_ONLY",
        "executes_model": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "require_wrp_binding": bool(require_wrp_binding),
        "bound_registry_kind": MODEL_CLIENT_REGISTRY_KIND,
        "rules": _default_routing_rules(),
        "governance": {
            "model_execution": "DISABLED",
            "runtime_execution": "DISABLED",
            "network_calls": "DISABLED",
            "shell_execution": "DISABLED",
            "provider_calls": "DISABLED",
            "artifact_is_authority": False,
            "routing_decision_executes": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_model_routing_policy(policy: dict[str, Any]) -> str:
    return json_lib.dumps(policy, indent=2, sort_keys=True) + "\n"


def write_model_routing_policy(policy: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_model_routing_policy(policy), encoding="utf-8")


def validate_model_routing_policy(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["model routing policy must be a JSON object"]
    if record.get("kind") != MODEL_ROUTING_POLICY_KIND:
        errors.append(f"kind must be {MODEL_ROUTING_POLICY_KIND}")
    if record.get("schema_version") != MODEL_ROUTING_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_ROUTING_POLICY_SCHEMA_VERSION}")
    if record.get("policy_state") != "RECOMMENDATION_ONLY":
        errors.append("policy_state must be RECOMMENDATION_ONLY")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false or NOT_AUTHORIZED")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false or NOT_AUTHORIZED")
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    rules = record.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty list")
    else:
        seen_rule_ids = set()
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"rules[{idx}] must be an object")
                continue
            rule_id = rule.get("rule_id")
            if not isinstance(rule_id, str) or not rule_id:
                errors.append(f"rules[{idx}].rule_id must be a non-empty string")
            elif rule_id in seen_rule_ids:
                errors.append(f"rules[{idx}].rule_id '{rule_id}' is not unique")
            else:
                seen_rule_ids.add(rule_id)
            task_intent = rule.get("task_intent")
            if not isinstance(task_intent, str) or not task_intent:
                errors.append(f"rules[{idx}].task_intent must be a non-empty string")
            rationale = rule.get("rationale")
            if not isinstance(rationale, str) or not rationale:
                errors.append(f"rules[{idx}].rationale must be a non-empty string")
            requires_tool_use = rule.get("requires_tool_use")
            if not isinstance(requires_tool_use, bool):
                errors.append(f"rules[{idx}].requires_tool_use must be a boolean")

            risk = rule.get("max_risk_classification")
            if not risk or risk not in ALLOWED_RISK_CLASSIFICATIONS:
                errors.append(f"rules[{idx}].max_risk_classification missing or invalid")
            pref_model = rule.get("preferred_model_id")
            if pref_model is not None and pref_model not in KNOWN_MODEL_IDS:
                errors.append(f"rules[{idx}].preferred_model_id '{pref_model}' is unknown")
            pref_provider = rule.get("preferred_provider_id")
            if pref_provider is not None and pref_provider not in KNOWN_PROVIDER_IDS:
                errors.append(f"rules[{idx}].preferred_provider_id '{pref_provider}' is unknown")
            pref_client = rule.get("preferred_client_id")
            if pref_client is not None and pref_client not in KNOWN_CLIENT_IDS:
                errors.append(f"rules[{idx}].preferred_client_id '{pref_client}' is unknown")

    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in ("model_execution", "runtime_execution", "network_calls", "shell_execution", "provider_calls"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("routing_decision_executes") is not False:
            errors.append("governance.routing_decision_executes must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    def _check_no_active_states(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in {"policy_state"}:
                    continue
                _check_no_active_states(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _check_no_active_states(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            if obj in {"EXECUTED", "AUTHORIZED", "PROMOTED", "ENABLED"}:
                errors.append(f"field '{path}' claims active authority state '{obj}'")

    _check_no_active_states(record, "policy")

    return errors


def validate_model_routing_policy_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_model_routing_policy(data)


def _build_wrp_binding(
    *,
    require: bool,
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Classify workload for S1 binding. Fail closed when require and classification fails.

    Free-text classification uses ``task_text`` / ``task`` only (not bare task_intent tokens),
    so default coding intents without free text do not re-rank candidates.
    """
    free_text = str(request.get("task_text") or request.get("task") or "").strip()
    if require and not free_text:
        # Fall back to task_intent only when binding is mandatory.
        free_text = str(request.get("task_intent") or "").strip()
        if not free_text:
            raise ValueError(
                "require_wrp_binding is true but request has no task_text/task/task_intent for classification"
            )
    if not free_text:
        return None
    try:
        from builder_ii.wrp.workload_classifier import classify_workload

        wrp_res = classify_workload(text=free_text)
        clf = wrp_res["classification"]
        return {
            "required": require,
            "classification_digest": wrp_res["digest"],
            "tier": clf["tier"],
            "recommended_model_alias": wrp_res["recommended_model_alias"],
            "confidence": clf["confidence"],
            "source_kind": wrp_res["kind"],
            "rationale": clf.get("rationale", ""),
        }
    except Exception as exc:
        if require:
            raise ValueError(f"WRP binding required but classification failed: {exc}") from exc
        return None


def create_model_routing_recommendation(
    policy: dict[str, Any],
    registry: dict[str, Any],
    request: dict[str, Any] | None = None,
    policy_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    policy_errors = validate_model_routing_policy(policy)
    if policy_errors:
        raise ValueError(f"Invalid model routing policy: {policy_errors}")
    registry_errors = validate_model_client_registry(registry)
    if registry_errors:
        raise ValueError(f"Invalid model client registry: {registry_errors}")

    req = request or {"task_intent": "coding", "max_risk_classification": "local_network", "requires_tool_use": True}
    require_wrp = bool(policy.get("require_wrp_binding")) or bool(req.get("require_wrp_binding"))
    wrp_binding = _build_wrp_binding(require=require_wrp, request=req)
    req_intent = req.get("task_intent", "coding")
    req_max_risk = req.get("max_risk_classification", "local_network")
    if req_max_risk not in _RISK_HIERARCHY:
        raise ValueError(f"Unknown max_risk_classification in request: '{req_max_risk}'")
    _RISK_HIERARCHY[req_max_risk]
    req_tools = req.get("requires_tool_use", False)

    # Validate explicit constraints against known universes before filtering
    from builder_ii.model_client_registry import MODEL_ALIASES

    req_model_id = req.get("required_model_id")
    if req_model_id and req_model_id not in KNOWN_MODEL_IDS:
        raise ValueError(f"Unknown required_model_id: '{req_model_id}'")

    req_alias = req.get("required_model_alias")
    if req_alias and req_alias not in MODEL_ALIASES:
        raise ValueError(f"Unknown required_model_alias: '{req_alias}'")

    req_lane = req.get("required_lane")
    if req_lane and req_lane not in KNOWN_MODEL_IDS and req_lane not in MODEL_ALIASES:
        raise ValueError(f"Unknown required_lane (neither known model ID nor alias): '{req_lane}'")

    # Find matching policy rule
    matched_rule = None
    for r in policy.get("rules", []):
        if r.get("task_intent") == req_intent:
            matched_rule = r
            break

    request_risk_num = _RISK_HIERARCHY[req_max_risk]
    effective_max_risk_num = request_risk_num
    effective_max_risk_label = req_max_risk
    policy_cap_applied = False

    if matched_rule:
        rule_risk = matched_rule.get("max_risk_classification")
        if rule_risk in _RISK_HIERARCHY:
            rule_risk_num = _RISK_HIERARCHY[rule_risk]
            if rule_risk_num < effective_max_risk_num:
                effective_max_risk_num = rule_risk_num
                effective_max_risk_label = rule_risk
                policy_cap_applied = True

    candidates = []
    for cand in registry.get("clients", []):
        if not cand.get("enabled"):
            continue
        cand_risk = cand.get("risk_classification")
        if not cand_risk or cand_risk not in _RISK_HIERARCHY:
            raise ValueError(f"Candidate model '{cand.get('model_id')}' missing valid risk classification")
        if _RISK_HIERARCHY[cand_risk] > effective_max_risk_num:
            continue
        if req_tools and not cand.get("tool_use_supported"):
            continue
        if req.get("required_model_id") and cand.get("model_id") != req.get("required_model_id"):
            continue
        if req.get("required_model_alias") and cand.get("model_alias") != req.get("required_model_alias"):
            continue
        if (
            req.get("required_lane")
            and cand.get("model_alias") != req.get("required_lane")
            and cand.get("model_id") != req.get("required_lane")
        ):
            continue

        score = 0
        reasons = [f"Risk level '{cand_risk}' satisfies requirement '{req_max_risk}'"]
        if policy_cap_applied:
            reasons.append(f"Risk level capped at policy limit '{effective_max_risk_label}'")
        if cand.get("tool_use_supported"):
            reasons.append("Supports required tool use")

        if matched_rule:
            if cand.get("model_id") == matched_rule.get("preferred_model_id"):
                score += 10
                reasons.append("Exact match for policy preferred model id")
            elif cand.get("model_family") == matched_rule.get("preferred_model_family"):
                score += 5
                reasons.append(f"Matches preferred model family '{cand.get('model_family')}'")

        candidates.append((score, cand, reasons))

    # Prefer fleet_binding.selected_alias when provided (P2 remainder / OmniRouter bind).
    fleet_binding = req.get("fleet_binding")
    if fleet_binding is None and isinstance(req.get("fleet_allocation"), dict):
        fleet_binding = req["fleet_allocation"].get("fleet_binding")
    prefer_alias: str | None = None
    if isinstance(fleet_binding, dict) and fleet_binding.get("selected_alias"):
        prefer_alias = str(fleet_binding["selected_alias"])

    # Re-rank when S1 require_wrp_binding is active and/or fleet_binding selects an alias.
    prefer_from_wrp = wrp_binding is not None and require_wrp
    if prefer_from_wrp:
        prefer_alias = str(wrp_binding.get("recommended_model_alias") or prefer_alias or "")

    if prefer_alias:
        matched_idx = next(
            (i for i, (_, cand, _) in enumerate(candidates) if cand.get("model_alias") == prefer_alias),
            None,
        )
        if matched_idx is not None:
            score, cand, reasons = candidates[matched_idx]
            tag = "WRP binding" if prefer_from_wrp else "fleet_binding"
            reasons = list(reasons) + [f"{tag} prefers alias '{prefer_alias}'"]
            candidates[matched_idx] = (score + 100, cand, reasons)
        elif prefer_from_wrp and wrp_binding is not None:
            wrp_binding = {
                **wrp_binding,
                "wrp_alias_excluded_reason": (
                    f"WRP recommended alias '{prefer_alias}' not in filtered registry candidates; "
                    "keeping policy-ranked winner (fail-open on alias, binding still recorded)"
                ),
            }

    candidates.sort(key=lambda x: x[0], reverse=True)

    if not candidates:
        raise ValueError("No candidate model client satisfies the requested criteria.")

    recommended_list = []
    for idx, (_, cand, reasons) in enumerate(candidates, start=1):
        cand_constraints = [
            f"Endpoint kind: {cand.get('endpoint_kind')}",
            f"Cost class: {cand.get('cost_class')}",
            "Passive recommendation only; requires human promotion before execution",
        ]
        if policy_cap_applied:
            cand_constraints.append(f"Policy risk cap applied: {effective_max_risk_label}")
        recommended_list.append(
            {
                "rank": idx,
                "provider_id": cand.get("provider_id"),
                "client_id": cand.get("client_id"),
                "model_id": cand.get("model_id"),
                "model_alias": cand.get("model_alias"),
                "risk_classification": cand.get("risk_classification"),
                "reasons": reasons,
                "constraints": cand_constraints,
            }
        )

    result: dict[str, Any] = {
        "kind": MODEL_ROUTING_RECOMMENDATION_KIND,
        "schema_version": MODEL_ROUTING_RECOMMENDATION_SCHEMA_VERSION,
        "recommendation_state": "RECOMMENDATION_ONLY",
        "executes_model": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "require_wrp_binding": require_wrp,
        "request": req,
        "source_policy_ref": {
            "kind": MODEL_ROUTING_POLICY_KIND,
            "path": str(policy_path) if policy_path else None,
            "sha256": _digest(policy),
        },
        "source_registry_ref": {
            "kind": MODEL_CLIENT_REGISTRY_KIND,
            "path": str(registry_path) if registry_path else None,
            "sha256": _digest(registry),
        },
        "recommended_candidates": recommended_list,
        "governance": {
            "model_execution": "DISABLED",
            "runtime_execution": "DISABLED",
            "network_calls": "DISABLED",
            "shell_execution": "DISABLED",
            "provider_calls": "DISABLED",
            "artifact_is_authority": False,
            "recommendation_executes": False,
            "core_workbench_coupling": "NONE",
        },
    }
    if wrp_binding is not None:
        result["wrp_binding"] = wrp_binding
    if isinstance(fleet_binding, dict) and fleet_binding.get("selected_alias"):
        result["fleet_binding"] = {
            "selected_alias": fleet_binding.get("selected_alias"),
            "token_budget_remaining": fleet_binding.get("token_budget_remaining"),
            "risk_class": fleet_binding.get("risk_class"),
            "source": "request.fleet_binding",
            "grants_authority": False,
        }
    return result


def dumps_model_routing_recommendation(rec: dict[str, Any]) -> str:
    return json_lib.dumps(rec, indent=2, sort_keys=True) + "\n"


def write_model_routing_recommendation(rec: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_model_routing_recommendation(rec), encoding="utf-8")


def validate_model_routing_recommendation(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["model routing recommendation must be a JSON object"]
    if record.get("kind") != MODEL_ROUTING_RECOMMENDATION_KIND:
        errors.append(f"kind must be {MODEL_ROUTING_RECOMMENDATION_KIND}")
    if record.get("schema_version") != MODEL_ROUTING_RECOMMENDATION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_ROUTING_RECOMMENDATION_SCHEMA_VERSION}")
    if record.get("recommendation_state") != "RECOMMENDATION_ONLY":
        errors.append("recommendation_state must be RECOMMENDATION_ONLY")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false or NOT_AUTHORIZED")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false or NOT_AUTHORIZED")
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    require_wrp = record.get("require_wrp_binding") is True
    wrp_binding = record.get("wrp_binding")
    if require_wrp:
        if not isinstance(wrp_binding, dict):
            errors.append("require_wrp_binding is true but wrp_binding is missing or not an object")
        else:
            for key in (
                "classification_digest",
                "tier",
                "recommended_model_alias",
                "confidence",
                "source_kind",
            ):
                if not wrp_binding.get(key):
                    errors.append(f"wrp_binding.{key} is required when require_wrp_binding is true")
            digest = wrp_binding.get("classification_digest")
            if isinstance(digest, str) and not _SHA256_RE.match(digest):
                errors.append("wrp_binding.classification_digest must be a 64-char hex SHA-256")
            if wrp_binding.get("required") is not True:
                errors.append("wrp_binding.required must be true when require_wrp_binding is true")
    elif wrp_binding is not None and not isinstance(wrp_binding, dict):
        errors.append("wrp_binding must be an object when present")

    policy_ref = record.get("source_policy_ref")
    if not isinstance(policy_ref, dict):
        errors.append("source_policy_ref must be an object")
    else:
        if policy_ref.get("kind") != MODEL_ROUTING_POLICY_KIND:
            errors.append(f"source_policy_ref.kind must be {MODEL_ROUTING_POLICY_KIND}")
        if not isinstance(policy_ref.get("sha256"), str) or not _SHA256_RE.match(policy_ref["sha256"]):
            errors.append("source_policy_ref.sha256 must be a valid SHA-256 digest")

    registry_ref = record.get("source_registry_ref")
    if not isinstance(registry_ref, dict):
        errors.append("source_registry_ref must be an object")
    else:
        if registry_ref.get("kind") != MODEL_CLIENT_REGISTRY_KIND:
            errors.append(f"source_registry_ref.kind must be {MODEL_CLIENT_REGISTRY_KIND}")
        if not isinstance(registry_ref.get("sha256"), str) or not _SHA256_RE.match(registry_ref["sha256"]):
            errors.append("source_registry_ref.sha256 must be a valid SHA-256 digest")

    candidates = record.get("recommended_candidates")
    if not isinstance(candidates, list):
        errors.append("recommended_candidates must be a list")
    else:
        for idx, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                errors.append(f"recommended_candidates[{idx}] must be an object")
                continue
            prov = cand.get("provider_id")
            if prov not in KNOWN_PROVIDER_IDS:
                errors.append(f"recommended_candidates[{idx}].provider_id '{prov}' is unknown")
            cli = cand.get("client_id")
            if cli not in KNOWN_CLIENT_IDS:
                errors.append(f"recommended_candidates[{idx}].client_id '{cli}' is unknown")
            mod = cand.get("model_id")
            if mod not in KNOWN_MODEL_IDS:
                errors.append(f"recommended_candidates[{idx}].model_id '{mod}' is unknown")
            risk = cand.get("risk_classification")
            if not risk or risk not in ALLOWED_RISK_CLASSIFICATIONS:
                errors.append(f"recommended_candidates[{idx}].risk_classification missing or invalid")

    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in ("model_execution", "runtime_execution", "network_calls", "shell_execution", "provider_calls"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("recommendation_executes") is not False:
            errors.append("governance.recommendation_executes must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    for k, v in record.items():
        if isinstance(v, str) and v in {"EXECUTED", "AUTHORIZED", "PROMOTED", "ENABLED"}:
            if k not in {"recommendation_state"}:
                errors.append(f"field '{k}' claims active authority state '{v}'")

    return errors


MODEL_EXECUTION_POLICY_KIND = "builder_ii.model_execution_policy"
MODEL_EXECUTION_POLICY_SCHEMA_VERSION = 1


def create_model_execution_policy(recommendation: dict[str, Any], max_tokens: int = 4096) -> dict[str, Any]:
    """Create a bounded model execution policy artifact.

    This is an operator-scoped execution policy. It does NOT grant authority; authority
    remains with the command authority registry (builder-model call / standalone-call) and
    explicit operator invocation. This artifact records the approved model set and token
    limits for a single governed call session.
    """
    return {
        "kind": MODEL_EXECUTION_POLICY_KIND,
        "schema_version": MODEL_EXECUTION_POLICY_SCHEMA_VERSION,
        "policy_state": "AUTHORIZED",
        "executes_model": True,
        "grants_authority": False,
        "operator_approval_required": True,
        "requires_human_promotion_for_execution": True,
        "max_tokens": max_tokens,
        "source_recommendation_ref": {"kind": MODEL_ROUTING_RECOMMENDATION_KIND, "sha256": _digest(recommendation)},
        "allowed_models": [cand["model_id"] for cand in recommendation.get("recommended_candidates", [])],
        "governance": {
            "model_execution": "ENABLED_UNDER_ENVELOPE",
            "runtime_execution": "DISABLED",
            "network_calls": "DISABLED",
            "shell_execution": "DISABLED",
            "provider_calls": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_model_execution_policy(policy: dict[str, Any]) -> str:
    return json_lib.dumps(policy, indent=2, sort_keys=True) + "\n"


def write_model_execution_policy(policy: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_model_execution_policy(policy), encoding="utf-8")


def validate_model_execution_policy(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["model execution policy must be a JSON object"]
    if record.get("kind") != MODEL_EXECUTION_POLICY_KIND:
        errors.append(f"kind must be {MODEL_EXECUTION_POLICY_KIND}")
    if record.get("schema_version") != MODEL_EXECUTION_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_EXECUTION_POLICY_SCHEMA_VERSION}")
    if record.get("policy_state") != "AUTHORIZED":
        errors.append("policy_state must be AUTHORIZED")
    if record.get("executes_model") is not True:
        errors.append("executes_model must be true")
    # Execution policy must NOT claim hidden authority; authority comes from command
    # authority registry and explicit operator invocation only.
    if record.get("grants_authority") is not False:
        errors.append(
            "grants_authority must be false or NOT_AUTHORIZED — execution policy is a bounded artifact, not an authority source"
        )
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    if not isinstance(record.get("max_tokens"), int) or record["max_tokens"] <= 0:
        errors.append("max_tokens must be a positive integer")

    rec_ref = record.get("source_recommendation_ref")
    if not isinstance(rec_ref, dict):
        errors.append("source_recommendation_ref must be an object")
    else:
        if rec_ref.get("kind") != MODEL_ROUTING_RECOMMENDATION_KIND:
            errors.append(f"source_recommendation_ref.kind must be {MODEL_ROUTING_RECOMMENDATION_KIND}")
        if not isinstance(rec_ref.get("sha256"), str) or not _SHA256_RE.match(rec_ref["sha256"]):
            errors.append("source_recommendation_ref.sha256 must be a valid SHA-256 digest")

    allowed_models = record.get("allowed_models")
    if not isinstance(allowed_models, list) or not allowed_models:
        errors.append("allowed_models must be a non-empty list")
    else:
        for idx, mod in enumerate(allowed_models):
            if not isinstance(mod, str) or not mod:
                errors.append(f"allowed_models[{idx}] must be a non-empty string")
            elif mod not in KNOWN_MODEL_IDS:
                errors.append(f"allowed_models[{idx}] '{mod}' is unknown")

    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "ENABLED_UNDER_ENVELOPE":
            errors.append("governance.model_execution must be ENABLED_UNDER_ENVELOPE")
        for key in ("runtime_execution", "network_calls", "shell_execution", "provider_calls"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_model_execution_policy_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_model_execution_policy(data)
