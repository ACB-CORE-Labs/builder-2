import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_chain_verification import extract_references, verify_artifact_chain
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.artifact_index_records import create_artifact_index_record, validate_artifact_index_record
from builder_ii.performance_measurements import PERFORMANCE_MEASUREMENT_KIND, create_performance_measurement_record
from builder_ii.readonly_inspection_promotion import READONLY_INSPECTION_PROMOTION_SPEC_KIND, create_readonly_inspection_promotion_spec
from builder_ii.research_adapters import RESEARCH_ADAPTER_KIND, create_research_adapter_artifact
from builder_ii.research_plans import RESEARCH_PLAN_KIND, create_research_plan_artifact
from builder_ii.readonly_inspection_reports import READONLY_INSPECTION_REPORT_KIND
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_REQUEST_KIND,
    HITL_EXECUTION_RECEIPT_KIND,
    create_hitl_execution_request,
    create_hitl_execution_receipt,
)
from builder_ii.hitl_patch_spec import (
    HITL_PATCH_APPLICATION_SPEC_KIND,
    create_hitl_patch_application_spec,
)
from builder_ii.rollback_artifacts import (
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    create_rollback_plan,
    create_rollback_receipt,
)
from builder_ii.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
    create_execution_postflight_record,
    create_execution_verification_record,
)
from builder_ii.hitl_evidence_bundle import (
    HITL_EVIDENCE_BUNDLE_KIND,
    create_hitl_evidence_bundle,
)
from builder_ii.session_workflow import (
    SESSION_WORKFLOW_PLAN_KIND,
    create_session_workflow_plan,
)
from builder_ii.repo_map import REPO_MAP_KIND
from builder_ii.context_packs import CONTEXT_PACK_KIND
from builder_ii.config import Settings
from builder_ii.convention_kernel import CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND
from builder_ii.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    create_governed_prepare_package,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
    summarize_governed_prepare_package_directory,
)
from builder_ii.orchestration_plan import (
    ORCHESTRATION_PLAN_KIND,
    create_orchestration_plan,
)
from builder_ii.orchestration_dry_run import (
    ORCHESTRATION_DRY_RUN_KIND,
    create_orchestration_dry_run,
)
from builder_ii.runtime_activation_approval import (
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
    create_runtime_activation_approval_spec,
)
from builder_ii.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    create_goose_readonly_session_plan,
)
from builder_ii.goose_projection import (
    GOOSE_PROJECTION_KIND,
    create_goose_projection,
)
from builder_ii.goose_wrapper_plan import (
    GOOSE_WRAPPER_PLAN_KIND,
    create_goose_wrapper_plan,
)
from builder_ii.verification_profile_reports import (
    VERIFICATION_PROFILE_REPORT_KIND,
    create_verification_profile_report,
)
from builder_ii.handoff_notes import (
    HANDOFF_NOTE_KIND,
    create_handoff_note,
)
from builder_ii.deepagents_bridge_readiness import (
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    create_deepagents_bridge_readiness_report,
)
from builder_ii.goose_session import (
    GOOSE_SESSION_KIND,
    create_goose_session_manifest,
)
from builder_ii.handoff_artifacts import (
    HANDOFF_KIND,
    create_handoff_artifact,
)
from builder_ii.session_config import (
    SESSION_CONFIG_KIND,
    create_session_configuration,
)
from builder_ii.release_manifest import (
    V0_RELEASE_MANIFEST_KIND,
    create_artifact_ref,
    create_v0_release_manifest,
)
from builder_ii.artifact_chain_verification import ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND




