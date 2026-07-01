from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as metadata
import json as json_lib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from builder_ii.deepagents_work_artifacts import (
    DEEPAGENTS_WORK_PLAN_KIND,
    validate_deepagents_work_plan,
)
from builder_ii.target_profiles import target_names


DEEPAGENTS_EXECUTION_CANDIDATE_KIND = "builder_ii.deepagents_execution_candidate"
DEEPAGENTS_EXECUTION_APPROVAL_KIND = "builder_ii.deepagents_execution_approval"
DEEPAGENTS_RUN_ENVELOPE_KIND = "builder_ii.deepagents_run_envelope"
DEEPAGENTS_EVENT_RECORD_KIND = "builder_ii.deepagents_event_record"
DEEPAGENTS_EVENT_LEDGER_KIND = "builder_ii.deepagents_event_ledger"
DEEPAGENTS_REPLAY_REPORT_KIND = "builder_ii.deepagents_replay_report"
DEEPAGENTS_CHECKPOINT_KIND = "builder_ii.deepagents_checkpoint"
DEEPAGENTS_EXECUTION_RECEIPT_KIND = "builder_ii.deepagents_execution_receipt"
DEEPAGENTS_EVIDENCE_BUNDLE_KIND = "builder_ii.deepagents_evidence_bundle"
DEEPAGENTS_BACKEND_READINESS_GATE_KIND = "builder_ii.deepagents_backend_readiness_gate"

DEEPAGENTS_EXECUTION_SCHEMA_VERSION = 1
DEEPAGENTS_APPROVAL_MODE = "hitl_deepagents_candidate_digest_approval"
OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION = "builder-ii.deepagents.backend.v1"
OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION_EXPORT = "BUILDER_II_DEEPAGENTS_PROTOCOL_VERSION"
OPTIONAL_DEEPAGENTS_RUNNER_EXPORT = "builder_ii_run_protocol_subagent"
OPTIONAL_DEEPAGENTS_FACTORY_EXPORT = "create_governed_deep_agent"

PROTOCOL_FAKE_BACKEND = "protocol_fake"
OPTIONAL_DEEPAGENTS_BACKEND = "optional_deepagents"
BACKEND_MODES = (PROTOCOL_FAKE_BACKEND, OPTIONAL_DEEPAGENTS_BACKEND)

RUN_STATUSES = ("COMPLETED", "CHECKPOINTED", "FAILED")
EVENT_TYPES = (
    "candidate_accepted",
    "backend_selected",
    "resume_started",
    "subagent_scheduled",
    "subagent_result_recorded",
    "checkpoint_recorded",
    "run_completed",
    "run_failed",
    "action_denied",
)

DENIED_CAPABILITIES = (
    "source writes",
    "shell execution",
    "git mutation",
    "mcp calls",
    "goose activation",
    "persistent memory mutation",
    "native deepagents model invocation",
    "direct tool execution",
    "core workbench coupling",
)

OPTIONAL_DENIAL_PROBE_CAPABILITIES = (
    "tool calls",
    "model calls",
    "shell execution",
    "mcp calls",
    "memory mutation",
    "source writes",
)

CAPABILITY_PROMOTION_GATE_NAMES = (
    "docs",
    "tests",
    "command_surface",
    "failure_mode",
    "human_approval_boundary",
    "output_artifact",
    "rollback_path",
    "verification_path",
)

OPTIONAL_BACKEND_RESULT_FALSE_FIELDS = (
    "writes_source",
    "executes_shell",
    "calls_models",
    "calls_tools",
    "calls_mcp",
    "mutates_memory",
    "constructs_deepagents",
)

OPTIONAL_BACKEND_RESULT_SCHEMA_FIELDS = (
    "calls_mcp",
    "calls_models",
    "calls_tools",
    "constructs_deepagents",
    "executes_shell",
    "mutates_memory",
    "result_digest",
    "result_mode",
    "subagent_profile",
    "summary",
    "writes_source",
)

_SHA256_HEX = set("0123456789abcdef")
_DIGEST_KEYS = {
    "candidate_digest",
    "approval_digest",
    "envelope_digest",
    "event_digest",
    "ledger_digest",
    "replay_digest",
    "checkpoint_digest",
    "receipt_digest",
    "evidence_bundle_digest",
    "readiness_gate_digest",
    "result_digest",
}


class DeepAgentsBackendDenied(RuntimeError):
    """Raised when a backend request is a governed denial, not a backend crash."""


@runtime_checkable
class DeepAgentsBackend(Protocol):
    name: str

    def run_subagent(self, *, subagent_profile: str, task: str) -> dict[str, Any]:
        """Return a proposal-only subagent result payload."""


@dataclass(frozen=True)
class ProtocolFakeBackend:
    name: str = PROTOCOL_FAKE_BACKEND

    def run_subagent(self, *, subagent_profile: str, task: str) -> dict[str, Any]:
        summary = (
            f"{subagent_profile} produced a proposal-only protocol result for: "
            f"{task.strip()}"
        )
        payload = {
            "subagent_profile": subagent_profile,
            "result_mode": "PROPOSAL_ONLY",
            "summary": summary,
            "writes_source": False,
            "executes_shell": False,
            "calls_models": False,
            "calls_tools": False,
            "calls_mcp": False,
            "mutates_memory": False,
            "constructs_deepagents": False,
        }
        payload["result_digest"] = _digest_jsonable(payload)
        return payload


@dataclass(frozen=True)
class OptionalDeepAgentsBackend:
    name: str = OPTIONAL_DEEPAGENTS_BACKEND
    readiness_gate: dict[str, Any] | None = None
    module_name: str = "deepagents"

    def run_subagent(self, *, subagent_profile: str, task: str) -> dict[str, Any]:
        if self.readiness_gate is None:
            raise DeepAgentsBackendDenied(
                "optional_deepagents requires a passing backend readiness gate"
            )
        gate_errors = validate_deepagents_backend_readiness_gate(self.readiness_gate)
        if gate_errors or self.readiness_gate.get("gate_state") != "PASS":
            raise DeepAgentsBackendDenied(
                "optional_deepagents readiness gate is not passing; create a fresh "
                "builder-deepagents backend-readiness artifact"
            )
        try:
            module = importlib.import_module(self.module_name)
        except ModuleNotFoundError as exc:
            raise DeepAgentsBackendDenied(
                "optional_deepagents dependency is unavailable at runtime"
            ) from exc
        runner = getattr(module, OPTIONAL_DEEPAGENTS_RUNNER_EXPORT, None)
        if not callable(runner):
            raise DeepAgentsBackendDenied(
                f"optional_deepagents is missing {OPTIONAL_DEEPAGENTS_RUNNER_EXPORT}"
            )
        try:
            payload = runner(subagent_profile=subagent_profile, task=task)
        except TimeoutError as exc:
            raise DeepAgentsBackendDenied(
                "optional_deepagents protocol runner timed out"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError("optional_deepagents protocol runner must return a JSON object")
        result = dict(payload)
        result_errors = _validate_backend_result_payload(
            result,
            expected_subagent_profile=subagent_profile,
        )
        if result_errors:
            raise ValueError("malformed optional_deepagents result: " + "; ".join(result_errors))
        return result


def backend_for(mode: str, *, readiness_gate: dict[str, Any] | None = None) -> DeepAgentsBackend:
    if mode == PROTOCOL_FAKE_BACKEND:
        return ProtocolFakeBackend()
    if mode == OPTIONAL_DEEPAGENTS_BACKEND:
        return OptionalDeepAgentsBackend(readiness_gate=readiness_gate)
    raise ValueError(f"unknown deepagents backend: {mode}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _digest_jsonable(value: dict[str, Any]) -> str:
    payload = _strip_digest_keys(value)
    raw = json_lib.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _strip_digest_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_digest_keys(item)
            for key, item in value.items()
            if key not in _DIGEST_KEYS
        }
    if isinstance(value, list):
        return [_strip_digest_keys(item) for item in value]
    return value


def _attach_digest(data: dict[str, Any], key: str) -> dict[str, Any]:
    payload = dict(data)
    payload[key] = _digest_jsonable(payload)
    return payload


def _result_schema_digest(value: dict[str, Any]) -> str:
    schema = {
        "fields": sorted(value),
        "types": {key: type(value[key]).__name__ for key in sorted(value)},
    }
    raw = json_lib.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _expected_optional_result_schema_digest() -> str:
    expected = {
        "fields": sorted(OPTIONAL_BACKEND_RESULT_SCHEMA_FIELDS),
        "types": {
            "calls_mcp": "bool",
            "calls_models": "bool",
            "calls_tools": "bool",
            "constructs_deepagents": "bool",
            "executes_shell": "bool",
            "mutates_memory": "bool",
            "result_digest": "str",
            "result_mode": "str",
            "subagent_profile": "str",
            "summary": "str",
            "writes_source": "bool",
        },
    }
    raw = json_lib.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_backend_result_payload(
    payload: Any, *, expected_subagent_profile: str | None = None
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["backend result must be a JSON object"]
    missing = [field for field in OPTIONAL_BACKEND_RESULT_SCHEMA_FIELDS if field not in payload]
    if missing:
        errors.append("backend result missing fields: " + ", ".join(missing))
    extra = [field for field in payload if field not in OPTIONAL_BACKEND_RESULT_SCHEMA_FIELDS]
    if extra:
        errors.append("backend result has unexpected fields: " + ", ".join(sorted(extra)))
    if expected_subagent_profile is not None and payload.get("subagent_profile") != expected_subagent_profile:
        errors.append("backend result subagent_profile must match scheduled subagent")
    if not isinstance(payload.get("subagent_profile"), str) or not payload.get("subagent_profile"):
        errors.append("backend result subagent_profile must be a non-empty string")
    if payload.get("result_mode") != "PROPOSAL_ONLY":
        errors.append("backend result result_mode must be PROPOSAL_ONLY")
    if not isinstance(payload.get("summary"), str) or not payload.get("summary"):
        errors.append("backend result summary must be a non-empty string")
    for field in OPTIONAL_BACKEND_RESULT_FALSE_FIELDS:
        if payload.get(field) is not False:
            errors.append(f"backend result {field} must be false")
    if not _is_sha256(payload.get("result_digest")):
        errors.append("backend result result_digest must be a SHA-256 hex digest")
    elif payload.get("result_digest") != _digest_jsonable(payload):
        errors.append("backend result result_digest does not match canonical payload")
    if _result_schema_digest(payload) != _expected_optional_result_schema_digest():
        errors.append("backend result schema digest does not match expected optional_deepagents shape")
    return errors


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in _SHA256_HEX for char in value.lower())
    )


