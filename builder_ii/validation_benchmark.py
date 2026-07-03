from __future__ import annotations

import copy
import json as json_lib
import time
from typing import Any

from builder_ii.approval_records import validate_approval_record
from builder_ii.goose_inspection import validate_readonly_inspection_audit
from builder_ii.goose_readonly import validate_readonly_runtime_audit
from builder_ii.goose_session import validate_goose_session_manifest
from builder_ii.hitl_execution_records import validate_hitl_execution_receipt, validate_hitl_execution_request
from builder_ii.performance_measurements import validate_performance_measurement_record

VALIDATION_BENCHMARK_KIND = "builder_ii.validation_benchmark"
VALIDATION_BENCHMARK_SCHEMA_VERSION = 1

VALIDATORS = {
    "builder_ii.goose_session_manifest": validate_goose_session_manifest,
    "builder_ii.goose_readonly_runtime_audit": validate_readonly_runtime_audit,
    "builder_ii.goose_readonly_inspection_audit": validate_readonly_inspection_audit,
    "builder_ii.performance_measurement": validate_performance_measurement_record,
    "builder_ii.hitl_execution_request": validate_hitl_execution_request,
    "builder_ii.hitl_execution_receipt": validate_hitl_execution_receipt,
    "builder_ii.approval_record": validate_approval_record,
}


def validate_validation_benchmark(record: Any) -> list[str]:
    errors = []
    if not isinstance(record, dict):
        return ["validation benchmark record must be a JSON object"]
    if record.get("kind") != VALIDATION_BENCHMARK_KIND:
        errors.append(f"kind must be {VALIDATION_BENCHMARK_KIND}")
    if record.get("schema_version") != VALIDATION_BENCHMARK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VALIDATION_BENCHMARK_SCHEMA_VERSION}")
    if record.get("validator_backend") not in ("python", "rust"):
        errors.append("validator_backend must be python or rust")
    if not record.get("artifact_kind"):
        errors.append("artifact_kind is required")
    for f in ("artifact_count", "bytes_total", "valid_count", "invalid_count"):
        if not isinstance(record.get(f), int) or record[f] < 0:
            errors.append(f"{f} must be a non-negative integer")
    for f in ("duration_ms", "p50_ms", "p95_ms", "p99_ms"):
        if not isinstance(record.get(f), (int, float)) or record[f] < 0:
            errors.append(f"{f} must be a non-negative number")
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    return errors


