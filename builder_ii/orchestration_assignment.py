from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any, Callable

from builder_ii.agent_profiles import (
    AGENT_PROFILE_RECORD_KIND,
    agent_profile_names,
    validate_agent_profile_record,
)
from builder_ii.context_packs import CONTEXT_PACK_KIND, validate_context_pack
from builder_ii.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    validate_governed_prepare_package,
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
from builder_ii.orchestration_dry_run import (
    ORCHESTRATION_DRY_RUN_KIND,
    validate_orchestration_dry_run,
)
from builder_ii.orchestration_plan import (
    ORCHESTRATION_PLAN_KIND,
    validate_orchestration_plan,
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
from builder_ii.target_profiles import (
    TARGET_PROFILE_ARTIFACT_KIND,
    target_names,
    validate_target_profile_artifact,
)
from builder_ii.verification_profiles import (
    VERIFICATION_ARTIFACT_KIND,
    validate_profile_artifact,
    verification_profile_names,
)

AGENT_ASSIGNMENT_PLAN_KIND = "builder_ii.agent_assignment_plan"
AGENT_ASSIGNMENT_PLAN_SCHEMA_VERSION = 1

ORCHESTRATION_ASSIGNMENT_PLAN_KIND = "builder_ii.orchestration_assignment_plan"
ORCHESTRATION_ASSIGNMENT_PLAN_SCHEMA_VERSION = 1

ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND = "builder_ii.orchestration_assignment_dry_run"
ORCHESTRATION_ASSIGNMENT_DRY_RUN_SCHEMA_VERSION = 1

ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND = "builder_ii.orchestration_assignment_validation_report"
ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_ACTIVE_STATES = {"EXECUTED", "AUTHORIZED", "PROMOTED", "ENABLED"}

_TASK_PROFILE_ENTRY_ID = "task-profile-planning-contract"
_TOOL_PROFILE_ENTRY_ID = "deny-by-default-tool-profile"
_HITL_POLICY_ENTRY_ID = "approval-policy-contract"
_OUTPUT_PROFILE_ENTRY_ID = "profile-pack-lifecycle"
_HANDOFF_PROFILE_ENTRY_ID = "handoff-profile-contract"

_PROFILE_PACK_ENTRY_ROLES: dict[str, tuple[str, str]] = {
    "task_profile": (_TASK_PROFILE_ENTRY_ID, "task_profile"),
    "tool_policy": (_TOOL_PROFILE_ENTRY_ID, "tool_profile"),
    "hitl_policy": (_HITL_POLICY_ENTRY_ID, "approval_policy"),
    "output_profile": (_OUTPUT_PROFILE_ENTRY_ID, "pack"),
    "handoff_profile": (_HANDOFF_PROFILE_ENTRY_ID, "handoff_profile"),
}

_REQUIRED_ASSIGNMENT_REF_ROLES: dict[str, str] = {
    "target_profile": TARGET_PROFILE_ARTIFACT_KIND,
    "agent_profile": AGENT_PROFILE_RECORD_KIND,
    "task_profile": PROFILE_PACK_MANIFEST_KIND,
    "context_pack": CONTEXT_PACK_KIND,
    "verification_profile": VERIFICATION_ARTIFACT_KIND,
    "tool_policy": PROFILE_PACK_MANIFEST_KIND,
    "hitl_policy": PROFILE_PACK_MANIFEST_KIND,
    "output_profile": PROFILE_PACK_MANIFEST_KIND,
    "handoff_profile": PROFILE_PACK_MANIFEST_KIND,
    "model_registry": MODEL_CLIENT_REGISTRY_KIND,
    "model_policy": MODEL_ROUTING_POLICY_KIND,
    "model_recommendation": MODEL_ROUTING_RECOMMENDATION_KIND,
    "profile_pack_manifest": PROFILE_PACK_MANIFEST_KIND,
    "profile_pack_render_plan": PROFILE_PACK_RENDER_PLAN_KIND,
    "profile_pack_dry_run": PROFILE_PACK_DRY_RUN_KIND,
    "profile_pack_validation_report": PROFILE_PACK_VALIDATION_REPORT_KIND,
    "profile_pack": PROFILE_PACK_KIND,
}

_OPTIONAL_ASSIGNMENT_REF_ROLES: dict[str, str] = {
    "orchestration_plan": ORCHESTRATION_PLAN_KIND,
    "orchestration_dry_run": ORCHESTRATION_DRY_RUN_KIND,
    "governed_prepare_package": GOVERNED_PREPARE_PACKAGE_KIND,
}

_KNOWN_REF_KINDS = (
    set(_REQUIRED_ASSIGNMENT_REF_ROLES.values())
    | set(_OPTIONAL_ASSIGNMENT_REF_ROLES.values())
    | {
        AGENT_ASSIGNMENT_PLAN_KIND,
        ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
        ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
    }
)

_AUTHORITY_FALSE_KEYS = (
    "executes_model",
    "executes_tools",
    "executes_shell",
    "invokes_goose",
    "constructs_deepagents",
    "invokes_mcp",
    "performs_network_calls",
    "mutates_target_repo",
    "grants_authority",
    "artifact_is_authority",
)

_DENIED_CAPABILITIES = [
    "model execution",
    "tool execution",
    "shell execution",
    "Goose invocation",
    "deepagents construction",
    "MCP invocation",
    "network calls",
    "target repository mutation",
    "runtime authority grant",
]


def canonical_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _artifact_ref(
    data: dict[str, Any],
    *,
    role: str,
    path: Path | None,
    name: str = "",
    entry_id: str = "",
    profile_kind: str = "",
) -> dict[str, Any]:
    ref = {
        "role": role,
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
        "name": name,
        "required": True,
    }
    if entry_id:
        ref["entry_id"] = entry_id
    if profile_kind:
        ref["profile_kind"] = profile_kind
    return ref


def _profile_pack_entry_ref(
    manifest: dict[str, Any],
    *,
    role: str,
    manifest_path: Path | None,
) -> dict[str, Any]:
    entry_id, profile_kind = _PROFILE_PACK_ENTRY_ROLES[role]
    return _artifact_ref(
        manifest,
        role=role,
        path=manifest_path,
        name=entry_id,
        entry_id=entry_id,
        profile_kind=profile_kind,
    )


def _default_authority_boundary(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
    }


def _default_governance(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime_start": "DISABLED",
        "agent_construction": "DISABLED",
        "subagent_construction": "DISABLED",
        "model_execution": "DISABLED",
        "tool_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "network_calls": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "mcp_tool_calls": "DISABLED",
        "verification_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "core_workbench_coupling": "NONE",
    }


def _validate_or_raise(label: str, errors: list[str]) -> None:
    if errors:
        raise ValueError(f"invalid {label}: " + "; ".join(errors))


def _profile_pack_entry(manifest: dict[str, Any], entry_id: str, profile_kind: str) -> dict[str, Any] | None:
    for area in manifest.get("areas", []):
        if not isinstance(area, dict):
            continue
        for entry in area.get("entries", []):
            if isinstance(entry, dict) and entry.get("id") == entry_id and entry.get("profile_kind") == profile_kind:
                return entry
    return None


def _profile_pack_lifecycle_errors(
    *,
    manifest: dict[str, Any],
    render_plan: dict[str, Any],
    dry_run: dict[str, Any],
    validation_report: dict[str, Any],
    profile_pack: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    manifest_digest = canonical_digest(manifest)
    render_digest = canonical_digest(render_plan)
    dry_run_digest = canonical_digest(dry_run)
    report_digest = canonical_digest(validation_report)

    for field in ("pack_id", "target_profile", "task"):
        expected = manifest.get(field)
        if render_plan.get(field) != expected:
            errors.append(f"profile_pack_render_plan.{field} must match profile_pack_manifest.{field}")
        if dry_run.get(field) != expected:
            errors.append(f"profile_pack_dry_run.{field} must match profile_pack_manifest.{field}")
        if profile_pack.get(field) != expected:
            errors.append(f"profile_pack.{field} must match profile_pack_manifest.{field}")

    checks = (
        (
            "profile_pack_render_plan.source_manifest_ref.sha256",
            render_plan.get("source_manifest_ref"),
            manifest_digest,
        ),
        (
            "profile_pack_dry_run.source_manifest_ref.sha256",
            dry_run.get("source_manifest_ref"),
            manifest_digest,
        ),
        (
            "profile_pack_dry_run.source_render_plan_ref.sha256",
            dry_run.get("source_render_plan_ref"),
            render_digest,
        ),
        (
            "profile_pack.manifest_ref.sha256",
            profile_pack.get("manifest_ref"),
            manifest_digest,
        ),
        (
            "profile_pack.render_plan_ref.sha256",
            profile_pack.get("render_plan_ref"),
            render_digest,
        ),
        (
            "profile_pack.dry_run_ref.sha256",
            profile_pack.get("dry_run_ref"),
            dry_run_digest,
        ),
        (
            "profile_pack.validation_report_ref.sha256",
            profile_pack.get("validation_report_ref"),
            report_digest,
        ),
    )
    for field, ref, expected_digest in checks:
        if not isinstance(ref, dict):
            errors.append(f"{field.rsplit('.', 1)[0]} must be an object")
        elif ref.get("sha256") != expected_digest:
            errors.append(f"{field} must match referenced artifact digest")

    bindings = profile_pack.get("lifecycle_bindings")
    if not isinstance(bindings, dict):
        errors.append("profile_pack.lifecycle_bindings must be an object")
    else:
        if bindings.get("manifest_sha256") != manifest_digest:
            errors.append("profile_pack.lifecycle_bindings.manifest_sha256 must match profile pack manifest digest")
        if bindings.get("render_plan_sha256") != render_digest:
            errors.append(
                "profile_pack.lifecycle_bindings.render_plan_sha256 must match profile pack render plan digest"
            )
        if bindings.get("dry_run_sha256") != dry_run_digest:
            errors.append("profile_pack.lifecycle_bindings.dry_run_sha256 must match profile pack dry-run digest")
        if bindings.get("validation_report_sha256") != report_digest:
            errors.append(
                "profile_pack.lifecycle_bindings.validation_report_sha256 must match validation report digest"
            )

    return errors


def create_agent_assignment_plan(
    *,
    target_profile: dict[str, Any],
    agent_profile: dict[str, Any],
    task: str,
    context_pack: dict[str, Any],
    verification_profile: dict[str, Any],
    model_registry: dict[str, Any],
    model_policy: dict[str, Any],
    model_recommendation: dict[str, Any],
    profile_pack_manifest: dict[str, Any],
    profile_pack_render_plan: dict[str, Any],
    profile_pack_dry_run: dict[str, Any],
    profile_pack_validation_report: dict[str, Any],
    profile_pack: dict[str, Any],
    target_profile_path: Path | None = None,
    agent_profile_path: Path | None = None,
    context_pack_path: Path | None = None,
    verification_profile_path: Path | None = None,
    model_registry_path: Path | None = None,
    model_policy_path: Path | None = None,
    model_recommendation_path: Path | None = None,
    profile_pack_manifest_path: Path | None = None,
    profile_pack_render_plan_path: Path | None = None,
    profile_pack_dry_run_path: Path | None = None,
    profile_pack_validation_report_path: Path | None = None,
    profile_pack_path: Path | None = None,
    orchestration_plan: dict[str, Any] | None = None,
    orchestration_plan_path: Path | None = None,
    orchestration_dry_run: dict[str, Any] | None = None,
    orchestration_dry_run_path: Path | None = None,
    governed_prepare_package: dict[str, Any] | None = None,
    governed_prepare_package_path: Path | None = None,
) -> dict[str, Any]:
    """Bind target, agent, task, model, context, verification, tools, HITL, output, and handoff.

    This is a deterministic artifact constructor only. It validates and hashes
    already-created source artifacts; it does not execute models, tools,
    shells, Goose, deepagents, MCP, verification commands, or target writes.
    """

    task_text = task.strip()
    if not task_text:
        raise ValueError("task must be a non-empty string")

    _validate_or_raise("target profile artifact", validate_target_profile_artifact(target_profile))
    _validate_or_raise("agent profile record", validate_agent_profile_record(agent_profile))
    _validate_or_raise("context pack", validate_context_pack(context_pack))
    _validate_or_raise("verification profile artifact", validate_profile_artifact(verification_profile))
    _validate_or_raise("model client registry", validate_model_client_registry(model_registry))
    _validate_or_raise("model routing policy", validate_model_routing_policy(model_policy))
    _validate_or_raise(
        "model routing recommendation",
        validate_model_routing_recommendation(model_recommendation),
    )
    _validate_or_raise("profile pack manifest", validate_profile_pack_manifest(profile_pack_manifest))
    _validate_or_raise(
        "profile pack render plan",
        validate_profile_pack_render_plan(profile_pack_render_plan),
    )
    _validate_or_raise("profile pack dry run", validate_profile_pack_dry_run(profile_pack_dry_run))
    _validate_or_raise(
        "profile pack validation report",
        validate_profile_pack_validation_report(profile_pack_validation_report),
    )
    _validate_or_raise("profile pack", validate_profile_pack(profile_pack))

    lifecycle_errors = _profile_pack_lifecycle_errors(
        manifest=profile_pack_manifest,
        render_plan=profile_pack_render_plan,
        dry_run=profile_pack_dry_run,
        validation_report=profile_pack_validation_report,
        profile_pack=profile_pack,
    )
    _validate_or_raise("profile pack lifecycle binding", lifecycle_errors)

    target_name = str(target_profile["name"])
    agent_name = str(agent_profile["name"])
    verification_name = str(verification_profile["name"])

    if target_name not in target_names():
        raise ValueError(f"unknown target profile: {target_name}")
    if agent_name not in agent_profile_names():
        raise ValueError(f"unknown agent profile: {agent_name}")
    if verification_name not in verification_profile_names():
        raise ValueError(f"unknown verification profile: {verification_name}")

    compatible_agents = agent_profile.get("compatible_targets")
    if isinstance(compatible_agents, list) and target_name not in compatible_agents:
        raise ValueError(f"agent profile {agent_name} is not compatible with target profile {target_name}")

    compatible_verification = verification_profile.get("compatible_targets")
    if isinstance(compatible_verification, list) and target_name not in compatible_verification:
        raise ValueError(
            f"verification profile {verification_name} is not compatible with target profile {target_name}"
        )

    if context_pack.get("target_name") != target_name:
        raise ValueError("context pack target_name must match target profile name")

    expected_registry_digest = canonical_digest(model_registry)
    expected_policy_digest = canonical_digest(model_policy)
    rec_registry_ref = model_recommendation.get("source_registry_ref")
    rec_policy_ref = model_recommendation.get("source_policy_ref")
    if not isinstance(rec_registry_ref, dict) or rec_registry_ref.get("sha256") != expected_registry_digest:
        raise ValueError("model routing recommendation source_registry_ref must be bound to the supplied registry")
    if not isinstance(rec_policy_ref, dict) or rec_policy_ref.get("sha256") != expected_policy_digest:
        raise ValueError("model routing recommendation source_policy_ref must be bound to the supplied policy")

    for role, (entry_id, profile_kind) in _PROFILE_PACK_ENTRY_ROLES.items():
        if _profile_pack_entry(profile_pack_manifest, entry_id, profile_kind) is None:
            raise ValueError(f"profile pack manifest missing {role} entry {entry_id}")

    source_refs = [
        _artifact_ref(
            target_profile,
            role="target_profile",
            path=target_profile_path,
            name=target_name,
        ),
        _artifact_ref(
            agent_profile,
            role="agent_profile",
            path=agent_profile_path,
            name=agent_name,
        ),
        _profile_pack_entry_ref(
            profile_pack_manifest,
            role="task_profile",
            manifest_path=profile_pack_manifest_path,
        ),
        _artifact_ref(
            context_pack,
            role="context_pack",
            path=context_pack_path,
            name=str(context_pack.get("target_name", "")),
        ),
        _artifact_ref(
            verification_profile,
            role="verification_profile",
            path=verification_profile_path,
            name=verification_name,
        ),
        _profile_pack_entry_ref(
            profile_pack_manifest,
            role="tool_policy",
            manifest_path=profile_pack_manifest_path,
        ),
        _profile_pack_entry_ref(
            profile_pack_manifest,
            role="hitl_policy",
            manifest_path=profile_pack_manifest_path,
        ),
        _profile_pack_entry_ref(
            profile_pack_manifest,
            role="output_profile",
            manifest_path=profile_pack_manifest_path,
        ),
        _profile_pack_entry_ref(
            profile_pack_manifest,
            role="handoff_profile",
            manifest_path=profile_pack_manifest_path,
        ),
        _artifact_ref(
            model_registry,
            role="model_registry",
            path=model_registry_path,
            name=str(model_registry.get("registry_name", "")),
        ),
        _artifact_ref(
            model_policy,
            role="model_policy",
            path=model_policy_path,
            name=str(model_policy.get("policy_name", "")),
        ),
        _artifact_ref(
            model_recommendation,
            role="model_recommendation",
            path=model_recommendation_path,
            name="model routing recommendation",
        ),
        _artifact_ref(
            profile_pack_manifest,
            role="profile_pack_manifest",
            path=profile_pack_manifest_path,
            name=str(profile_pack_manifest.get("pack_id", "")),
        ),
        _artifact_ref(
            profile_pack_render_plan,
            role="profile_pack_render_plan",
            path=profile_pack_render_plan_path,
            name=str(profile_pack_render_plan.get("pack_id", "")),
        ),
        _artifact_ref(
            profile_pack_dry_run,
            role="profile_pack_dry_run",
            path=profile_pack_dry_run_path,
            name=str(profile_pack_dry_run.get("pack_id", "")),
        ),
        _artifact_ref(
            profile_pack_validation_report,
            role="profile_pack_validation_report",
            path=profile_pack_validation_report_path,
            name=str(profile_pack_validation_report.get("subject_kind", "")),
        ),
        _artifact_ref(
            profile_pack,
            role="profile_pack",
            path=profile_pack_path,
            name=str(profile_pack.get("pack_id", "")),
        ),
    ]

    if orchestration_plan is not None:
        _validate_or_raise("orchestration plan", validate_orchestration_plan(orchestration_plan))
        source_refs.append(
            _artifact_ref(
                orchestration_plan,
                role="orchestration_plan",
                path=orchestration_plan_path,
                name="legacy orchestration plan",
            )
        )
    if orchestration_dry_run is not None:
        _validate_or_raise(
            "orchestration dry run",
            validate_orchestration_dry_run(orchestration_dry_run),
        )
        source_refs.append(
            _artifact_ref(
                orchestration_dry_run,
                role="orchestration_dry_run",
                path=orchestration_dry_run_path,
                name="legacy orchestration dry run",
            )
        )
    if governed_prepare_package is not None:
        _validate_or_raise(
            "governed prepare package",
            validate_governed_prepare_package(governed_prepare_package),
        )
        source_refs.append(
            _artifact_ref(
                governed_prepare_package,
                role="governed_prepare_package",
                path=governed_prepare_package_path,
                name="governed prepare package",
            )
        )

    source_digests = {ref["role"]: ref["sha256"] for ref in source_refs}
    recommended_candidates = list(model_recommendation.get("recommended_candidates", []))
    selected_model = recommended_candidates[0] if recommended_candidates else {}

    assignment = {
        "kind": AGENT_ASSIGNMENT_PLAN_KIND,
        "schema_version": AGENT_ASSIGNMENT_PLAN_SCHEMA_VERSION,
        "assignment_state": "BOUND_ONLY",
        "target": target_name,
        "task": task_text,
        "bindings": {
            "target": {
                "name": target_name,
                "repo": target_profile.get("repo", ""),
                "source_ref_role": "target_profile",
            },
            "agent": {
                "name": agent_name,
                "authority": agent_profile.get("authority", ""),
                "source_ref_role": "agent_profile",
            },
            "task": {
                "description": task_text,
                "profile_entry_id": _TASK_PROFILE_ENTRY_ID,
                "source_ref_role": "task_profile",
                "task_state": "PLANNED_ONLY",
            },
            "model": {
                "recommendation_state": model_recommendation.get("recommendation_state", ""),
                "selected_candidate": selected_model,
                "source_ref_roles": [
                    "model_registry",
                    "model_policy",
                    "model_recommendation",
                ],
                "executes_model": False,
                "routing_grants_authority": False,
            },
            "context": {
                "target_name": context_pack.get("target_name", ""),
                "selected_file_count": len(context_pack.get("selected_files", []))
                if isinstance(context_pack.get("selected_files"), list)
                else 0,
                "source_ref_role": "context_pack",
                "context_is_proof": False,
            },
            "verification": {
                "name": verification_name,
                "required_evidence": list(verification_profile.get("required_evidence", [])),
                "proposed_commands": list(verification_profile.get("proposed_commands", [])),
                "source_ref_role": "verification_profile",
                "verification_status": "NOT_RUN",
                "executes_commands": False,
            },
            "tools": {
                "source_ref_role": "tool_policy",
                "default_policy": "denied",
                "allowed_tools": [],
                "executes_tools": False,
            },
            "hitl": {
                "source_ref_role": "hitl_policy",
                "approval_state": "NOT_GRANTED",
                "requires_human_promotion_for_execution": True,
                "grants_authority": False,
            },
            "outputs": {
                "source_ref_role": "output_profile",
                "expected_artifacts": [
                    AGENT_ASSIGNMENT_PLAN_KIND,
                    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
                    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
                ],
                "mutates_target_repo": False,
            },
            "handoff": {
                "source_ref_role": "handoff_profile",
                "expectations": [
                    "preserve target, task, bindings, denied capabilities, required promotions, and verification status",
                    "do not claim verification evidence without separate execution receipts",
                ],
                "claims_verification_evidence": False,
            },
        },
        "profile_pack_lifecycle": {
            "pack_id": profile_pack.get("pack_id", ""),
            "manifest_sha256": canonical_digest(profile_pack_manifest),
            "render_plan_sha256": canonical_digest(profile_pack_render_plan),
            "dry_run_sha256": canonical_digest(profile_pack_dry_run),
            "validation_report_sha256": canonical_digest(profile_pack_validation_report),
            "profile_pack_sha256": canonical_digest(profile_pack),
            "lifecycle_bindings": dict(profile_pack.get("lifecycle_bindings", {})),
        },
        "model_routing": {
            "recommendation": model_recommendation,
            "registry_sha256": expected_registry_digest,
            "policy_sha256": expected_policy_digest,
            "recommendation_sha256": canonical_digest(model_recommendation),
        },
        "source_refs": source_refs,
        "source_digests": source_digests,
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("agent_assignment_plan"),
        "governance": _default_governance("agent_assignment_plan"),
    }

    errors = validate_agent_assignment_plan(assignment)
    if errors:
        raise ValueError("created invalid agent assignment plan: " + "; ".join(errors))
    return assignment


def create_orchestration_assignment_plan(
    assignment_plan: dict[str, Any],
    *,
    assignment_plan_path: Path | None = None,
) -> dict[str, Any]:
    assignment_errors = validate_agent_assignment_plan(assignment_plan)
    if assignment_errors:
        raise ValueError("assignment plan is invalid: " + "; ".join(assignment_errors))

    assignment_ref = _artifact_ref(
        assignment_plan,
        role="assignment_plan",
        path=assignment_plan_path,
        name=str(assignment_plan.get("target", "")),
    )
    bindings = assignment_plan["bindings"]
    plan = {
        "kind": ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
        "schema_version": ORCHESTRATION_ASSIGNMENT_PLAN_SCHEMA_VERSION,
        "plan_state": "BOUND_ONLY",
        "orchestration_mode": "passive_assignment_v2",
        "target": assignment_plan["target"],
        "task": assignment_plan["task"],
        "assignment_plan_ref": assignment_ref,
        "source_refs": [assignment_ref],
        "bound_source_refs": list(assignment_plan.get("source_refs", [])),
        "planned_bindings": {
            "target": bindings["target"],
            "task": bindings["task"],
            "agent": bindings["agent"],
            "model": bindings["model"],
            "context": bindings["context"],
            "verification": bindings["verification"],
            "tools": bindings["tools"],
            "hitl": bindings["hitl"],
            "outputs": bindings["outputs"],
            "handoff": bindings["handoff"],
        },
        "binding_order": [
            "target",
            "task",
            "agent",
            "model",
            "context",
            "verification",
            "tools",
            "hitl",
            "outputs",
            "handoff",
        ],
        "expected_evidence": list(bindings["verification"].get("required_evidence", [])),
        "denied_capabilities": list(_DENIED_CAPABILITIES),
        "required_promotions": [
            "HITL approval artifact before execution",
            "separate capability promotion before model/tool/shell/runtime authority",
            "execution receipts before any verification claim",
        ],
        "handoff_expectations": list(bindings["handoff"].get("expectations", [])),
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("orchestration_assignment_plan"),
        "governance": _default_governance("orchestration_assignment_plan"),
    }
    errors = validate_orchestration_assignment_plan(plan)
    if errors:
        raise ValueError("created invalid orchestration assignment plan: " + "; ".join(errors))
    return plan


def create_orchestration_assignment_dry_run(
    orchestration_assignment_plan: dict[str, Any],
    *,
    orchestration_assignment_plan_path: Path | None = None,
) -> dict[str, Any]:
    plan_errors = validate_orchestration_assignment_plan(orchestration_assignment_plan)
    if plan_errors:
        raise ValueError("orchestration assignment plan is invalid: " + "; ".join(plan_errors))

    plan_ref = _artifact_ref(
        orchestration_assignment_plan,
        role="orchestration_assignment_plan",
        path=orchestration_assignment_plan_path,
        name=str(orchestration_assignment_plan.get("target", "")),
    )
    planned_bindings = dict(orchestration_assignment_plan["planned_bindings"])
    dry_run = {
        "kind": ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
        "schema_version": ORCHESTRATION_ASSIGNMENT_DRY_RUN_SCHEMA_VERSION,
        "dry_run_state": "DRY_RUN_ONLY",
        "source_orchestration_assignment_plan_ref": plan_ref,
        "source_refs": [plan_ref],
        "target": orchestration_assignment_plan["target"],
        "task": orchestration_assignment_plan["task"],
        "planned_bindings": planned_bindings,
        "would_happen": [
            "bind source artifacts by kind, role, and SHA-256 digest",
            "present agent, model, context, verification, tool, HITL, output, and handoff surfaces for review",
            "require human promotion before any runtime or execution authority exists",
        ],
        "why": [
            "assignment planning is artifact-only",
            "model routing is advisory and not authorization",
            "dry-run is explanatory and cannot execute or mutate",
        ],
        "denied_capabilities": list(orchestration_assignment_plan["denied_capabilities"]),
        "required_promotions": list(orchestration_assignment_plan["required_promotions"]),
        "expected_evidence": list(orchestration_assignment_plan["expected_evidence"]),
        "handoff_expectations": list(orchestration_assignment_plan["handoff_expectations"]),
        "execution_summary": {
            "models_called": 0,
            "tools_called": 0,
            "shell_commands_run": 0,
            "goose_invocations": 0,
            "deepagents_constructed": 0,
            "mcp_calls": 0,
            "network_calls": 0,
            "target_repo_mutations": 0,
            "verification_status": "NOT_RUN",
            "authority_granted": False,
        },
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("orchestration_assignment_dry_run"),
        "governance": _default_governance("orchestration_assignment_dry_run"),
    }
    errors = validate_orchestration_assignment_dry_run(dry_run)
    if errors:
        raise ValueError("created invalid orchestration assignment dry-run: " + "; ".join(errors))
    return dry_run


def create_orchestration_assignment_validation_report(
    subject: Any,
    *,
    subject_path: Path | None = None,
) -> dict[str, Any]:
    subject_kind = ""
    errors: list[str] = []
    subject_ref = {
        "role": "subject",
        "kind": "",
        "path": str(subject_path) if subject_path else "",
        "sha256": "",
        "name": "",
        "required": True,
    }

    if not isinstance(subject, dict):
        errors.append("subject must be a JSON object")
    else:
        subject_kind = str(subject.get("kind", ""))
        subject_ref = _artifact_ref(subject, role="subject", path=subject_path, name=subject_kind)
        validator = _assignment_validators().get(subject_kind)
        if validator is None:
            errors.append(f"unknown orchestration assignment artifact kind: {subject_kind or '<missing>'}")
        else:
            try:
                errors.extend(validator(subject))
            except Exception as exc:
                errors.append(f"subject validation raised: {exc}")

    valid = errors == []
    report = {
        "kind": ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND,
        "schema_version": ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_SCHEMA_VERSION,
        "validation_state": "VALIDATED_ONLY",
        "subject_kind": subject_kind,
        "subject_ref": subject_ref,
        "status": "valid" if valid else "invalid",
        "valid": valid,
        "errors": errors,
        "warnings": [],
        "checked_boundaries": [
            "assignment_is_artifact_only",
            "dry_run_is_not_execution",
            "model_routing_is_not_authorization",
            "source_refs_require_hashes",
            "artifact_is_not_authority",
        ],
        "claims": {
            "validated": True,
            "executed": False,
            "authorized": False,
            "promoted": False,
        },
        "governance": _default_governance("orchestration_assignment_validation_report"),
    }
    report_errors = validate_orchestration_assignment_validation_report(report)
    if report_errors:
        raise ValueError("created invalid orchestration assignment validation report: " + "; ".join(report_errors))
    return report


def dumps_agent_assignment_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def dumps_orchestration_assignment_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def dumps_orchestration_assignment_dry_run(dry_run: dict[str, Any]) -> str:
    return json_lib.dumps(dry_run, indent=2, sort_keys=True) + "\n"


def dumps_orchestration_assignment_validation_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_agent_assignment_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_agent_assignment_plan(plan), encoding="utf-8")


def write_orchestration_assignment_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_assignment_plan(plan), encoding="utf-8")


