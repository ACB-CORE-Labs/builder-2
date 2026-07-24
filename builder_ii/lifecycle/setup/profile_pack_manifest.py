from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from builder_ii.core.canonical_json import canonical_digest, canonical_json
from typing import Any

from builder_ii.lifecycle.setup.target_profiles import target_names

PROFILE_PACK_MANIFEST_KIND = "builder_ii.profile_pack_manifest"
PROFILE_PACK_MANIFEST_SCHEMA_VERSION = 1

REQUIRED_PACK_AREAS: tuple[str, ...] = (
    "target_profiles",
    "agent_profiles",
    "subagent_profiles",
    "task_profiles",
    "tool_profiles",
    "context_definitions",
    "verification_profiles",
    "approval_policies",
    "goose_projection_stubs",
    "deepagents_projection_stubs",
    "mcp_inventory_policy_stubs",
    "handoff_profiles",
    "packs",
)

KNOWN_PACK_AREAS: tuple[str, ...] = REQUIRED_PACK_AREAS + ("model_policies",)

KNOWN_PROFILE_KINDS: tuple[str, ...] = (
    "target_profile",
    "agent_profile",
    "subagent_profile",
    "task_profile",
    "tool_profile",
    "context_definition",
    "verification_profile",
    "approval_policy",
    "goose_projection_stub",
    "deepagents_projection_stub",
    "mcp_inventory_stub",
    "mcp_policy_stub",
    "handoff_profile",
    "model_client_registry",
    "model_routing_policy",
    "model_routing_recommendation",
    "pack",
    "model_policy_stub",
)

PROFILE_KINDS_BY_AREA: dict[str, tuple[str, ...]] = {
    "target_profiles": ("target_profile",),
    "agent_profiles": ("agent_profile",),
    "subagent_profiles": ("subagent_profile",),
    "task_profiles": ("task_profile",),
    "tool_profiles": ("tool_profile",),
    "context_definitions": ("context_definition",),
    "verification_profiles": ("verification_profile",),
    "approval_policies": ("approval_policy",),
    "goose_projection_stubs": ("goose_projection_stub",),
    "deepagents_projection_stubs": ("deepagents_projection_stub",),
    "mcp_inventory_policy_stubs": ("mcp_inventory_stub", "mcp_policy_stub"),
    "handoff_profiles": ("handoff_profile",),
    "packs": ("pack",),
    "model_policies": (
        "model_policy_stub",
        "model_client_registry",
        "model_routing_policy",
        "model_routing_recommendation",
    ),
}

EXPECTED_AUTHORITY_BY_KIND: dict[str, str] = {
    "target_profile": "spec_only",
    "agent_profile": "profile_spec_only",
    "subagent_profile": "profile_spec_only",
    "task_profile": "plan_only",
    "tool_profile": "denied_by_default",
    "context_definition": "spec_only",
    "verification_profile": "plan_only",
    "approval_policy": "policy_stub_only",
    "goose_projection_stub": "projection_stub_only",
    "deepagents_projection_stub": "projection_stub_only",
    "mcp_inventory_stub": "inventory_stub_only",
    "mcp_policy_stub": "policy_stub_only",
    "handoff_profile": "handoff_only",
    "pack": "artifact_only",
    "model_policy_stub": "policy_stub_only",
    "model_client_registry": "artifact_only",
    "model_routing_policy": "policy_stub_only",
    "model_routing_recommendation": "artifact_only",
}