def _artifact_ref(
    artifact: dict[str, Any],
    *,
    role: str,
    path: Path | str | None,
    name: str = "",
) -> dict[str, Any]:
    """Create a digest ref; path is empty only for in-memory/stdout artifacts."""
    return {
        "role": role,
        "kind": str(artifact.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": _digest_jsonable(artifact),
        "name": name,
        "required": True,
    }


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _write_json(artifact: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _string_list(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        if item in seen:
            errors.append(f"{field}[{index}] must be unique")
        seen.add(item)
    return errors


def _ref_errors(ref: Any, *, field: str, kind: str | None = None, role: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(ref, dict):
        return [f"{field} must be an object"]
    if role is not None and ref.get("role") != role:
        errors.append(f"{field}.role must be {role}")
    if kind is not None and ref.get("kind") != kind:
        errors.append(f"{field}.kind must be {kind}")
    if not isinstance(ref.get("path"), str):
        errors.append(f"{field}.path must be a string")
    if not _is_sha256(ref.get("sha256")):
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    if ref.get("required") is not True:
        errors.append(f"{field}.required must be true")
    if not isinstance(ref.get("name", ""), str):
        errors.append(f"{field}.name must be a string")
    return errors


def _package_version(package_name: str, module: Any | None = None) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        version = getattr(module, "__version__", "") if module is not None else ""
        return version if isinstance(version, str) else ""


def _capability_gate_records(*, passed: bool) -> list[dict[str, Any]]:
    state = "PASS" if passed else "FAIL"
    return [
        {
            "gate": gate,
            "state": state,
            "evidence": "operator asserted issue #195 promotion surface is covered" if passed else "not asserted",
        }
        for gate in CAPABILITY_PROMOTION_GATE_NAMES
    ]


def _denial_probe_records(module: Any | None) -> list[dict[str, Any]]:
    raw = getattr(module, "BUILDER_II_DENIAL_PROBES", {}) if module is not None else {}
    probes = raw if isinstance(raw, dict) else {}
    records: list[dict[str, Any]] = []
    for capability in OPTIONAL_DENIAL_PROBE_CAPABILITIES:
        state = probes.get(capability, "UNKNOWN")
        records.append(
            {
                "capability": capability,
                "state": state,
                "event_type": "action_denied",
                "records_runtime_event": state == "DENIED",
            }
        )
    return records


def _readiness_gate_errors(gate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    protocol = gate.get("protocol_compatibility", {})
    contract = gate.get("contract_tests", {})
    schema = gate.get("schema_drift_detection", {})
    partial = gate.get("partial_failure_fixtures", {})
    model = gate.get("model_gateway_routing", {})
    replay = gate.get("replay_proof", {})
    if protocol.get("version_compatible") is not True:
        errors.append("protocol version is not compatible")
    if protocol.get("factory_export_present") is not True:
        errors.append(f"{OPTIONAL_DEEPAGENTS_FACTORY_EXPORT} export is missing")
    if protocol.get("protocol_runner_export_present") is not True:
        errors.append(f"{OPTIONAL_DEEPAGENTS_RUNNER_EXPORT} export is missing")
    for key in ("backend_protocol_bound", "deterministic_shape", "proposal_only_payload"):
        if contract.get(key) is not True:
            errors.append(f"contract_tests.{key} must be true")
    if schema.get("stable") is not True:
        errors.append("schema drift detector is not stable")
    for probe in gate.get("denial_probes", []):
        if not isinstance(probe, dict) or probe.get("state") != "DENIED":
            errors.append("all denial probes must be DENIED")
            break
        if probe.get("event_type") != "action_denied" or probe.get("records_runtime_event") is not True:
            errors.append("all denial probes must record action_denied runtime events")
            break
    for key in (
        "interrupted_run_failed_receipt",
        "malformed_result_capped_or_rejected",
        "timeout_or_dependency_absence_backend_denied",
    ):
        if partial.get(key) is not True:
            errors.append(f"partial_failure_fixtures.{key} must be true")
    if model.get("builder_ii_model_gateway_required") is not True:
        errors.append("model gateway routing must require builder-II model gateway")
    if model.get("native_deepagents_model_invocation") != "DENIED":
        errors.append("native deepagents model invocation must be DENIED")
    if model.get("model_work_expected") is True and not model.get("model_call_receipt_refs"):
        errors.append("model_call_receipt_refs must be populated when backend performs model work")
    if replay.get("replay_run_required") is not True or replay.get("replay_executes_runtime") is not False:
        errors.append("replay proof must reconstruct without runtime execution")
    for record in gate.get("capability_promotion_gates", []):
        if not isinstance(record, dict) or record.get("state") != "PASS":
            errors.append("all capability promotion gates must be PASS")
            break
    return errors


def create_deepagents_backend_readiness_gate(
    *,
    module_name: str = "deepagents",
    package_name: str = "deepagents",
    capability_gates_passed: bool = False,
    model_call_receipt_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    module: Any | None = None
    import_error = ""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        import_error = f"{type(exc).__name__}: {exc}"

    observed_version = _package_version(package_name, module)
    observed_protocol_version = (
        getattr(module, OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION_EXPORT, "") if module is not None else ""
    )
    factory = getattr(module, OPTIONAL_DEEPAGENTS_FACTORY_EXPORT, None) if module is not None else None
    runner = getattr(module, OPTIONAL_DEEPAGENTS_RUNNER_EXPORT, None) if module is not None else None
    backend = backend_for(OPTIONAL_DEEPAGENTS_BACKEND)
    backend_protocol_bound = isinstance(backend, DeepAgentsBackend)

    first_result: dict[str, Any] | None = None
    second_result: dict[str, Any] | None = None
    contract_errors: list[str] = []
    if callable(runner):
        try:
            first_raw = runner(
                subagent_profile="readiness_probe",
                task="builder-II optional_deepagents readiness probe",
            )
            second_raw = runner(
                subagent_profile="readiness_probe",
                task="builder-II optional_deepagents readiness probe",
            )
            if isinstance(first_raw, dict):
                first_result = dict(first_raw)
            if isinstance(second_raw, dict):
                second_result = dict(second_raw)
            contract_errors.extend(
                _validate_backend_result_payload(
                    first_result,
                    expected_subagent_profile="readiness_probe",
                )
                if first_result is not None
                else ["first contract probe did not return a JSON object"]
            )
            contract_errors.extend(
                _validate_backend_result_payload(
                    second_result,
                    expected_subagent_profile="readiness_probe",
                )
                if second_result is not None
                else ["second contract probe did not return a JSON object"]
            )
        except Exception as exc:
            contract_errors.append(f"contract probe failed: {type(exc).__name__}: {exc}")
    else:
        contract_errors.append(f"{OPTIONAL_DEEPAGENTS_RUNNER_EXPORT} is not callable")
    contract_errors = list(dict.fromkeys(contract_errors))

    first_schema = _result_schema_digest(first_result) if first_result is not None else ""
    second_schema = _result_schema_digest(second_result) if second_result is not None else ""
    expected_schema = _expected_optional_result_schema_digest()
    deterministic_shape = bool(first_schema and first_schema == second_schema)
    proposal_only = first_result is not None and not _validate_backend_result_payload(
        first_result,
        expected_subagent_profile="readiness_probe",
    )
    model_work_expected = bool(getattr(module, "BUILDER_II_MODEL_WORK_EXPECTED", False)) if module is not None else False

    content = {
        "kind": DEEPAGENTS_BACKEND_READINESS_GATE_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "backend_mode": OPTIONAL_DEEPAGENTS_BACKEND,
        "gate_state": "UNKNOWN",
        "module": {
            "package": package_name,
            "module": module_name,
            "available": module is not None,
            "version": observed_version,
            "import_error": import_error,
        },
        "protocol_compatibility": {
            "required_version": OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION,
            "version_export": OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION_EXPORT,
            "observed_version": observed_protocol_version,
            "version_compatible": observed_protocol_version == OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION,
            "factory_export": OPTIONAL_DEEPAGENTS_FACTORY_EXPORT,
            "factory_export_present": callable(factory),
            "factory_constructed": False,
            "protocol_runner_export": OPTIONAL_DEEPAGENTS_RUNNER_EXPORT,
            "protocol_runner_export_present": callable(runner),
        },
        "contract_tests": {
            "backend_protocol_bound": backend_protocol_bound,
            "deterministic_shape": deterministic_shape,
            "proposal_only_payload": proposal_only,
            "result_schema_fields": list(OPTIONAL_BACKEND_RESULT_SCHEMA_FIELDS),
            "contract_errors": contract_errors,
        },
        "schema_drift_detection": {
            "expected_schema_digest": expected_schema,
            "observed_schema_digest": first_schema,
            "repeat_observed_schema_digest": second_schema,
            "stable": bool(first_schema and first_schema == second_schema == expected_schema),
        },
        "denial_probes": _denial_probe_records(module),
        "partial_failure_fixtures": {
            "interrupted_run_failed_receipt": True,
            "malformed_result_capped_or_rejected": True,
            "timeout_or_dependency_absence_backend_denied": True,
        },
        "model_gateway_routing": {
            "builder_ii_model_gateway_required": True,
            "native_deepagents_model_invocation": "DENIED",
            "model_work_expected": model_work_expected,
            "model_call_receipt_refs": list(model_call_receipt_refs or []),
        },
        "replay_proof": {
            "replay_run_required": True,
            "replay_executes_runtime": False,
        },
        "capability_promotion_gates": _capability_gate_records(passed=capability_gates_passed),
        "denied_capabilities": list(DENIED_CAPABILITIES),
        **_common_authority_fields(protocol_execution=False),
        "authority_boundary": _authority_boundary("deepagents_backend_readiness_gate"),
        "governance": _base_governance("deepagents_backend_readiness_gate"),
        "summary": {
            "passed": False,
            "errors": [],
            "next_valid_command": "builder-deepagents execution-candidate --backend-mode optional_deepagents --backend-readiness-gate <gate.json>",
        },
    }
    errors = _readiness_gate_errors(content)
    content["gate_state"] = "PASS" if not errors else "FAIL"
    content["summary"] = {
        "passed": not errors,
        "errors": errors,
        "next_valid_command": (
            "builder-deepagents execution-candidate --backend-mode optional_deepagents "
            "--backend-readiness-gate <gate.json>"
            if not errors
            else "Fix readiness errors, rerun builder-deepagents backend-readiness, then create the candidate."
        ),
    }
    gate = _attach_digest(content, "readiness_gate_digest")
    gate_errors = validate_deepagents_backend_readiness_gate(gate)
    if gate_errors:
        raise ValueError("created invalid deepagents backend readiness gate: " + "; ".join(gate_errors))
    return gate


def _target_from_plan(work_plan: dict[str, Any]) -> str:
    target = work_plan.get("target")
    return target if isinstance(target, str) else "builder"


def _subagents_from_plan(work_plan: dict[str, Any]) -> list[str]:
    values = work_plan.get("proposed_subagents")
    if isinstance(values, list) and values:
        return [str(item) for item in values if isinstance(item, str) and item.strip()]
    return ["planning_delegate"]


def _base_governance(capability_state: str, *, protocol_execution: bool = False) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "ENABLED_UNDER_APPROVED_PROTOCOL" if protocol_execution else "DISABLED",
        "protocol_backend_execution": "ENABLED_UNDER_APPROVED_PROTOCOL" if protocol_execution else "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "git_mutation": "DISABLED",
        "commit_push": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_construction": "DISABLED",
        "native_deepagents_model_invocation": "DISABLED",
        "mcp_tool_calls": "DISABLED",
        "memory_mutation": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }


_AUTHORITY_FALSE_FIELDS = (
    "executes_model",
    "executes_tools",
    "executes_shell",
    "invokes_goose",
    "constructs_deepagents",
    "constructs_subagents",
    "invokes_mcp",
    "performs_network_calls",
    "mutates_target_repo",
    "mutates_memory",
    "grants_authority",
    "artifact_is_authority",
)

_GOVERNANCE_DISABLED_FIELDS = (
    "model_execution",
    "shell_execution",
    "target_repo_writes",
    "git_mutation",
    "commit_push",
    "goose_runtime_start",
    "deepagents_construction",
    "native_deepagents_model_invocation",
    "mcp_tool_calls",
    "memory_mutation",
)


def _authority_boundary(capability_state: str, *, protocol_execution: bool = False) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runs_protocol_backend": protocol_execution,
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
    }


def _common_authority_fields(*, protocol_execution: bool = False) -> dict[str, Any]:
    return {
        "runs_protocol_backend": protocol_execution,
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
    }


def _validate_common_authority(
    data: dict[str, Any], *, capability_state: str, protocol_execution: bool
) -> list[str]:
    errors: list[str] = []
    if data.get("runs_protocol_backend") is not protocol_execution:
        errors.append(f"runs_protocol_backend must be {protocol_execution}")
    for key in _AUTHORITY_FALSE_FIELDS:
        if data.get(key) is not False:
            errors.append(f"{key} must be false")
    if data.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")
    boundary = data.get("authority_boundary")
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
    else:
        if boundary.get("capability_state") != capability_state:
            errors.append(f"authority_boundary.capability_state must be {capability_state}")
        if boundary.get("runs_protocol_backend") is not protocol_execution:
            errors.append(f"authority_boundary.runs_protocol_backend must be {protocol_execution}")
        for key in _AUTHORITY_FALSE_FIELDS:
            if boundary.get(key) is not False:
                errors.append(f"authority_boundary.{key} must be false")
        if boundary.get("requires_human_promotion_for_execution") is not True:
            errors.append("authority_boundary.requires_human_promotion_for_execution must be true")
    errors.extend(
        _validate_governance(
            data.get("governance"),
            capability_state=capability_state,
            protocol_execution=protocol_execution,
        )
    )
    return errors


def _validate_governance(
    governance: Any, *, capability_state: str, protocol_execution: bool
) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != capability_state:
        errors.append(f"governance.capability_state must be {capability_state}")
    expected_protocol = "ENABLED_UNDER_APPROVED_PROTOCOL" if protocol_execution else "DISABLED"
    if governance.get("runtime_execution") != expected_protocol:
        errors.append(f"governance.runtime_execution must be {expected_protocol}")
    if governance.get("protocol_backend_execution") != expected_protocol:
        errors.append(f"governance.protocol_backend_execution must be {expected_protocol}")
    for key in _GOVERNANCE_DISABLED_FIELDS:
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "grants_runtime_authority", "grants_action_authority"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def create_deepagents_execution_candidate(
    *,
    work_plan: dict[str, Any],
    work_plan_path: Path | None,
    output_root: Path,
    backend_mode: str = PROTOCOL_FAKE_BACKEND,
    backend_readiness_gate: dict[str, Any] | None = None,
    backend_readiness_gate_path: Path | None = None,
    allowed_subagents: list[str] | None = None,
    max_subagents: int = 8,
    max_events: int = 256,
    max_output_bytes: int = 65536,
) -> dict[str, Any]:
    errors = validate_deepagents_work_plan(work_plan)
    if errors:
        raise ValueError("invalid deepagents work plan: " + "; ".join(errors))
    if backend_mode not in BACKEND_MODES:
        raise ValueError(f"backend_mode must be one of: {', '.join(BACKEND_MODES)}")
    subagents = list(allowed_subagents or _subagents_from_plan(work_plan))
    if not subagents:
        raise ValueError("allowed_subagents must contain at least one item")
    if max_subagents <= 0 or max_events <= 0 or max_output_bytes <= 0:
        raise ValueError("max_subagents, max_events, and max_output_bytes must be positive")
    if len(subagents) > max_subagents:
        raise ValueError("allowed_subagents exceeds max_subagents budget")
    model_call_receipt_refs: list[dict[str, Any]] = []
    backend_readiness_ref: dict[str, Any] | None = None
    backend_readiness_summary: dict[str, Any] | None = None
    if backend_mode == OPTIONAL_DEEPAGENTS_BACKEND:
        if backend_readiness_gate is None:
            raise ValueError(
                "optional_deepagents requires --backend-readiness-gate; run "
                "builder-deepagents backend-readiness first"
            )
        gate_errors = validate_deepagents_backend_readiness_gate(backend_readiness_gate)
        if gate_errors or backend_readiness_gate.get("gate_state") != "PASS":
            details = "; ".join(gate_errors or backend_readiness_gate.get("summary", {}).get("errors", []))
            raise ValueError(
                "optional_deepagents backend readiness gate must PASS before candidate creation"
                + (f": {details}" if details else "")
            )
        backend_readiness_ref = _artifact_ref(
            backend_readiness_gate,
            role="backend_readiness_gate",
            path=backend_readiness_gate_path,
            name="optional_deepagents backend readiness gate",
        )
        routing = backend_readiness_gate.get("model_gateway_routing", {})
        model_call_receipt_refs = list(routing.get("model_call_receipt_refs", [])) if isinstance(routing, dict) else []
        backend_readiness_summary = {
            "gate_state": backend_readiness_gate.get("gate_state"),
            "protocol_version": backend_readiness_gate.get("protocol_compatibility", {}).get("observed_version"),
            "denial_probe_count": len(backend_readiness_gate.get("denial_probes", [])),
            "model_work_expected": routing.get("model_work_expected") if isinstance(routing, dict) else False,
        }
    elif backend_readiness_gate is not None:
        raise ValueError("backend_readiness_gate is only valid for optional_deepagents")

    content = {
        "kind": DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "candidate_state": "CANDIDATE_ONLY",
        "approval_state": "NOT_GRANTED",
        "target": _target_from_plan(work_plan),
        "task": str(work_plan.get("task", "")).strip(),
        "backend_mode": backend_mode,
        "backend_readiness_ref": backend_readiness_ref,
        "backend_readiness_summary": backend_readiness_summary,
        "work_plan_ref": _artifact_ref(work_plan, role="work_plan", path=work_plan_path, name="deepagents work plan"),
        "allowed_subagents": subagents,
        "output_root": str(output_root),
        "budgets": {
            "max_subagents": max_subagents,
            "max_events": max_events,
            "max_output_bytes": max_output_bytes,
        },
        "model_boundary": {
            "builder_ii_model_gateway_required": True,
            "native_deepagents_model_invocation": "DENIED",
            "model_call_receipt_refs": model_call_receipt_refs,
        },
        "denied_capabilities": list(DENIED_CAPABILITIES),
        **_common_authority_fields(protocol_execution=False),
        "authority_boundary": _authority_boundary("deepagents_execution_candidate"),
        "governance": _base_governance("deepagents_execution_candidate"),
    }
    candidate = _attach_digest(content, "candidate_digest")
    candidate_errors = validate_deepagents_execution_candidate(candidate)
    if candidate_errors:
        raise ValueError("created invalid deepagents execution candidate: " + "; ".join(candidate_errors))
    return candidate


def create_deepagents_execution_approval(
    *,
    candidate: dict[str, Any],
    candidate_path: Path | None,
    approval_actor: str,
    approval_reason: str,
    expires_at: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    errors = validate_deepagents_execution_candidate(candidate)
    if errors:
        raise ValueError("invalid deepagents execution candidate: " + "; ".join(errors))
    generated = generated_at or _utc_now()
    candidate_digest = str(candidate.get("candidate_digest", ""))
    content = {
        "kind": DEEPAGENTS_EXECUTION_APPROVAL_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "approval_state": "APPROVED_FOR_RUNNER_ONLY",
        "approval_mode": DEEPAGENTS_APPROVAL_MODE,
        "approved": True,
        "generated_at": generated,
        "expires_at": expires_at,
        "approval_actor": approval_actor.strip(),
        "approval_reason": approval_reason.strip(),
        "candidate_ref": _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate"),
        "candidate_digest": candidate_digest,
        "approved_backend_mode": candidate.get("backend_mode"),
        "approved_subagents": list(candidate.get("allowed_subagents", [])),
        "approval_statement": (
            "Approval binds only to the exact deepagents execution candidate digest "
            f"{candidate_digest}; only builder-deepagents run-approved may execute the bounded protocol lane."
        ),
        "approval_enables_direct_deepagents": False,
        **_common_authority_fields(protocol_execution=False),
        "authority_boundary": _authority_boundary("deepagents_execution_approval"),
        "governance": _base_governance("deepagents_execution_approval"),
    }
    approval = _attach_digest(content, "approval_digest")
    approval_errors = validate_deepagents_execution_approval_against_candidate(approval, candidate)
    if approval_errors:
        raise ValueError("created invalid deepagents execution approval: " + "; ".join(approval_errors))
    return approval


def create_deepagents_event_record(
    *,
    session_id: str,
    sequence: int,
    event_type: str,
    subject_refs: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
    previous_event_ref: dict[str, Any] | None = None,
    message: str = "",
) -> dict[str, Any]:
    payload_obj = dict(payload or {})
    content = {
        "kind": DEEPAGENTS_EVENT_RECORD_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "event_state": "RECORDED_ONLY",
        "session_id": session_id,
        "sequence": sequence,
        "event_type": event_type,
        "recorded_at": _utc_now(),
        "message": message.strip(),
        "payload": payload_obj,
        "payload_sha256": _digest_jsonable(payload_obj),
        "subject_refs": list(subject_refs),
        "previous_event_ref": previous_event_ref,
        "previous_event_sha256": previous_event_ref.get("sha256") if isinstance(previous_event_ref, dict) else None,
        **_common_authority_fields(protocol_execution=True),
        "authority_boundary": _authority_boundary("deepagents_event_record", protocol_execution=True),
        "governance": _base_governance("deepagents_event_record", protocol_execution=True),
    }
    event = _attach_digest(content, "event_digest")
    event_errors = validate_deepagents_event_record(event)
    if event_errors:
        raise ValueError("created invalid deepagents event record: " + "; ".join(event_errors))
    return event


def create_deepagents_checkpoint(
    *,
    session_id: str,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    candidate_path: Path,
    approval_path: Path,
    event_tail_ref: dict[str, Any],
    completed_subagents: list[str],
    remaining_subagents: list[str],
    events_dir: Path,
) -> dict[str, Any]:
    content = {
        "kind": DEEPAGENTS_CHECKPOINT_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "checkpoint_state": "INTERRUPT_RECORDED",
        "session_id": session_id,
        "candidate_ref": _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate"),
        "approval_ref": _artifact_ref(approval, role="approval", path=approval_path, name="deepagents execution approval"),
        "event_tail_ref": event_tail_ref,
        "events_dir": str(events_dir),
        "completed_subagents": list(completed_subagents),
        "remaining_subagents": list(remaining_subagents),
        "resume_command": "builder-deepagents resume-approved --candidate <candidate> --approval <approval> --checkpoint <checkpoint> --output-dir <output-dir>",
        **_common_authority_fields(protocol_execution=True),
        "authority_boundary": _authority_boundary("deepagents_checkpoint", protocol_execution=True),
        "governance": _base_governance("deepagents_checkpoint", protocol_execution=True),
    }
    checkpoint = _attach_digest(content, "checkpoint_digest")
    checkpoint_errors = validate_deepagents_checkpoint(checkpoint)
    if checkpoint_errors:
        raise ValueError("created invalid deepagents checkpoint: " + "; ".join(checkpoint_errors))
    return checkpoint


def create_deepagents_replay_report(
    *,
    session_id: str,
    event_records: list[tuple[dict[str, Any], Path]],
) -> dict[str, Any]:
    ordered = sorted(event_records, key=lambda item: int(item[0].get("sequence", 10**9)))
    errors: list[str] = []
    completed: list[str] = []
    scheduled: list[str] = []
    denied: list[str] = []
    status = "RUNNING"
    previous_ref: dict[str, Any] | None = None
    expected_sequence = 1

    for event, path in ordered:
        for error in validate_deepagents_event_record(event):
            errors.append(f"{path}: {error}")
        if event.get("session_id") != session_id:
            errors.append(f"{path}: session_id does not match replay session")
        if event.get("sequence") != expected_sequence:
            errors.append(f"{path}: sequence must be {expected_sequence}")
        if expected_sequence > 1:
            if event.get("previous_event_sha256") != (previous_ref or {}).get("sha256"):
                errors.append(f"{path}: previous_event_sha256 does not match prior event")
        expected_sequence += 1
        previous_ref = _artifact_ref(event, role="event", path=path, name=str(event.get("event_type", "")))

        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_type = event.get("event_type")
        if event_type == "subagent_scheduled":
            profile = payload.get("subagent_profile")
            if isinstance(profile, str) and profile not in scheduled:
                scheduled.append(profile)
        elif event_type == "subagent_result_recorded":
            profile = payload.get("subagent_profile")
            if isinstance(profile, str) and profile not in completed:
                completed.append(profile)
        elif event_type == "action_denied":
            capability = payload.get("denied_capability")
            if isinstance(capability, str):
                denied.append(capability)
        elif event_type == "checkpoint_recorded":
            status = "CHECKPOINTED"
        elif event_type == "run_completed":
            status = "COMPLETED"
        elif event_type == "run_failed":
            status = "FAILED"

    event_refs = [
        _artifact_ref(event, role="event", path=path, name=str(event.get("event_type", "")))
        for event, path in ordered
    ]
    content = {
        "kind": DEEPAGENTS_REPLAY_REPORT_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "replay_state": "RECONSTRUCTED_FROM_EVENTS_ONLY",
        "session_id": session_id,
        "status": "INVALID" if errors else status,
        "valid": errors == [],
        "event_count": len(event_refs),
        "completed_subagents": completed,
        "scheduled_subagents": scheduled,
        "denied_capabilities": denied,
        "event_refs": event_refs,
        "last_event_ref": event_refs[-1] if event_refs else None,
        "errors": errors,
        "warnings": [],
        "replay_executes_runtime": False,
        **_common_authority_fields(protocol_execution=False),
        "authority_boundary": _authority_boundary("deepagents_replay_report"),
        "governance": _base_governance("deepagents_replay_report"),
    }
    replay = _attach_digest(content, "replay_digest")
    replay_errors = validate_deepagents_replay_report(replay)
    if replay_errors:
        raise ValueError("created invalid deepagents replay report: " + "; ".join(replay_errors))
    return replay


def create_deepagents_event_ledger(
    *,
    session_id: str,
    event_records: list[tuple[dict[str, Any], Path]],
    replay_report: dict[str, Any],
    replay_report_path: Path,
) -> dict[str, Any]:
    event_refs = [
        _artifact_ref(event, role="event", path=path, name=str(event.get("event_type", "")))
        for event, path in sorted(event_records, key=lambda item: int(item[0].get("sequence", 10**9)))
    ]
    content = {
        "kind": DEEPAGENTS_EVENT_LEDGER_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "ledger_state": "HASH_CHAIN_RECORDED",
        "session_id": session_id,
        "event_count": len(event_refs),
        "event_refs": event_refs,
        "last_event_ref": event_refs[-1] if event_refs else None,
        "replay_report_ref": _artifact_ref(replay_report, role="replay_report", path=replay_report_path, name="deepagents replay report"),
        "reconstructed_status": {
            "valid": replay_report.get("valid", False),
            "status": replay_report.get("status", ""),
            "completed_subagents": replay_report.get("completed_subagents", []),
        },
        **_common_authority_fields(protocol_execution=False),
        "authority_boundary": _authority_boundary("deepagents_event_ledger"),
        "governance": _base_governance("deepagents_event_ledger"),
    }
    ledger = _attach_digest(content, "ledger_digest")
    ledger_errors = validate_deepagents_event_ledger(ledger)
    if ledger_errors:
        raise ValueError("created invalid deepagents event ledger: " + "; ".join(ledger_errors))
    return ledger


def create_deepagents_run_envelope(
    *,
    session_id: str,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    candidate_path: Path,
    approval_path: Path,
    event_ledger: dict[str, Any],
    event_ledger_path: Path,
    replay_report: dict[str, Any],
    replay_report_path: Path,
    checkpoint: dict[str, Any] | None,
    checkpoint_path: Path | None,
    output_dir: Path,
    status: str,
) -> dict[str, Any]:
    content = {
        "kind": DEEPAGENTS_RUN_ENVELOPE_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "envelope_state": status,
        "session_id": session_id,
        "backend_mode": candidate.get("backend_mode"),
        "output_dir": str(output_dir),
        "candidate_ref": _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate"),
        "approval_ref": _artifact_ref(approval, role="approval", path=approval_path, name="deepagents execution approval"),
        "event_ledger_ref": _artifact_ref(event_ledger, role="event_ledger", path=event_ledger_path, name="deepagents event ledger"),
        "replay_report_ref": _artifact_ref(replay_report, role="replay_report", path=replay_report_path, name="deepagents replay report"),
        "checkpoint_ref": _artifact_ref(checkpoint, role="checkpoint", path=checkpoint_path, name="deepagents checkpoint") if checkpoint is not None else None,
        **_common_authority_fields(protocol_execution=True),
        "authority_boundary": _authority_boundary("deepagents_run_envelope", protocol_execution=True),
        "governance": _base_governance("deepagents_run_envelope", protocol_execution=True),
    }
    envelope = _attach_digest(content, "envelope_digest")
    envelope_errors = validate_deepagents_run_envelope(envelope)
    if envelope_errors:
        raise ValueError("created invalid deepagents run envelope: " + "; ".join(envelope_errors))
    return envelope


def create_deepagents_execution_receipt(
    *,
    session_id: str,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    envelope: dict[str, Any],
    replay_report: dict[str, Any],
    event_ledger: dict[str, Any],
    candidate_path: Path,
    approval_path: Path,
    envelope_path: Path,
    replay_report_path: Path,
    event_ledger_path: Path,
    checkpoint: dict[str, Any] | None,
    checkpoint_path: Path | None,
    status: str,
) -> dict[str, Any]:
    content = {
        "kind": DEEPAGENTS_EXECUTION_RECEIPT_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "receipt_state": status,
        "session_id": session_id,
        "backend_mode": candidate.get("backend_mode"),
        "candidate_ref": _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate"),
        "approval_ref": _artifact_ref(approval, role="approval", path=approval_path, name="deepagents execution approval"),
        "envelope_ref": _artifact_ref(envelope, role="run_envelope", path=envelope_path, name="deepagents run envelope"),
        "event_ledger_ref": _artifact_ref(event_ledger, role="event_ledger", path=event_ledger_path, name="deepagents event ledger"),
        "replay_report_ref": _artifact_ref(replay_report, role="replay_report", path=replay_report_path, name="deepagents replay report"),
        "checkpoint_ref": _artifact_ref(checkpoint, role="checkpoint", path=checkpoint_path, name="deepagents checkpoint") if checkpoint is not None else None,
        "completed_subagents": list(replay_report.get("completed_subagents", [])),
        "denied_capabilities": list(replay_report.get("denied_capabilities", [])),
        "no_mutation_proof": "protocol backend writes only explicit deepagents artifact outputs",
        "rollback_path": "discard emitted deepagents artifact output directory; target repository mutation is not possible in this lane",
        "verification_path": "builder-deepagents replay-run followed by builder-deepagents evidence-bundle",
        **_common_authority_fields(protocol_execution=True),
        "authority_boundary": _authority_boundary("deepagents_execution_receipt", protocol_execution=True),
        "governance": _base_governance("deepagents_execution_receipt", protocol_execution=True),
    }
    receipt = _attach_digest(content, "receipt_digest")
    receipt_errors = validate_deepagents_execution_receipt(receipt)
    if receipt_errors:
        raise ValueError("created invalid deepagents execution receipt: " + "; ".join(receipt_errors))
    return receipt


def create_deepagents_evidence_bundle(
    *,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    envelope: dict[str, Any],
    receipt: dict[str, Any],
    event_ledger: dict[str, Any],
    replay_report: dict[str, Any],
    candidate_path: Path,
    approval_path: Path,
    envelope_path: Path,
    receipt_path: Path,
    event_ledger_path: Path,
    replay_report_path: Path,
    checkpoint: dict[str, Any] | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    content = {
        "kind": DEEPAGENTS_EVIDENCE_BUNDLE_KIND,
        "schema_version": DEEPAGENTS_EXECUTION_SCHEMA_VERSION,
        "bundle_state": "EVIDENCE_ONLY",
        "status": receipt.get("receipt_state"),
        "candidate_ref": _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate"),
        "approval_ref": _artifact_ref(approval, role="approval", path=approval_path, name="deepagents execution approval"),
        "envelope_ref": _artifact_ref(envelope, role="run_envelope", path=envelope_path, name="deepagents run envelope"),
        "receipt_ref": _artifact_ref(receipt, role="receipt", path=receipt_path, name="deepagents execution receipt"),
        "event_ledger_ref": _artifact_ref(event_ledger, role="event_ledger", path=event_ledger_path, name="deepagents event ledger"),
        "replay_report_ref": _artifact_ref(replay_report, role="replay_report", path=replay_report_path, name="deepagents replay report"),
        "checkpoint_ref": _artifact_ref(checkpoint, role="checkpoint", path=checkpoint_path, name="deepagents checkpoint") if checkpoint is not None else None,
        "operator_summary": {
            "path": "candidate -> approval -> run-approved -> replay-run -> evidence-bundle",
            "completed_subagents": replay_report.get("completed_subagents", []),
            "target_mutation": "none",
        },
        **_common_authority_fields(protocol_execution=False),
        "authority_boundary": _authority_boundary("deepagents_evidence_bundle"),
        "governance": _base_governance("deepagents_evidence_bundle"),
    }
    bundle = _attach_digest(content, "evidence_bundle_digest")
    bundle_errors = validate_deepagents_evidence_bundle(bundle)
    if bundle_errors:
        raise ValueError("created invalid deepagents evidence bundle: " + "; ".join(bundle_errors))
    return bundle


def validate_deepagents_execution_candidate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents execution candidate must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_EXECUTION_CANDIDATE_KIND:
        errors.append(f"kind must be {DEEPAGENTS_EXECUTION_CANDIDATE_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("candidate_state") != "CANDIDATE_ONLY":
        errors.append("candidate_state must be CANDIDATE_ONLY")
    if data.get("approval_state") != "NOT_GRANTED":
        errors.append("approval_state must be NOT_GRANTED")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")
    if not isinstance(data.get("task"), str) or not data.get("task"):
        errors.append("task must be a non-empty string")
    if data.get("backend_mode") not in BACKEND_MODES:
        errors.append(f"backend_mode must be one of: {', '.join(BACKEND_MODES)}")
    if data.get("backend_mode") == OPTIONAL_DEEPAGENTS_BACKEND:
        errors.extend(
            _ref_errors(
                data.get("backend_readiness_ref"),
                field="backend_readiness_ref",
                kind=DEEPAGENTS_BACKEND_READINESS_GATE_KIND,
                role="backend_readiness_gate",
            )
        )
        summary = data.get("backend_readiness_summary")
        if not isinstance(summary, dict):
            errors.append("backend_readiness_summary must be an object for optional_deepagents")
        else:
            if summary.get("gate_state") != "PASS":
                errors.append("backend_readiness_summary.gate_state must be PASS")
            if summary.get("protocol_version") != OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION:
                errors.append(
                    f"backend_readiness_summary.protocol_version must be {OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION}"
                )
            if not isinstance(summary.get("denial_probe_count"), int) or summary["denial_probe_count"] < len(OPTIONAL_DENIAL_PROBE_CAPABILITIES):
                errors.append("backend_readiness_summary.denial_probe_count must cover all denial probes")
            if not isinstance(summary.get("model_work_expected"), bool):
                errors.append("backend_readiness_summary.model_work_expected must be a boolean")
    else:
        if data.get("backend_readiness_ref") is not None:
            errors.append("backend_readiness_ref must be null unless backend_mode is optional_deepagents")
        if data.get("backend_readiness_summary") is not None:
            errors.append("backend_readiness_summary must be null unless backend_mode is optional_deepagents")
    errors.extend(_ref_errors(data.get("work_plan_ref"), field="work_plan_ref", kind=DEEPAGENTS_WORK_PLAN_KIND, role="work_plan"))
    errors.extend(_string_list(data.get("allowed_subagents"), field="allowed_subagents", allow_empty=False))
    if not isinstance(data.get("output_root"), str) or not data.get("output_root"):
        errors.append("output_root must be a non-empty string")
    budgets = data.get("budgets")
    if not isinstance(budgets, dict):
        errors.append("budgets must be an object")
    else:
        for key in ("max_subagents", "max_events", "max_output_bytes"):
            if not isinstance(budgets.get(key), int) or budgets[key] <= 0:
                errors.append(f"budgets.{key} must be a positive integer")
        if isinstance(data.get("allowed_subagents"), list) and isinstance(budgets.get("max_subagents"), int):
            if len(data["allowed_subagents"]) > budgets["max_subagents"]:
                errors.append("allowed_subagents must not exceed budgets.max_subagents")
    model_boundary = data.get("model_boundary")
    if not isinstance(model_boundary, dict):
        errors.append("model_boundary must be an object")
    else:
        if model_boundary.get("builder_ii_model_gateway_required") is not True:
            errors.append("model_boundary.builder_ii_model_gateway_required must be true")
        if model_boundary.get("native_deepagents_model_invocation") != "DENIED":
            errors.append("model_boundary.native_deepagents_model_invocation must be DENIED")
        if not isinstance(model_boundary.get("model_call_receipt_refs"), list):
            errors.append("model_boundary.model_call_receipt_refs must be a list")
        else:
            for index, ref in enumerate(model_boundary["model_call_receipt_refs"]):
                errors.extend(_ref_errors(ref, field=f"model_boundary.model_call_receipt_refs[{index}]"))
        summary = data.get("backend_readiness_summary")
        if isinstance(summary, dict) and summary.get("model_work_expected") is True:
            if not model_boundary.get("model_call_receipt_refs"):
                errors.append("model_boundary.model_call_receipt_refs must be populated when optional backend performs model work")
    denied = data.get("denied_capabilities")
    if not isinstance(denied, list):
        errors.append("denied_capabilities must be a list")
    else:
        for capability in DENIED_CAPABILITIES:
            if capability not in denied:
                errors.append(f"denied_capabilities must include {capability}")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_execution_candidate",
            protocol_execution=False,
        )
    )
    if data.get("candidate_digest") != _digest_jsonable(data):
        errors.append("candidate_digest does not match canonical candidate payload")
    return errors


def validate_deepagents_execution_approval(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents execution approval must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_EXECUTION_APPROVAL_KIND:
        errors.append(f"kind must be {DEEPAGENTS_EXECUTION_APPROVAL_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("approval_state") != "APPROVED_FOR_RUNNER_ONLY":
        errors.append("approval_state must be APPROVED_FOR_RUNNER_ONLY")
    if data.get("approval_mode") != DEEPAGENTS_APPROVAL_MODE:
        errors.append(f"approval_mode must be {DEEPAGENTS_APPROVAL_MODE}")
    if data.get("approved") is not True:
        errors.append("approved must be true")
    for field in ("generated_at", "approval_actor", "approval_reason", "approval_statement"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    if data.get("expires_at") is not None:
        if not isinstance(data.get("expires_at"), str) or _parse_time(data["expires_at"]) is None:
            errors.append("expires_at must be an ISO timestamp or null")
    errors.extend(_ref_errors(data.get("candidate_ref"), field="candidate_ref", kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND, role="candidate"))
    if not _is_sha256(data.get("candidate_digest")):
        errors.append("candidate_digest must be a SHA-256 hex digest")
    if data.get("approved_backend_mode") not in BACKEND_MODES:
        errors.append(f"approved_backend_mode must be one of: {', '.join(BACKEND_MODES)}")
    errors.extend(_string_list(data.get("approved_subagents"), field="approved_subagents", allow_empty=False))
    if data.get("approval_enables_direct_deepagents") is not False:
        errors.append("approval_enables_direct_deepagents must be false")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_execution_approval",
            protocol_execution=False,
        )
    )
    if data.get("approval_digest") != _digest_jsonable(data):
        errors.append("approval_digest does not match canonical approval payload")
    return errors


def validate_deepagents_execution_approval_against_candidate(
    approval: Any, candidate: Any, *, check_expiry: bool = False
) -> list[str]:
    errors = validate_deepagents_execution_approval(approval)
    errors.extend(validate_deepagents_execution_candidate(candidate))
    if not isinstance(approval, dict) or not isinstance(candidate, dict):
        return errors
    candidate_digest = candidate.get("candidate_digest")
    if approval.get("candidate_digest") != candidate_digest:
        errors.append("approval candidate_digest must match candidate.candidate_digest")
    ref = approval.get("candidate_ref")
    if isinstance(ref, dict) and ref.get("sha256") != _digest_jsonable(candidate):
        errors.append("approval candidate_ref.sha256 must match candidate payload")
    if approval.get("approved_backend_mode") != candidate.get("backend_mode"):
        errors.append("approval approved_backend_mode must match candidate backend_mode")
    if approval.get("approved_subagents") != candidate.get("allowed_subagents"):
        errors.append("approval approved_subagents must match candidate allowed_subagents")
    if check_expiry and approval.get("expires_at"):
        expires = _parse_time(str(approval["expires_at"]))
        if expires is None:
            errors.append("approval expires_at is not parseable")
        elif expires <= datetime.now(timezone.utc):
            errors.append("approval has expired")
    return errors


def validate_deepagents_event_record(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents event record must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_EVENT_RECORD_KIND:
        errors.append(f"kind must be {DEEPAGENTS_EVENT_RECORD_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("event_state") != "RECORDED_ONLY":
        errors.append("event_state must be RECORDED_ONLY")
    if not isinstance(data.get("session_id"), str) or not data["session_id"]:
        errors.append("session_id must be a non-empty string")
    if not isinstance(data.get("sequence"), int) or data["sequence"] <= 0:
        errors.append("sequence must be a positive integer")
    if data.get("event_type") not in EVENT_TYPES:
        errors.append(f"event_type must be one of: {', '.join(EVENT_TYPES)}")
    if not isinstance(data.get("recorded_at"), str) or not data["recorded_at"]:
        errors.append("recorded_at must be a non-empty string")
    if not isinstance(data.get("message"), str):
        errors.append("message must be a string")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        errors.append("payload must be an object")
    elif data.get("payload_sha256") != _digest_jsonable(payload):
        errors.append("payload_sha256 does not match payload")
    subject_refs = data.get("subject_refs")
    if not isinstance(subject_refs, list):
        errors.append("subject_refs must be a list")
    else:
        for index, ref in enumerate(subject_refs):
            errors.extend(_ref_errors(ref, field=f"subject_refs[{index}]"))
    previous = data.get("previous_event_ref")
    if previous is not None:
        errors.extend(_ref_errors(previous, field="previous_event_ref", kind=DEEPAGENTS_EVENT_RECORD_KIND, role="event"))
    if data.get("previous_event_sha256") is not None and not _is_sha256(data.get("previous_event_sha256")):
        errors.append("previous_event_sha256 must be a SHA-256 hex digest or null")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_event_record",
            protocol_execution=True,
        )
    )
    if data.get("event_digest") != _digest_jsonable(data):
        errors.append("event_digest does not match canonical event payload")
    return errors


def validate_deepagents_checkpoint(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents checkpoint must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_CHECKPOINT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_CHECKPOINT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("checkpoint_state") != "INTERRUPT_RECORDED":
        errors.append("checkpoint_state must be INTERRUPT_RECORDED")
    if not isinstance(data.get("session_id"), str) or not data["session_id"]:
        errors.append("session_id must be a non-empty string")
    errors.extend(_ref_errors(data.get("candidate_ref"), field="candidate_ref", kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND, role="candidate"))
    errors.extend(_ref_errors(data.get("approval_ref"), field="approval_ref", kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND, role="approval"))
    errors.extend(_ref_errors(data.get("event_tail_ref"), field="event_tail_ref", kind=DEEPAGENTS_EVENT_RECORD_KIND, role="event"))
    if not isinstance(data.get("events_dir"), str) or not data["events_dir"]:
        errors.append("events_dir must be a non-empty string")
    errors.extend(_string_list(data.get("completed_subagents"), field="completed_subagents"))
    errors.extend(_string_list(data.get("remaining_subagents"), field="remaining_subagents"))
    if not isinstance(data.get("resume_command"), str) or "builder-deepagents resume-approved" not in data["resume_command"]:
        errors.append("resume_command must describe builder-deepagents resume-approved")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_checkpoint",
            protocol_execution=True,
        )
    )
    if data.get("checkpoint_digest") != _digest_jsonable(data):
        errors.append("checkpoint_digest does not match canonical checkpoint payload")
    return errors


def validate_deepagents_replay_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents replay report must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_REPLAY_REPORT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_REPLAY_REPORT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("replay_state") != "RECONSTRUCTED_FROM_EVENTS_ONLY":
        errors.append("replay_state must be RECONSTRUCTED_FROM_EVENTS_ONLY")
    if data.get("status") not in ("RUNNING", "COMPLETED", "CHECKPOINTED", "FAILED", "INVALID"):
        errors.append("status must be RUNNING, COMPLETED, CHECKPOINTED, FAILED, or INVALID")
    if not isinstance(data.get("valid"), bool):
        errors.append("valid must be a boolean")
    if not isinstance(data.get("event_count"), int) or data["event_count"] < 0:
        errors.append("event_count must be a non-negative integer")
    for field in ("completed_subagents", "scheduled_subagents", "denied_capabilities", "warnings", "errors"):
        errors.extend(_string_list(data.get(field), field=field))
    if not isinstance(data.get("event_refs"), list):
        errors.append("event_refs must be a list")
    else:
        for index, ref in enumerate(data["event_refs"]):
            errors.extend(_ref_errors(ref, field=f"event_refs[{index}]", kind=DEEPAGENTS_EVENT_RECORD_KIND, role="event"))
    if data.get("last_event_ref") is not None:
        errors.extend(_ref_errors(data.get("last_event_ref"), field="last_event_ref", kind=DEEPAGENTS_EVENT_RECORD_KIND, role="event"))
    if data.get("replay_executes_runtime") is not False:
        errors.append("replay_executes_runtime must be false")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_replay_report",
            protocol_execution=False,
        )
    )
    if data.get("replay_digest") != _digest_jsonable(data):
        errors.append("replay_digest does not match canonical replay payload")
    return errors


def validate_deepagents_event_ledger(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents event ledger must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_EVENT_LEDGER_KIND:
        errors.append(f"kind must be {DEEPAGENTS_EVENT_LEDGER_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("ledger_state") != "HASH_CHAIN_RECORDED":
        errors.append("ledger_state must be HASH_CHAIN_RECORDED")
    if not isinstance(data.get("session_id"), str) or not data["session_id"]:
        errors.append("session_id must be a non-empty string")
    if not isinstance(data.get("event_count"), int) or data["event_count"] < 0:
        errors.append("event_count must be a non-negative integer")
    if not isinstance(data.get("event_refs"), list):
        errors.append("event_refs must be a list")
    else:
        for index, ref in enumerate(data["event_refs"]):
            errors.extend(_ref_errors(ref, field=f"event_refs[{index}]", kind=DEEPAGENTS_EVENT_RECORD_KIND, role="event"))
    if data.get("last_event_ref") is not None:
        errors.extend(_ref_errors(data.get("last_event_ref"), field="last_event_ref", kind=DEEPAGENTS_EVENT_RECORD_KIND, role="event"))
    errors.extend(_ref_errors(data.get("replay_report_ref"), field="replay_report_ref", kind=DEEPAGENTS_REPLAY_REPORT_KIND, role="replay_report"))
    if not isinstance(data.get("reconstructed_status"), dict):
        errors.append("reconstructed_status must be an object")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_event_ledger",
            protocol_execution=False,
        )
    )
    if data.get("ledger_digest") != _digest_jsonable(data):
        errors.append("ledger_digest does not match canonical ledger payload")
    return errors


def validate_deepagents_run_envelope(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents run envelope must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_RUN_ENVELOPE_KIND:
        errors.append(f"kind must be {DEEPAGENTS_RUN_ENVELOPE_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("envelope_state") not in RUN_STATUSES:
        errors.append(f"envelope_state must be one of: {', '.join(RUN_STATUSES)}")
    if data.get("backend_mode") not in BACKEND_MODES:
        errors.append(f"backend_mode must be one of: {', '.join(BACKEND_MODES)}")
    if not isinstance(data.get("session_id"), str) or not data["session_id"]:
        errors.append("session_id must be a non-empty string")
    if not isinstance(data.get("output_dir"), str) or not data["output_dir"]:
        errors.append("output_dir must be a non-empty string")
    errors.extend(_ref_errors(data.get("candidate_ref"), field="candidate_ref", kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND, role="candidate"))
    errors.extend(_ref_errors(data.get("approval_ref"), field="approval_ref", kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND, role="approval"))
    errors.extend(_ref_errors(data.get("event_ledger_ref"), field="event_ledger_ref", kind=DEEPAGENTS_EVENT_LEDGER_KIND, role="event_ledger"))
    errors.extend(_ref_errors(data.get("replay_report_ref"), field="replay_report_ref", kind=DEEPAGENTS_REPLAY_REPORT_KIND, role="replay_report"))
    if data.get("checkpoint_ref") is not None:
        errors.extend(_ref_errors(data.get("checkpoint_ref"), field="checkpoint_ref", kind=DEEPAGENTS_CHECKPOINT_KIND, role="checkpoint"))
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_run_envelope",
            protocol_execution=True,
        )
    )
    if data.get("envelope_digest") != _digest_jsonable(data):
        errors.append("envelope_digest does not match canonical envelope payload")
    return errors


def validate_deepagents_execution_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents execution receipt must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_EXECUTION_RECEIPT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_EXECUTION_RECEIPT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("receipt_state") not in RUN_STATUSES:
        errors.append(f"receipt_state must be one of: {', '.join(RUN_STATUSES)}")
    if not isinstance(data.get("session_id"), str) or not data["session_id"]:
        errors.append("session_id must be a non-empty string")
    if data.get("backend_mode") not in BACKEND_MODES:
        errors.append(f"backend_mode must be one of: {', '.join(BACKEND_MODES)}")
    errors.extend(_ref_errors(data.get("candidate_ref"), field="candidate_ref", kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND, role="candidate"))
    errors.extend(_ref_errors(data.get("approval_ref"), field="approval_ref", kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND, role="approval"))
    errors.extend(_ref_errors(data.get("envelope_ref"), field="envelope_ref", kind=DEEPAGENTS_RUN_ENVELOPE_KIND, role="run_envelope"))
    errors.extend(_ref_errors(data.get("event_ledger_ref"), field="event_ledger_ref", kind=DEEPAGENTS_EVENT_LEDGER_KIND, role="event_ledger"))
    errors.extend(_ref_errors(data.get("replay_report_ref"), field="replay_report_ref", kind=DEEPAGENTS_REPLAY_REPORT_KIND, role="replay_report"))
    if data.get("checkpoint_ref") is not None:
        errors.extend(_ref_errors(data.get("checkpoint_ref"), field="checkpoint_ref", kind=DEEPAGENTS_CHECKPOINT_KIND, role="checkpoint"))
    for field in ("completed_subagents", "denied_capabilities"):
        errors.extend(_string_list(data.get(field), field=field))
    for field in ("no_mutation_proof", "rollback_path", "verification_path"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_execution_receipt",
            protocol_execution=True,
        )
    )
    if data.get("receipt_digest") != _digest_jsonable(data):
        errors.append("receipt_digest does not match canonical receipt payload")
    return errors


def validate_deepagents_evidence_bundle(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents evidence bundle must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_EVIDENCE_BUNDLE_KIND:
        errors.append(f"kind must be {DEEPAGENTS_EVIDENCE_BUNDLE_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("bundle_state") != "EVIDENCE_ONLY":
        errors.append("bundle_state must be EVIDENCE_ONLY")
    if data.get("status") not in RUN_STATUSES:
        errors.append(f"status must be one of: {', '.join(RUN_STATUSES)}")
    errors.extend(_ref_errors(data.get("candidate_ref"), field="candidate_ref", kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND, role="candidate"))
    errors.extend(_ref_errors(data.get("approval_ref"), field="approval_ref", kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND, role="approval"))
    errors.extend(_ref_errors(data.get("envelope_ref"), field="envelope_ref", kind=DEEPAGENTS_RUN_ENVELOPE_KIND, role="run_envelope"))
    errors.extend(_ref_errors(data.get("receipt_ref"), field="receipt_ref", kind=DEEPAGENTS_EXECUTION_RECEIPT_KIND, role="receipt"))
    errors.extend(_ref_errors(data.get("event_ledger_ref"), field="event_ledger_ref", kind=DEEPAGENTS_EVENT_LEDGER_KIND, role="event_ledger"))
    errors.extend(_ref_errors(data.get("replay_report_ref"), field="replay_report_ref", kind=DEEPAGENTS_REPLAY_REPORT_KIND, role="replay_report"))
    if data.get("checkpoint_ref") is not None:
        errors.extend(_ref_errors(data.get("checkpoint_ref"), field="checkpoint_ref", kind=DEEPAGENTS_CHECKPOINT_KIND, role="checkpoint"))
    if not isinstance(data.get("operator_summary"), dict):
        errors.append("operator_summary must be an object")
    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_evidence_bundle",
            protocol_execution=False,
        )
    )
    if data.get("evidence_bundle_digest") != _digest_jsonable(data):
        errors.append("evidence_bundle_digest does not match canonical evidence bundle payload")
    return errors


def validate_deepagents_backend_readiness_gate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents backend readiness gate must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_BACKEND_READINESS_GATE_KIND:
        errors.append(f"kind must be {DEEPAGENTS_BACKEND_READINESS_GATE_KIND}")
    if data.get("schema_version") != DEEPAGENTS_EXECUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_EXECUTION_SCHEMA_VERSION}")
    if data.get("backend_mode") != OPTIONAL_DEEPAGENTS_BACKEND:
        errors.append(f"backend_mode must be {OPTIONAL_DEEPAGENTS_BACKEND}")
    if data.get("gate_state") not in ("PASS", "FAIL"):
        errors.append("gate_state must be PASS or FAIL")

    module = data.get("module")
    if not isinstance(module, dict):
        errors.append("module must be an object")
    else:
        for field in ("package", "module", "version", "import_error"):
            if not isinstance(module.get(field), str):
                errors.append(f"module.{field} must be a string")
        if not isinstance(module.get("available"), bool):
            errors.append("module.available must be a boolean")

    protocol = data.get("protocol_compatibility")
    if not isinstance(protocol, dict):
        errors.append("protocol_compatibility must be an object")
    else:
        expected_strings = {
            "required_version": OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION,
            "version_export": OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION_EXPORT,
            "factory_export": OPTIONAL_DEEPAGENTS_FACTORY_EXPORT,
            "protocol_runner_export": OPTIONAL_DEEPAGENTS_RUNNER_EXPORT,
        }
        for field, expected in expected_strings.items():
            if protocol.get(field) != expected:
                errors.append(f"protocol_compatibility.{field} must be {expected}")
        if not isinstance(protocol.get("observed_version"), str):
            errors.append("protocol_compatibility.observed_version must be a string")
        for field in (
            "version_compatible",
            "factory_export_present",
            "factory_constructed",
            "protocol_runner_export_present",
        ):
            if not isinstance(protocol.get(field), bool):
                errors.append(f"protocol_compatibility.{field} must be a boolean")
        if protocol.get("factory_constructed") is not False:
            errors.append("protocol_compatibility.factory_constructed must be false")

    contract = data.get("contract_tests")
    if not isinstance(contract, dict):
        errors.append("contract_tests must be an object")
    else:
        for field in ("backend_protocol_bound", "deterministic_shape", "proposal_only_payload"):
            if not isinstance(contract.get(field), bool):
                errors.append(f"contract_tests.{field} must be a boolean")
        if contract.get("result_schema_fields") != list(OPTIONAL_BACKEND_RESULT_SCHEMA_FIELDS):
            errors.append("contract_tests.result_schema_fields must match optional backend schema")
        errors.extend(_string_list(contract.get("contract_errors"), field="contract_tests.contract_errors"))

    schema = data.get("schema_drift_detection")
    if not isinstance(schema, dict):
        errors.append("schema_drift_detection must be an object")
    else:
        for field in ("expected_schema_digest", "observed_schema_digest", "repeat_observed_schema_digest"):
            value = schema.get(field)
            if value and not _is_sha256(value):
                errors.append(f"schema_drift_detection.{field} must be a SHA-256 hex digest or empty string")
            if not isinstance(value, str):
                errors.append(f"schema_drift_detection.{field} must be a string")
        if schema.get("expected_schema_digest") != _expected_optional_result_schema_digest():
            errors.append("schema_drift_detection.expected_schema_digest must match builder-II expected schema")
        if not isinstance(schema.get("stable"), bool):
            errors.append("schema_drift_detection.stable must be a boolean")

    probes = data.get("denial_probes")
    if not isinstance(probes, list) or len(probes) != len(OPTIONAL_DENIAL_PROBE_CAPABILITIES):
        errors.append("denial_probes must include one record for each required capability")
    else:
        seen = set()
        for index, probe in enumerate(probes):
            if not isinstance(probe, dict):
                errors.append(f"denial_probes[{index}] must be an object")
                continue
            capability = probe.get("capability")
            if capability not in OPTIONAL_DENIAL_PROBE_CAPABILITIES:
                errors.append(f"denial_probes[{index}].capability is not a required denial probe")
            if capability in seen:
                errors.append(f"denial_probes[{index}].capability must be unique")
            seen.add(capability)
            if probe.get("state") not in ("DENIED", "UNKNOWN", "ALLOWED"):
                errors.append(f"denial_probes[{index}].state must be DENIED, UNKNOWN, or ALLOWED")
            if probe.get("event_type") != "action_denied":
                errors.append(f"denial_probes[{index}].event_type must be action_denied")
            if not isinstance(probe.get("records_runtime_event"), bool):
                errors.append(f"denial_probes[{index}].records_runtime_event must be a boolean")

    partial = data.get("partial_failure_fixtures")
    if not isinstance(partial, dict):
        errors.append("partial_failure_fixtures must be an object")
    else:
        for field in (
            "interrupted_run_failed_receipt",
            "malformed_result_capped_or_rejected",
            "timeout_or_dependency_absence_backend_denied",
        ):
            if not isinstance(partial.get(field), bool):
                errors.append(f"partial_failure_fixtures.{field} must be a boolean")

    model = data.get("model_gateway_routing")
    if not isinstance(model, dict):
        errors.append("model_gateway_routing must be an object")
    else:
        if model.get("builder_ii_model_gateway_required") is not True:
            errors.append("model_gateway_routing.builder_ii_model_gateway_required must be true")
        if model.get("native_deepagents_model_invocation") != "DENIED":
            errors.append("model_gateway_routing.native_deepagents_model_invocation must be DENIED")
        if not isinstance(model.get("model_work_expected"), bool):
            errors.append("model_gateway_routing.model_work_expected must be a boolean")
        refs = model.get("model_call_receipt_refs")
        if not isinstance(refs, list):
            errors.append("model_gateway_routing.model_call_receipt_refs must be a list")
        else:
            for index, ref in enumerate(refs):
                errors.extend(_ref_errors(ref, field=f"model_gateway_routing.model_call_receipt_refs[{index}]"))

    replay = data.get("replay_proof")
    if not isinstance(replay, dict):
        errors.append("replay_proof must be an object")
    else:
        if replay.get("replay_run_required") is not True:
            errors.append("replay_proof.replay_run_required must be true")
        if replay.get("replay_executes_runtime") is not False:
            errors.append("replay_proof.replay_executes_runtime must be false")

    gates = data.get("capability_promotion_gates")
    if not isinstance(gates, list) or len(gates) != len(CAPABILITY_PROMOTION_GATE_NAMES):
        errors.append("capability_promotion_gates must include all capability gates")
    else:
        seen = set()
        for index, gate in enumerate(gates):
            if not isinstance(gate, dict):
                errors.append(f"capability_promotion_gates[{index}] must be an object")
                continue
            name = gate.get("gate")
            if name not in CAPABILITY_PROMOTION_GATE_NAMES:
                errors.append(f"capability_promotion_gates[{index}].gate is not a required gate")
            if name in seen:
                errors.append(f"capability_promotion_gates[{index}].gate must be unique")
            seen.add(name)
            if gate.get("state") not in ("PASS", "FAIL"):
                errors.append(f"capability_promotion_gates[{index}].state must be PASS or FAIL")
            if not isinstance(gate.get("evidence"), str):
                errors.append(f"capability_promotion_gates[{index}].evidence must be a string")

    denied = data.get("denied_capabilities")
    if not isinstance(denied, list):
        errors.append("denied_capabilities must be a list")
    else:
        for capability in DENIED_CAPABILITIES:
            if capability not in denied:
                errors.append(f"denied_capabilities must include {capability}")
    summary = data.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        if not isinstance(summary.get("passed"), bool):
            errors.append("summary.passed must be a boolean")
        errors.extend(_string_list(summary.get("errors"), field="summary.errors"))
        if not isinstance(summary.get("next_valid_command"), str) or not summary["next_valid_command"]:
            errors.append("summary.next_valid_command must be a non-empty string")

    errors.extend(
        _validate_common_authority(
            data,
            capability_state="deepagents_backend_readiness_gate",
            protocol_execution=False,
        )
    )
    if data.get("readiness_gate_digest") != _digest_jsonable(data):
        errors.append("readiness_gate_digest does not match canonical readiness gate payload")

    if data.get("gate_state") == "PASS":
        errors.extend(_readiness_gate_errors(data))
        if isinstance(summary, dict) and summary.get("passed") is not True:
            errors.append("summary.passed must be true when gate_state is PASS")
    return errors


def write_deepagents_execution_candidate(artifact: dict[str, Any], output: Path) -> None:
    _write_json(artifact, output)


def write_deepagents_execution_approval(artifact: dict[str, Any], output: Path) -> None:
    _write_json(artifact, output)


def write_deepagents_evidence_bundle(artifact: dict[str, Any], output: Path) -> None:
    _write_json(artifact, output)


def write_deepagents_backend_readiness_gate(artifact: dict[str, Any], output: Path) -> None:
    _write_json(artifact, output)


def dumps_deepagents_execution_candidate(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_execution_approval(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_evidence_bundle(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_backend_readiness_gate(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def _event_path(events_dir: Path, sequence: int, event_type: str) -> Path:
    return events_dir / f"event-{sequence:04d}-{event_type}.json"


def _load_event_records(events_dir: Path) -> list[tuple[dict[str, Any], Path]]:
    if not events_dir.is_dir():
        return []
    records: list[tuple[dict[str, Any], Path]] = []
    for path in sorted(events_dir.glob("event-*.json")):
        records.append((_load_json_object(path, label="deepagents event record"), path))
    return records


def _path_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _candidate_output_root(candidate: dict[str, Any]) -> Path:
    output_root = Path(str(candidate.get("output_root", ""))).expanduser()
    if not output_root.is_absolute():
        output_root = (Path.cwd() / output_root).resolve()
    return output_root


def _assert_candidate_path_allowed(candidate: dict[str, Any], path: Path, *, field: str) -> None:
    output_root = _candidate_output_root(candidate)
    resolved_path = path.expanduser().resolve()
    if not _path_within(resolved_path, output_root):
        raise ValueError(
            f"{field} must be inside candidate.output_root; use the candidate's "
            "declared artifact root or create a new candidate"
        )


def _assert_output_dir_allowed(candidate: dict[str, Any], output_dir: Path) -> None:
    _assert_candidate_path_allowed(candidate, output_dir, field="output_dir")


def _new_session_id(candidate: dict[str, Any]) -> str:
    candidate_digest = str(candidate.get("candidate_digest") or _digest_jsonable(candidate))
    nonce_source = f"{candidate_digest}:{datetime.now(timezone.utc).isoformat()}".encode("utf-8")
    nonce = hashlib.sha256(nonce_source).hexdigest()[:8]
    return f"deepagents-{candidate_digest[:12]}-{nonce}"


def _candidate_budget(candidate: dict[str, Any], key: str) -> int:
    budgets = candidate.get("budgets")
    if not isinstance(budgets, dict) or not isinstance(budgets.get(key), int):
        raise ValueError(f"candidate.budgets.{key} must be present before run-approved")
    return int(budgets[key])


def _json_size(value: dict[str, Any]) -> int:
    return len(
        json_lib.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    )


def _assert_event_budget(candidate: dict[str, Any], planned_event_count: int) -> None:
    max_events = _candidate_budget(candidate, "max_events")
    if planned_event_count > max_events:
        raise ValueError(
            "candidate.budgets.max_events is too small for this bounded run; "
            "create a new candidate with --max-events large enough for the "
            "approved subagent queue"
        )


def _cap_result_payload(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    max_output_bytes = _candidate_budget(candidate, "max_output_bytes")
    if _json_size(payload) <= max_output_bytes:
        return payload
    capped = {
        "subagent_profile": str(payload.get("subagent_profile", "")),
        "result_mode": "PROPOSAL_ONLY_TRUNCATED",
        "summary": "Backend result exceeded candidate.budgets.max_output_bytes; original digest retained.",
        "output_truncated": True,
        "original_output_bytes": _json_size(payload),
        "original_output_sha256": _digest_jsonable(payload),
        "max_output_bytes": max_output_bytes,
        "writes_source": False,
        "executes_shell": False,
        "calls_models": False,
        "calls_tools": False,
        "calls_mcp": False,
        "mutates_memory": False,
        "constructs_deepagents": False,
    }
    capped["result_digest"] = _digest_jsonable(capped)
    if _json_size(capped) <= max_output_bytes:
        return capped
    raise ValueError(
        "candidate.budgets.max_output_bytes is too small to record bounded "
        "result metadata; create a new candidate with a larger --max-output-bytes"
    )


def _approval_guard(candidate: dict[str, Any], approval: dict[str, Any]) -> None:
    errors = validate_deepagents_execution_approval_against_candidate(
        approval,
        candidate,
        check_expiry=True,
    )
    if errors:
        raise ValueError("approval does not bind to candidate: " + "; ".join(errors))


def _load_candidate_backend_readiness_gate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    if candidate.get("backend_mode") != OPTIONAL_DEEPAGENTS_BACKEND:
        return None
    ref = candidate.get("backend_readiness_ref")
    if not isinstance(ref, dict):
        raise ValueError("optional_deepagents candidate is missing backend_readiness_ref")
    path_text = ref.get("path")
    if not isinstance(path_text, str) or not path_text:
        raise ValueError("optional_deepagents backend_readiness_ref.path must be a non-empty string")
    path = Path(path_text)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    gate = _load_json_object(path, label="deepagents backend readiness gate")
    if ref.get("sha256") != _digest_jsonable(gate):
        raise ValueError("backend readiness gate digest drifted after candidate creation")
    gate_errors = validate_deepagents_backend_readiness_gate(gate)
    if gate_errors or gate.get("gate_state") != "PASS":
        raise ValueError(
            "optional_deepagents backend readiness gate is not passing: "
            + "; ".join(gate_errors or gate.get("summary", {}).get("errors", []))
        )
    return gate


def _denial_probe_payloads(readiness_gate: dict[str, Any] | None) -> list[dict[str, Any]]:
    if readiness_gate is None:
        return []
    payloads: list[dict[str, Any]] = []
    for probe in readiness_gate.get("denial_probes", []):
        if isinstance(probe, dict) and probe.get("state") == "DENIED":
            payloads.append(
                {
                    "denied_capability": str(probe.get("capability", "")),
                    "source": "optional_deepagents_readiness_gate",
                    "state": "DENIED",
                    "next_valid_command": "builder-deepagents replay-run --events-dir <events> --output <replay.json>",
                }
            )
    return payloads


def _failure_payload(exc: Exception) -> dict[str, Any]:
    payload = {
        "error": str(exc),
        "error_type": type(exc).__name__,
    }
    if isinstance(exc, DeepAgentsBackendDenied):
        payload["backend_denial"] = True
        payload["denied_capability"] = "optional_deepagents backend activation"
    return payload


def _write_event(
    *,
    events_dir: Path,
    session_id: str,
    sequence: int,
    event_type: str,
    subject_refs: list[dict[str, Any]],
    payload: dict[str, Any] | None,
    previous_ref: dict[str, Any] | None,
    message: str,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    event = create_deepagents_event_record(
        session_id=session_id,
        sequence=sequence,
        event_type=event_type,
        subject_refs=subject_refs,
        payload=payload,
        previous_event_ref=previous_ref,
        message=message,
    )
    path = _event_path(events_dir, sequence, event_type)
    _write_json(event, path)
    return event, path, _artifact_ref(event, role="event", path=path, name=event_type)


def _finalize_run_artifacts(
    *,
    session_id: str,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    candidate_path: Path,
    approval_path: Path,
    output_dir: Path,
    events_dir: Path,
    checkpoint: dict[str, Any] | None,
    checkpoint_path: Path | None,
    status: str,
) -> dict[str, Any]:
    event_records = _load_event_records(events_dir)
    replay_path = output_dir / "deepagents-replay-report.json"
    replay = create_deepagents_replay_report(session_id=session_id, event_records=event_records)
    _write_json(replay, replay_path)

    ledger_path = output_dir / "deepagents-event-ledger.json"
    ledger = create_deepagents_event_ledger(
        session_id=session_id,
        event_records=event_records,
        replay_report=replay,
        replay_report_path=replay_path,
    )
    _write_json(ledger, ledger_path)

    envelope_path = output_dir / "deepagents-run-envelope.json"
    envelope = create_deepagents_run_envelope(
        session_id=session_id,
        candidate=candidate,
        approval=approval,
        candidate_path=candidate_path,
        approval_path=approval_path,
        event_ledger=ledger,
        event_ledger_path=ledger_path,
        replay_report=replay,
        replay_report_path=replay_path,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        output_dir=output_dir,
        status=status,
    )
    _write_json(envelope, envelope_path)

    receipt_path = output_dir / "deepagents-execution-receipt.json"
    receipt = create_deepagents_execution_receipt(
        session_id=session_id,
        candidate=candidate,
        approval=approval,
        envelope=envelope,
        replay_report=replay,
        event_ledger=ledger,
        candidate_path=candidate_path,
        approval_path=approval_path,
        envelope_path=envelope_path,
        replay_report_path=replay_path,
        event_ledger_path=ledger_path,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        status=status,
    )
    _write_json(receipt, receipt_path)

    return {
        "session_id": session_id,
        "status": status,
        "output_dir": str(output_dir),
        "events_dir": str(events_dir),
        "envelope_path": str(envelope_path),
        "receipt_path": str(receipt_path),
        "event_ledger_path": str(ledger_path),
        "replay_report_path": str(replay_path),
        "checkpoint_path": str(checkpoint_path) if checkpoint_path is not None else "",
    }


def run_deepagents_approved_candidate(
    *,
    candidate_path: Path,
    approval_path: Path,
    output_dir: Path,
    stop_after: int | None = None,
) -> dict[str, Any]:
    candidate = _load_json_object(candidate_path, label="deepagents execution candidate")
    approval = _load_json_object(approval_path, label="deepagents execution approval")
    _approval_guard(candidate, approval)
    _assert_output_dir_allowed(candidate, output_dir)
    readiness_gate = _load_candidate_backend_readiness_gate(candidate)
    denial_probe_payloads = _denial_probe_payloads(readiness_gate)
    if stop_after is not None and stop_after <= 0:
        raise ValueError("stop_after must be positive when supplied")
    allowed = list(candidate["allowed_subagents"])
    planned_events = 3 + len(denial_probe_payloads) + (2 * len(allowed))
    if stop_after is not None and stop_after < len(allowed):
        planned_events = 3 + len(denial_probe_payloads) + (2 * stop_after)
    _assert_event_budget(candidate, planned_events)

    output_dir.mkdir(parents=True, exist_ok=True)
    events_dir = output_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    if _load_event_records(events_dir):
        raise ValueError("output_dir already contains deepagents events; choose a fresh output-dir")
    session_id = _new_session_id(candidate)
    backend = backend_for(str(candidate["backend_mode"]), readiness_gate=readiness_gate)
    candidate_ref = _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate")
    approval_ref = _artifact_ref(approval, role="approval", path=approval_path, name="deepagents execution approval")

    sequence = 1
    previous_ref: dict[str, Any] | None = None
    _, _, previous_ref = _write_event(
        events_dir=events_dir,
        session_id=session_id,
        sequence=sequence,
        event_type="candidate_accepted",
        subject_refs=[candidate_ref, approval_ref],
        payload={"candidate_digest": candidate["candidate_digest"]},
        previous_ref=previous_ref,
        message="Candidate and approval binding accepted for bounded protocol run.",
    )
    sequence += 1
    _, _, previous_ref = _write_event(
        events_dir=events_dir,
        session_id=session_id,
        sequence=sequence,
        event_type="backend_selected",
        subject_refs=[candidate_ref],
        payload={
            "backend_mode": backend.name,
            "backend_readiness_gate_digest": readiness_gate.get("readiness_gate_digest") if readiness_gate else "",
        },
        previous_ref=previous_ref,
        message="Protocol backend selected.",
    )
    sequence += 1
    for payload in denial_probe_payloads:
        _, _, previous_ref = _write_event(
            events_dir=events_dir,
            session_id=session_id,
            sequence=sequence,
            event_type="action_denied",
            subject_refs=[candidate_ref],
            payload=payload,
            previous_ref=previous_ref,
            message=f"Recorded optional_deepagents denial probe for {payload['denied_capability']}.",
        )
        sequence += 1

    completed: list[str] = []
    checkpoint: dict[str, Any] | None = None
    checkpoint_path: Path | None = None

    try:
        for index, subagent in enumerate(allowed):
            _, _, previous_ref = _write_event(
                events_dir=events_dir,
                session_id=session_id,
                sequence=sequence,
                event_type="subagent_scheduled",
                subject_refs=[candidate_ref],
                payload={"subagent_profile": subagent},
                previous_ref=previous_ref,
                message=f"Scheduled proposal-only subagent {subagent}.",
            )
            sequence += 1
            result = _cap_result_payload(
                candidate,
                backend.run_subagent(subagent_profile=subagent, task=str(candidate["task"])),
            )
            _, _, previous_ref = _write_event(
                events_dir=events_dir,
                session_id=session_id,
                sequence=sequence,
                event_type="subagent_result_recorded",
                subject_refs=[candidate_ref],
                payload=result,
                previous_ref=previous_ref,
                message=f"Recorded proposal-only result for {subagent}.",
            )
            sequence += 1
            completed.append(subagent)
            if stop_after is not None and len(completed) >= stop_after and index + 1 < len(allowed):
                remaining = allowed[index + 1 :]
                checkpoint = create_deepagents_checkpoint(
                    session_id=session_id,
                    candidate=candidate,
                    approval=approval,
                    candidate_path=candidate_path,
                    approval_path=approval_path,
                    event_tail_ref=previous_ref,
                    completed_subagents=completed,
                    remaining_subagents=remaining,
                    events_dir=events_dir,
                )
                checkpoint_path = output_dir / "deepagents-checkpoint.json"
                _write_json(checkpoint, checkpoint_path)
                _, _, previous_ref = _write_event(
                    events_dir=events_dir,
                    session_id=session_id,
                    sequence=sequence,
                    event_type="checkpoint_recorded",
                    subject_refs=[_artifact_ref(checkpoint, role="checkpoint", path=checkpoint_path, name="deepagents checkpoint")],
                    payload={"completed_subagents": completed, "remaining_subagents": remaining},
                    previous_ref=previous_ref,
                    message="Checkpoint recorded for explicit resume.",
                )
                sequence += 1
                return _finalize_run_artifacts(
                    session_id=session_id,
                    candidate=candidate,
                    approval=approval,
                    candidate_path=candidate_path,
                    approval_path=approval_path,
                    output_dir=output_dir,
                    events_dir=events_dir,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    status="CHECKPOINTED",
                )
        _, _, previous_ref = _write_event(
            events_dir=events_dir,
            session_id=session_id,
            sequence=sequence,
            event_type="run_completed",
            subject_refs=[candidate_ref],
            payload={"completed_subagents": completed},
            previous_ref=previous_ref,
            message="Bounded protocol run completed.",
        )
        sequence += 1
        return _finalize_run_artifacts(
            session_id=session_id,
            candidate=candidate,
            approval=approval,
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=output_dir,
            events_dir=events_dir,
            checkpoint=None,
            checkpoint_path=None,
            status="COMPLETED",
        )
    except Exception as exc:
        _, _, previous_ref = _write_event(
            events_dir=events_dir,
            session_id=session_id,
            sequence=sequence,
            event_type="run_failed",
            subject_refs=[candidate_ref],
            payload=_failure_payload(exc),
            previous_ref=previous_ref,
            message="Bounded protocol run failed before completion.",
        )
        sequence += 1
        return _finalize_run_artifacts(
            session_id=session_id,
            candidate=candidate,
            approval=approval,
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=output_dir,
            events_dir=events_dir,
            checkpoint=None,
            checkpoint_path=None,
            status="FAILED",
        )


def resume_deepagents_approved_candidate(
    *,
    candidate_path: Path,
    approval_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    candidate = _load_json_object(candidate_path, label="deepagents execution candidate")
    approval = _load_json_object(approval_path, label="deepagents execution approval")
    checkpoint = _load_json_object(checkpoint_path, label="deepagents checkpoint")
    _approval_guard(candidate, approval)
    readiness_gate = _load_candidate_backend_readiness_gate(candidate)
    checkpoint_errors = validate_deepagents_checkpoint(checkpoint)
    if checkpoint_errors:
        raise ValueError("invalid checkpoint: " + "; ".join(checkpoint_errors))
    if checkpoint["candidate_ref"]["sha256"] != _digest_jsonable(candidate):
        raise ValueError("checkpoint candidate_ref does not match candidate")
    if checkpoint["approval_ref"]["sha256"] != _digest_jsonable(approval):
        raise ValueError("checkpoint approval_ref does not match approval")
    _assert_output_dir_allowed(candidate, output_dir)

    events_dir = Path(str(checkpoint["events_dir"]))
    if not events_dir.is_absolute():
        events_dir = (Path.cwd() / events_dir).resolve()
    _assert_candidate_path_allowed(candidate, events_dir, field="checkpoint.events_dir")
    event_records = _load_event_records(events_dir)
    if not event_records:
        raise ValueError("checkpoint events_dir has no events")
    if any(event.get("event_type") in {"run_completed", "run_failed"} for event, _path in event_records):
        raise ValueError("run is already terminal; resume is not allowed")
    previous_event, previous_event_path = sorted(event_records, key=lambda item: int(item[0]["sequence"]))[-1]
    previous_ref = _artifact_ref(previous_event, role="event", path=previous_event_path, name=str(previous_event["event_type"]))
    session_id = str(checkpoint["session_id"])
    sequence = int(previous_event["sequence"]) + 1
    candidate_ref = _artifact_ref(candidate, role="candidate", path=candidate_path, name="deepagents execution candidate")
    approval_ref = _artifact_ref(approval, role="approval", path=approval_path, name="deepagents execution approval")
    backend = backend_for(str(candidate["backend_mode"]), readiness_gate=readiness_gate)
    remaining = list(checkpoint["remaining_subagents"])
    _assert_event_budget(candidate, len(event_records) + 2 + (2 * len(remaining)))

    _, _, previous_ref = _write_event(
        events_dir=events_dir,
        session_id=session_id,
        sequence=sequence,
        event_type="resume_started",
        subject_refs=[candidate_ref, approval_ref, _artifact_ref(checkpoint, role="checkpoint", path=checkpoint_path, name="deepagents checkpoint")],
        payload={"remaining_subagents": checkpoint["remaining_subagents"]},
        previous_ref=previous_ref,
        message="Resume accepted for the same candidate and approval.",
    )
    sequence += 1
    completed = list(checkpoint["completed_subagents"])
    try:
        for subagent in remaining:
            _, _, previous_ref = _write_event(
                events_dir=events_dir,
                session_id=session_id,
                sequence=sequence,
                event_type="subagent_scheduled",
                subject_refs=[candidate_ref],
                payload={"subagent_profile": subagent},
                previous_ref=previous_ref,
                message=f"Scheduled proposal-only subagent {subagent}.",
            )
            sequence += 1
            result = _cap_result_payload(
                candidate,
                backend.run_subagent(subagent_profile=subagent, task=str(candidate["task"])),
            )
            _, _, previous_ref = _write_event(
                events_dir=events_dir,
                session_id=session_id,
                sequence=sequence,
                event_type="subagent_result_recorded",
                subject_refs=[candidate_ref],
                payload=result,
                previous_ref=previous_ref,
                message=f"Recorded proposal-only result for {subagent}.",
            )
            sequence += 1
            completed.append(subagent)

        _, _, previous_ref = _write_event(
            events_dir=events_dir,
            session_id=session_id,
            sequence=sequence,
            event_type="run_completed",
            subject_refs=[candidate_ref],
            payload={"completed_subagents": completed},
            previous_ref=previous_ref,
            message="Bounded protocol run resumed and completed.",
        )
        sequence += 1
        return _finalize_run_artifacts(
            session_id=session_id,
            candidate=candidate,
            approval=approval,
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=output_dir,
            events_dir=events_dir,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            status="COMPLETED",
        )
    except Exception as exc:
        _, _, previous_ref = _write_event(
            events_dir=events_dir,
            session_id=session_id,
            sequence=sequence,
            event_type="run_failed",
            subject_refs=[candidate_ref],
            payload=_failure_payload(exc),
            previous_ref=previous_ref,
            message="Bounded protocol resume failed before completion.",
        )
        sequence += 1
        return _finalize_run_artifacts(
            session_id=session_id,
            candidate=candidate,
            approval=approval,
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=output_dir,
            events_dir=events_dir,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            status="FAILED",
        )


def replay_deepagents_run(*, events_dir: Path, output: Path) -> dict[str, Any]:
    event_records = _load_event_records(events_dir)
    if not event_records:
        raise ValueError("events_dir contains no deepagents event records")
    first = sorted(event_records, key=lambda item: int(item[0].get("sequence", 10**9)))[0][0]
    session_id = str(first.get("session_id", ""))
    replay = create_deepagents_replay_report(session_id=session_id, event_records=event_records)
    _write_json(replay, output)
    return replay


def _validate_or_raise(label: str, errors: list[str]) -> None:
    if errors:
        raise ValueError(f"invalid {label}: " + "; ".join(errors))


def _ref_matches(artifact: dict[str, Any], field: str, expected: dict[str, Any]) -> bool:
    ref = artifact.get(field)
    return isinstance(ref, dict) and ref.get("sha256") == _digest_jsonable(expected)


def _validate_ref_match(
    errors: list[str],
    *,
    artifact: dict[str, Any],
    field: str,
    expected: dict[str, Any],
    label: str,
) -> None:
    if not _ref_matches(artifact, field, expected):
        errors.append(f"{label}.{field} must reference the supplied {expected.get('kind', 'artifact')}")


def _validate_evidence_inputs(
    *,
    candidate: dict[str, Any],
    approval: dict[str, Any],
    envelope: dict[str, Any],
    receipt: dict[str, Any],
    ledger: dict[str, Any],
    replay: dict[str, Any],
    checkpoint: dict[str, Any] | None,
) -> None:
    _validate_or_raise("deepagents execution candidate", validate_deepagents_execution_candidate(candidate))
    _validate_or_raise(
        "deepagents execution approval",
        validate_deepagents_execution_approval_against_candidate(approval, candidate),
    )
    _validate_or_raise("deepagents run envelope", validate_deepagents_run_envelope(envelope))
    _validate_or_raise("deepagents execution receipt", validate_deepagents_execution_receipt(receipt))
    _validate_or_raise("deepagents event ledger", validate_deepagents_event_ledger(ledger))
    _validate_or_raise("deepagents replay report", validate_deepagents_replay_report(replay))
    if replay.get("valid") is not True:
        raise ValueError("deepagents replay report must be valid before evidence bundling")

    errors: list[str] = []
    for artifact, label in ((envelope, "envelope"), (receipt, "receipt")):
        _validate_ref_match(errors, artifact=artifact, field="candidate_ref", expected=candidate, label=label)
        _validate_ref_match(errors, artifact=artifact, field="approval_ref", expected=approval, label=label)
        _validate_ref_match(errors, artifact=artifact, field="event_ledger_ref", expected=ledger, label=label)
        _validate_ref_match(errors, artifact=artifact, field="replay_report_ref", expected=replay, label=label)
    _validate_ref_match(errors, artifact=receipt, field="envelope_ref", expected=envelope, label="receipt")
    _validate_ref_match(errors, artifact=ledger, field="replay_report_ref", expected=replay, label="ledger")

    session_ids = {
        str(envelope.get("session_id", "")),
        str(receipt.get("session_id", "")),
        str(ledger.get("session_id", "")),
        str(replay.get("session_id", "")),
    }
    if len(session_ids) != 1 or "" in session_ids:
        errors.append("envelope, receipt, ledger, and replay must share the same session_id")
    if envelope.get("envelope_state") != receipt.get("receipt_state"):
        errors.append("envelope.envelope_state must match receipt.receipt_state")
    if replay.get("status") != receipt.get("receipt_state"):
        errors.append("replay.status must match receipt.receipt_state")
    if ledger.get("event_count") != replay.get("event_count"):
        errors.append("ledger.event_count must match replay.event_count")

    checkpoint_refs = (envelope.get("checkpoint_ref"), receipt.get("checkpoint_ref"))
    if checkpoint is None:
        if any(ref is not None for ref in checkpoint_refs):
            errors.append("checkpoint artifact must be supplied when envelope or receipt references one")
    else:
        _validate_or_raise("deepagents checkpoint", validate_deepagents_checkpoint(checkpoint))
        _validate_ref_match(errors, artifact=checkpoint, field="candidate_ref", expected=candidate, label="checkpoint")
        _validate_ref_match(errors, artifact=checkpoint, field="approval_ref", expected=approval, label="checkpoint")
        _validate_ref_match(errors, artifact=envelope, field="checkpoint_ref", expected=checkpoint, label="envelope")
        _validate_ref_match(errors, artifact=receipt, field="checkpoint_ref", expected=checkpoint, label="receipt")

    if errors:
        raise ValueError("invalid deepagents evidence chain: " + "; ".join(errors))


def create_evidence_bundle_from_files(
    *,
    candidate_path: Path,
    approval_path: Path,
    envelope_path: Path,
    receipt_path: Path,
    event_ledger_path: Path,
    replay_report_path: Path,
    output_path: Path,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    candidate = _load_json_object(candidate_path, label="deepagents execution candidate")
    approval = _load_json_object(approval_path, label="deepagents execution approval")
    envelope = _load_json_object(envelope_path, label="deepagents run envelope")
    receipt = _load_json_object(receipt_path, label="deepagents execution receipt")
    ledger = _load_json_object(event_ledger_path, label="deepagents event ledger")
    replay = _load_json_object(replay_report_path, label="deepagents replay report")
    checkpoint = _load_json_object(checkpoint_path, label="deepagents checkpoint") if checkpoint_path is not None else None
    _validate_evidence_inputs(
        candidate=candidate,
        approval=approval,
        envelope=envelope,
        receipt=receipt,
        ledger=ledger,
        replay=replay,
        checkpoint=checkpoint,
    )
    bundle = create_deepagents_evidence_bundle(
        candidate=candidate,
        approval=approval,
        envelope=envelope,
        receipt=receipt,
        event_ledger=ledger,
        replay_report=replay,
        candidate_path=candidate_path,
        approval_path=approval_path,
        envelope_path=envelope_path,
        receipt_path=receipt_path,
        event_ledger_path=event_ledger_path,
        replay_report_path=replay_report_path,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
    )
    _write_json(bundle, output_path)
    return bundle


def validate_deepagents_execution_artifact(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["deepagents execution artifact must be a JSON object"]
    validators = {
        DEEPAGENTS_EXECUTION_CANDIDATE_KIND: validate_deepagents_execution_candidate,
        DEEPAGENTS_EXECUTION_APPROVAL_KIND: validate_deepagents_execution_approval,
        DEEPAGENTS_RUN_ENVELOPE_KIND: validate_deepagents_run_envelope,
        DEEPAGENTS_EVENT_RECORD_KIND: validate_deepagents_event_record,
        DEEPAGENTS_EVENT_LEDGER_KIND: validate_deepagents_event_ledger,
        DEEPAGENTS_REPLAY_REPORT_KIND: validate_deepagents_replay_report,
        DEEPAGENTS_CHECKPOINT_KIND: validate_deepagents_checkpoint,
        DEEPAGENTS_EXECUTION_RECEIPT_KIND: validate_deepagents_execution_receipt,
        DEEPAGENTS_EVIDENCE_BUNDLE_KIND: validate_deepagents_evidence_bundle,
        DEEPAGENTS_BACKEND_READINESS_GATE_KIND: validate_deepagents_backend_readiness_gate,
    }
    validator = validators.get(str(data.get("kind", "")))
    if validator is None:
        return [f"unknown deepagents execution artifact kind: {data.get('kind', '')}"]
    return validator(data)