def write_orchestration_assignment_dry_run(dry_run: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_assignment_dry_run(dry_run), encoding="utf-8")


def write_orchestration_assignment_validation_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_assignment_validation_report(report), encoding="utf-8")


def _validate_sha(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        return [f"{field} must be a SHA-256 hex digest"]
    return []


def _validate_ref(
    value: Any,
    *,
    field: str,
    expected_kind: str | None = None,
    expected_role: str | None = None,
    lenient_subject: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if expected_role is not None and value.get("role") != expected_role:
        errors.append(f"{field}.role must be {expected_role}")
    kind = value.get("kind")
    if lenient_subject:
        if kind is not None and not isinstance(kind, str):
            errors.append(f"{field}.kind must be a string")
    else:
        if not isinstance(kind, str) or not kind:
            errors.append(f"{field}.kind must be a non-empty string")
        elif kind not in _KNOWN_REF_KINDS:
            errors.append(f"{field}.kind is an unknown artifact kind")
        elif expected_kind is not None and kind != expected_kind:
            errors.append(f"{field}.kind must be {expected_kind}")
    if not isinstance(value.get("path", ""), str):
        errors.append(f"{field}.path must be a string")
    sha = value.get("sha256")
    if lenient_subject:
        if sha != "" and sha is not None:
            errors.extend(_validate_sha(sha, field=f"{field}.sha256"))
    else:
        errors.extend(_validate_sha(sha, field=f"{field}.sha256"))
    if value.get("required") is not True:
        errors.append(f"{field}.required must be true")
    if not isinstance(value.get("name", ""), str):
        errors.append(f"{field}.name must be a string")
    return errors


def _source_refs_by_role(
    data: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    refs = data.get("source_refs")
    if not isinstance(refs, list) or not refs:
        return {}, ["source_refs must be a non-empty list"]
    by_role: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(refs):
        field = f"source_refs[{index}]"
        if not isinstance(ref, dict):
            errors.append(f"{field} must be an object")
            continue
        role = ref.get("role")
        if not isinstance(role, str) or not role:
            errors.append(f"{field}.role must be a non-empty string")
            continue
        if role in by_role:
            errors.append(f"duplicate source ref role: {role}")
        by_role[role] = ref
    return by_role, errors


def _validate_required_source_refs(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    by_role, role_errors = _source_refs_by_role(data)
    errors.extend(role_errors)
    source_digests = data.get("source_digests")
    if not isinstance(source_digests, dict):
        errors.append("source_digests must be an object")
        source_digests = {}

    for role, expected_kind in _REQUIRED_ASSIGNMENT_REF_ROLES.items():
        ref = by_role.get(role)
        if ref is None:
            errors.append(f"missing {role} ref")
            continue
        errors.extend(
            _validate_ref(
                ref,
                field=f"source_refs.{role}",
                expected_kind=expected_kind,
                expected_role=role,
            )
        )
        if source_digests.get(role) != ref.get("sha256"):
            errors.append(f"source_digests.{role} must match {role} ref sha256")
        if role in _PROFILE_PACK_ENTRY_ROLES:
            expected_entry_id, expected_profile_kind = _PROFILE_PACK_ENTRY_ROLES[role]
            if ref.get("entry_id") != expected_entry_id:
                errors.append(f"source_refs.{role}.entry_id must be {expected_entry_id}")
            if ref.get("profile_kind") != expected_profile_kind:
                errors.append(f"source_refs.{role}.profile_kind must be {expected_profile_kind}")

    for role, ref in by_role.items():
        if role in _REQUIRED_ASSIGNMENT_REF_ROLES:
            continue
        expected_kind = _OPTIONAL_ASSIGNMENT_REF_ROLES.get(role)
        if expected_kind is None:
            errors.append(f"unknown source ref role: {role}")
            continue
        errors.extend(
            _validate_ref(
                ref,
                field=f"source_refs.{role}",
                expected_kind=expected_kind,
                expected_role=role,
            )
        )
        if isinstance(source_digests, dict) and source_digests.get(role) != ref.get("sha256"):
            errors.append(f"source_digests.{role} must match {role} ref sha256")

    return errors


def _validate_authority_boundary(data: dict[str, Any], *, capability_state: str) -> list[str]:
    errors: list[str] = []
    for key in _AUTHORITY_FALSE_KEYS:
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
        for key in _AUTHORITY_FALSE_KEYS:
            if boundary.get(key) is not False:
                errors.append(f"authority_boundary.{key} must be false")
        if boundary.get("requires_human_promotion_for_execution") is not True:
            errors.append("authority_boundary.requires_human_promotion_for_execution must be true")
    return errors


def _validate_governance(governance: Any, *, capability_state: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != capability_state:
        errors.append(f"governance.capability_state must be {capability_state}")
    for key in (
        "runtime_execution",
        "goose_runtime_start",
        "deepagents_runtime_start",
        "agent_construction",
        "subagent_construction",
        "model_execution",
        "tool_execution",
        "shell_execution",
        "network_calls",
        "target_repo_writes",
        "memory_mutation",
        "mcp_tool_calls",
        "verification_execution",
    ):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "grants_authority"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false")
    if governance.get("requires_human_promotion_for_execution") is not True:
        errors.append("governance.requires_human_promotion_for_execution must be true")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def _validate_no_active_state_claims(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_validate_no_active_state_claims(item, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_validate_no_active_state_claims(item, f"{path}[{index}]"))
    elif isinstance(value, str) and value in _FORBIDDEN_ACTIVE_STATES:
        errors.append(f"field '{path}' claims active authority state '{value}'")
    return errors


def validate_agent_assignment_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["agent assignment plan must be a JSON object"]
    if data.get("kind") != AGENT_ASSIGNMENT_PLAN_KIND:
        errors.append(f"kind must be {AGENT_ASSIGNMENT_PLAN_KIND}")
    if data.get("schema_version") != AGENT_ASSIGNMENT_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {AGENT_ASSIGNMENT_PLAN_SCHEMA_VERSION}")
    if data.get("assignment_state") != "BOUND_ONLY":
        errors.append("assignment_state must be BOUND_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")

    bindings = data.get("bindings")
    if not isinstance(bindings, dict):
        errors.append("bindings must be an object")
    else:
        target_binding = bindings.get("target")
        if not isinstance(target_binding, dict) or target_binding.get("name") not in target_names():
            errors.append("bindings.target.name must be a known target profile")
        agent_binding = bindings.get("agent")
        if not isinstance(agent_binding, dict) or agent_binding.get("name") not in agent_profile_names():
            errors.append("bindings.agent.name must be a known agent profile")
        task_binding = bindings.get("task")
        if not isinstance(task_binding, dict):
            errors.append("bindings.task must be an object")
        else:
            if task_binding.get("profile_entry_id") != _TASK_PROFILE_ENTRY_ID:
                errors.append(f"bindings.task.profile_entry_id must be {_TASK_PROFILE_ENTRY_ID}")
            if task_binding.get("task_state") != "PLANNED_ONLY":
                errors.append("bindings.task.task_state must be PLANNED_ONLY")
        verification_binding = bindings.get("verification")
        if (
            not isinstance(verification_binding, dict)
            or verification_binding.get("name") not in verification_profile_names()
        ):
            errors.append("bindings.verification.name must be a known verification profile")
        elif verification_binding.get("verification_status") != "NOT_RUN":
            errors.append("bindings.verification.verification_status must be NOT_RUN")
        tools_binding = bindings.get("tools")
        if not isinstance(tools_binding, dict):
            errors.append("bindings.tools must be an object")
        else:
            if tools_binding.get("default_policy") != "denied":
                errors.append("bindings.tools.default_policy must be denied")
            if tools_binding.get("allowed_tools") != []:
                errors.append("bindings.tools.allowed_tools must be empty")
            if tools_binding.get("executes_tools") is not False:
                errors.append("bindings.tools.executes_tools must be false")
        hitl_binding = bindings.get("hitl")
        if not isinstance(hitl_binding, dict):
            errors.append("bindings.hitl must be an object")
        else:
            if hitl_binding.get("approval_state") != "NOT_GRANTED":
                errors.append("bindings.hitl.approval_state must be NOT_GRANTED")
            if hitl_binding.get("grants_authority") is not False:
                errors.append("bindings.hitl.grants_authority must be false")
        outputs_binding = bindings.get("outputs")
        if not isinstance(outputs_binding, dict):
            errors.append("bindings.outputs must be an object")
        elif outputs_binding.get("mutates_target_repo") is not False:
            errors.append("bindings.outputs.mutates_target_repo must be false")
        handoff_binding = bindings.get("handoff")
        if not isinstance(handoff_binding, dict):
            errors.append("bindings.handoff must be an object")
        elif handoff_binding.get("claims_verification_evidence") is not False:
            errors.append("bindings.handoff.claims_verification_evidence must be false")

        model_binding = bindings.get("model")
        if not isinstance(model_binding, dict):
            errors.append("bindings.model must be an object")
        else:
            if model_binding.get("executes_model") is not False:
                errors.append("bindings.model.executes_model must be false")
            if model_binding.get("routing_grants_authority") is not False:
                errors.append("bindings.model.routing_grants_authority must be false")
            if model_binding.get("recommendation_state") != "RECOMMENDATION_ONLY":
                errors.append("bindings.model.recommendation_state must be RECOMMENDATION_ONLY")
            if not isinstance(model_binding.get("selected_candidate"), dict):
                errors.append("bindings.model.selected_candidate must be an object")

        context_binding = bindings.get("context")
        if not isinstance(context_binding, dict):
            errors.append("bindings.context must be an object")
        else:
            if context_binding.get("context_is_proof") is not False:
                errors.append("bindings.context.context_is_proof must be false")
            if context_binding.get("source_ref_role") != "context_pack":
                errors.append("bindings.context.source_ref_role must be context_pack")
            if context_binding.get("target_name") != data.get("target"):
                errors.append("bindings.context.target_name must match assignment target")

    errors.extend(_validate_required_source_refs(data))

    lifecycle = data.get("profile_pack_lifecycle")
    by_role, _ = _source_refs_by_role(data)
    if not isinstance(lifecycle, dict):
        errors.append("profile_pack_lifecycle must be an object")
    else:
        lifecycle_fields = (
            ("manifest_sha256", "profile_pack_manifest"),
            ("render_plan_sha256", "profile_pack_render_plan"),
            ("dry_run_sha256", "profile_pack_dry_run"),
            ("validation_report_sha256", "profile_pack_validation_report"),
            ("profile_pack_sha256", "profile_pack"),
        )
        for lifecycle_field, role in lifecycle_fields:
            errors.extend(
                _validate_sha(
                    lifecycle.get(lifecycle_field),
                    field=f"profile_pack_lifecycle.{lifecycle_field}",
                )
            )
            ref = by_role.get(role)
            if isinstance(ref, dict) and lifecycle.get(lifecycle_field) != ref.get("sha256"):
                errors.append(f"profile_pack_lifecycle.{lifecycle_field} must match {role} ref sha256")
        bindings = lifecycle.get("lifecycle_bindings")
        if not isinstance(bindings, dict):
            errors.append("profile_pack_lifecycle.lifecycle_bindings must be an object")
        else:
            if bindings.get("manifest_sha256") != lifecycle.get("manifest_sha256"):
                errors.append("profile_pack_lifecycle.lifecycle_bindings.manifest_sha256 must match manifest_sha256")
            if bindings.get("render_plan_sha256") != lifecycle.get("render_plan_sha256"):
                errors.append(
                    "profile_pack_lifecycle.lifecycle_bindings.render_plan_sha256 must match render_plan_sha256"
                )
            if bindings.get("dry_run_sha256") != lifecycle.get("dry_run_sha256"):
                errors.append("profile_pack_lifecycle.lifecycle_bindings.dry_run_sha256 must match dry_run_sha256")
            if bindings.get("validation_report_sha256") != lifecycle.get("validation_report_sha256"):
                errors.append(
                    "profile_pack_lifecycle.lifecycle_bindings.validation_report_sha256 must match validation_report_sha256"
                )

    model_routing = data.get("model_routing")
    if not isinstance(model_routing, dict):
        errors.append("model_routing must be an object")
    else:
        recommendation = model_routing.get("recommendation")
        rec_errors = validate_model_routing_recommendation(recommendation)
        errors.extend(f"model_routing.recommendation invalid: {error}" for error in rec_errors)
        if isinstance(recommendation, dict):
            rec_ref = by_role.get("model_recommendation")
            if isinstance(rec_ref, dict) and model_routing.get("recommendation_sha256") != rec_ref.get("sha256"):
                errors.append("model_routing.recommendation_sha256 must match model_recommendation ref sha256")
            registry_ref = by_role.get("model_registry")
            policy_ref = by_role.get("model_policy")
            if isinstance(registry_ref, dict) and model_routing.get("registry_sha256") != registry_ref.get("sha256"):
                errors.append("model_routing.registry_sha256 must match model_registry ref sha256")
            if isinstance(policy_ref, dict) and model_routing.get("policy_sha256") != policy_ref.get("sha256"):
                errors.append("model_routing.policy_sha256 must match model_policy ref sha256")
            source_registry_ref = recommendation.get("source_registry_ref")
            source_policy_ref = recommendation.get("source_policy_ref")
            if (
                isinstance(registry_ref, dict)
                and isinstance(source_registry_ref, dict)
                and source_registry_ref.get("sha256") != registry_ref.get("sha256")
            ):
                errors.append("model routing recommendation must be bound to the model_registry source ref")
            if (
                isinstance(policy_ref, dict)
                and isinstance(source_policy_ref, dict)
                and source_policy_ref.get("sha256") != policy_ref.get("sha256")
            ):
                errors.append("model routing recommendation must be bound to the model_policy source ref")

    errors.extend(_validate_authority_boundary(data, capability_state="agent_assignment_plan"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="agent_assignment_plan"))
    errors.extend(_validate_no_active_state_claims(data, "assignment"))
    return errors


def validate_orchestration_assignment_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["orchestration assignment plan must be a JSON object"]
    if data.get("kind") != ORCHESTRATION_ASSIGNMENT_PLAN_KIND:
        errors.append(f"kind must be {ORCHESTRATION_ASSIGNMENT_PLAN_KIND}")
    if data.get("schema_version") != ORCHESTRATION_ASSIGNMENT_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ORCHESTRATION_ASSIGNMENT_PLAN_SCHEMA_VERSION}")
    if data.get("plan_state") != "BOUND_ONLY":
        errors.append("plan_state must be BOUND_ONLY")
    if data.get("orchestration_mode") != "passive_assignment_v2":
        errors.append("orchestration_mode must be passive_assignment_v2")
    if data.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")
    errors.extend(
        _validate_ref(
            data.get("assignment_plan_ref"),
            field="assignment_plan_ref",
            expected_kind=AGENT_ASSIGNMENT_PLAN_KIND,
            expected_role="assignment_plan",
        )
    )
    refs = data.get("source_refs")
    if not isinstance(refs, list) or len(refs) != 1:
        errors.append("source_refs must contain exactly the assignment plan ref")
    elif isinstance(data.get("assignment_plan_ref"), dict) and refs[0].get("sha256") != data["assignment_plan_ref"].get(
        "sha256"
    ):
        errors.append("source_refs[0] must match assignment_plan_ref")
    if not isinstance(data.get("bound_source_refs"), list) or not data["bound_source_refs"]:
        errors.append("bound_source_refs must be a non-empty list")
    planned = data.get("planned_bindings")
    if not isinstance(planned, dict):
        errors.append("planned_bindings must be an object")
    else:
        for key in (
            "target",
            "task",
            "agent",
            "model",
            "context",
            "verification",
            "tools",
            "hitl",
            "outputs",
            "handoff",
        ):
            if key not in planned:
                errors.append(f"planned_bindings.{key} is required")
        model = planned.get("model")
        if isinstance(model, dict) and model.get("executes_model") is not False:
            errors.append("planned_bindings.model.executes_model must be false")
        verification = planned.get("verification")
        if isinstance(verification, dict) and verification.get("verification_status") != "NOT_RUN":
            errors.append("planned_bindings.verification.verification_status must be NOT_RUN")
        tools = planned.get("tools")
        if isinstance(tools, dict) and tools.get("executes_tools") is not False:
            errors.append("planned_bindings.tools.executes_tools must be false")
        hitl = planned.get("hitl")
        if isinstance(hitl, dict) and hitl.get("grants_authority") is not False:
            errors.append("planned_bindings.hitl.grants_authority must be false")
        outputs = planned.get("outputs")
        if isinstance(outputs, dict) and outputs.get("mutates_target_repo") is not False:
            errors.append("planned_bindings.outputs.mutates_target_repo must be false")
        handoff = planned.get("handoff")
        if isinstance(handoff, dict) and handoff.get("claims_verification_evidence") is not False:
            errors.append("planned_bindings.handoff.claims_verification_evidence must be false")
    if data.get("binding_order") != [
        "target",
        "task",
        "agent",
        "model",
        "context",
        "verification",
        "tools",
        "hitl",
        "outputs",
        "handoff",
    ]:
        errors.append(
            "binding_order must preserve target/task/agent/model/context/verification/tools/HITL/output/handoff"
        )
    for field in (
        "expected_evidence",
        "denied_capabilities",
        "required_promotions",
        "handoff_expectations",
    ):
        if not isinstance(data.get(field), list) or any(
            not isinstance(item, str) or not item for item in data.get(field, [])
        ):
            errors.append(f"{field} must be a list of non-empty strings")
    errors.extend(_validate_authority_boundary(data, capability_state="orchestration_assignment_plan"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="orchestration_assignment_plan"))
    errors.extend(_validate_no_active_state_claims(data, "orchestration_assignment_plan"))
    return errors


def validate_orchestration_assignment_dry_run(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["orchestration assignment dry run must be a JSON object"]
    if data.get("kind") != ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND:
        errors.append(f"kind must be {ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND}")
    if data.get("schema_version") != ORCHESTRATION_ASSIGNMENT_DRY_RUN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ORCHESTRATION_ASSIGNMENT_DRY_RUN_SCHEMA_VERSION}")
    if data.get("dry_run_state") != "DRY_RUN_ONLY":
        errors.append("dry_run_state must be DRY_RUN_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")
    errors.extend(
        _validate_ref(
            data.get("source_orchestration_assignment_plan_ref"),
            field="source_orchestration_assignment_plan_ref",
            expected_kind=ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
            expected_role="orchestration_assignment_plan",
        )
    )
    refs = data.get("source_refs")
    if not isinstance(refs, list) or len(refs) != 1:
        errors.append("source_refs must contain exactly the orchestration assignment plan ref")
    elif isinstance(data.get("source_orchestration_assignment_plan_ref"), dict) and refs[0].get("sha256") != data[
        "source_orchestration_assignment_plan_ref"
    ].get("sha256"):
        errors.append("source_refs[0] must match source_orchestration_assignment_plan_ref")
    if not isinstance(data.get("planned_bindings"), dict):
        errors.append("planned_bindings must be an object")
    for field in (
        "would_happen",
        "why",
        "denied_capabilities",
        "required_promotions",
        "expected_evidence",
        "handoff_expectations",
    ):
        if not isinstance(data.get(field), list) or any(
            not isinstance(item, str) or not item for item in data.get(field, [])
        ):
            errors.append(f"{field} must be a list of non-empty strings")
    summary = data.get("execution_summary")
    if not isinstance(summary, dict):
        errors.append("execution_summary must be an object")
    else:
        expected_zeroes = (
            "models_called",
            "tools_called",
            "shell_commands_run",
            "goose_invocations",
            "deepagents_constructed",
            "mcp_calls",
            "network_calls",
            "target_repo_mutations",
        )
        for key in expected_zeroes:
            if summary.get(key) != 0:
                errors.append(f"execution_summary.{key} must be 0")
        if summary.get("verification_status") != "NOT_RUN":
            errors.append("execution_summary.verification_status must be NOT_RUN")
        if summary.get("authority_granted") is not False:
            errors.append("execution_summary.authority_granted must be false")
    errors.extend(_validate_authority_boundary(data, capability_state="orchestration_assignment_dry_run"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="orchestration_assignment_dry_run"))
    errors.extend(_validate_no_active_state_claims(data, "orchestration_assignment_dry_run"))
    return errors


def validate_orchestration_assignment_validation_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["orchestration assignment validation report must be a JSON object"]
    if data.get("kind") != ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND:
        errors.append(f"kind must be {ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND}")
    if data.get("schema_version") != ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_SCHEMA_VERSION}")
    if data.get("validation_state") != "VALIDATED_ONLY":
        errors.append("validation_state must be VALIDATED_ONLY")
    valid = data.get("valid")
    subject_kind = data.get("subject_kind")
    if valid is True:
        if not isinstance(subject_kind, str):
            errors.append("subject_kind must be a string")
        elif not subject_kind:
            errors.append("subject_kind must be a non-empty string")
        elif subject_kind not in _assignment_validators():
            errors.append("subject_kind must be a known orchestration assignment artifact kind")
    else:
        if subject_kind is not None and not isinstance(subject_kind, str):
            errors.append("subject_kind must be a string")

    errors.extend(
        _validate_ref(
            data.get("subject_ref"),
            field="subject_ref",
            expected_role="subject",
            lenient_subject=(valid is False),
        )
    )
    if data.get("status") not in {"valid", "invalid"}:
        errors.append("status must be valid or invalid")
    if not isinstance(data.get("valid"), bool):
        errors.append("valid must be a boolean")
    if data.get("valid") is True and data.get("errors") != []:
        errors.append("errors must be empty when valid is true")
    if data.get("valid") is False and data.get("status") != "invalid":
        errors.append("status must be invalid when valid is false")
    for field in ("errors", "warnings", "checked_boundaries"):
        if not isinstance(data.get(field), list) or any(not isinstance(item, str) for item in data.get(field, [])):
            errors.append(f"{field} must be a list of strings")
    claims = data.get("claims")
    if not isinstance(claims, dict):
        errors.append("claims must be an object")
    else:
        if claims.get("validated") is not True:
            errors.append("claims.validated must be true")
        for key in ("executed", "authorized", "promoted"):
            if claims.get(key) is not False:
                errors.append(f"claims.{key} must be false")
    errors.extend(
        _validate_governance(
            data.get("governance"),
            capability_state="orchestration_assignment_validation_report",
        )
    )
    errors.extend(_validate_no_active_state_claims(data, "orchestration_assignment_validation_report"))
    return errors


def _assignment_validators() -> dict[str, Callable[[Any], list[str]]]:
    return {
        AGENT_ASSIGNMENT_PLAN_KIND: validate_agent_assignment_plan,
        ORCHESTRATION_ASSIGNMENT_PLAN_KIND: validate_orchestration_assignment_plan,
        ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND: validate_orchestration_assignment_dry_run,
        ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND: validate_orchestration_assignment_validation_report,
    }


def _validate_file(path: Path, validator: Callable[[Any], list[str]]) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validator(data)


def validate_agent_assignment_plan_file(path: Path) -> list[str]:
    return _validate_file(path, validate_agent_assignment_plan)


def validate_orchestration_assignment_plan_file(path: Path) -> list[str]:
    return _validate_file(path, validate_orchestration_assignment_plan)


def validate_orchestration_assignment_dry_run_file(path: Path) -> list[str]:
    return _validate_file(path, validate_orchestration_assignment_dry_run)


def validate_orchestration_assignment_validation_report_file(path: Path) -> list[str]:
    return _validate_file(path, validate_orchestration_assignment_validation_report)
