from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Callable

# Import kinds and validators
from builder_ii.approval_records import APPROVAL_RECORD_KIND, validate_approval_record
from builder_ii.artifact_index_records import (
    ARTIFACT_INDEX_RECORD_KIND,
    validate_artifact_index_record,
)
from builder_ii.chain_summary_records import (
    CHAIN_SUMMARY_RECORD_KIND,
    validate_chain_summary_record,
)
from builder_ii.goose_command_proposal import (
    GOOSE_COMMAND_PROPOSAL_KIND,
    validate_goose_command_proposal,
)
from builder_ii.handoff_bundle_records import (
    HANDOFF_BUNDLE_RECORD_KIND,
    validate_handoff_bundle_record,
)
from builder_ii.preflight_records import (
    PREFLIGHT_RECORD_KIND,
    validate_preflight_record,
)
from builder_ii.promotion_decision_records import (
    PROMOTION_DECISION_RECORD_KIND,
    validate_promotion_decision_record,
)
from builder_ii.promotion_readiness_records import (
    PROMOTION_READINESS_RECORD_KIND,
    validate_promotion_readiness_record,
)
from builder_ii.receipt_records import RECEIPT_RECORD_KIND, validate_receipt_record
from builder_ii.receive_records import RECEIVE_RECORD_KIND, validate_receive_record
from builder_ii.snapshot_records import SNAPSHOT_RECORD_KIND, validate_snapshot_record
from builder_ii.state_ledger_records import (
    STATE_LEDGER_RECORD_KIND,
    validate_state_ledger_record,
)
from builder_ii.agent_profiles import (
    AGENT_PROFILE_RECORD_KIND,
    validate_agent_profile_record,
)
from builder_ii.context_pack import (
    CONTEXT_PACK_RECORD_KIND,
    validate_context_pack_record,
)
from builder_ii.target_profiles import (
    TARGET_PROFILE_ARTIFACT_KIND,
    validate_target_profile_artifact,
)
from builder_ii.verification_profiles import (
    VERIFICATION_ARTIFACT_KIND,
    validate_profile_artifact,
)
from builder_ii.verification_execution_plan import (
    VERIFICATION_EXECUTION_PLAN_KIND,
    validate_verification_execution_plan_artifact,
)
from builder_ii.verification_execution_approval import (
    VERIFICATION_EXECUTION_APPROVAL_KIND,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_receipt import (
    VERIFICATION_EXECUTION_RECEIPT_KIND,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.verification_execution_ledger import (
    VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND,
    VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND,
    VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
    validate_verification_execution_ledger_integrity_report,
    validate_verification_execution_ledger_reconstruction_report,
    validate_verification_execution_ledger_record,
)
from builder_ii.git_state import GIT_STATE_RECORD_KIND, validate_git_state_record
from builder_ii.research_plans import (
    RESEARCH_PLAN_KIND,
    validate_research_plan_artifact,
)
from builder_ii.research_adapters import (
    RESEARCH_ADAPTER_KIND,
    validate_research_adapter_artifact,
)
from builder_ii.performance_measurements import (
    PERFORMANCE_MEASUREMENT_KIND,
    validate_performance_measurement_record,
)
from builder_ii.readonly_inspection_promotion import (
    READONLY_INSPECTION_PROMOTION_SPEC_KIND,
    validate_readonly_inspection_promotion_spec,
)
from builder_ii.readonly_inspection_reports import (
    READONLY_INSPECTION_REPORT_KIND,
    validate_readonly_inspection_report,
)
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_REQUEST_KIND,
    validate_hitl_execution_request,
)
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    validate_hitl_execution_receipt,
)
from builder_ii.hitl_verification_candidate import (
    HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND,
    validate_hitl_verification_execution_candidate,
)
from builder_ii.hitl_patch_proposal import (
    HITL_PATCH_PROPOSAL_KIND,
    validate_hitl_patch_proposal,
)
from builder_ii.rollback_artifacts import ROLLBACK_PLAN_KIND, validate_rollback_plan
from builder_ii.rollback_artifacts import (
    ROLLBACK_RECEIPT_KIND,
    validate_rollback_receipt,
)
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
from builder_ii.hitl_chain_binding import (
    HITL_CHAIN_BINDING_KIND,
    HITL_CHAIN_BINDING_SLOT_FIELDS,
    HITL_CHAIN_BINDING_SLOT_KIND_MAP,
    validate_hitl_chain_binding,
)
from builder_ii.session_workflow import (
    SESSION_WORKFLOW_PLAN_KIND,
    validate_session_workflow_plan,
)
from builder_ii.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    validate_goose_readonly_session_plan,
)

