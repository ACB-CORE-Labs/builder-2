from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Callable

# Import kinds and validators
from builder_ii.approval_records import APPROVAL_RECORD_KIND, validate_approval_record
from builder_ii.artifact_index_records import ARTIFACT_INDEX_RECORD_KIND, validate_artifact_index_record
from builder_ii.chain_summary_records import CHAIN_SUMMARY_RECORD_KIND, validate_chain_summary_record
from builder_ii.goose_command_proposal import GOOSE_COMMAND_PROPOSAL_KIND, validate_goose_command_proposal
from builder_ii.handoff_bundle_records import HANDOFF_BUNDLE_RECORD_KIND, validate_handoff_bundle_record
from builder_ii.preflight_records import PREFLIGHT_RECORD_KIND, validate_preflight_record
from builder_ii.promotion_decision_records import PROMOTION_DECISION_RECORD_KIND, validate_promotion_decision_record
from builder_ii.promotion_readiness_records import PROMOTION_READINESS_RECORD_KIND, validate_promotion_readiness_record
from builder_ii.receipt_records import RECEIPT_RECORD_KIND, validate_receipt_record
from builder_ii.receive_records import RECEIVE_RECORD_KIND, validate_receive_record
from builder_ii.snapshot_records import SNAPSHOT_RECORD_KIND, validate_snapshot_record
from builder_ii.state_ledger_records import STATE_LEDGER_RECORD_KIND, validate_state_ledger_record
from builder_ii.agent_profiles import AGENT_PROFILE_RECORD_KIND, validate_agent_profile_record
from builder_ii.context_pack import CONTEXT_PACK_RECORD_KIND, validate_context_pack_record
from builder_ii.target_profiles import TARGET_PROFILE_ARTIFACT_KIND, validate_target_profile_artifact
from builder_ii.verification_profiles import VERIFICATION_ARTIFACT_KIND, validate_profile_artifact
from builder_ii.git_state import GIT_STATE_RECORD_KIND, validate_git_state_record
from builder_ii.research_plans import RESEARCH_PLAN_KIND, validate_research_plan_artifact
from builder_ii.research_adapters import RESEARCH_ADAPTER_KIND, validate_research_adapter_artifact
from builder_ii.performance_measurements import PERFORMANCE_MEASUREMENT_KIND, validate_performance_measurement_record
from builder_ii.readonly_inspection_promotion import READONLY_INSPECTION_PROMOTION_SPEC_KIND, validate_readonly_inspection_promotion_spec
from builder_ii.readonly_inspection_reports import READONLY_INSPECTION_REPORT_KIND, validate_readonly_inspection_report
from builder_ii.hitl_execution_records import HITL_EXECUTION_REQUEST_KIND, validate_hitl_execution_request
from builder_ii.hitl_execution_records import HITL_EXECUTION_RECEIPT_KIND, validate_hitl_execution_receipt
from builder_ii.hitl_patch_spec import HITL_PATCH_APPLICATION_SPEC_KIND, validate_hitl_patch_application_spec
from builder_ii.rollback_artifacts import ROLLBACK_PLAN_KIND, validate_rollback_plan
from builder_ii.rollback_artifacts import ROLLBACK_RECEIPT_KIND, validate_rollback_receipt
from builder_ii.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    validate_execution_postflight_record,
    EXECUTION_VERIFICATION_RECORD_KIND,
    validate_execution_verification_record,
)
from builder_ii.hitl_evidence_bundle import (
    HITL_EVIDENCE_BUNDLE_KIND,
    validate_hitl_evidence_bundle,
)
from builder_ii.session_workflow import (
    SESSION_WORKFLOW_PLAN_KIND,
    validate_session_workflow_plan,
)
from builder_ii.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    validate_goose_readonly_session_plan,
)