CLOSURE_KINDS = {
    "builder_ii.target_profile",
    "builder_ii.verification_profile",
    "builder_ii.context_pack_record",
    "builder_ii.agent_profile_record",
    "builder_ii.git_state_record",
    RESEARCH_PLAN_KIND,
    RESEARCH_ADAPTER_KIND,
    PERFORMANCE_MEASUREMENT_KIND,
    READONLY_INSPECTION_PROMOTION_SPEC_KIND,
    READONLY_INSPECTION_REPORT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_PATCH_APPLICATION_SPEC_KIND,
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
    HITL_EVIDENCE_BUNDLE_KIND,
    SESSION_WORKFLOW_PLAN_KIND,
    REPO_MAP_KIND,
    CONTEXT_PACK_KIND,
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
    GOVERNED_PREPARE_PACKAGE_KIND,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
    ORCHESTRATION_PLAN_KIND,
    ORCHESTRATION_DRY_RUN_KIND,
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
    GOOSE_READONLY_SESSION_PLAN_KIND,
    GOOSE_PROJECTION_KIND,
    GOOSE_WRAPPER_PLAN_KIND,
    VERIFICATION_PROFILE_REPORT_KIND,
    HANDOFF_NOTE_KIND,
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    GOOSE_SESSION_KIND,
    HANDOFF_KIND,
    SESSION_CONFIG_KIND,
    V0_RELEASE_MANIFEST_KIND,
    ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND,
}

# ---------------------------------------------------------------------------
# Governance artifact kinds added in PR W / PR X / PR Y / PR AD / PR AE / PR AF
# ---------------------------------------------------------------------------

GOVERNANCE_ARTIFACT_KINDS = {
    HITL_EXECUTION_REQUEST_KIND,
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_PATCH_APPLICATION_SPEC_KIND,
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
    HITL_EVIDENCE_BUNDLE_KIND,
    SESSION_WORKFLOW_PLAN_KIND,
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
    GOVERNED_PREPARE_PACKAGE_KIND,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
    ORCHESTRATION_PLAN_KIND,
    ORCHESTRATION_DRY_RUN_KIND,
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
    GOOSE_READONLY_SESSION_PLAN_KIND,
    GOOSE_PROJECTION_KIND,
    GOOSE_WRAPPER_PLAN_KIND,
    VERIFICATION_PROFILE_REPORT_KIND,
    HANDOFF_NOTE_KIND,
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    GOOSE_SESSION_KIND,
    HANDOFF_KIND,
    SESSION_CONFIG_KIND,
    V0_RELEASE_MANIFEST_KIND,
    ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND,
}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plan() -> dict[str, Any]:
    return create_research_plan_artifact(
        target="builder",
        profile_name="research_planner",
        task="plan registry closure",
        topic="registry closure",
    )


def _adapter(plan: dict[str, Any]) -> dict[str, Any]:
    return create_research_adapter_artifact(
        target="builder",
        topic="registry closure",
        research_question="Which registries must stay aligned?",
        plan_path="research-plan.json",
        plan_sha256=_digest(plan),
    )


def _measurement() -> dict[str, Any]:
    return create_performance_measurement_record(
        target="builder",
        candidate_name="registry_closure",
        metric_name="closure_artifact_count",
        metric_value=4,
        unit="artifacts",
        method="operator supplied test fixture",
        source_ref="tests/test_registry_closure.py",
    )


# ---------------------------------------------------------------------------
# Governance artifact fixture factories
# ---------------------------------------------------------------------------

def _hitl_execution_request() -> dict[str, Any]:
    return create_hitl_execution_request(
        target_name="generic",
        command_proposal_ref="proposal.json",
        approval_record_ref="approval.json",
        preflight_record_ref="preflight.json",
        requested_by="operator",
        requested_at="2026-06-26T00:00:00Z",
        explicit_operator_intent="test fixture",
        command_preview="echo test",
    )


def _hitl_execution_receipt() -> dict[str, Any]:
    return create_hitl_execution_receipt(
        target_name="generic",
        request_ref="request.json",
    )


def _hitl_patch_application_spec() -> dict[str, Any]:
    return create_hitl_patch_application_spec(
        target_name="generic",
        patch_description="test patch",
        reason="test fixture",
    )


def _rollback_plan() -> dict[str, Any]:
    return create_rollback_plan(
        target_name="generic",
        related_artifact_refs=["receipt.json"],
        rollback_strategy="revert commit",
        operator_note="test fixture",
    )