from builder_ii.handoff_notes import (
    HANDOFF_NOTE_KIND,
    validate_handoff_note,
)
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
from builder_ii.goose_session import (
    GOOSE_SESSION_KIND,
    validate_goose_session_manifest,
)
from builder_ii.handoff_artifacts import HANDOFF_KIND, validate_handoff_artifact
from builder_ii.verification_profile_reports import (
    VERIFICATION_PROFILE_REPORT_KIND,
    validate_verification_profile_report,
)
from builder_ii.session_config import (
    SESSION_CONFIG_KIND,
    validate_session_configuration,
)
from builder_ii.goose_projection import GOOSE_PROJECTION_KIND, validate_goose_projection
from builder_ii.goose_wrapper_plan import (
    GOOSE_WRAPPER_PLAN_KIND,
    validate_goose_wrapper_plan,
)
from builder_ii.orchestration_plan import (
    ORCHESTRATION_PLAN_KIND,
    validate_orchestration_plan,
)
from builder_ii.deepagents_bridge_readiness import (
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    validate_deepagents_bridge_readiness_report,
)
from builder_ii.deepagents_policy import (
    DEEPAGENTS_POLICY_KIND,
    validate_deepagents_policy_artifact,
)
from builder_ii.deepagents_readiness import (
    DEEPAGENTS_READINESS_KIND,
    validate_deepagents_readiness_artifact,
)
from builder_ii.repo_map import REPO_MAP_KIND, validate_repo_map
from builder_ii.context_packs import CONTEXT_PACK_KIND, validate_context_pack
from builder_ii.convention_kernel import (
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
    validate_convention_kernel_platform_bundle,
)
from builder_ii.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    validate_governed_prepare_package,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
    validate_governed_prepare_package_summary,
)
from builder_ii.orchestration_dry_run import (
    ORCHESTRATION_DRY_RUN_KIND,
    validate_orchestration_dry_run,
)
from builder_ii.runtime_activation_approval import (
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
    validate_runtime_activation_approval_spec,
)
from builder_ii.release_manifest import (
    V0_RELEASE_MANIFEST_KIND,
    validate_v0_release_manifest,
)
from builder_ii.model_capabilities import (
    MODEL_CAPABILITY_REGISTRY_KIND,
    validate_model_capability_registry,
)
from builder_ii.profile_pack import PROFILE_PACK_KIND, validate_profile_pack
from builder_ii.profile_pack_manifest import (
    PROFILE_PACK_MANIFEST_KIND,
    validate_profile_pack_manifest,
)
from builder_ii.profile_pack_render_plan import (
    PROFILE_PACK_RENDER_PLAN_KIND,
    validate_profile_pack_render_plan,
)
from builder_ii.profile_pack_dry_run import (
    PROFILE_PACK_DRY_RUN_KIND,
    validate_profile_pack_dry_run,
)
from builder_ii.profile_pack_validation_report import (
    PROFILE_PACK_VALIDATION_REPORT_KIND,
    validate_profile_pack_validation_report,
)
from builder_ii.model_client_registry import (
    MODEL_CLIENT_REGISTRY_KIND,
    validate_model_client_registry,
)
from builder_ii.model_routing_policy import (
    MODEL_ROUTING_POLICY_KIND,
    validate_model_routing_policy,
    MODEL_ROUTING_RECOMMENDATION_KIND,
    validate_model_routing_recommendation,
)
from builder_ii.orchestration_assignment import (
    AGENT_ASSIGNMENT_PLAN_KIND,
    validate_agent_assignment_plan,
    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
    validate_orchestration_assignment_plan,
    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
    validate_orchestration_assignment_dry_run,
    ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND,
    validate_orchestration_assignment_validation_report,
)
from builder_ii.deepagents_work_artifacts import (
    DEEPAGENTS_WORK_PLAN_KIND,
    validate_deepagents_work_plan,
    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
    validate_deepagents_subagent_assignment,
    DEEPAGENTS_SUBAGENT_RESULT_KIND,
    validate_deepagents_subagent_result,
    DEEPAGENTS_SUBAGENT_REVIEW_KIND,
    validate_deepagents_subagent_review,
    DEEPAGENTS_HUMAN_GATE_REQUEST_KIND,
    validate_deepagents_human_gate_request,
    DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND,
    validate_deepagents_blocked_action_record,
    DEEPAGENTS_PROPOSAL_RESULT_KIND,
    validate_deepagents_proposal_result,
    DEEPAGENTS_WORK_VALIDATION_REPORT_KIND,
    validate_deepagents_work_validation_report,
)
from builder_ii.hitl_promotion_artifacts import (
    HITL_PROMOTION_REQUEST_KIND,
    validate_hitl_promotion_request,
    HITL_PROMOTION_REVIEW_KIND,
    validate_hitl_promotion_review,
    HITL_PROMOTION_DECISION_KIND,
    validate_hitl_promotion_decision,
    HITL_APPROVAL_BOUNDARY_KIND,
    validate_hitl_approval_boundary,
    HITL_REJECTION_RECORD_KIND,
    validate_hitl_rejection_record,
    HITL_PROMOTION_VALIDATION_REPORT_KIND,
    validate_hitl_promotion_validation_report,
)
from builder_ii.execution_candidate_manifest import (
    EXECUTION_CANDIDATE_MANIFEST_KIND,
    validate_execution_candidate_manifest,
    EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND,
    validate_execution_candidate_manifest_validation_report,
)
from builder_ii.event_ledger import (
    EVENT_LEDGER_KIND,
    EVENT_RECORD_KIND,
    LEDGER_REPLAY_REPORT_KIND,
    validate_event_ledger,
    validate_event_record,
    validate_ledger_replay_report,
)
from builder_ii.workflow_records import (
    WORKFLOW_SESSION_KIND,
    WORKFLOW_STATUS_KIND,
    WORKFLOW_TRANSITION_KIND,
    validate_workflow_session,
    validate_workflow_status,
    validate_workflow_transition,
)
from builder_ii.readonly_founder_demo import (
    TARGET_INSPECTION_PLAN_KIND,
    TARGET_PATCH_PROPOSAL_KIND,
    TARGET_VERIFICATION_PLAN_KIND,
    validate_target_inspection_plan,
    validate_target_patch_proposal,
    validate_target_verification_plan,
)



ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND = (
    "builder_ii.artifact_chain_verification_report"
)