VALIDATORS: dict[str, Callable[[Any], list[str]]] = {
    GOOSE_COMMAND_PROPOSAL_KIND: validate_goose_command_proposal,
    APPROVAL_RECORD_KIND: validate_approval_record,
    PREFLIGHT_RECORD_KIND: validate_preflight_record,
    RECEIPT_RECORD_KIND: validate_receipt_record,
    CHAIN_SUMMARY_RECORD_KIND: validate_chain_summary_record,
    HANDOFF_BUNDLE_RECORD_KIND: validate_handoff_bundle_record,
    RECEIVE_RECORD_KIND: validate_receive_record,
    PROMOTION_READINESS_RECORD_KIND: validate_promotion_readiness_record,
    PROMOTION_DECISION_RECORD_KIND: validate_promotion_decision_record,
    STATE_LEDGER_RECORD_KIND: validate_state_ledger_record,
    ARTIFACT_INDEX_RECORD_KIND: validate_artifact_index_record,
    SNAPSHOT_RECORD_KIND: validate_snapshot_record,
    TARGET_PROFILE_ARTIFACT_KIND: validate_target_profile_artifact,
    VERIFICATION_ARTIFACT_KIND: validate_profile_artifact,
    CONTEXT_PACK_RECORD_KIND: validate_context_pack_record,
    AGENT_PROFILE_RECORD_KIND: validate_agent_profile_record,
    GIT_STATE_RECORD_KIND: validate_git_state_record,
    RESEARCH_PLAN_KIND: validate_research_plan_artifact,
    RESEARCH_ADAPTER_KIND: validate_research_adapter_artifact,
    PERFORMANCE_MEASUREMENT_KIND: validate_performance_measurement_record,
    READONLY_INSPECTION_PROMOTION_SPEC_KIND: validate_readonly_inspection_promotion_spec,
    READONLY_INSPECTION_REPORT_KIND: validate_readonly_inspection_report,
    HITL_EXECUTION_REQUEST_KIND: validate_hitl_execution_request,
    HITL_EXECUTION_RECEIPT_KIND: validate_hitl_execution_receipt,
    HITL_PATCH_APPLICATION_SPEC_KIND: validate_hitl_patch_application_spec,
    ROLLBACK_PLAN_KIND: validate_rollback_plan,
    ROLLBACK_RECEIPT_KIND: validate_rollback_receipt,
    EXECUTION_POSTFLIGHT_RECORD_KIND: validate_execution_postflight_record,
    EXECUTION_VERIFICATION_RECORD_KIND: validate_execution_verification_record,
    HITL_EVIDENCE_BUNDLE_KIND: validate_hitl_evidence_bundle,
    SESSION_WORKFLOW_PLAN_KIND: validate_session_workflow_plan,
    GOOSE_READONLY_SESSION_PLAN_KIND: validate_goose_readonly_session_plan,
}