def generate_mock_artifacts(kind: str, count: int) -> list[dict[str, Any]]:
    if kind == "builder_ii.goose_session_manifest":
        from builder_ii.config import load_settings
        from builder_ii.goose_session import create_goose_session_manifest

        settings = load_settings()
        valid_tpl = create_goose_session_manifest(
            settings, target_name="builder", agent_profile="patch_planner", runtime_mode="read_only"
        )
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    elif kind == "builder_ii.goose_readonly_runtime_audit":
        from builder_ii.config import load_settings
        from builder_ii.goose_readonly import create_readonly_runtime_audit
        from builder_ii.goose_session import create_goose_session_manifest

        settings = load_settings()
        manifest = create_goose_session_manifest(
            settings, target_name="builder", agent_profile="patch_planner", runtime_mode="read_only"
        )
        valid_tpl = create_readonly_runtime_audit(manifest, manifest_path="manifest.json")
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    elif kind == "builder_ii.goose_readonly_inspection_audit":
        valid_tpl = {
            "kind": "builder_ii.goose_readonly_inspection_audit",
            "schema_version": 1,
            "runtime_mode": "read_only",
            "capability_state": "read_only_runtime_candidate",
            "current_runtime_state": "CANDIDATE_INSPECTION",
            "runtime_started": False,
            "goose_process_started": False,
            "manifest_path": "manifest.json",
            "manifest_kind": "builder_ii.goose_session_manifest",
            "manifest_schema_version": 1,
            "manifest_requested_runtime_mode": "read_only",
            "task": "test",
            "target": {"name": "builder", "repo": ".", "description": "desc"},
            "agent_profile": {"name": "patch_planner", "description": "desc", "authority": "auth"},
            "linked_artifacts_declared": {},
            "expected_audit_artifact": "audit.json",
            "actual_audit_artifact": "actual.json",
            "timestamps": {
                "created_at_utc": "2023-10-10T10:10:10Z",
                "runtime_started_at_utc": "",
                "runtime_ended_at_utc": "",
            },
            "actions_performed": [
                "validate_goose_session_manifest",
                "read_explicit_operator_requested_repository_files",
                "emit_readonly_inspection_audit_artifact",
            ],
            "allowed_actions": [
                "validate_goose_session_manifest",
                "read_explicit_operator_requested_repository_files",
                "emit_readonly_inspection_audit_artifact",
            ],
            "denied_actions": [
                "start_goose_process",
                "start_goose_runtime",
                "inspect_git_status",
                "read_linked_target_artifacts",
                "execute_commands",
                "execute_shell",
                "write_source_files",
                "apply_patches",
                "mutate_memory",
                "create_commits",
                "push_refs",
                "open_pull_requests",
                "construct_deepagents",
                "call_models",
                "source_collection",
                "web_search",
                "mcp_execution",
            ],
            "files_read": ["manifest.json", "file.py"],
            "requested_repository_paths": ["file.py"],
            "repository_files_read": [
                {"path": "file.py", "bytes_read": 10, "sha256": "abc", "line_count": 1, "content_recorded": False}
            ],
            "repository_file_contents_recorded": False,
            "target_artifacts_read": [],
            "git_status_inspected": False,
            "commands_proposed": [],
            "commands_executed": [],
            "shell_commands_executed": [],
            "source_writes_proposed": [],
            "source_writes_applied": [],
            "patches_applied": [],
            "model_calls": [],
            "deepagents_constructed": False,
            "denied_action_attempts": [],
            "approval_events": [],
            "verification_output_refs": [],
            "rollback_refs": ["no source mutation"],
            "handoff_ref": "",
            "governance": {
                "capability_state": "read_only_runtime_candidate",
                "runtime_execution": "READ_ONLY_CANDIDATE_INSPECTION",
                "goose_runtime_start": "DISABLED",
                "model_execution": "DISABLED",
                "agent_construction": "DISABLED",
                "deepagents_construction": "DISABLED",
                "shell_execution": "DISABLED",
                "command_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "commit_push": "DISABLED",
                "pull_request_creation": "DISABLED",
                "source_collection": "DISABLED",
                "web_search": "DISABLED",
                "mcp_execution": "DISABLED",
                "repository_file_reads": "ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY",
                "target_artifact_reads": "DISABLED_IN_THIS_CANDIDATE",
                "git_status_inspection": "DISABLED_IN_THIS_CANDIDATE",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            },
        }
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    elif kind == "builder_ii.performance_measurement":
        from builder_ii.performance_measurements import create_performance_measurement_record

        valid_tpl = create_performance_measurement_record(
            target="generic",
            candidate_name="test",
            metric_name="test",
            metric_value=1.0,
            unit="ms",
            method="test",
            source_ref="test",
        )
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    elif kind == "builder_ii.hitl_execution_request":
        from builder_ii.hitl_execution_records import create_hitl_execution_request

        valid_tpl = create_hitl_execution_request(
            target_name="generic",
            command_proposal_ref="prop",
            approval_record_ref="app",
            preflight_record_ref="pre",
            requested_by="me",
            requested_at="now",
            explicit_operator_intent="intent",
            command_preview="cmd",
        )
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    elif kind == "builder_ii.hitl_execution_receipt":
        from builder_ii.hitl_execution_records import create_hitl_execution_receipt

        valid_tpl = create_hitl_execution_receipt(target_name="generic", request_ref="req")
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    elif kind == "builder_ii.approval_record":
        from builder_ii.approval_records import create_approval_record
        from builder_ii.config import load_settings
        from builder_ii.goose_command_proposal import create_goose_command_proposal
        from builder_ii.goose_session import create_goose_session_manifest

        settings = load_settings()
        manifest = create_goose_session_manifest(
            settings, target_name="builder", agent_profile="patch_planner", runtime_mode="read_only"
        )
        proposal = create_goose_command_proposal(manifest, manifest_path="manifest.json", command="echo 1")
        valid_tpl = create_approval_record(
            proposal, proposal_path="proposal.json", decision="approved", decided_by="me"
        )
        invalid_tpl = copy.deepcopy(valid_tpl)
        invalid_tpl["kind"] = "wrong"
    else:
        raise ValueError(f"Unknown artifact kind for benchmark fixtures: {kind}")

    artifacts = []
    for i in range(count):
        if i % 10 == 0:
            artifacts.append(copy.deepcopy(invalid_tpl))
        else:
            artifacts.append(copy.deepcopy(valid_tpl))
    return artifacts