def validate_artifact_chain_verification_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["artifact chain verification report must be a JSON object"]
    if record.get("kind") != ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND:
        errors.append(f"kind must be {ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND}")
    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if record.get("status") not in ("valid", "invalid"):
        errors.append("status must be valid or invalid")
    if not isinstance(record.get("valid"), bool):
        errors.append("valid must be a boolean")
    if not isinstance(record.get("counts"), dict):
        errors.append("counts must be an object")
    if not isinstance(record.get("files"), list):
        errors.append("files must be a list")
    if not isinstance(record.get("links"), list):
        errors.append("links must be a list")
    if not isinstance(record.get("errors"), list):
        errors.append("errors must be a list")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
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
    VERIFICATION_EXECUTION_PLAN_KIND: validate_verification_execution_plan_artifact,
    VERIFICATION_EXECUTION_APPROVAL_KIND: validate_verification_execution_approval_artifact,
    VERIFICATION_EXECUTION_RECEIPT_KIND: validate_verification_execution_receipt_artifact,
    VERIFICATION_EXECUTION_LEDGER_RECORD_KIND: validate_verification_execution_ledger_record,
    VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND: validate_verification_execution_ledger_integrity_report,
    VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND: validate_verification_execution_ledger_reconstruction_report,
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
    GOOSE_SESSION_KIND: validate_goose_session_manifest,
    HANDOFF_KIND: validate_handoff_artifact,
    VERIFICATION_PROFILE_REPORT_KIND: validate_verification_profile_report,
    SESSION_CONFIG_KIND: validate_session_configuration,
    GOOSE_PROJECTION_KIND: validate_goose_projection,
    GOOSE_WRAPPER_PLAN_KIND: validate_goose_wrapper_plan,
    ORCHESTRATION_PLAN_KIND: validate_orchestration_plan,
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND: validate_deepagents_bridge_readiness_report,
    DEEPAGENTS_POLICY_KIND: validate_deepagents_policy_artifact,
    DEEPAGENTS_READINESS_KIND: validate_deepagents_readiness_artifact,
    REPO_MAP_KIND: validate_repo_map,
    CONTEXT_PACK_KIND: validate_context_pack,
    CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND: validate_convention_kernel_platform_bundle,
    GOVERNED_PREPARE_PACKAGE_KIND: validate_governed_prepare_package,
    GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND: validate_governed_prepare_package_summary,
    ORCHESTRATION_DRY_RUN_KIND: validate_orchestration_dry_run,
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND: validate_runtime_activation_approval_spec,
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
    ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND: validate_artifact_chain_verification_report,
}


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    kind = record.get("kind")
    refs: list[dict[str, Any]] = []

    def append_artifact_ref(field: str, value: Any, expected_kind: str | None = None) -> None:
        if not isinstance(value, dict) or not (value.get("path") or value.get("sha256")):
            return
        resolved_kind = expected_kind or value.get("kind")
        if resolved_kind not in VALIDATORS:
            return
        refs.append(
            {
                "field": field,
                "sha256": value.get("sha256"),
                "path": value.get("path"),
                "expected_kind": resolved_kind,
            }
        )

    if kind == APPROVAL_RECORD_KIND:
        prop = record.get("proposal", {})
        if isinstance(prop, dict):
            refs.append(
                {
                    "field": "proposal",
                    "sha256": prop.get("sha256"),
                    "path": prop.get("path"),
                    "expected_kind": GOOSE_COMMAND_PROPOSAL_KIND,
                }
            )

    elif kind == PREFLIGHT_RECORD_KIND:
        prop = record.get("proposal", {})
        if isinstance(prop, dict):
            refs.append(
                {
                    "field": "proposal",
                    "sha256": prop.get("sha256"),
                    "path": prop.get("path"),
                    "expected_kind": GOOSE_COMMAND_PROPOSAL_KIND,
                }
            )
        appr = record.get("approval", {})
        if isinstance(appr, dict):
            refs.append(
                {
                    "field": "approval",
                    "sha256": appr.get("sha256"),
                    "path": appr.get("path"),
                    "expected_kind": APPROVAL_RECORD_KIND,
                }
            )

    elif kind == RECEIPT_RECORD_KIND:
        pref = record.get("preflight", {})
        if isinstance(pref, dict):
            refs.append(
                {
                    "field": "preflight",
                    "sha256": pref.get("sha256"),
                    "path": pref.get("path"),
                    "expected_kind": PREFLIGHT_RECORD_KIND,
                }
            )

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
                    refs.append(
                        {
                            "field": f"artifacts.{name}",
                            "sha256": item.get("sha256"),
                            "path": item.get("path"),
                            "expected_kind": expected,
                        }
                    )

    elif kind == HANDOFF_BUNDLE_RECORD_KIND:
        sum_field = record.get("summary", {})
        if isinstance(sum_field, dict):
            refs.append(
                {
                    "field": "summary",
                    "sha256": sum_field.get("sha256"),
                    "path": sum_field.get("path"),
                    "expected_kind": CHAIN_SUMMARY_RECORD_KIND,
                }
            )
        digests = record.get("artifact_digests", {})
        if isinstance(digests, dict):
            for name, item in digests.items():
                if isinstance(item, dict):
                    refs.append(
                        {
                            "field": f"artifact_digests.{name}",
                            "sha256": item.get("sha256"),
                            "path": item.get("path"),
                            "expected_kind": item.get("kind"),
                        }
                    )

    elif kind == RECEIVE_RECORD_KIND:
        bundle = record.get("bundle", {})
        if isinstance(bundle, dict):
            refs.append(
                {
                    "field": "bundle",
                    "sha256": bundle.get("sha256"),
                    "path": bundle.get("path"),
                    "expected_kind": HANDOFF_BUNDLE_RECORD_KIND,
                }
            )
        digests = record.get("artifact_digests", {})
        if isinstance(digests, dict):
            for name, item in digests.items():
                if isinstance(item, dict):
                    refs.append(
                        {
                            "field": f"artifact_digests.{name}",
                            "sha256": item.get("sha256"),
                            "path": item.get("path"),
                            "expected_kind": item.get("kind"),
                        }
                    )

    elif kind == PROMOTION_DECISION_RECORD_KIND:
        readiness = record.get("readiness", {})
        if isinstance(readiness, dict):
            refs.append(
                {
                    "field": "readiness",
                    "sha256": readiness.get("sha256"),
                    "path": readiness.get("path"),
                    "expected_kind": PROMOTION_READINESS_RECORD_KIND,
                }
            )

    elif kind == STATE_LEDGER_RECORD_KIND:
        entries = record.get("entries", [])
        if isinstance(entries, list):
            for idx, entry in enumerate(entries):
                if isinstance(entry, dict):
                    dec = entry.get("decision", {})
                    if isinstance(dec, dict):
                        refs.append(
                            {
                                "field": f"entries[{idx}].decision",
                                "sha256": dec.get("sha256"),
                                "path": dec.get("path"),
                                "expected_kind": PROMOTION_DECISION_RECORD_KIND,
                            }
                        )

    elif kind == SNAPSHOT_RECORD_KIND:
        idx = record.get("artifact_index", {})
        if isinstance(idx, dict):
            refs.append(
                {
                    "field": "artifact_index",
                    "sha256": idx.get("sha256"),
                    "path": idx.get("path"),
                    "expected_kind": ARTIFACT_INDEX_RECORD_KIND,
                }
            )
        ledger = record.get("state_ledger", {})
        if isinstance(ledger, dict):
            refs.append(
                {
                    "field": "state_ledger",
                    "sha256": ledger.get("sha256"),
                    "path": ledger.get("path"),
                    "expected_kind": STATE_LEDGER_RECORD_KIND,
                }
            )

    elif kind == RESEARCH_ADAPTER_KIND:
        plan = record.get("research_plan", {})
        if isinstance(plan, dict):
            refs.append(
                {
                    "field": "research_plan",
                    "sha256": plan.get("sha256"),
                    "path": plan.get("path"),
                    "expected_kind": RESEARCH_PLAN_KIND,
                }
            )

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
                refs.append(
                    {
                        "field": field,
                        "sha256": None,
                        "path": val,
                        "expected_kind": expected,
                    }
                )

        # Rollback references are optional but typed when present
        for field, expected in [
            ("rollback_plan_ref", ROLLBACK_PLAN_KIND),
            ("rollback_receipt_ref", ROLLBACK_RECEIPT_KIND),
        ]:
            val = record.get(field)
            if isinstance(val, str) and val:
                refs.append(
                    {
                        "field": field,
                        "sha256": None,
                        "path": val,
                        "expected_kind": expected,
                    }
                )

    elif kind == HITL_CHAIN_BINDING_KIND:
        for slot, field in HITL_CHAIN_BINDING_SLOT_FIELDS.items():
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": HITL_CHAIN_BINDING_SLOT_KIND_MAP[slot],
                    }
                )

    elif kind == HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND:
        for field, expected in [
            ("proposal_ref", GOOSE_COMMAND_PROPOSAL_KIND),
            ("approval_ref", APPROVAL_RECORD_KIND),
            ("preflight_ref", PREFLIGHT_RECORD_KIND),
            ("request_ref", HITL_EXECUTION_REQUEST_KIND),
        ]:
            val = record.get(field)
            if isinstance(val, str) and val:
                refs.append(
                    {
                        "field": field,
                        "sha256": None,
                        "path": val,
                        "expected_kind": expected,
                    }
                )
        command_ref = record.get("verification_command_ref")
        command_ref_kind = record.get("verification_command_ref_kind")
        if (
            isinstance(command_ref, str)
            and command_ref
            and isinstance(command_ref_kind, str)
            and command_ref_kind
        ):
            refs.append(
                {
                    "field": "verification_command_ref",
                    "sha256": None,
                    "path": command_ref,
                    "expected_kind": command_ref_kind,
                }
            )

    elif kind == HANDOFF_NOTE_KIND:
        for field, expected_kind in (
            ("session_ref", SESSION_WORKFLOW_PLAN_KIND),
            ("goose_readonly_session_ref", GOOSE_READONLY_SESSION_PLAN_KIND),
            ("verification_report_ref", VERIFICATION_PROFILE_REPORT_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

        evidence_refs = record.get("verification_evidence_refs")
        if isinstance(evidence_refs, list):
            for index, value in enumerate(evidence_refs):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"verification_evidence_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == MEMORY_ATOM_KIND:
        append_artifact_ref("artifact_ref", record.get("artifact_ref"))
        source_refs = record.get("source_refs")
        if isinstance(source_refs, list):
            for index, value in enumerate(source_refs):
                append_artifact_ref(f"source_refs[{index}]", value)
        parent_refs = record.get("parent_refs")
        if isinstance(parent_refs, list):
            for index, value in enumerate(parent_refs):
                append_artifact_ref(f"parent_refs[{index}]", value, MEMORY_ATOM_KIND)
        append_artifact_ref("superseded_by_ref", record.get("superseded_by_ref"), MEMORY_ATOM_KIND)

    elif kind == MEMORY_INDEX_KIND:
        entries = record.get("entries")
        if isinstance(entries, list):
            for index, entry in enumerate(entries):
                if isinstance(entry, dict):
                    append_artifact_ref(f"entries[{index}].atom_ref", entry.get("atom_ref"), MEMORY_ATOM_KIND)

    elif kind == MEMORY_SEARCH_RESULT_KIND:
        append_artifact_ref("index_ref", record.get("index_ref"), MEMORY_INDEX_KIND)
        matches = record.get("matches")
        if isinstance(matches, list):
            for index, match in enumerate(matches):
                if isinstance(match, dict):
                    append_artifact_ref(f"matches[{index}].atom_ref", match.get("atom_ref"), MEMORY_ATOM_KIND)
        excluded = record.get("excluded_atom_refs")
        if isinstance(excluded, list):
            for index, item in enumerate(excluded):
                if isinstance(item, dict):
                    append_artifact_ref(f"excluded_atom_refs[{index}].ref", item.get("ref"), MEMORY_ATOM_KIND)

    elif kind == MEMORY_RECONSTRUCTION_KIND:
        append_artifact_ref("index_ref", record.get("index_ref"), MEMORY_INDEX_KIND)
        selected_refs = record.get("selected_atom_refs")
        if isinstance(selected_refs, list):
            for index, value in enumerate(selected_refs):
                append_artifact_ref(f"selected_atom_refs[{index}]", value, MEMORY_ATOM_KIND)
        excluded = record.get("excluded_atom_refs")
        if isinstance(excluded, list):
            for index, item in enumerate(excluded):
                if isinstance(item, dict):
                    append_artifact_ref(f"excluded_atom_refs[{index}].ref", item.get("ref"), MEMORY_ATOM_KIND)
        context = record.get("reconstructed_context")
        if isinstance(context, list):
            for index, item in enumerate(context):
                if isinstance(item, dict):
                    append_artifact_ref(f"reconstructed_context[{index}].atom_ref", item.get("atom_ref"), MEMORY_ATOM_KIND)

    elif kind == CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND:
        handoff = record.get("handoff_note")
        if isinstance(handoff, dict):
            for field, expected_kind in (
                ("session_ref", SESSION_WORKFLOW_PLAN_KIND),
                ("goose_readonly_session_ref", GOOSE_READONLY_SESSION_PLAN_KIND),
                ("verification_report_ref", VERIFICATION_PROFILE_REPORT_KIND),
            ):
                value = handoff.get(field)
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"handoff_note.{field}",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": expected_kind,
                        }
                    )

    elif kind == GOVERNED_PREPARE_PACKAGE_KIND:
        refs_list = record.get("artifact_refs")
        if isinstance(refs_list, list):
            for index, value in enumerate(refs_list):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"artifact_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND:
        refs_list = record.get("artifacts")
        if isinstance(refs_list, list):
            for index, value in enumerate(refs_list):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"artifacts[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == V0_RELEASE_MANIFEST_KIND:
        session_proof = record.get("governed_session_proof")
        if isinstance(session_proof, dict):
            for field, expected_kind in [
                ("prepare_package_ref", GOVERNED_PREPARE_PACKAGE_KIND),
                ("session_workflow_ref", SESSION_WORKFLOW_PLAN_KIND),
                ("goose_readonly_session_ref", GOOSE_READONLY_SESSION_PLAN_KIND),
                ("verification_report_ref", VERIFICATION_PROFILE_REPORT_KIND),
                ("repo_map_ref", REPO_MAP_KIND),
                ("context_pack_ref", CONTEXT_PACK_KIND),
                ("handoff_note_ref", HANDOFF_NOTE_KIND),
                ("deepagents_readiness_ref", DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND),
            ]:
                val = session_proof.get(field)
                if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
                    refs.append(
                        {
                            "field": f"governed_session_proof.{field}",
                            "sha256": val.get("sha256") or None,
                            "path": val.get("path"),
                            "expected_kind": expected_kind,
                        }
                    )
        spine_proof = record.get("platform_spine_proof")
        if isinstance(spine_proof, dict):
            val = spine_proof.get("platform_spine_ref")
            if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
                refs.append(
                    {
                        "field": "platform_spine_proof.platform_spine_ref",
                        "sha256": val.get("sha256") or None,
                        "path": val.get("path"),
                        "expected_kind": CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
                    }
                )
        audit_refs = record.get("audit_references")
        if isinstance(audit_refs, dict):
            for field, expected_kind in [
                ("artifact_index_ref", ARTIFACT_INDEX_RECORD_KIND),
                (
                    "chain_verification_report_ref",
                    ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND,
                ),
            ]:
                val = audit_refs.get(field)
                if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
                    refs.append(
                        {
                            "field": f"audit_references.{field}",
                            "sha256": val.get("sha256") or None,
                            "path": val.get("path"),
                            "expected_kind": expected_kind,
                        }
                    )

    elif kind == PROFILE_PACK_RENDER_PLAN_KIND:
        value = record.get("source_manifest_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "source_manifest_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": PROFILE_PACK_MANIFEST_KIND,
                }
            )

    elif kind == PROFILE_PACK_DRY_RUN_KIND:
        for field, expected_kind in (
            ("source_manifest_ref", PROFILE_PACK_MANIFEST_KIND),
            ("source_render_plan_ref", PROFILE_PACK_RENDER_PLAN_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == PROFILE_PACK_VALIDATION_REPORT_KIND:
        value = record.get("subject_ref")
        expected_kind = record.get("subject_kind")
        if (
            isinstance(value, dict)
            and isinstance(expected_kind, str)
            and (value.get("path") or value.get("sha256"))
        ):
            refs.append(
                {
                    "field": "subject_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": expected_kind,
                }
            )

    elif kind == MODEL_ROUTING_RECOMMENDATION_KIND:
        for field, expected_kind in (
            ("source_policy_ref", MODEL_ROUTING_POLICY_KIND),
            ("source_registry_ref", MODEL_CLIENT_REGISTRY_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == PROFILE_PACK_KIND:
        for field, expected_kind in (
            ("manifest_ref", PROFILE_PACK_MANIFEST_KIND),
            ("render_plan_ref", PROFILE_PACK_RENDER_PLAN_KIND),
            ("dry_run_ref", PROFILE_PACK_DRY_RUN_KIND),
            ("validation_report_ref", PROFILE_PACK_VALIDATION_REPORT_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == AGENT_ASSIGNMENT_PLAN_KIND:
        refs_list = record.get("source_refs")
        if isinstance(refs_list, list):
            for index, value in enumerate(refs_list):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"source_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == ORCHESTRATION_ASSIGNMENT_PLAN_KIND:
        value = record.get("assignment_plan_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "assignment_plan_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": AGENT_ASSIGNMENT_PLAN_KIND,
                }
            )
        refs_list = record.get("bound_source_refs")
        if isinstance(refs_list, list):
            for index, value in enumerate(refs_list):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"bound_source_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND:
        value = record.get("source_orchestration_assignment_plan_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "source_orchestration_assignment_plan_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
                }
            )

    elif kind == ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND:
        value = record.get("subject_ref")
        expected_kind = record.get("subject_kind")
        if (
            isinstance(value, dict)
            and isinstance(expected_kind, str)
            and (value.get("path") or value.get("sha256"))
        ):
            refs.append(
                {
                    "field": "subject_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": expected_kind,
                }
            )

    elif kind == DEEPAGENTS_WORK_PLAN_KIND:
        for field, expected_kind in (
            ("orchestration_assignment_plan_ref", ORCHESTRATION_ASSIGNMENT_PLAN_KIND),
            (
                "orchestration_assignment_dry_run_ref",
                ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
            ),
            ("deepagents_policy_ref", DEEPAGENTS_POLICY_KIND),
            ("deepagents_readiness_ref", DEEPAGENTS_READINESS_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND:
        value = record.get("work_plan_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "work_plan_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": DEEPAGENTS_WORK_PLAN_KIND,
                }
            )

    elif kind == DEEPAGENTS_SUBAGENT_RESULT_KIND:
        value = record.get("subagent_assignment_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "subagent_assignment_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
                }
            )

    elif kind == DEEPAGENTS_SUBAGENT_REVIEW_KIND:
        for field, expected_kind in (
            ("subagent_result_ref", DEEPAGENTS_SUBAGENT_RESULT_KIND),
            ("subagent_assignment_ref", DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == DEEPAGENTS_HUMAN_GATE_REQUEST_KIND:
        value = record.get("reviewed_artifact_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "reviewed_artifact_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": value.get("kind"),
                }
            )

    elif kind == DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND:
        value = record.get("triggering_artifact_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "triggering_artifact_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": value.get("kind"),
                }
            )

    elif kind == DEEPAGENTS_PROPOSAL_RESULT_KIND:
        value = record.get("work_plan_ref")
        if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
            refs.append(
                {
                    "field": "work_plan_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": DEEPAGENTS_WORK_PLAN_KIND,
                }
            )
        reviewed_result_refs = record.get("reviewed_result_refs")
        if isinstance(reviewed_result_refs, list):
            for index, value in enumerate(reviewed_result_refs):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"reviewed_result_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == DEEPAGENTS_WORK_VALIDATION_REPORT_KIND:
        value = record.get("subject_ref")
        expected_kind = record.get("subject_kind")
        if (
            isinstance(value, dict)
            and isinstance(expected_kind, str)
            and (value.get("path") or value.get("sha256"))
        ):
            refs.append(
                {
                    "field": "subject_ref",
                    "sha256": value.get("sha256"),
                    "path": value.get("path"),
                    "expected_kind": expected_kind,
                }
            )

    elif kind == HITL_PROMOTION_REQUEST_KIND:
        for field, expected_kind in (
            ("proposal_ref", None),
            ("target_profile_ref", None),
            ("session_manifest_ref", None),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": value.get("kind") or expected_kind,
                    }
                )

    elif kind == HITL_PROMOTION_REVIEW_KIND:
        for field, expected_kind in (
            ("promotion_request_ref", HITL_PROMOTION_REQUEST_KIND),
            ("policy_ref", None),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind or value.get("kind"),
                    }
                )

    elif kind == HITL_PROMOTION_DECISION_KIND:
        for field, expected_kind in (
            ("promotion_request_ref", HITL_PROMOTION_REQUEST_KIND),
            ("promotion_review_ref", HITL_PROMOTION_REVIEW_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == HITL_APPROVAL_BOUNDARY_KIND:
        for field, expected_kind in (
            ("promotion_decision_ref", HITL_PROMOTION_DECISION_KIND),
            ("promotion_request_ref", HITL_PROMOTION_REQUEST_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind,
                    }
                )

    elif kind == HITL_REJECTION_RECORD_KIND:
        for field, expected_kind in (
            ("promotion_request_ref", HITL_PROMOTION_REQUEST_KIND),
            ("promotion_decision_ref", HITL_PROMOTION_DECISION_KIND),
        ):
            value = record.get(field)
            if isinstance(value, dict) and (value.get("path") or value.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": value.get("sha256"),
                        "path": value.get("path"),
                        "expected_kind": expected_kind
                        if field == "promotion_request_ref"
                        else (value.get("kind") or expected_kind),
                    }
                )

    elif kind == HITL_PROMOTION_VALIDATION_REPORT_KIND:
        subjects = record.get("subject_refs")
        if isinstance(subjects, list):
            for index, value in enumerate(subjects):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"subject_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == EXECUTION_CANDIDATE_MANIFEST_KIND:
        for field, expected in [
            ("approval_boundary_ref", HITL_APPROVAL_BOUNDARY_KIND),
            ("promotion_decision_ref", HITL_PROMOTION_DECISION_KIND),
            ("promotion_review_ref", HITL_PROMOTION_REVIEW_KIND),
            ("promotion_request_ref", HITL_PROMOTION_REQUEST_KIND),
            ("target_profile_ref", None),
            ("rollback_plan_ref", ROLLBACK_PLAN_KIND),
            ("git_state_ref", GIT_STATE_RECORD_KIND),
            ("preflight_ref", PREFLIGHT_RECORD_KIND),
            (
                "artifact_chain_verification_report_ref",
                ARTIFACT_CHAIN_VERIFICATION_REPORT_KIND,
            ),
            (
                "specialized_candidate_ref",
                HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND,
            ),
        ]:
            val = record.get(field)
            if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": val.get("sha256"),
                        "path": val.get("path"),
                        "expected_kind": expected or val.get("kind"),
                    }
                )

        # command_authority_snapshot_ref is the verifiable path pointing to a registered snapshot record kind.
        # command_authority_ref is metadata-only and is not extracted as a verifiable reference by the chain.
        val = record.get("command_authority_snapshot_ref")
        if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
            refs.append(
                {
                    "field": "command_authority_snapshot_ref",
                    "sha256": val.get("sha256"),
                    "path": val.get("path"),
                    "expected_kind": SNAPSHOT_RECORD_KIND,
                }
            )

        for field in ("verification_profile_ref", "verification_profile_report_ref"):
            val = record.get(field)
            if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
                refs.append(
                    {
                        "field": field,
                        "sha256": val.get("sha256"),
                        "path": val.get("path"),
                        "expected_kind": val.get("kind"),
                    }
                )

        proposal_refs = record.get("source_proposal_refs")
        if isinstance(proposal_refs, list):
            for index, val in enumerate(proposal_refs):
                if isinstance(val, dict) and (val.get("path") or val.get("sha256")):
                    refs.append(
                        {
                            "field": f"source_proposal_refs[{index}]",
                            "sha256": val.get("sha256"),
                            "path": val.get("path"),
                            "expected_kind": val.get("kind"),
                        }
                    )

    elif kind == EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND:
        subjects = record.get("subject_refs")
        if isinstance(subjects, list):
            for index, value in enumerate(subjects):
                if isinstance(value, dict) and (
                    value.get("path") or value.get("sha256")
                ):
                    refs.append(
                        {
                            "field": f"subject_refs[{index}]",
                            "sha256": value.get("sha256"),
                            "path": value.get("path"),
                            "expected_kind": value.get("kind"),
                        }
                    )

    elif kind == WORKFLOW_TRANSITION_KIND:
        previous = record.get("previous_transition_ref")
        append_artifact_ref("previous_transition_ref", previous, WORKFLOW_TRANSITION_KIND)
        subject_refs = record.get("subject_refs")
        if isinstance(subject_refs, list):
            for index, value in enumerate(subject_refs):
                append_artifact_ref(f"subject_refs[{index}]", value)

    elif kind == WORKFLOW_STATUS_KIND:
        append_artifact_ref("last_event_ref", record.get("last_event_ref"), EVENT_RECORD_KIND)
        artifact_refs = record.get("artifact_refs")
        if isinstance(artifact_refs, list):
            for index, value in enumerate(artifact_refs):
                append_artifact_ref(f"artifact_refs[{index}]", value)

    elif kind == EVENT_RECORD_KIND:
        append_artifact_ref("previous_event_ref", record.get("previous_event_ref"), EVENT_RECORD_KIND)
        subject_refs = record.get("subject_refs")
        if isinstance(subject_refs, list):
            for index, value in enumerate(subject_refs):
                append_artifact_ref(f"subject_refs[{index}]", value)

    elif kind == EVENT_LEDGER_KIND:
        append_artifact_ref("last_event_ref", record.get("last_event_ref"), EVENT_RECORD_KIND)
        append_artifact_ref("replay_report_ref", record.get("replay_report_ref"), LEDGER_REPLAY_REPORT_KIND)
        event_refs = record.get("event_refs")
        if isinstance(event_refs, list):
            for index, value in enumerate(event_refs):
                append_artifact_ref(f"event_refs[{index}]", value, EVENT_RECORD_KIND)

    elif kind == LEDGER_REPLAY_REPORT_KIND:
        append_artifact_ref("last_event_ref", record.get("last_event_ref"), EVENT_RECORD_KIND)

    elif kind == VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND:
        evidence_refs = record.get("evidence_refs")
        if isinstance(evidence_refs, list):
            for index, value in enumerate(evidence_refs):
                append_artifact_ref(f"evidence_refs[{index}]", value, VERIFICATION_EXECUTION_LEDGER_RECORD_KIND)

    elif kind == VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND:
        evidence_refs = record.get("evidence_refs")
        if isinstance(evidence_refs, list):
            for index, value in enumerate(evidence_refs):
                append_artifact_ref(f"evidence_refs[{index}]", value, VERIFICATION_EXECUTION_LEDGER_RECORD_KIND)

    elif kind == TARGET_INSPECTION_PLAN_KIND:
        append_artifact_ref("target_profile_ref", record.get("target_profile_ref"), TARGET_PROFILE_ARTIFACT_KIND)
        append_artifact_ref("workflow_session_ref", record.get("workflow_session_ref"), WORKFLOW_SESSION_KIND)

    elif kind == TARGET_PATCH_PROPOSAL_KIND:
        append_artifact_ref("inspection_plan_ref", record.get("inspection_plan_ref"), TARGET_INSPECTION_PLAN_KIND)
        append_artifact_ref("target_profile_ref", record.get("target_profile_ref"), TARGET_PROFILE_ARTIFACT_KIND)
        append_artifact_ref("workflow_session_ref", record.get("workflow_session_ref"), WORKFLOW_SESSION_KIND)

    elif kind == TARGET_VERIFICATION_PLAN_KIND:
        append_artifact_ref("patch_proposal_ref", record.get("patch_proposal_ref"), TARGET_PATCH_PROPOSAL_KIND)
        append_artifact_ref("target_profile_ref", record.get("target_profile_ref"), TARGET_PROFILE_ARTIFACT_KIND)
        append_artifact_ref("workflow_session_ref", record.get("workflow_session_ref"), WORKFLOW_SESSION_KIND)

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
                return (
                    declared_path,
                    loaded_by_path[declared_path],
                    "exact_input_path",
                    [],
                )
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
                    return (
                        rel_path,
                        None,
                        "relative_path",
                        [f"Referenced file {rel_path} must be a JSON object"],
                    )
                except Exception as e:
                    return (
                        rel_path,
                        None,
                        "relative_path",
                        [f"Failed to load referenced file {rel_path}: {e}"],
                    )
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
                    return (
                        as_is_path,
                        None,
                        "as_is_path",
                        [f"Referenced file {as_is_path} must be a JSON object"],
                    )
                except Exception as e:
                    return (
                        as_is_path,
                        None,
                        "as_is_path",
                        [f"Failed to load referenced file {as_is_path}: {e}"],
                    )
        except Exception:
            pass

    if expected_sha256:
        candidates = loaded_by_digest.get(expected_sha256, [])
        if candidates:
            matching_candidates = [
                (path, data)
                for path, data in candidates
                if not expected_kind or data.get("kind") == expected_kind
            ]
            if len(matching_candidates) > 1:
                paths_set = {p.resolve() for p, _ in matching_candidates}
                if len(paths_set) > 1:
                    paths_str = ", ".join(str(p) for p in paths_set)
                    return (
                        None,
                        None,
                        "ambiguous",
                        [
                            f"Ambiguous digest fallback match. Multiple paths found with digest '{expected_sha256}': {paths_str}"
                        ],
                    )
                return (
                    matching_candidates[0][0],
                    matching_candidates[0][1],
                    "digest_fallback",
                    [],
                )
            if len(matching_candidates) == 1:
                return (
                    matching_candidates[0][0],
                    matching_candidates[0][1],
                    "digest_fallback",
                    [],
                )

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
            files_report.append(
                {
                    "path": str(path),
                    "kind": "",
                    "sha256": "",
                    "native_valid": False,
                    "native_errors": [err_msg],
                }
            )
            native_invalid_count += 1
            continue

        try:
            content = path.read_text(encoding="utf-8")
            data = json_lib.loads(content)
        except json_lib.JSONDecodeError as exc:
            err_msg = f"Invalid JSON in {path}: {exc}"
            global_errors.append(err_msg)
            files_report.append(
                {
                    "path": str(path),
                    "kind": "",
                    "sha256": "",
                    "native_valid": False,
                    "native_errors": [err_msg],
                }
            )
            native_invalid_count += 1
            continue
        except Exception as exc:
            err_msg = f"Failed to read {path}: {exc}"
            global_errors.append(err_msg)
            files_report.append(
                {
                    "path": str(path),
                    "kind": "",
                    "sha256": "",
                    "native_valid": False,
                    "native_errors": [err_msg],
                }
            )
            native_invalid_count += 1
            continue

        if not isinstance(data, dict):
            err_msg = f"Artifact {path} must be a JSON object"
            global_errors.append(err_msg)
            files_report.append(
                {
                    "path": str(path),
                    "kind": "",
                    "sha256": "",
                    "native_valid": False,
                    "native_errors": [err_msg],
                }
            )
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
            global_errors.extend(
                f"Native validation error in {path}: {e}" for e in native_errors
            )

        files_report.append(
            {
                "path": str(path),
                "kind": kind,
                "sha256": digest_val,
                "native_valid": is_valid,
                "native_errors": native_errors,
            }
        )

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
                    link_errors.append(
                        f"Digest mismatch: referenced '{expected_sha256}', resolved file '{target_path}' has '{actual_sha256}'"
                    )

                actual_kind = target_data.get("kind", "")
                if expected_kind and actual_kind != expected_kind:
                    link_errors.append(
                        f"Kind mismatch: expected '{expected_kind}', resolved file '{target_path}' has '{actual_kind}'"
                    )

                for target_error in _target_native_errors(target_data):
                    link_errors.append(
                        f"Resolved target native validation failed: {target_error}"
                    )

            link_valid = len(link_errors) == 0
            if link_valid:
                resolved_links_count += 1
            else:
                broken_links_count += 1
                global_errors.extend(
                    f"Link error in {path} (field '{field}'): {e}" for e in link_errors
                )

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