def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    kind = record.get("kind")
    refs: list[dict[str, Any]] = []

    if kind == APPROVAL_RECORD_KIND:
        prop = record.get("proposal", {})
        if isinstance(prop, dict):
            refs.append({"field": "proposal", "sha256": prop.get("sha256"), "path": prop.get("path"), "expected_kind": GOOSE_COMMAND_PROPOSAL_KIND})

    elif kind == PREFLIGHT_RECORD_KIND:
        prop = record.get("proposal", {})
        if isinstance(prop, dict):
            refs.append({"field": "proposal", "sha256": prop.get("sha256"), "path": prop.get("path"), "expected_kind": GOOSE_COMMAND_PROPOSAL_KIND})
        appr = record.get("approval", {})
        if isinstance(appr, dict):
            refs.append({"field": "approval", "sha256": appr.get("sha256"), "path": appr.get("path"), "expected_kind": APPROVAL_RECORD_KIND})

    elif kind == RECEIPT_RECORD_KIND:
        pref = record.get("preflight", {})
        if isinstance(pref, dict):
            refs.append({"field": "preflight", "sha256": pref.get("sha256"), "path": pref.get("path"), "expected_kind": PREFLIGHT_RECORD_KIND})

    elif kind == CHAIN_SUMMARY_RECORD_KIND:
        artifacts = record.get("artifacts", {})
        if isinstance(artifacts, dict):
            for name, expected in [
                ("proposal", GOOSE_COMMAND_PROPOSAL_KIND),
                ("approval", APPROVAL_RECORD_KIND),
                ("preflight", PREFLIGHT_RECORD_KIND),
                ("receipt", RECEIPT_RECORD_KIND),
            ]:
                item = artifacts.get(name, {})
                if isinstance(item, dict):
                    refs.append({"field": f"artifacts.{name}", "sha256": item.get("sha256"), "path": item.get("path"), "expected_kind": expected})

    elif kind == HANDOFF_BUNDLE_RECORD_KIND:
        sum_field = record.get("summary", {})
        if isinstance(sum_field, dict):
            refs.append({"field": "summary", "sha256": sum_field.get("sha256"), "path": sum_field.get("path"), "expected_kind": CHAIN_SUMMARY_RECORD_KIND})
        digests = record.get("artifact_digests", {})
        if isinstance(digests, dict):
            for name, item in digests.items():
                if isinstance(item, dict):
                    refs.append({"field": f"artifact_digests.{name}", "sha256": item.get("sha256"), "path": item.get("path"), "expected_kind": item.get("kind")})

    elif kind == RECEIVE_RECORD_KIND:
        bundle = record.get("bundle", {})
        if isinstance(bundle, dict):
            refs.append({"field": "bundle", "sha256": bundle.get("sha256"), "path": bundle.get("path"), "expected_kind": HANDOFF_BUNDLE_RECORD_KIND})
        digests = record.get("artifact_digests", {})
        if isinstance(digests, dict):
            for name, item in digests.items():
                if isinstance(item, dict):
                    refs.append({"field": f"artifact_digests.{name}", "sha256": item.get("sha256"), "path": item.get("path"), "expected_kind": item.get("kind")})

    elif kind == PROMOTION_DECISION_RECORD_KIND:
        readiness = record.get("readiness", {})
        if isinstance(readiness, dict):
            refs.append({"field": "readiness", "sha256": readiness.get("sha256"), "path": readiness.get("path"), "expected_kind": PROMOTION_READINESS_RECORD_KIND})

    elif kind == STATE_LEDGER_RECORD_KIND:
        entries = record.get("entries", [])
        if isinstance(entries, list):
            for idx, entry in enumerate(entries):
                if isinstance(entry, dict):
                    dec = entry.get("decision", {})
                    if isinstance(dec, dict):
                        refs.append({"field": f"entries[{idx}].decision", "sha256": dec.get("sha256"), "path": dec.get("path"), "expected_kind": PROMOTION_DECISION_RECORD_KIND})

    elif kind == SNAPSHOT_RECORD_KIND:
        idx = record.get("artifact_index", {})
        if isinstance(idx, dict):
            refs.append({"field": "artifact_index", "sha256": idx.get("sha256"), "path": idx.get("path"), "expected_kind": ARTIFACT_INDEX_RECORD_KIND})
        ledger = record.get("state_ledger", {})
        if isinstance(ledger, dict):
            refs.append({"field": "state_ledger", "sha256": ledger.get("sha256"), "path": ledger.get("path"), "expected_kind": STATE_LEDGER_RECORD_KIND})

    elif kind == RESEARCH_ADAPTER_KIND:
        plan = record.get("research_plan", {})
        if isinstance(plan, dict):
            refs.append({"field": "research_plan", "sha256": plan.get("sha256"), "path": plan.get("path"), "expected_kind": RESEARCH_PLAN_KIND})

    elif kind == HITL_EVIDENCE_BUNDLE_KIND:
        for field, expected in [
            ("proposal_ref", GOOSE_COMMAND_PROPOSAL_KIND),
            ("approval_ref", APPROVAL_RECORD_KIND),
            ("preflight_ref", PREFLIGHT_RECORD_KIND),
            ("request_ref", HITL_EXECUTION_REQUEST_KIND),
            ("postflight_ref", EXECUTION_POSTFLIGHT_RECORD_KIND),
            ("verification_ref", EXECUTION_VERIFICATION_RECORD_KIND),
        ]:
            val = record.get(field)
            if isinstance(val, str) and val:
                refs.append({"field": field, "sha256": None, "path": val, "expected_kind": expected})

        # Rollback references are optional but typed when present
        for field, expected in [
            ("rollback_plan_ref", ROLLBACK_PLAN_KIND),
            ("rollback_receipt_ref", ROLLBACK_RECEIPT_KIND),
        ]:
            val = record.get(field)
            if isinstance(val, str) and val:
                refs.append({"field": field, "sha256": None, "path": val, "expected_kind": expected})

    return refs


