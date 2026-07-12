from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Callable

from builder_ii.agent_profiles import (
    AGENT_PROFILE_RECORD_KIND,
    validate_agent_profile_record,
)
from builder_ii.approval_records import APPROVAL_RECORD_KIND, validate_approval_record
from builder_ii.artifact_memory import (
    MEMORY_ATOM_KIND,
    MEMORY_INDEX_KIND,
    MEMORY_RECONSTRUCTION_KIND,
    MEMORY_SEARCH_RESULT_KIND,
    validate_memory_atom,
    validate_memory_index,
    validate_memory_reconstruction,
    validate_memory_search_result,
)
from builder_ii.chain_summary_records import (
    CHAIN_SUMMARY_RECORD_KIND,
    validate_chain_summary_record,
)
from builder_ii.code_vault.bench import (
    CODE_VAULT_BENCH_REPORT_KIND,
    validate_code_vault_bench_report,
)
from builder_ii.code_vault.context_bridge import (
    CONTEXT_PROJECTION_KIND,
    validate_context_projection,
)
from builder_ii.code_vault.extractor_manifest import (
    EXTRACTOR_MANIFEST_KIND,
    validate_extractor_manifest,
)
from builder_ii.code_vault.hierarchy import (
    HIERARCHICAL_FRAME_KIND,
    hierarchical_frame_from_dict,
    validate_hierarchical_frame,
)
from builder_ii.code_vault.recall import (
    RECALL_REPORT_KIND,
    validate_recall_report,
)
from builder_ii.code_vault.reports.linter import (
    LINTER_REPORT_KIND,
    validate_linter_report,
)
from builder_ii.code_vault.evidence_correction import (
    EVIDENCE_RELATION_KIND,
    validate_evidence_relation,
)
from builder_ii.code_vault.reconstruction import (
    RECONSTRUCTION_KIND,
    validate_reconstruction,
)
from builder_ii.code_vault.relation_field import (
    RELATION_FIELD_KIND,
    validate_relation_field,
)
from builder_ii.code_vault.structural_field import (
    STRUCTURAL_FIELD_KIND,
    validate_structural_field,
)
from builder_ii.code_vault.utility_eval_record import (
    UTILITY_EVAL_RECORD_KIND,
    validate_utility_eval_record,
)
from builder_ii.code_vault.utility_task_registry import (
    UTILITY_TASK_REGISTRY_KIND,
    validate_utility_task_registry,
)
from builder_ii.code_vault_receipt_bridge import (
    CODE_VAULT_CORROBORATION_RECORD_KIND,
    validate_code_vault_corroboration_record,
)
from builder_ii.context_pack import (
    CONTEXT_PACK_RECORD_KIND,
    validate_context_pack_record,
)
from builder_ii.context_packs import (
    CONTEXT_PACK_KIND,
    validate_context_pack,
)
from builder_ii.convention_kernel import (
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
    validate_convention_kernel_platform_bundle,
)
from builder_ii.deepagents_bridge_readiness import (
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    validate_deepagents_bridge_readiness_report,
)
from builder_ii.deepagents_execution import (
    DEEPAGENTS_BACKEND_READINESS_GATE_KIND,
    DEEPAGENTS_CHECKPOINT_KIND,
    DEEPAGENTS_EVENT_LEDGER_KIND,
    DEEPAGENTS_EVENT_RECORD_KIND,
    DEEPAGENTS_EVIDENCE_BUNDLE_KIND,
    DEEPAGENTS_EXECUTION_APPROVAL_KIND,
    DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    DEEPAGENTS_REPLAY_REPORT_KIND,
    DEEPAGENTS_RUN_ENVELOPE_KIND,
    validate_deepagents_backend_readiness_gate,
    validate_deepagents_checkpoint,
    validate_deepagents_event_ledger,
    validate_deepagents_event_record,
    validate_deepagents_evidence_bundle,
    validate_deepagents_execution_approval,
    validate_deepagents_execution_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_replay_report,
    validate_deepagents_run_envelope,
)
from builder_ii.deepagents_policy import (
    DEEPAGENTS_POLICY_KIND,
    validate_deepagents_policy_artifact,
)
from builder_ii.deepagents_readiness import (
    DEEPAGENTS_READINESS_KIND,
    validate_deepagents_readiness_artifact,
)
from builder_ii.deepagents_work_artifacts import (
    DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND,
    DEEPAGENTS_HUMAN_GATE_REQUEST_KIND,
    DEEPAGENTS_PROPOSAL_RESULT_KIND,
    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
    DEEPAGENTS_SUBAGENT_RESULT_KIND,
    DEEPAGENTS_SUBAGENT_REVIEW_KIND,
    DEEPAGENTS_WORK_PLAN_KIND,
    DEEPAGENTS_WORK_VALIDATION_REPORT_KIND,
    validate_deepagents_blocked_action_record,
    validate_deepagents_human_gate_request,
    validate_deepagents_proposal_result,
    validate_deepagents_subagent_assignment,
    validate_deepagents_subagent_result,
    validate_deepagents_subagent_review,
    validate_deepagents_work_plan,
    validate_deepagents_work_validation_report,
)
from builder_ii.demo_loop import (
    DEMO_PLANNER_KIND,
    DEMO_PREFLIGHT_KIND,
    DEMO_REPORT_KIND,
    DEMO_VERIFICATION_RECEIPT_KIND,
    validate_demo_planner,
    validate_demo_preflight,
    validate_demo_report,
    validate_demo_verification_receipt,
)
from builder_ii.event_ledger import (
    EVENT_LEDGER_KIND,
    EVENT_RECORD_KIND,
    LEDGER_REPLAY_REPORT_KIND,
    validate_event_ledger,
    validate_event_record,
    validate_ledger_replay_report,
)
from builder_ii.execution_candidate_manifest import (
    EXECUTION_CANDIDATE_MANIFEST_KIND,
    EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND,
    validate_execution_candidate_manifest,
    validate_execution_candidate_manifest_validation_report,
)
from builder_ii.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
    validate_execution_postflight_record,
    validate_execution_verification_record,
)
from builder_ii.gate_battery_receipt import (
    GATE_BATTERY_RECEIPT_KIND,
    validate_gate_battery_receipt,
)
from builder_ii.git_state import GIT_STATE_RECORD_KIND, validate_git_state_record
from builder_ii.goose_command_proposal import (
    GOOSE_COMMAND_PROPOSAL_KIND,
    validate_goose_command_proposal,
)
from builder_ii.goose_projection import (
    GOOSE_PROJECTION_KIND,
    validate_goose_projection,
)
from builder_ii.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    validate_goose_readonly_session_plan,
)
from builder_ii.goose_session import (
    GOOSE_SESSION_KIND,
    validate_goose_session_manifest,
)
from builder_ii.goose_wrapper_plan import (
    GOOSE_WRAPPER_PLAN_KIND,
    validate_goose_wrapper_plan,
)
from builder_ii.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
    validate_governed_prepare_package,
    validate_governed_prepare_package_summary,
)
from builder_ii.handoff_artifacts import (
    HANDOFF_KIND,
    validate_handoff_artifact,
)
from builder_ii.handoff_bundle_records import (
    HANDOFF_BUNDLE_RECORD_KIND,
    validate_handoff_bundle_record,
)
from builder_ii.handoff_notes import (
    HANDOFF_NOTE_KIND,
    validate_handoff_note,
)
from builder_ii.hitl_chain_binding import (
    HITL_CHAIN_BINDING_KIND,
    validate_hitl_chain_binding,
)
from builder_ii.hitl_evidence_bundle import (
    HITL_EVIDENCE_BUNDLE_KIND,
    validate_hitl_evidence_bundle,
)
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
    validate_hitl_execution_receipt,
    validate_hitl_execution_request,
)
from builder_ii.hitl_patch_apply import (
    PATCH_APPLY_RECEIPT_KIND,
    ROLLBACK_BUNDLE_KIND,
    validate_patch_apply_receipt,
    validate_rollback_bundle,
)
from builder_ii.hitl_patch_approval import (
    HITL_PATCH_APPROVAL_KIND,
    validate_hitl_patch_approval,
)
from builder_ii.hitl_patch_ledger import (
    HITL_PATCH_LEDGER_RECORD_KIND,
    validate_hitl_patch_ledger_record,
)
from builder_ii.hitl_patch_proposal import (
    HITL_PATCH_PROPOSAL_KIND,
    validate_hitl_patch_proposal,
)
from builder_ii.hitl_promotion_artifacts import (
    HITL_APPROVAL_BOUNDARY_KIND,
    HITL_PROMOTION_DECISION_KIND,
    HITL_PROMOTION_REQUEST_KIND,
    HITL_PROMOTION_REVIEW_KIND,
    HITL_PROMOTION_VALIDATION_REPORT_KIND,
    HITL_REJECTION_RECORD_KIND,
    validate_hitl_approval_boundary,
    validate_hitl_promotion_decision,
    validate_hitl_promotion_request,
    validate_hitl_promotion_review,
    validate_hitl_promotion_validation_report,
    validate_hitl_rejection_record,
)
from builder_ii.hitl_rollback_approval import (
    HITL_ROLLBACK_APPROVAL_KIND,
    validate_hitl_rollback_approval,
)
from builder_ii.hitl_verification_candidate import (
    HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND,
    validate_hitl_verification_execution_candidate,
)
from builder_ii.model_capabilities import (
    MODEL_CAPABILITY_REGISTRY_KIND,
    validate_model_capability_registry,
)
from builder_ii.model_client_registry import (
    MODEL_CLIENT_REGISTRY_KIND,
    validate_model_client_registry,
)
from builder_ii.model_routing_policy import (
    MODEL_ROUTING_POLICY_KIND,
    MODEL_ROUTING_RECOMMENDATION_KIND,
    validate_model_routing_policy,
    validate_model_routing_recommendation,
)
from builder_ii.orchestration_assignment import (
    AGENT_ASSIGNMENT_PLAN_KIND,
    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
    ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND,
    validate_agent_assignment_plan,
    validate_orchestration_assignment_dry_run,
    validate_orchestration_assignment_plan,
    validate_orchestration_assignment_validation_report,
)
from builder_ii.orchestration_dry_run import (
    ORCHESTRATION_DRY_RUN_KIND,
    validate_orchestration_dry_run,
)
from builder_ii.orchestration_lane_policy import (
    LANE_POLICY_KIND,
    validate_orchestration_lane_policy_artifact,
)
from builder_ii.orchestration_obligation import (
    OBLIGATION_KIND,
    validate_orchestration_obligation,
)
from builder_ii.orchestration_plan import (
    ORCHESTRATION_PLAN_KIND,
    validate_orchestration_plan,
)
from builder_ii.performance_measurements import (
    PERFORMANCE_MEASUREMENT_KIND,
    validate_performance_measurement_record,
)
from builder_ii.preflight_records import (
    PREFLIGHT_RECORD_KIND,
    validate_preflight_record,
)
from builder_ii.profile_pack import PROFILE_PACK_KIND, validate_profile_pack
from builder_ii.profile_pack_dry_run import (
    PROFILE_PACK_DRY_RUN_KIND,
    validate_profile_pack_dry_run,
)
from builder_ii.profile_pack_manifest import (
    PROFILE_PACK_MANIFEST_KIND,
    validate_profile_pack_manifest,
)
from builder_ii.profile_pack_render_plan import (
    PROFILE_PACK_RENDER_PLAN_KIND,
    validate_profile_pack_render_plan,
)
from builder_ii.profile_pack_validation_report import (
    PROFILE_PACK_VALIDATION_REPORT_KIND,
    validate_profile_pack_validation_report,
)
from builder_ii.promotion_decision_records import (
    PROMOTION_DECISION_RECORD_KIND,
    validate_promotion_decision_record,
)
from builder_ii.promotion_readiness_records import (
    PROMOTION_READINESS_RECORD_KIND,
    validate_promotion_readiness_record,
)
from builder_ii.readonly_founder_demo import (
    TARGET_INSPECTION_PLAN_KIND,
    TARGET_PATCH_PROPOSAL_KIND,
    TARGET_VERIFICATION_PLAN_KIND,
    validate_target_inspection_plan,
    validate_target_patch_proposal,
    validate_target_verification_plan,
)
from builder_ii.readonly_inspection_promotion import (
    READONLY_INSPECTION_PROMOTION_SPEC_KIND,
    validate_readonly_inspection_promotion_spec,
)
from builder_ii.readonly_inspection_reports import (
    READONLY_INSPECTION_REPORT_KIND,
    validate_readonly_inspection_report,
)
from builder_ii.receipt_records import RECEIPT_RECORD_KIND, validate_receipt_record
from builder_ii.receive_records import RECEIVE_RECORD_KIND, validate_receive_record
from builder_ii.release_manifest import (
    V0_RELEASE_MANIFEST_KIND,
    validate_v0_release_manifest,
)
from builder_ii.repo_map import (
    REPO_MAP_KIND,
    validate_repo_map,
)
from builder_ii.research_adapters import (
    RESEARCH_ADAPTER_KIND,
    validate_research_adapter_artifact,
)
from builder_ii.research_plans import (
    RESEARCH_PLAN_KIND,
    validate_research_plan_artifact,
)
from builder_ii.rollback_artifacts import (
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    validate_rollback_plan,
    validate_rollback_receipt,
)
from builder_ii.runtime_activation_approval import (
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
    validate_runtime_activation_approval_spec,
)
from builder_ii.session_config import (
    SESSION_CONFIG_KIND,
    validate_session_configuration,
)
from builder_ii.session_workflow import (
    SESSION_WORKFLOW_PLAN_KIND,
    validate_session_workflow_plan,
)
from builder_ii.state_ledger_records import (
    STATE_LEDGER_RECORD_KIND,
    validate_state_ledger_record,
)
from builder_ii.target_profiles import (
    TARGET_PROFILE_ARTIFACT_KIND,
    validate_target_profile_artifact,
)
from builder_ii.verification_execution_approval import (
    VERIFICATION_EXECUTION_APPROVAL_KIND,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_plan import (
    VERIFICATION_EXECUTION_PLAN_KIND,
    validate_verification_execution_plan_artifact,
)
from builder_ii.verification_execution_receipt import (
    VERIFICATION_EXECUTION_RECEIPT_KIND,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.verification_profile_reports import (
    VERIFICATION_PROFILE_REPORT_KIND,
    validate_verification_profile_report,
)
from builder_ii.verification_profiles import (
    VERIFICATION_ARTIFACT_KIND,
    validate_profile_artifact,
)
from builder_ii.verification_promotion_gate import (
    PROMOTION_EVIDENCE_KIND,
    validate_promotion_evidence,
)
from builder_ii.workflow_records import (
    WORKFLOW_SESSION_KIND,
    WORKFLOW_STATUS_KIND,
    WORKFLOW_TRANSITION_KIND,
    validate_workflow_session,
    validate_workflow_status,
    validate_workflow_transition,
)

ARTIFACT_INDEX_RECORD_KIND = "builder_ii.artifact_index_record"
ARTIFACT_INDEX_RECORD_SCHEMA_VERSION = 1
_SNAPSHOT_RECORD_KIND = "builder_ii.snapshot_record"
_GRANTS_RUNTIME_AUTHORITY = "".join(("grants_", "run", "time_", "authority"))
_RUNTIME_EXECUTION = "".join(("run", "time_", "execution"))
_MODEL_EXECUTION = "".join(("model_", "execution"))
_SOURCE_WRITES = "".join(("source_", "writes"))
_MEMORY_MUTATION = "".join(("memory_", "mutation"))


_ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND = "builder_ii.artifact_chain_verification_report"


def _validate_chain_verification_report(record: Any) -> list[str]:
    from builder_ii.artifact_chain_verification import (
        validate_artifact_chain_verification_report,
    )

    return validate_artifact_chain_verification_report(record)


def _validate_snapshot_record(record: Any) -> list[str]:
    from builder_ii.snapshot_records import validate_snapshot_record

    return validate_snapshot_record(record)


def _validate_hierarchical_frame_record(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["hierarchical frame must be a JSON object"]
    return validate_hierarchical_frame(hierarchical_frame_from_dict(record))


_VALIDATORS: dict[str, Callable[[Any], list[str]]] = {
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
    _SNAPSHOT_RECORD_KIND: _validate_snapshot_record,
    TARGET_PROFILE_ARTIFACT_KIND: validate_target_profile_artifact,
    VERIFICATION_ARTIFACT_KIND: validate_profile_artifact,
    VERIFICATION_EXECUTION_PLAN_KIND: validate_verification_execution_plan_artifact,
    VERIFICATION_EXECUTION_APPROVAL_KIND: validate_verification_execution_approval_artifact,
    VERIFICATION_EXECUTION_RECEIPT_KIND: validate_verification_execution_receipt_artifact,
    PROMOTION_EVIDENCE_KIND: validate_promotion_evidence,
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
    HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND: validate_hitl_verification_execution_candidate,
    HITL_PATCH_PROPOSAL_KIND: validate_hitl_patch_proposal,
    HITL_PATCH_APPROVAL_KIND: validate_hitl_patch_approval,
    HITL_ROLLBACK_APPROVAL_KIND: validate_hitl_rollback_approval,
    HITL_PATCH_LEDGER_RECORD_KIND: validate_hitl_patch_ledger_record,
    PATCH_APPLY_RECEIPT_KIND: validate_patch_apply_receipt,
    ROLLBACK_BUNDLE_KIND: validate_rollback_bundle,
    ROLLBACK_PLAN_KIND: validate_rollback_plan,
    ROLLBACK_RECEIPT_KIND: validate_rollback_receipt,
    EXECUTION_POSTFLIGHT_RECORD_KIND: validate_execution_postflight_record,
    EXECUTION_VERIFICATION_RECORD_KIND: validate_execution_verification_record,
    HITL_EVIDENCE_BUNDLE_KIND: validate_hitl_evidence_bundle,
    HITL_CHAIN_BINDING_KIND: validate_hitl_chain_binding,
    SESSION_WORKFLOW_PLAN_KIND: validate_session_workflow_plan,
    GOOSE_READONLY_SESSION_PLAN_KIND: validate_goose_readonly_session_plan,
    HANDOFF_NOTE_KIND: validate_handoff_note,
    MEMORY_ATOM_KIND: validate_memory_atom,
    MEMORY_INDEX_KIND: validate_memory_index,
    MEMORY_RECONSTRUCTION_KIND: validate_memory_reconstruction,
    MEMORY_SEARCH_RESULT_KIND: validate_memory_search_result,
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND: validate_deepagents_bridge_readiness_report,
    DEEPAGENTS_POLICY_KIND: validate_deepagents_policy_artifact,
    DEEPAGENTS_READINESS_KIND: validate_deepagents_readiness_artifact,
    REPO_MAP_KIND: validate_repo_map,
    HIERARCHICAL_FRAME_KIND: _validate_hierarchical_frame_record,
    EXTRACTOR_MANIFEST_KIND: validate_extractor_manifest,
    LINTER_REPORT_KIND: validate_linter_report,
    STRUCTURAL_FIELD_KIND: validate_structural_field,
    RELATION_FIELD_KIND: validate_relation_field,
    EVIDENCE_RELATION_KIND: validate_evidence_relation,
    RECONSTRUCTION_KIND: validate_reconstruction,
    UTILITY_TASK_REGISTRY_KIND: validate_utility_task_registry,
    UTILITY_EVAL_RECORD_KIND: validate_utility_eval_record,
    CONTEXT_PROJECTION_KIND: validate_context_projection,
    RECALL_REPORT_KIND: validate_recall_report,
    CODE_VAULT_BENCH_REPORT_KIND: validate_code_vault_bench_report,
    CONTEXT_PACK_KIND: validate_context_pack,
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND: validate_convention_kernel_platform_bundle,
    GOVERNED_PREPARE_PACKAGE_KIND: validate_governed_prepare_package,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND: validate_governed_prepare_package_summary,
    ORCHESTRATION_PLAN_KIND: validate_orchestration_plan,
    ORCHESTRATION_DRY_RUN_KIND: validate_orchestration_dry_run,
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND: validate_runtime_activation_approval_spec,
    GOOSE_SESSION_KIND: validate_goose_session_manifest,
    HANDOFF_KIND: validate_handoff_artifact,
    VERIFICATION_PROFILE_REPORT_KIND: validate_verification_profile_report,
    SESSION_CONFIG_KIND: validate_session_configuration,
    GOOSE_PROJECTION_KIND: validate_goose_projection,
    GOOSE_WRAPPER_PLAN_KIND: validate_goose_wrapper_plan,
    V0_RELEASE_MANIFEST_KIND: validate_v0_release_manifest,
    MODEL_CAPABILITY_REGISTRY_KIND: validate_model_capability_registry,
    PROFILE_PACK_KIND: validate_profile_pack,
    PROFILE_PACK_MANIFEST_KIND: validate_profile_pack_manifest,
    PROFILE_PACK_RENDER_PLAN_KIND: validate_profile_pack_render_plan,
    PROFILE_PACK_DRY_RUN_KIND: validate_profile_pack_dry_run,
    PROFILE_PACK_VALIDATION_REPORT_KIND: validate_profile_pack_validation_report,
    MODEL_CLIENT_REGISTRY_KIND: validate_model_client_registry,
    MODEL_ROUTING_POLICY_KIND: validate_model_routing_policy,
    MODEL_ROUTING_RECOMMENDATION_KIND: validate_model_routing_recommendation,
    AGENT_ASSIGNMENT_PLAN_KIND: validate_agent_assignment_plan,
    ORCHESTRATION_ASSIGNMENT_PLAN_KIND: validate_orchestration_assignment_plan,
    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND: validate_orchestration_assignment_dry_run,
    ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND: validate_orchestration_assignment_validation_report,
    DEEPAGENTS_WORK_PLAN_KIND: validate_deepagents_work_plan,
    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND: validate_deepagents_subagent_assignment,
    DEEPAGENTS_SUBAGENT_RESULT_KIND: validate_deepagents_subagent_result,
    DEEPAGENTS_SUBAGENT_REVIEW_KIND: validate_deepagents_subagent_review,
    DEEPAGENTS_HUMAN_GATE_REQUEST_KIND: validate_deepagents_human_gate_request,
    DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND: validate_deepagents_blocked_action_record,
    DEEPAGENTS_PROPOSAL_RESULT_KIND: validate_deepagents_proposal_result,
    DEEPAGENTS_WORK_VALIDATION_REPORT_KIND: validate_deepagents_work_validation_report,
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
    HITL_PROMOTION_REQUEST_KIND: validate_hitl_promotion_request,
    HITL_PROMOTION_REVIEW_KIND: validate_hitl_promotion_review,
    HITL_PROMOTION_DECISION_KIND: validate_hitl_promotion_decision,
    HITL_APPROVAL_BOUNDARY_KIND: validate_hitl_approval_boundary,
    HITL_REJECTION_RECORD_KIND: validate_hitl_rejection_record,
    HITL_PROMOTION_VALIDATION_REPORT_KIND: validate_hitl_promotion_validation_report,
    EXECUTION_CANDIDATE_MANIFEST_KIND: validate_execution_candidate_manifest,
    EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND: validate_execution_candidate_manifest_validation_report,
    WORKFLOW_SESSION_KIND: validate_workflow_session,
    WORKFLOW_STATUS_KIND: validate_workflow_status,
    WORKFLOW_TRANSITION_KIND: validate_workflow_transition,
    EVENT_RECORD_KIND: validate_event_record,
    EVENT_LEDGER_KIND: validate_event_ledger,
    LEDGER_REPLAY_REPORT_KIND: validate_ledger_replay_report,
    TARGET_INSPECTION_PLAN_KIND: validate_target_inspection_plan,
    TARGET_PATCH_PROPOSAL_KIND: validate_target_patch_proposal,
    TARGET_VERIFICATION_PLAN_KIND: validate_target_verification_plan,
    DEMO_PLANNER_KIND: validate_demo_planner,
    DEMO_PREFLIGHT_KIND: validate_demo_preflight,
    DEMO_VERIFICATION_RECEIPT_KIND: validate_demo_verification_receipt,
    DEMO_REPORT_KIND: validate_demo_report,
    OBLIGATION_KIND: validate_orchestration_obligation,
    LANE_POLICY_KIND: validate_orchestration_lane_policy_artifact,
    _ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND: _validate_chain_verification_report,
    CODE_VAULT_CORROBORATION_RECORD_KIND: validate_code_vault_corroboration_record,
    GATE_BATTERY_RECEIPT_KIND: validate_gate_battery_receipt,
}


def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _digest_bytes(raw)


def _artifact_entry(path: Path, root: Path) -> dict[str, Any]:
    rel_path = path.relative_to(root).as_posix()
    raw = path.read_bytes()
    data = json_lib.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        return {
            "path": rel_path,
            "sha256": _digest_bytes(raw),
            "bytes": len(raw),
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": ["artifact must be a JSON object"],
        }
    kind = str(data.get("kind", ""))
    validator = _VALIDATORS.get(kind)
    errors = ["unknown artifact kind"] if validator is None else validator(data)
    return {
        "path": rel_path,
        "sha256": _json_digest(data),
        "bytes": len(raw),
        "kind": kind,
        "schema_version": data.get("schema_version"),
        "known": validator is not None,
        "valid": errors == [],
        "errors": errors,
    }


def _safe_entry(path: Path, root: Path) -> dict[str, Any]:
    rel_path = path.relative_to(root).as_posix()
    try:
        return _artifact_entry(path, root)
    except json_lib.JSONDecodeError as exc:
        raw = path.read_bytes()
        return {
            "path": rel_path,
            "sha256": _digest_bytes(raw),
            "bytes": len(raw),
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": [f"invalid JSON: {exc}"],
        }
    except UnicodeDecodeError as exc:
        raw = path.read_bytes()
        return {
            "path": rel_path,
            "sha256": _digest_bytes(raw),
            "bytes": len(raw),
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": [f"artifact is not utf-8: {exc}"],
        }
    except Exception as exc:
        return {
            "path": rel_path,
            "sha256": "",
            "bytes": 0,
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": [f"failed to read artifact: {exc}"],
        }


def create_artifact_index_record(
    root: Path, *, recursive: bool = False, exclude_paths: tuple[Path, ...] = ()
) -> dict[str, Any]:
    root = root.resolve()
    excluded = tuple(path.resolve() for path in exclude_paths)
    entries: list[dict[str, Any]] = []
    issues: list[str] = []
    if not root.exists():
        issues.append(f"directory not found: {root}")
    elif not root.is_dir():
        issues.append(f"not a directory: {root}")
    else:
        paths = sorted(root.rglob("*.json") if recursive else root.glob("*.json"))
        entries = [
            _safe_entry(path, root)
            for path in paths
            if path.is_file() and not any(path.resolve().is_relative_to(excluded_path) for excluded_path in excluded)
        ]
    invalid_count = sum(1 for entry in entries if not entry.get("valid"))
    known_count = sum(1 for entry in entries if entry.get("known"))
    return {
        "kind": ARTIFACT_INDEX_RECORD_KIND,
        "schema_version": ARTIFACT_INDEX_RECORD_SCHEMA_VERSION,
        "capability_state": "artifact_index_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "root": str(root),
        "recursive": recursive,
        "excluded_paths": [str(path) for path in excluded],
        "status": "complete" if not issues and invalid_count == 0 else "incomplete",
        "complete": not issues and invalid_count == 0,
        "issues": issues,
        "counts": {
            "total": len(entries),
            "known": known_count,
            "unknown": len(entries) - known_count,
            "valid": len(entries) - invalid_count,
            "invalid": invalid_count,
        },
        "artifacts": entries,
        "allowed_actions": [
            "read_json_artifact_metadata",
            "validate_known_artifacts",
            "render_artifact_index",
        ],
        "performed_actions": [],
        _GRANTS_RUNTIME_AUTHORITY: False,
        "grants_action_authority": False,
        "governance": build_standard_governance("artifact_index_record"),
    }


def dumps_artifact_index_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_artifact_index_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_artifact_index_record(record), encoding="utf-8")


def validate_artifact_index_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["artifact index record must be a JSON object"]
    if record.get("kind") != ARTIFACT_INDEX_RECORD_KIND:
        errors.append(f"kind must be {ARTIFACT_INDEX_RECORD_KIND}")
    if record.get("schema_version") != ARTIFACT_INDEX_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ARTIFACT_INDEX_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED or NOT_AUTHORIZED")
    if record.get("status") not in ("complete", "incomplete"):
        errors.append("status must be complete or incomplete")
    if record.get("complete") is not (record.get("status") == "complete"):
        errors.append("complete must match status")
    if not isinstance(record.get("issues"), list):
        errors.append("issues must be a list")
    if not isinstance(record.get("counts"), dict):
        errors.append("counts must be an object")
    if not isinstance(record.get("artifacts"), list):
        errors.append("artifacts must be a list")
    for key in (_GRANTS_RUNTIME_AUTHORITY, "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "artifact_index_record"))
    return errors


def validate_artifact_index_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_artifact_index_record(data)