def _rollback_receipt() -> dict[str, Any]:
    return create_rollback_receipt(
        target_name="generic",
        rollback_plan_ref="rollback-plan.json",
    )


def _execution_postflight_record() -> dict[str, Any]:
    return create_execution_postflight_record(
        target_name="generic",
        request_ref="request.json",
        receipt_ref="receipt.json",
        preflight_ref="preflight.json",
        approval_ref="approval.json",
        expected_outcome="outcome",
        observed_state_ref="state",
    )


def _execution_verification_record() -> dict[str, Any]:
    return create_execution_verification_record(
        target_name="generic",
        request_ref="request.json",
        receipt_ref="receipt.json",
        postflight_ref="postflight.json",
    )


def _hitl_evidence_bundle() -> dict[str, Any]:
    return create_hitl_evidence_bundle(
        target_name="generic",
        bundle_id="bundle-123",
        created_at="2026-06-26T00:00:00Z",
        created_by="operator",
        proposal_ref="proposal.json",
        approval_ref="approval.json",
        preflight_ref="preflight.json",
        request_ref="request.json",
        postflight_ref="postflight.json",
        verification_ref="verification.json",
    )


def _session_workflow_plan() -> dict[str, Any]:
    from builder_ii.config import load_settings
    return create_session_workflow_plan(
        load_settings(),
        "generic",
    )