def resolve_reference(
    source_path: Path,
    declared_path_str: str | None,
    expected_kind: str | None,
    expected_sha256: str | None,
    loaded_by_path: dict[Path, dict[str, Any]],
    loaded_by_digest: dict[str, list[tuple[Path, dict[str, Any]]]],
) -> tuple[Path | None, dict[str, Any] | None, str, list[str]]:
    """Resolves a reference using the deterministic priority order:
    1. Exact normalized path from loaded input paths
    2. Declared path relative to the referencing file's parent
    3. Declared path as-is
    4. Loaded file with matching (kind, sha256) as a fallback
    """

    if declared_path_str:
        try:
            declared_path = Path(declared_path_str).resolve()
            if declared_path in loaded_by_path:
                return declared_path, loaded_by_path[declared_path], "exact_input_path", []
        except Exception:
            pass

    if declared_path_str:
        try:
            rel_path = (source_path.parent / Path(declared_path_str)).resolve()
            if rel_path in loaded_by_path:
                return rel_path, loaded_by_path[rel_path], "relative_path", []
            if rel_path.is_file():
                try:
                    data = json_lib.loads(rel_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return rel_path, data, "relative_path", []
                    return rel_path, None, "relative_path", [f"Referenced file {rel_path} must be a JSON object"]
                except Exception as e:
                    return rel_path, None, "relative_path", [f"Failed to load referenced file {rel_path}: {e}"]
        except Exception:
            pass

    if declared_path_str:
        try:
            as_is_path = Path(declared_path_str).resolve()
            if as_is_path in loaded_by_path:
                return as_is_path, loaded_by_path[as_is_path], "as_is_path", []
            if as_is_path.is_file():
                try:
                    data = json_lib.loads(as_is_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return as_is_path, data, "as_is_path", []
                    return as_is_path, None, "as_is_path", [f"Referenced file {as_is_path} must be a JSON object"]
                except Exception as e:
                    return as_is_path, None, "as_is_path", [f"Failed to load referenced file {as_is_path}: {e}"]
        except Exception:
            pass

    if expected_sha256:
        candidates = loaded_by_digest.get(expected_sha256, [])
        if candidates:
            matching_candidates = [(path, data) for path, data in candidates if not expected_kind or data.get("kind") == expected_kind]
            if len(matching_candidates) > 1:
                paths_set = {p.resolve() for p, _ in matching_candidates}
                if len(paths_set) > 1:
                    paths_str = ", ".join(str(p) for p in paths_set)
                    return None, None, "ambiguous", [f"Ambiguous digest fallback match. Multiple paths found with digest '{expected_sha256}': {paths_str}"]
                return matching_candidates[0][0], matching_candidates[0][1], "digest_fallback", []
            if len(matching_candidates) == 1:
                return matching_candidates[0][0], matching_candidates[0][1], "digest_fallback", []

    msg = f"Digest '{expected_sha256}' referenced by '{expected_kind}' could not be resolved"
    if declared_path_str:
        msg += f" at path '{declared_path_str}'"
    return None, None, "unresolved", [msg]


def _target_native_errors(target_data: dict[str, Any]) -> list[str]:
    target_kind = target_data.get("kind", "")
    validator = VALIDATORS.get(target_kind)
    if not target_kind:
        return ["resolved target is missing kind"]
    if validator is None:
        return [f"resolved target has unknown kind '{target_kind}'"]
    return validator(target_data)


def verify_artifact_chain(paths: list[Path]) -> dict[str, Any]:
    """Validates a set of artifacts and checks their cross-record references."""
    loaded_by_path: dict[Path, dict[str, Any]] = {}
    loaded_by_digest: dict[str, list[tuple[Path, dict[str, Any]]]] = {}

    files_report: list[dict[str, Any]] = []
    links_report: list[dict[str, Any]] = []
    global_errors: list[str] = []

    native_valid_count = 0
    native_invalid_count = 0

    for path in paths:
        resolved_path = path.resolve()

        if not path.exists():
            err_msg = f"File not found: {path}"
            global_errors.append(err_msg)
            files_report.append({"path": str(path), "kind": "", "sha256": "", "native_valid": False, "native_errors": [err_msg]})
            native_invalid_count += 1
            continue

        try:
            content = path.read_text(encoding="utf-8")
            data = json_lib.loads(content)
        except json_lib.JSONDecodeError as exc:
            err_msg = f"Invalid JSON in {path}: {exc}"
            global_errors.append(err_msg)
            files_report.append({"path": str(path), "kind": "", "sha256": "", "native_valid": False, "native_errors": [err_msg]})
            native_invalid_count += 1
            continue
        except Exception as exc:
            err_msg = f"Failed to read {path}: {exc}"
            global_errors.append(err_msg)
            files_report.append({"path": str(path), "kind": "", "sha256": "", "native_valid": False, "native_errors": [err_msg]})
            native_invalid_count += 1
            continue

        if not isinstance(data, dict):
            err_msg = f"Artifact {path} must be a JSON object"
            global_errors.append(err_msg)
            files_report.append({"path": str(path), "kind": "", "sha256": "", "native_valid": False, "native_errors": [err_msg]})
            native_invalid_count += 1
            continue

        kind = data.get("kind", "")
        digest_val = _digest(data)

        loaded_by_path[resolved_path] = data
        loaded_by_digest.setdefault(digest_val, []).append((resolved_path, data))

        validator = VALIDATORS.get(kind)
        if not kind:
            native_errors = ["Missing 'kind' field in artifact"]
        elif validator is None:
            native_errors = [f"Unknown artifact kind '{kind}'"]
        else:
            native_errors = validator(data)

        is_valid = len(native_errors) == 0
        if is_valid:
            native_valid_count += 1
        else:
            native_invalid_count += 1
            global_errors.extend(f"Native validation error in {path}: {e}" for e in native_errors)

        files_report.append({"path": str(path), "kind": kind, "sha256": digest_val, "native_valid": is_valid, "native_errors": native_errors})

    resolved_links_count = 0
    broken_links_count = 0

    for path in paths:
        resolved_path = path.resolve()
        if resolved_path not in loaded_by_path:
            continue
        record = loaded_by_path[resolved_path]
        kind = record.get("kind", "")

        refs = extract_references(record)
        for ref in refs:
            field = ref["field"]
            declared_path_str = ref.get("path")
            expected_kind = ref.get("expected_kind")
            expected_sha256 = ref.get("sha256")

            target_path, target_data, resolved_via, link_errors = resolve_reference(
                resolved_path,
                declared_path_str,
                expected_kind,
                expected_sha256,
                loaded_by_path,
                loaded_by_digest,
            )

            if target_data is not None:
                actual_sha256 = _digest(target_data)
                if expected_sha256 and actual_sha256 != expected_sha256:
                    link_errors.append(f"Digest mismatch: referenced '{expected_sha256}', resolved file '{target_path}' has '{actual_sha256}'")

                actual_kind = target_data.get("kind", "")
                if expected_kind and actual_kind != expected_kind:
                    link_errors.append(f"Kind mismatch: expected '{expected_kind}', resolved file '{target_path}' has '{actual_kind}'")

                for target_error in _target_native_errors(target_data):
                    link_errors.append(f"Resolved target native validation failed: {target_error}")

            link_valid = len(link_errors) == 0
            if link_valid:
                resolved_links_count += 1
            else:
                broken_links_count += 1
                global_errors.extend(f"Link error in {path} (field '{field}'): {e}" for e in link_errors)

            links_report.append(
                {
                    "source_path": str(path),
                    "source_kind": kind,
                    "field": field,
                    "target_path_declared": declared_path_str,
                    "target_kind_expected": expected_kind,
                    "target_sha256_expected": expected_sha256,
                    "resolved": link_valid,
                    "resolved_via": resolved_via,
                    "resolved_path": str(target_path) if target_path else None,
                    "errors": link_errors,
                }
            )

    is_overall_valid = len(global_errors) == 0
    return {
        "kind": "builder_ii.artifact_chain_verification_report",
        "schema_version": 1,
        "status": "valid" if is_overall_valid else "invalid",
        "valid": is_overall_valid,
        "counts": {
            "files": len(paths),
            "native_valid": native_valid_count,
            "native_invalid": native_invalid_count,
            "links": len(links_report),
            "resolved_links": resolved_links_count,
            "broken_links": broken_links_count,
        },
        "files": files_report,
        "links": links_report,
        "errors": global_errors,
        "governance": {
            "capability_state": "artifact_chain_verification_report",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
