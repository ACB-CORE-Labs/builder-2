from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.model_client_registry import (
    ALLOWED_COST_CLASSES,
    ALLOWED_ENDPOINT_KINDS,
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
            "max_risk_classification": "local_offline",
            "requires_tool_use": True,
            "preferred_model_family": "qwen2.5",
            "preferred_model_id": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            "rationale": "Default coding tasks prefer local offline tool-capable Qwen 2.5 Coder.",
        },
        {
            "rule_id": "reasoning_local_default",
            "task_intent": "reasoning",
            "max_risk_classification": "local_offline",
            "requires_tool_use": False,
            "preferred_model_family": "phi3",
            "preferred_model_id": "mlx-community/Phi-3.5-mini-instruct-4bit",
            "rationale": "Reasoning tasks prefer local offline Phi 3.5 Mini.",
        },
    ]


def create_model_routing_policy() -> dict[str, Any]:
    return {
        "kind": MODEL_ROUTING_POLICY_KIND,
        "schema_version": MODEL_ROUTING_POLICY_SCHEMA_VERSION,
        "policy_name": "passive_model_routing_policy",
        "policy_state": "RECOMMENDATION_ONLY",
        "executes_model": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
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
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
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
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("routing_decision_executes") is not False:
            errors.append("governance.routing_decision_executes must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

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

    req = request or {"task_intent": "coding", "max_risk_classification": "local_offline", "requires_tool_use": True}
    req_intent = req.get("task_intent", "coding")
    req_max_risk = req.get("max_risk_classification", "local_offline")
    if req_max_risk not in _RISK_HIERARCHY:
        raise ValueError(f"Unknown max_risk_classification in request: '{req_max_risk}'")
    max_risk_num = _RISK_HIERARCHY[req_max_risk]
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

    candidates = []
    for cand in registry.get("clients", []):
        if not cand.get("enabled"):
            continue
        cand_risk = cand.get("risk_classification")
        if not cand_risk or cand_risk not in _RISK_HIERARCHY:
            raise ValueError(f"Candidate model '{cand.get('model_id')}' missing valid risk classification")
        if _RISK_HIERARCHY[cand_risk] > max_risk_num:
            continue
        if req_tools and not cand.get("tool_use_supported"):
            continue
        if req.get("required_model_id") and cand.get("model_id") != req.get("required_model_id"):
            continue
        if req.get("required_model_alias") and cand.get("model_alias") != req.get("required_model_alias"):
            continue
        if req.get("required_lane") and cand.get("model_alias") != req.get("required_lane") and cand.get("model_id") != req.get("required_lane"):
            continue

        score = 0
        reasons = [f"Risk level '{cand_risk}' satisfies requirement '{req_max_risk}'"]
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

    candidates.sort(key=lambda x: x[0], reverse=True)

    if not candidates:
        raise ValueError("No candidate model client satisfies the requested criteria.")

    recommended_list = []
    for idx, (_, cand, reasons) in enumerate(candidates, start=1):
        recommended_list.append(
            {
                "rank": idx,
                "provider_id": cand.get("provider_id"),
                "client_id": cand.get("client_id"),
                "model_id": cand.get("model_id"),
                "model_alias": cand.get("model_alias"),
                "risk_classification": cand.get("risk_classification"),
                "reasons": reasons,
                "constraints": [
                    f"Endpoint kind: {cand.get('endpoint_kind')}",
                    f"Cost class: {cand.get('cost_class')}",
                    "Passive recommendation only; requires human promotion before execution",
                ],
            }
        )

    return {
        "kind": MODEL_ROUTING_RECOMMENDATION_KIND,
        "schema_version": MODEL_ROUTING_RECOMMENDATION_SCHEMA_VERSION,
        "recommendation_state": "RECOMMENDATION_ONLY",
        "executes_model": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
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
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

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
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("recommendation_executes") is not False:
            errors.append("governance.recommendation_executes must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    for k, v in record.items():
        if isinstance(v, str) and v in {"EXECUTED", "AUTHORIZED", "PROMOTED", "ENABLED"}:
            if k not in {"recommendation_state"}:
                errors.append(f"field '{k}' claims active authority state '{v}'")

    return errors