def _convention_kernel_platform_bundle() -> dict[str, Any]:
    return {
        "kind": CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
        "schema_version": 1,
        "bundle_state": "PLANNED_ONLY",
        "target": "builder",
        "repo_path": ".",
        "operator_review_required": True,
        "executes_now": False,
        "verification_status": "planned-only",
        "target_profile": {"name": "builder"},
        "command_authority_check": {
            "kind": "builder_ii.command_authority_check",
            "schema_version": 1,
            "all_referenced_commands_registered": True,
            "referenced_commands": [],
            "verification_status": "planned-only"
        },
        "session_configuration": {
            "kind": "builder_ii.session_configuration",
            "schema_version": 1,
            "target_profile": {"name": "builder"},
            "repo_path": ".",
            "selected_agent_profile": {"name": "default"},
            "selected_prompt_profile": {"name": "default"},
            "selected_verification_profile": {"name": "default"},
            "authority_mode": "PLANNED_ONLY",
            "model_policy": {},
            "governance": {
                "runtime_execution": "DISABLED",
                "goose_runtime_start": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "repo_map": {
            "kind": "builder_ii.repo_map",
            "schema_version": 1,
            "target_name": "builder",
            "repo_path": ".",
            "files": [],
            "governance": {
                "capability_state": "repo_map",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "context_pack": {
            "kind": "builder_ii.context_pack",
            "schema_version": 1,
            "target_name": "builder",
            "task": "test",
            "repo_map": {},
            "governance": {
                "capability_state": "context_pack",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "prepare_package": {
            "kind": "builder_ii.governed_prepare_package",
            "schema_version": 1,
            "target_name": "builder",
            "repo_path": ".",
            "task": "test",
            "output_dir": ".",
            "artifact_refs": [
                {"kind": "builder_ii.session_workflow_plan", "path": "session-workflow.json", "sha256": "f" * 64, "name": "session workflow plan"},
                {"kind": "builder_ii.goose_readonly_session_plan", "path": "goose-readonly-session.json", "sha256": "f" * 64, "name": "Goose read-only session plan"},
                {"kind": "builder_ii.verification_profile_report", "path": "verification-profile-report.json", "sha256": "f" * 64, "name": "verification profile report"},
                {"kind": "builder_ii.repo_map", "path": "repo-map.json", "sha256": "f" * 64, "name": "bounded repo map"},
                {"kind": "builder_ii.context_pack", "path": "context-pack.json", "sha256": "f" * 64, "name": "bounded context pack"},
                {"kind": "builder_ii.handoff_note", "path": "handoff-note.json", "sha256": "f" * 64, "name": "governed handoff note"},
            ],
            "package_state": "PREPARED_ONLY",
            "runtime_execution_performed": False,
            "target_repo_writes_performed": False,
            "governance": {
                "capability_state": "governed_prepare_package",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY",
                "target_repo_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "goose_activation": "DISABLED",
                "deepagents_delegation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "goose_projection": {
            "kind": "builder_ii.goose_projection",
            "schema_version": 1,
            "goose_native_surface": {
                "env": {
                    "GOOSE_PROVIDER": "unbound",
                    "GOOSE_MODEL": "unbound",
                    "GOOSE_PLANNER_PROVIDER": "",
                    "GOOSE_PLANNER_MODEL": "",
                    "BUILDER_MODEL_TIER": "",
                    "BUILDER_SESSION_MODE": "",
                },
                "recipe_path": "",
                "working_directory": ".",
                "session_name": "",
                "context_pack_ref": "",
            },
            "governance": {
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "goose_wrapper_plan": {
            "kind": "builder_ii.goose_wrapper_plan",
            "schema_version": 1,
            "operator_launch": {
                "requires_operator_execution": True,
                "executes_now": False,
            },
            "governance": {
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "verification_profile_report": {
            "kind": "builder_ii.verification_profile_report",
            "schema_version": 1,
            "target": "builder",
            "task": "test",
            "verification_profile": {
                "kind": "builder_ii.verification_profile",
                "schema_version": 1,
                "name": "builder_fast",
                "description": "test",
                "target": "builder",
                "task": "test",
                "compatible_targets": ["builder"],
                "purpose": "test",
                "proposed_commands": [],
                "required_evidence": [],
                "failure_mode": "test",
                "rollback_hint": "test",
                "governance": {
                    "capability_state": "verification_profile_artifact",
                    "runtime_execution": "DISABLED",
                    "model_execution": "DISABLED",
                    "shell_execution": "DISABLED",
                    "source_writes": "DISABLED",
                    "writes": "DISABLED",
                    "memory_mutation": "DISABLED",
                    "executes_commands": False,
                    "artifact_is_authority": False,
                    "core_workbench_coupling": "NONE",
                }
            },
            "governance": {
                "capability_state": "verification_profile_report",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "handoff_note": {
            "kind": "builder_ii.handoff_note",
            "schema_version": 1,
            "target_name": "builder",
            "status": "READY_FOR_REVIEW",
            "summary": "test",
            "changed_files_summary": [],
            "verification_summary": "test",
            "session_ref": {"kind": "builder_ii.session_workflow_plan", "path": "session-workflow.json", "sha256": "f" * 64, "name": "session workflow plan"},
            "goose_readonly_session_ref": {"kind": "builder_ii.goose_readonly_session_plan", "path": "goose-readonly-session.json", "sha256": "f" * 64, "name": "Goose read-only session plan"},
            "verification_report_ref": {"kind": "builder_ii.verification_profile_report", "path": "verification-profile-report.json", "sha256": "f" * 64, "name": "verification profile report"},
            "open_risks": [],
            "next_recommended_action": "test",
            "governance": {
                "capability_state": "handoff_note",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            }
        },
        "governance": {
            "runtime_execution": "DISABLED",
            "runtime_activation": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "deepagents_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }


def _governed_prepare_package() -> dict[str, Any]:
    return {
        "kind": GOVERNED_PREPARE_PACKAGE_KIND,
        "schema_version": 1,
        "target_name": "generic",
        "repo_path": ".",
        "task": "test task",
        "output_dir": ".",
        "artifact_refs": [
            {
                "kind": "builder_ii.session_workflow_plan",
                "path": "session-workflow.json",
                "sha256": "f" * 64,
                "name": "session workflow plan"
            }
        ],
        "package_state": "PREPARED_ONLY",
        "runtime_execution_performed": False,
        "target_repo_writes_performed": False,
        "governance": {
            "capability_state": "governed_prepare_package",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "goose_activation": "DISABLED",
            "deepagents_delegation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }


def _governed_prepare_package_summary() -> dict[str, Any]:
    return {
        "kind": GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
        "schema_version": 1,
        "package_manifest": "prepare-package.json",
        "package_directory": ".",
        "target_name": "generic",
        "repo_path": ".",
        "task": "test task",
        "package_state": "PREPARED_ONLY",
        "validation_state": "VALIDATED",
        "artifact_count": 1,
        "artifact_kinds": ["builder_ii.session_workflow_plan"],
        "artifacts": [
            {
                "kind": "builder_ii.session_workflow_plan",
                "path": "session-workflow.json",
                "sha256": "f" * 64,
                "name": "session workflow plan"
            }
        ],
        "runtime_execution_performed": False,
        "target_repo_writes_performed": False,
        "operator_report": {
            "summary": "Governed prepare package is structurally valid and artifact hashes match.",
            "verification_status": "Planned verification has not been executed by this summary.",
            "next_actions": ["Inspect generated artifacts."],
        },
        "governance": {
            "capability_state": "governed_prepare_package_summary",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT SUMMARY OUTPUT PATH",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "goose_activation": "DISABLED",
            "deepagents_delegation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }


def _orchestration_plan() -> dict[str, Any]:
    return create_orchestration_plan(target="generic", task="test task")


def _orchestration_dry_run() -> dict[str, Any]:
    from builder_ii.config import load_settings
    plan = _orchestration_plan()
    return create_orchestration_dry_run(load_settings(), plan, repo_path=".", generic_repo=Path("."))


def _runtime_activation_approval_spec() -> dict[str, Any]:
    projection = _goose_projection()
    wrapper_plan = create_goose_wrapper_plan(projection)
    return create_runtime_activation_approval_spec(wrapper_plan)


def _goose_readonly_session_plan() -> dict[str, Any]:
    from builder_ii.config import load_settings
    return create_goose_readonly_session_plan(load_settings(), "generic", task="test task")


def _goose_projection() -> dict[str, Any]:
    from builder_ii.config import load_settings
    config = _session_config()
    return create_goose_projection(load_settings(), config)


def _goose_wrapper_plan() -> dict[str, Any]:
    projection = _goose_projection()
    return create_goose_wrapper_plan(projection)


def _verification_profile_report() -> dict[str, Any]:
    from builder_ii.config import load_settings
    goose_plan = _goose_readonly_session_plan()
    return create_verification_profile_report(load_settings(), "generic", task="test task", goose_readonly_session_plan=goose_plan)


def _handoff_note() -> dict[str, Any]:
    return create_handoff_note(
        target_name="generic",
        status="READY_FOR_REVIEW",
        summary="summary text",
        changed_files_summary=[],
        verification_summary="verif summary",
        session_ref={"kind": "builder_ii.session_workflow_plan", "path": "session-workflow.json", "sha256": "f" * 64},
        goose_readonly_session_ref={"kind": "builder_ii.goose_readonly_session_plan", "path": "goose-readonly-session.json", "sha256": "f" * 64},
        verification_report_ref={"kind": "builder_ii.verification_profile_report", "path": "verification-profile-report.json", "sha256": "f" * 64},
        open_risks=[],
        next_recommended_action="none",
    )


def _deepagents_bridge_readiness_report() -> dict[str, Any]:
    return create_deepagents_bridge_readiness_report(
        target_profile="generic",
        agent_profile_compatibility_summary="summary",
        readiness_verdict="NOT_READY",
    )


def _goose_session() -> dict[str, Any]:
    from builder_ii.config import load_settings
    return create_goose_session_manifest(load_settings(), target_name="generic", agent_profile="repo_mapper")


def _handoff_artifact() -> dict[str, Any]:
    return create_handoff_artifact(target="generic", agent_profile="repo_mapper", task="test task", summary="summary")


def _session_config() -> dict[str, Any]:
    from builder_ii.config import load_settings
    return create_session_configuration(load_settings(), "generic", agent_profile_name="repo_mapper", task="test task", generic_repo=Path("."))


# ---------------------------------------------------------------------------
# Original closure tests
# ---------------------------------------------------------------------------

def test_recent_artifact_kinds_are_registered_in_both_registries() -> None:
    for kind in CLOSURE_KINDS:
        assert kind in INDEX_VALIDATORS
        assert kind in CHAIN_VALIDATORS


def test_recent_artifact_fixtures_validate_through_both_registries() -> None:
    plan = _plan()
    records = [plan, _adapter(plan), _measurement(), create_readonly_inspection_promotion_spec(target="builder")]

    for record in records:
        kind = record["kind"]
        assert INDEX_VALIDATORS[kind](record) == []
        assert CHAIN_VALIDATORS[kind](record) == []


def test_artifact_index_recognizes_recent_artifacts(tmp_path: Path) -> None:
    plan = _plan()
    for filename, artifact in {
        "research-plan.json": plan,
        "research-adapter.json": _adapter(plan),
        "performance.json": _measurement(),
        "readonly-spec.json": create_readonly_inspection_promotion_spec(target="builder"),
    }.items():
        _write(tmp_path / filename, artifact)

    index = create_artifact_index_record(tmp_path)

    assert index["counts"] == {"total": 4, "known": 4, "unknown": 0, "valid": 4, "invalid": 0}
    assert validate_artifact_index_record(index) == []


def test_research_adapter_link_resolves_to_plan(tmp_path: Path) -> None:
    plan = _plan()
    adapter = _adapter(plan)
    plan_path = tmp_path / "research-plan.json"
    adapter_path = tmp_path / "research-adapter.json"
    _write(plan_path, plan)
    _write(adapter_path, adapter)

    report = verify_artifact_chain([adapter_path])

    assert report["valid"] is True
    assert report["counts"]["links"] == 1
    assert report["counts"]["resolved_links"] == 1
    assert report["links"][0]["field"] == "research_plan"
    assert report["links"][0]["target_kind_expected"] == RESEARCH_PLAN_KIND


# ---------------------------------------------------------------------------
# PR AA — Governance artifact registry closure tests
# ---------------------------------------------------------------------------


def _artifact_chain_verification_report() -> dict[str, Any]:
    return {
        "kind": "builder_ii.artifact_chain_verification_report",
        "schema_version": 1,
        "status": "valid",
        "valid": True,
        "counts": {},
        "files": [],
        "links": [],
        "errors": [],
        "governance": {
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }


def _v0_release_manifest() -> dict[str, Any]:
    ref = create_artifact_ref(kind="builder_ii.session_workflow_plan", path="session-workflow.json", sha256="a"*64)
    prepare_ref = create_artifact_ref(kind="builder_ii.governed_prepare_package", path="prepare-package.json", sha256="a"*64)
    readonly_ref = create_artifact_ref(kind="builder_ii.goose_readonly_session_plan", path="goose-readonly-session.json", sha256="a"*64)
    report_ref = create_artifact_ref(kind="builder_ii.verification_profile_report", path="verification-profile-report.json", sha256="a"*64)
    repomap_ref = create_artifact_ref(kind="builder_ii.repo_map", path="repo-map.json", sha256="a"*64)
    context_ref = create_artifact_ref(kind="builder_ii.context_pack", path="context-pack.json", sha256="a"*64)
    handoff_ref = create_artifact_ref(kind="builder_ii.handoff_note", path="handoff-note.json", sha256="a"*64)
    bridge_ref = create_artifact_ref(kind="builder_ii.deepagents_bridge_readiness_report", path="deepagents-bridge-readiness.json", sha256="a"*64)
    spine_ref = create_artifact_ref(kind="builder_ii.convention_kernel_platform_bundle", path="platform-spine.json", sha256="a"*64)
    index_ref = create_artifact_ref(kind="builder_ii.artifact_index_record", path="artifact-index.json", sha256="")
    chain_ref = create_artifact_ref(kind="builder_ii.artifact_chain_verification_report", path="chain-verification-report.json", sha256="a"*64)

    return create_v0_release_manifest(
        governed_session_proof={
            "prepare_package_ref": prepare_ref,
            "session_workflow_ref": ref,
            "goose_readonly_session_ref": readonly_ref,
            "verification_report_ref": report_ref,
            "repo_map_ref": repomap_ref,
            "context_pack_ref": context_ref,
            "handoff_note_ref": handoff_ref,
            "deepagents_readiness_ref": bridge_ref,
        },
        platform_spine_proof={
            "platform_spine_ref": spine_ref,
        },
        audit_references={
            "artifact_index_ref": index_ref,
            "chain_verification_report_ref": chain_ref,
        }
    )


def test_governance_artifact_kinds_are_registered_in_both_registries() -> None:
    """Fails if any governance artifact kind from PR W/X/Y is missing from
    either the artifact index or chain verification registry."""
    for kind in GOVERNANCE_ARTIFACT_KINDS:
        assert kind in INDEX_VALIDATORS, f"{kind} missing from artifact index _VALIDATORS"
        assert kind in CHAIN_VALIDATORS, f"{kind} missing from chain verification VALIDATORS"


def test_governance_artifact_fixtures_validate_through_both_registries() -> None:
    """Creates valid fixtures for all governance artifact kinds and
    validates them through both registries."""
    fixtures = [
        _hitl_execution_request(),
        _hitl_execution_receipt(),
        _hitl_patch_application_spec(),
        _rollback_plan(),
        _rollback_receipt(),
        _execution_postflight_record(),
        _execution_verification_record(),
        _hitl_evidence_bundle(),
        _session_workflow_plan(),
        _convention_kernel_platform_bundle(),
        _governed_prepare_package(),
        _governed_prepare_package_summary(),
        _orchestration_plan(),
        _orchestration_dry_run(),
        _runtime_activation_approval_spec(),
        _goose_readonly_session_plan(),
        _goose_projection(),
        _goose_wrapper_plan(),
        _verification_profile_report(),
        _handoff_note(),
        _deepagents_bridge_readiness_report(),
        _goose_session(),
        _handoff_artifact(),
        _session_config(),
        _artifact_chain_verification_report(),
        _v0_release_manifest(),
    ]

    for record in fixtures:
        kind = record["kind"]
        idx_errors = INDEX_VALIDATORS[kind](record)
        chain_errors = CHAIN_VALIDATORS[kind](record)
        assert idx_errors == [], f"{kind} index validation errors: {idx_errors}"
        assert chain_errors == [], f"{kind} chain validation errors: {chain_errors}"


def test_governance_artifacts_recognized_by_artifact_index(tmp_path: Path) -> None:
    """Writes all governance artifact fixtures to disk and asserts the
    artifact index recognizes them all as known and valid."""
    fixtures = {
        "hitl-request.json": _hitl_execution_request(),
        "hitl-receipt.json": _hitl_execution_receipt(),
        "hitl-patch-spec.json": _hitl_patch_application_spec(),
        "rollback-plan.json": _rollback_plan(),
        "rollback-receipt.json": _rollback_receipt(),
        "postflight.json": _execution_postflight_record(),
        "verification.json": _execution_verification_record(),
        "hitl-evidence-bundle.json": _hitl_evidence_bundle(),
        "session-plan.json": _session_workflow_plan(),
        "platform-bundle.json": _convention_kernel_platform_bundle(),
        "prepare-package.json": _governed_prepare_package(),
        "prepare-package-summary.json": _governed_prepare_package_summary(),
        "orchestration-plan.json": _orchestration_plan(),
        "orchestration-dry-run.json": _orchestration_dry_run(),
        "runtime-activation.json": _runtime_activation_approval_spec(),
        "goose-readonly.json": _goose_readonly_session_plan(),
        "goose-projection.json": _goose_projection(),
        "goose-wrapper.json": _goose_wrapper_plan(),
        "verification-profile-report.json": _verification_profile_report(),
        "handoff-note.json": _handoff_note(),
        "deepagents-bridge.json": _deepagents_bridge_readiness_report(),
        "goose-session.json": _goose_session(),
        "handoff-artifact.json": _handoff_artifact(),
        "session-config.json": _session_config(),
        "chain-report.json": _artifact_chain_verification_report(),
        "release-manifest.json": _v0_release_manifest(),
    }
    for filename, artifact in fixtures.items():
        _write(tmp_path / filename, artifact)

    index = create_artifact_index_record(tmp_path)

    assert index["counts"]["invalid"] == 0, f"Artifact index validation failed: {index['issues']}"
    assert validate_artifact_index_record(index) == []

    indexed_kinds = {entry["kind"] for entry in index["artifacts"]}
    for kind in GOVERNANCE_ARTIFACT_KINDS:
        assert kind in indexed_kinds, f"{kind} not found in artifact index entries"


def test_governance_artifacts_are_not_chain_evidence() -> None:
    """Explicitly verifies that governance artifact kinds do not produce
    outbound chain references.  They are standalone design records.

    If a future PR adds cross-reference fields to any of these kinds,
    extract_references() should be updated and this test should be revised."""
    fixtures = [
        _hitl_execution_request(),
        _hitl_execution_receipt(),
        _hitl_patch_application_spec(),
        _rollback_plan(),
        _rollback_receipt(),
        _execution_postflight_record(),
        _execution_verification_record(),
        _session_workflow_plan(),
        _orchestration_plan(),
        _orchestration_dry_run(),
        _runtime_activation_approval_spec(),
        _goose_readonly_session_plan(),
        _goose_projection(),
        _goose_wrapper_plan(),
        _verification_profile_report(),
        _deepagents_bridge_readiness_report(),
        _goose_session(),
        _handoff_artifact(),
        _session_config(),
        _artifact_chain_verification_report(),
    ]

    for record in fixtures:
        refs = extract_references(record)
        assert refs == [], (
            f"{record['kind']} unexpectedly produced chain references: {refs}"
        )


def test_governance_artifacts_chain_verify_natively(tmp_path: Path) -> None:
    """Writes all governance artifacts and runs chain verification.
    All should be natively valid with zero links and zero errors."""
    fixtures = {
        "hitl-request.json": _hitl_execution_request(),
        "hitl-receipt.json": _hitl_execution_receipt(),
        "hitl-patch-spec.json": _hitl_patch_application_spec(),
        "rollback-plan.json": _rollback_plan(),
        "rollback-receipt.json": _rollback_receipt(),
        "postflight.json": _execution_postflight_record(),
        "verification.json": _execution_verification_record(),
        "session-plan.json": _session_workflow_plan(),
        "orchestration-plan.json": _orchestration_plan(),
        "orchestration-dry-run.json": _orchestration_dry_run(),
        "runtime-activation.json": _runtime_activation_approval_spec(),
        "goose-readonly.json": _goose_readonly_session_plan(),
        "goose-projection.json": _goose_projection(),
        "goose-wrapper.json": _goose_wrapper_plan(),
        "verification-profile-report.json": _verification_profile_report(),
        "deepagents-bridge.json": _deepagents_bridge_readiness_report(),
        "goose-session.json": _goose_session(),
        "handoff-artifact.json": _handoff_artifact(),
        "session-config.json": _session_config(),
        "chain-report.json": _artifact_chain_verification_report(),
    }
    paths = []
    for filename, artifact in fixtures.items():
        p = tmp_path / filename
        _write(p, artifact)
        paths.append(p)

    report = verify_artifact_chain(paths)

    assert report["valid"] is True, f"Chain validation failed: {report['errors']}"
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["links"] == 0
    assert report["counts"]["broken_links"] == 0


def test_docs_list_governance_artifact_kinds() -> None:
    """Reads ARTIFACT_INDEX.md and asserts all five governance artifact
    kinds appear in the documentation.  Fails if docs are out of sync."""
    docs_path = Path(__file__).resolve().parent.parent / "docs" / "ARTIFACT_INDEX.md"
    content = docs_path.read_text(encoding="utf-8")

    for kind in GOVERNANCE_ARTIFACT_KINDS:
        assert kind in content, (
            f"{kind} not found in docs/ARTIFACT_INDEX.md — "
            f"registry closure requires docs coverage"
        )