ALLOWED_AUTHORITY_CLASSIFICATIONS = tuple(sorted(set(EXPECTED_AUTHORITY_BY_KIND.values())))
FORBIDDEN_LIFECYCLE_STATES = {"EXECUTED", "AUTHORIZED", "PROMOTED", "ENABLED"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_ref(project_root: Path, path: str, *, kind: str) -> dict[str, Any]:
    source_path = project_root / path
    return {
        "kind": kind,
        "path": path,
        "sha256": _file_sha256(source_path),
        "required": True,
    }


def _entry_digest_material(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "content_hash"}


def _with_content_hash(entry: dict[str, Any]) -> dict[str, Any]:
    material = dict(entry)
    material["content_hash"] = canonical_digest(_entry_digest_material(material))
    return material


def _entry(
    *,
    entry_id: str,
    area: str,
    profile_kind: str,
    title: str,
    description: str,
    source_refs: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _with_content_hash(
        {
            "id": entry_id,
            "area": area,
            "profile_kind": profile_kind,
            "title": title,
            "description": description,
            "lifecycle_state": "PLANNED_ONLY",
            "authority_classification": EXPECTED_AUTHORITY_BY_KIND[profile_kind],
            "source_refs": source_refs,
            "payload": payload,
        }
    )


def _default_governance(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime_start": "DISABLED",
        "agent_construction": "DISABLED",
        "subagent_construction": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "mcp_tool_calls": "DISABLED",
        "verification_execution": "DISABLED",
        "artifact_is_authority": False,
        "executed": False,
        "authorized": False,
        "promoted": False,
        "core_workbench_coupling": "NONE",
    }


def create_profile_pack_manifest(
    *,
    pack_id: str,
    target_profile: str,
    task: str,
    project_root: Path,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a passive profile-pack manifest with all required pack areas.

    The scaffold reads local source-of-truth files only to hash them. It does
    not construct agents, call models, start Goose/deepagents, connect to MCP,
    execute commands, or mutate target repositories.
    """

    root = project_root.resolve()

    def source(path, kind="module"):
        return [_source_ref(root, path, kind=kind)]

    areas: list[dict[str, Any]] = [
        {
            "area": "target_profiles",
            "entries": [
                _entry(
                    entry_id="target-profile-bundle",
                    area="target_profiles",
                    profile_kind="target_profile",
                    title="Target profile bundle",
                    description="References generic, builder, and core target profile definitions.",
                    source_refs=source("builder_ii/lifecycle/setup/target_profiles.py"),
                    payload={
                        "supported_targets": list(target_names()),
                        "core_specific_behavior_scope": "core target profile only",
                    },
                )
            ],
        },
        {
            "area": "agent_profiles",
            "entries": [
                _entry(
                    entry_id="generic-agent-profile-bundle",
                    area="agent_profiles",
                    profile_kind="agent_profile",
                    title="Generic agent profile bundle",
                    description="Static agent role contracts rendered without runtime activation.",
                    source_refs=source("builder_ii/routing/agent_profiles.py"),
                    payload={"renders_profiles": True, "constructs_agents": False},
                )
            ],
        },
        {
            "area": "subagent_profiles",
            "entries": [
                _entry(
                    entry_id="passive-subagent-profile-contract",
                    area="subagent_profiles",
                    profile_kind="subagent_profile",
                    title="Passive subagent profile contract",
                    description="Subagents remain profile contracts and never runtime actors in this pack.",
                    source_refs=source(
                        "docs/adrs/ADR-0002-builder-convention-layer-over-codename-goose.md", kind="doc"
                    ),
                    payload={
                        "runtime_binding": "UNBOUND",
                        "constructs_subagents": False,
                        "delegates": False,
                    },
                )
            ],
        },
        {
            "area": "task_profiles",
            "entries": [
                _entry(
                    entry_id="task-profile-planning-contract",
                    area="task_profiles",
                    profile_kind="task_profile",
                    title="Task profile planning contract",
                    description="Task profiles organize intent and expected artifacts without executing work.",
                    source_refs=source("builder_ii/core/session_workflow.py"),
                    payload={"task_state": "PLANNED_ONLY", "executes_tasks": False},
                )
            ],
        },
        {
            "area": "tool_profiles",
            "entries": [
                _entry(
                    entry_id="deny-by-default-tool-profile",
                    area="tool_profiles",
                    profile_kind="tool_profile",
                    title="Deny-by-default tool profile",
                    description="Tool profiles are declarations; all tool use is denied unless separately promoted.",
                    source_refs=source("docs/COMMAND_AUTHORITY.md", kind="doc"),
                    payload={
                        "default_policy": "denied",
                        "allowed_tools": [],
                        "denied_actions": [
                            "shell_execution",
                            "source_writes",
                            "model_execution",
                            "runtime_start",
                            "mcp_tool_call",
                        ],
                    },
                )
            ],
        },
        {
            "area": "context_definitions",
            "entries": [
                _entry(
                    entry_id="context-definition-contract",
                    area="context_definitions",
                    profile_kind="context_definition",
                    title="Context definition contract",
                    description="Context definitions describe bounded context artifacts without proving correctness.",
                    source_refs=source("builder_ii/core/context_packs.py"),
                    payload={"reads_source_for_context": False, "artifact_is_proof": False},
                )
            ],
        },
        {
            "area": "verification_profiles",
            "entries": [
                _entry(
                    entry_id="verification-profile-contract",
                    area="verification_profiles",
                    profile_kind="verification_profile",
                    title="Verification profile contract",
                    description="Verification profiles propose commands and evidence requirements only.",
                    source_refs=source("builder_ii/lifecycle/candidate/verification_profiles.py"),
                    payload={"executes_commands": False, "verification_status": "NOT_RUN"},
                )
            ],
        },
        {
            "area": "approval_policies",
            "entries": [
                _entry(
                    entry_id="approval-policy-contract",
                    area="approval_policies",
                    profile_kind="approval_policy",
                    title="Approval policy contract",
                    description="Approval policies describe required human gates without granting approval.",
                    source_refs=source("docs/CAPABILITY_PROMOTION.md", kind="doc"),
                    payload={"approval_state": "NOT_GRANTED", "grants_authority": False},
                )
            ],
        },
        {
            "area": "goose_projection_stubs",
            "entries": [
                _entry(
                    entry_id="goose-projection-stub",
                    area="goose_projection_stubs",
                    profile_kind="goose_projection_stub",
                    title="Goose projection stub",
                    description="Goose projection data is rendered as planned-only configuration.",
                    source_refs=source("builder_ii/adapters/goose/goose_projection.py"),
                    payload={"starts_goose": False, "runtime_execution": "DISABLED"},
                )
            ],
        },
        {
            "area": "deepagents_projection_stubs",
            "entries": [
                _entry(
                    entry_id="deepagents-projection-stub",
                    area="deepagents_projection_stubs",
                    profile_kind="deepagents_projection_stub",
                    title="deepagents projection stub",
                    description="deepagents projection data never constructs agents or delegates work.",
                    source_refs=source("docs/DEEPAGENTS_POLICY.md", kind="doc"),
                    payload={
                        "constructs_agents": False,
                        "constructs_subagents": False,
                        "delegates": False,
                    },
                )
            ],
        },
        {
            "area": "mcp_inventory_policy_stubs",
            "entries": [
                _entry(
                    entry_id="mcp-inventory-stub",
                    area="mcp_inventory_policy_stubs",
                    profile_kind="mcp_inventory_stub",
                    title="MCP inventory stub",
                    description="MCP inventory is a passive policy precursor and never calls tools.",
                    source_refs=source("docs/plan/MCP_TOOL_INVENTORY_RFC.md", kind="doc"),
                    payload={
                        "stub_only": True,
                        "connects_to_mcp": False,
                        "calls_tools": False,
                        "fetches_resources": False,
                        "sampling": "disabled",
                        "default_policy": "denied",
                    },
                ),
                _entry(
                    entry_id="mcp-policy-stub",
                    area="mcp_inventory_policy_stubs",
                    profile_kind="mcp_policy_stub",
                    title="MCP policy stub",
                    description="MCP policy remains deny-by-default metadata without invocation authority.",
                    source_refs=source("docs/plan/MCP_POLICY_ARTIFACT_RFC.md", kind="doc"),
                    payload={
                        "stub_only": True,
                        "connects_to_mcp": False,
                        "calls_tools": False,
                        "fetches_resources": False,
                        "sampling": "disabled",
                        "default_policy": "denied",
                    },
                ),
            ],
        },
        {
            "area": "handoff_profiles",
            "entries": [
                _entry(
                    entry_id="handoff-profile-contract",
                    area="handoff_profiles",
                    profile_kind="handoff_profile",
                    title="Handoff profile contract",
                    description="Handoff profiles preserve continuity without claiming verification evidence.",
                    source_refs=source("builder_ii/core/handoff_notes.py"),
                    payload={"verification_claim": "NOT_CLAIMED", "claims_verification_evidence": False},
                )
            ],
        },
        {
            "area": "packs",
            "entries": [
                _entry(
                    entry_id="profile-pack-lifecycle",
                    area="packs",
                    profile_kind="pack",
                    title="Profile pack lifecycle",
                    description="Pack lifecycle artifacts remain passive, deterministic, and reviewable.",
                    source_refs=source("docs/ARTIFACT_INDEX.md", kind="doc"),
                    payload={"artifact_is_authority": False, "lifecycle": "passive_only"},
                )
            ],
        },
        {
            "area": "model_policies",
            "entries": [
                _entry(
                    entry_id="model-policy-stub",
                    area="model_policies",
                    profile_kind="model_policy_stub",
                    title="Model policy stub",
                    description="Model policy metadata never calls models or routes requests by itself.",
                    source_refs=source("docs/model_operating_policy.md", kind="doc"),
                    payload={"calls_models": False, "model_execution": "DISABLED"},
                )
            ],
        },
    ]

    if target_profile == "core":
        for area in areas:
            if area["area"] == "agent_profiles":
                area["entries"].extend(
                    [
                        _entry(
                            entry_id="core-invariant-auditor",
                            area="agent_profiles",
                            profile_kind="agent_profile",
                            title="CORE invariant auditor",
                            description="Read-only CORE invariant audit role contract.",
                            source_refs=source("builder_ii/routing/agent_profiles.py"),
                            payload={
                                "agent_profile": "core.invariant_auditor",
                                "target": "core",
                                "authority": "read_only",
                                "constructs_agents": False,
                            },
                        ),
                        _entry(
                            entry_id="core-patch-planner",
                            area="agent_profiles",
                            profile_kind="agent_profile",
                            title="CORE patch planner",
                            description="Proposal-only CORE patch planning role contract.",
                            source_refs=source("builder_ii/routing/agent_profiles.py"),
                            payload={
                                "agent_profile": "core.patch_planner",
                                "target": "core",
                                "authority": "proposal_only",
                                "constructs_agents": False,
                            },
                        ),
                        _entry(
                            entry_id="core-verification-planner",
                            area="agent_profiles",
                            profile_kind="agent_profile",
                            title="CORE verification planner",
                            description="Plan-only CORE verification role contract.",
                            source_refs=source("builder_ii/routing/agent_profiles.py"),
                            payload={
                                "agent_profile": "core.verification_planner",
                                "target": "core",
                                "authority": "plan_only",
                                "constructs_agents": False,
                            },
                        ),
                    ]
                )
                break

    manifest = {
        "kind": PROFILE_PACK_MANIFEST_KIND,
        "schema_version": PROFILE_PACK_MANIFEST_SCHEMA_VERSION,
        "manifest_state": "PLANNED_ONLY",
        "pack_id": pack_id,
        "name": name or pack_id,
        "description": description or "Passive profile-pack substrate scaffold.",
        "target_profile": target_profile,
        "task": task,
        "areas": areas,
        "lifecycle_boundaries": {
            "planned": True,
            "rendered": False,
            "dry_run": False,
            "validated": False,
            "executed": False,
            "authorized": False,
            "promoted": False,
        },
        "governance": _default_governance("profile_pack_manifest"),
    }
    errors = validate_profile_pack_manifest(manifest)
    if errors:
        raise ValueError("created invalid profile pack manifest: " + "; ".join(errors))
    return manifest


def dumps_profile_pack_manifest(manifest: dict[str, Any]) -> str:
    return json_lib.dumps(manifest, indent=2, sort_keys=True) + "\n"


def write_profile_pack_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_pack_manifest(manifest), encoding="utf-8")


def _validate_source_ref(value: Any, *, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if value.get("kind") not in {"doc", "module", "schema", "test", "artifact", "profile"}:
        errors.append(f"{field}.kind must be a known source ref kind")
    if not isinstance(value.get("path"), str) or not value["path"]:
        errors.append(f"{field}.path must be a non-empty string")
    if not isinstance(value.get("sha256"), str) or not _SHA256_RE.match(value["sha256"]):
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    if value.get("required") is not True:
        errors.append(f"{field}.required must be true")
    return errors


def _validate_entry_payload(entry: dict[str, Any], *, field: str) -> list[str]:
    errors: list[str] = []
    payload = entry.get("payload")
    if not isinstance(payload, dict):
        return [f"{field}.payload must be an object"]
    profile_kind = entry.get("profile_kind")

    if profile_kind == "tool_profile":
        if payload.get("default_policy") != "denied":
            errors.append(f"{field}.payload.default_policy must be denied")
        if payload.get("allowed_tools") != []:
            errors.append(f"{field}.payload.allowed_tools must be empty")

    if profile_kind in {"mcp_inventory_stub", "mcp_policy_stub"}:
        for key in ("stub_only",):
            if payload.get(key) is not True:
                errors.append(f"{field}.payload.{key} must be true")
        for key in ("connects_to_mcp", "calls_tools", "fetches_resources"):
            if payload.get(key) is not False:
                errors.append(f"{field}.payload.{key} must be false or NOT_AUTHORIZED")
        if payload.get("sampling") != "disabled":
            errors.append(f"{field}.payload.sampling must be disabled")
        if payload.get("default_policy") != "denied":
            errors.append(f"{field}.payload.default_policy must be denied")

    if profile_kind == "goose_projection_stub":
        if payload.get("starts_goose") is not False:
            errors.append(f"{field}.payload.starts_goose must be false or NOT_AUTHORIZED")
        if payload.get("runtime_execution") != "DISABLED":
            errors.append(f"{field}.payload.runtime_execution must be DISABLED or NOT_AUTHORIZED")

    if profile_kind == "deepagents_projection_stub":
        for key in ("constructs_agents", "constructs_subagents", "delegates"):
            if payload.get(key) is not False:
                errors.append(f"{field}.payload.{key} must be false or NOT_AUTHORIZED")

    if profile_kind in {
        "model_policy_stub",
        "model_client_registry",
        "model_routing_policy",
        "model_routing_recommendation",
    }:
        if payload.get("calls_models") is not False:
            errors.append(f"{field}.payload.calls_models must be false or NOT_AUTHORIZED")
        if payload.get("model_execution") != "DISABLED":
            errors.append(f"{field}.payload.model_execution must be DISABLED or NOT_AUTHORIZED")

    if profile_kind == "verification_profile":
        if payload.get("executes_commands") is not False:
            errors.append(f"{field}.payload.executes_commands must be false or NOT_AUTHORIZED")
        if payload.get("verification_status") != "NOT_RUN":
            errors.append(f"{field}.payload.verification_status must be NOT_RUN")

    if profile_kind == "handoff_profile":
        if payload.get("claims_verification_evidence") is not False:
            errors.append(f"{field}.payload.claims_verification_evidence must be false or NOT_AUTHORIZED")
        if payload.get("verification_claim") != "NOT_CLAIMED":
            errors.append(f"{field}.payload.verification_claim must be NOT_CLAIMED")

    if profile_kind == "approval_policy":
        if payload.get("grants_authority") is not False:
            errors.append(f"{field}.payload.grants_authority must be false or NOT_AUTHORIZED")
        if payload.get("approval_state") in {"APPROVED", "AUTHORIZED"}:
            errors.append(f"{field}.payload.approval_state must not grant approval")

    if profile_kind == "pack":
        if payload.get("artifact_is_authority") is not False:
            errors.append(f"{field}.payload.artifact_is_authority must be false or NOT_AUTHORIZED")

    return errors


def _validate_entry(entry: Any, *, expected_area: str, field: str, seen_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{field} must be an object"]

    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        errors.append(f"{field}.id must be a non-empty string")
    elif entry_id in seen_ids:
        errors.append(f"duplicate profile pack entry id: {entry_id}")
    else:
        seen_ids.add(entry_id)

    if entry.get("area") != expected_area:
        errors.append(f"{field}.area must be {expected_area}")

    profile_kind = entry.get("profile_kind")
    if profile_kind not in KNOWN_PROFILE_KINDS:
        errors.append(f"{field}.profile_kind must be a known profile kind")
    elif profile_kind not in PROFILE_KINDS_BY_AREA[expected_area]:
        errors.append(f"{field}.profile_kind is not allowed in area {expected_area}")

    for name in ("title", "description"):
        if not isinstance(entry.get(name), str) or not entry[name]:
            errors.append(f"{field}.{name} must be a non-empty string")

    if entry.get("lifecycle_state") != "PLANNED_ONLY":
        errors.append(f"{field}.lifecycle_state must be PLANNED_ONLY")

    authority = entry.get("authority_classification")
    if authority not in ALLOWED_AUTHORITY_CLASSIFICATIONS:
        errors.append(f"{field}.authority_classification must be known")
    elif profile_kind in EXPECTED_AUTHORITY_BY_KIND and authority != EXPECTED_AUTHORITY_BY_KIND[profile_kind]:
        errors.append(f"{field}.authority_classification must be {EXPECTED_AUTHORITY_BY_KIND[profile_kind]}")

    refs = entry.get("source_refs")
    if not isinstance(refs, list) or not refs:
        errors.append(f"{field}.source_refs must be a non-empty list")
    else:
        for index, ref in enumerate(refs):
            errors.extend(_validate_source_ref(ref, field=f"{field}.source_refs[{index}]"))

    if not isinstance(entry.get("content_hash"), str) or not _SHA256_RE.match(entry["content_hash"]):
        errors.append(f"{field}.content_hash must be a SHA-256 hex digest")
    else:
        expected_hash = canonical_digest(_entry_digest_material(entry))
        if entry["content_hash"] != expected_hash:
            errors.append(f"{field}.content_hash does not match entry content")

    errors.extend(_validate_entry_payload(entry, field=field))
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
        "shell_execution",
        "target_repo_writes",
        "memory_mutation",
        "mcp_tool_calls",
        "verification_execution",
    ):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "executed", "authorized", "promoted"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_profile_pack_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile pack manifest must be a JSON object"]
    if data.get("kind") != PROFILE_PACK_MANIFEST_KIND:
        errors.append(f"kind must be {PROFILE_PACK_MANIFEST_KIND}")
    if data.get("schema_version") != PROFILE_PACK_MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROFILE_PACK_MANIFEST_SCHEMA_VERSION}")
    if data.get("manifest_state") != "PLANNED_ONLY":
        errors.append("manifest_state must be PLANNED_ONLY")
    for field in ("pack_id", "name", "description", "task"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    if data.get("target_profile") not in target_names():
        errors.append("target_profile must be one of: generic, builder, core")

    areas = data.get("areas")
    seen_ids: set[str] = set()
    seen_areas: set[str] = set()
    if not isinstance(areas, list) or not areas:
        errors.append("areas must be a non-empty list")
    else:
        for area_index, area_record in enumerate(areas):
            field = f"areas[{area_index}]"
            if not isinstance(area_record, dict):
                errors.append(f"{field} must be an object")
                continue
            area_name = area_record.get("area")
            if area_name not in KNOWN_PACK_AREAS:
                errors.append(f"{field}.area must be a known pack area")
                continue
            if area_name in seen_areas:
                errors.append(f"duplicate profile pack area: {area_name}")
            seen_areas.add(area_name)
            entries = area_record.get("entries")
            if not isinstance(entries, list) or not entries:
                errors.append(f"{field}.entries must be a non-empty list")
                continue
            for entry_index, entry in enumerate(entries):
                errors.extend(
                    _validate_entry(
                        entry,
                        expected_area=area_name,
                        field=f"{field}.entries[{entry_index}]",
                        seen_ids=seen_ids,
                    )
                )
    for required_area in REQUIRED_PACK_AREAS:
        if required_area not in seen_areas:
            errors.append(f"missing required profile pack area: {required_area}")

    lifecycle = data.get("lifecycle_boundaries")
    if not isinstance(lifecycle, dict):
        errors.append("lifecycle_boundaries must be an object")
    else:
        expected = {
            "planned": True,
            "rendered": False,
            "dry_run": False,
            "validated": False,
            "executed": False,
            "authorized": False,
            "promoted": False,
        }
        for key, value in expected.items():
            if lifecycle.get(key) is not value:
                errors.append(f"lifecycle_boundaries.{key} must be {str(value).lower()}")

    errors.extend(_validate_governance(data.get("governance"), capability_state="profile_pack_manifest"))

    for key, value in data.items():
        if key.endswith("_state") and isinstance(value, str) and value in FORBIDDEN_LIFECYCLE_STATES:
            errors.append(f"{key} must not be {value}")
    return errors


def validate_profile_pack_manifest_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_pack_manifest(data)