def benchmark_validator(kind: str, count: int, backend: str = "python") -> dict[str, Any]:
    from builder_ii.rust_validator import validate_via_rust

    validator = VALIDATORS.get(kind)
    if not validator:
        raise ValueError(f"No validator registered for kind: {kind}")

    artifacts = generate_mock_artifacts(kind, count)

    bytes_total = 0
    for art in artifacts:
        bytes_total += len(json_lib.dumps(art).encode("utf-8"))

    durations = []
    valid_count = 0
    invalid_count = 0

    for art in artifacts:
        t0 = time.perf_counter()
        if backend == "rust":
            valid, errors = validate_via_rust(kind, art)
        else:
            errors = validator(art)
        durations.append((time.perf_counter() - t0) * 1000.0)

        # Determine validity
        if backend == "rust":
            if valid:
                valid_count += 1
            else:
                invalid_count += 1
        else:
            if not errors:
                valid_count += 1
            else:
                invalid_count += 1

    durations.sort()
    duration_ms = sum(durations)
    p50 = durations[int(len(durations) * 0.50)]
    p95 = durations[int(len(durations) * 0.95)]
    p99 = durations[int(len(durations) * 0.99)]

    return {
        "kind": VALIDATION_BENCHMARK_KIND,
        "schema_version": VALIDATION_BENCHMARK_SCHEMA_VERSION,
        "validator_backend": backend,
        "artifact_kind": kind,
        "artifact_count": count,
        "bytes_total": bytes_total,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "duration_ms": round(duration_ms, 3),
        "p50_ms": round(p50, 4),
        "p95_ms": round(p95, 4),
        "p99_ms": round(p99, 4),
        "artifact_is_authority": False,
    }


VALIDATION_PARITY_REPORT_KIND = "builder_ii.validation_parity_report"
VALIDATION_PARITY_REPORT_SCHEMA_VERSION = 1


def validate_validation_parity_report(record: Any) -> list[str]:
    errors = []
    if not isinstance(record, dict):
        return ["validation parity report must be a JSON object"]
    if record.get("kind") != VALIDATION_PARITY_REPORT_KIND:
        errors.append(f"kind must be {VALIDATION_PARITY_REPORT_KIND}")
    if record.get("schema_version") != VALIDATION_PARITY_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VALIDATION_PARITY_REPORT_SCHEMA_VERSION}")
    if not record.get("artifact_kind"):
        errors.append("artifact_kind is required")
    if not isinstance(record.get("cases_total"), int) or record["cases_total"] < 0:
        errors.append("cases_total must be a non-negative integer")
    if not isinstance(record.get("matches"), int) or record["matches"] < 0:
        errors.append("matches must be a non-negative integer")
    if not isinstance(record.get("mismatches"), list):
        errors.append("mismatches must be a list")
    if not isinstance(record.get("rust_promoted"), bool):
        errors.append("rust_promoted must be a boolean")
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    return errors


def generate_parity_report(kind: str, count: int) -> dict[str, Any]:
    from builder_ii.rust_validator import validate_via_rust

    validator = VALIDATORS.get(kind)
    if not validator:
        raise ValueError(f"No validator registered for kind: {kind}")

    artifacts = generate_mock_artifacts(kind, count)

    matches = 0
    mismatches = []

    for idx, art in enumerate(artifacts):
        py_errors = validator(art)
        rust_valid, rust_errors = validate_via_rust(kind, art)

        py_valid = len(py_errors) == 0
        if py_valid == rust_valid and set(py_errors) == set(rust_errors):
            matches += 1
        else:
            mismatches.append(
                {
                    "case_index": idx,
                    "python_errors": py_errors,
                    "rust_errors": rust_errors,
                }
            )

    return {
        "kind": VALIDATION_PARITY_REPORT_KIND,
        "schema_version": VALIDATION_PARITY_REPORT_SCHEMA_VERSION,
        "artifact_kind": kind,
        "python_validator_version": "reference",
        "rust_validator_version": "0.1.0",
        "cases_total": count,
        "matches": matches,
        "mismatches": mismatches,
        "rust_promoted": False,
        "artifact_is_authority": False,
    }
