from __future__ import annotations

import importlib.util
import json as json_lib
from pathlib import Path
from typing import Any, Literal

DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND = "builder_ii.deepagents_bridge_readiness_report"
DEEPAGENTS_BRIDGE_READINESS_REPORT_SCHEMA_VERSION = 1

OptionalDependencyState = Literal["PRESENT", "ABSENT", "UNKNOWN"]
ReadinessVerdict = Literal["READY_FOR_DRY_RUN_SPEC", "BLOCKED_PENDING_HITL", "NOT_READY"]

_DISABLED_CAPABILITIES = (
    "shell_execution",
    "source_writes",
    "runtime_execution",
    "model_execution",
    "delegation",
    "memory_mutation",
)

_REQUIRED_PROMOTION_GATES = (
    "docs",
    "tests",
    "command surface",
    "failure mode",
    "human approval boundary",
    "output artifact",
    "rollback path",
    "verification path",
)


def _check_dependency_state() -> OptionalDependencyState:
    try:
        spec = importlib.util.find_spec("deepagents")
        return "PRESENT" if spec is not None else "ABSENT"
    except Exception:
        return "UNKNOWN"


def create_deepagents_bridge_readiness_report(
    *,
    target_profile: str,
    agent_profile_compatibility_summary: str,
    readiness_verdict: ReadinessVerdict = "NOT_READY",
) -> dict[str, Any]:
    return {
        "kind": DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
        "schema_version": DEEPAGENTS_BRIDGE_READINESS_REPORT_SCHEMA_VERSION,
        "target_profile": target_profile,
        "agent_profile_compatibility_summary": agent_profile_compatibility_summary,
        "optional_dependency_state": _check_dependency_state(),
        "bridge_mode": "READINESS_ONLY",
        "disabled_capabilities": list(_DISABLED_CAPABILITIES),
        "required_promotion_gates": list(_REQUIRED_PROMOTION_GATES),
        "readiness_verdict": readiness_verdict,
        "governance": {
            "capability_state": "bridge_readiness_report",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_deepagents_bridge_readiness_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_deepagents_bridge_readiness_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_bridge_readiness_report(report), encoding="utf-8")


def validate_deepagents_bridge_readiness_report(report: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["deepagents bridge readiness report must be a JSON object"]

    if report.get("kind") != DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND}")
    if report.get("schema_version") != DEEPAGENTS_BRIDGE_READINESS_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_BRIDGE_READINESS_REPORT_SCHEMA_VERSION}")

    if not isinstance(report.get("target_profile"), str) or not report.get("target_profile"):
        errors.append("target_profile must be a non-empty string")

    if not isinstance(report.get("agent_profile_compatibility_summary"), str) or not report.get(
        "agent_profile_compatibility_summary"
    ):
        errors.append("agent_profile_compatibility_summary must be a non-empty string")

    if report.get("optional_dependency_state") not in ("PRESENT", "ABSENT", "UNKNOWN"):
        errors.append("optional_dependency_state must be PRESENT, ABSENT, or UNKNOWN")

    if report.get("bridge_mode") != "READINESS_ONLY":
        errors.append("bridge_mode must be READINESS_ONLY")

    disabled_caps = report.get("disabled_capabilities")
    if not isinstance(disabled_caps, list):
        errors.append("disabled_capabilities must be a list")
    else:
        for cap in _DISABLED_CAPABILITIES:
            if cap not in disabled_caps:
                errors.append(f"disabled_capabilities must include {cap}")
        if len(disabled_caps) != len(_DISABLED_CAPABILITIES):
            errors.append("disabled_capabilities contains unexpected items")

    gates = report.get("required_promotion_gates")
    if not isinstance(gates, list):
        errors.append("required_promotion_gates must be a list")
    else:
        for gate in _REQUIRED_PROMOTION_GATES:
            if gate not in gates:
                errors.append(f"required_promotion_gates must include {gate}")
        if len(gates) != len(_REQUIRED_PROMOTION_GATES):
            errors.append("required_promotion_gates contains unexpected items")

    if report.get("readiness_verdict") not in ("READY_FOR_DRY_RUN_SPEC", "BLOCKED_PENDING_HITL", "NOT_READY"):
        errors.append("readiness_verdict must be READY_FOR_DRY_RUN_SPEC, BLOCKED_PENDING_HITL, or NOT_READY")

    governance = report.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "bridge_readiness_report":
            errors.append("governance.capability_state must be bridge_readiness_report")
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "source_writes",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")

        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    return errors


def validate_deepagents_bridge_readiness_report_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_deepagents_bridge_readiness_report(data)
