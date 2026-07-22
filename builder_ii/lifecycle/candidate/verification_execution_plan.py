from __future__ import annotations

import datetime
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.lifecycle.candidate.verification_profiles import verification_profile_names, verification_profiles
from builder_ii.lifecycle.setup.target_profiles import target_names

VERIFICATION_EXECUTION_PLAN_KIND = "builder_ii.verification_execution_plan"
# Schema v2 (Ledger Genesis, D9 hard cut 2026-07-07): adds a required per-profile
# `timeout_seconds` and reconciles the pytest lane naming so the profile is runnable.
# There are no external users and validators are strict single-version, so no
# dual-version parser exists by design -- old v1 plans/approvals/receipts are
# invalidated on purpose. Bumped in lockstep with the approval and receipt schemas.
VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION = 3
B1_1_SUPPORTED_TARGET_PROFILE = "builder"
B1_1_SUPPORTED_VERIFICATION_PROFILE = "builder_full"

# Command profiles whose bounded invocation runs the TARGET repository's own code:
# pytest imports and executes the target's conftest.py, plugins, and test modules on
# this host with the operator's privileges. D7 (ratified 2026-07-07) requires the
# approval artifact to carry an explicit execution-risk acknowledgment for these, and
# the bounded runner refuses to spawn them without it. The safe builder-II-argv
# profiles (platform_status/docs_audit) are deliberately excluded so the safe lane
# carries no consent noise. This bounds *invocation* only, never *code behavior* --
# it is not a sandbox and must never be described as one.
TARGET_CODE_EXECUTING_PROFILES: tuple[str, ...] = ("pytest_full", "builder_full")

# D7 timeout policy: every plan profile/step declares a per-profile timeout, replacing
# the former hardcoded 30s. Range-checked to [1, 1800] seconds here (and again in the
# runner) so a silent default can never mask a hang.
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 1800

REQUIRED_DISABLED_AUTHORITY: dict[str, str] = {
    "arbitrary_shell": "disabled",
    "subprocess_execution": "disabled",
    "source_writes": "disabled",
    "patch_authority": "disabled",
    "git_mutation": "disabled",
    "model_execution": "disabled",
    "mcp_tool_invocation": "disabled",
    "goose_runtime": "disabled",
    "deepagents_runtime": "disabled",
    "autonomous_writes": "disabled",
    "b2_patch_authority": "disabled",
}

FORBIDDEN_STEP_KEYS = {
    "argv",
    "args",
    "command",
    "commands",
    "command_line",
    "command_string",
    "executable",
    "raw_command",
    "raw_shell",
    "shell",
    "shell_command",
    "subprocess",
}

FORBIDDEN_STEP_TOKENS = (
    "&&",
    "||",
    ";",
    "|",
    "`",
    "$(",
    "\n",
    "\r",
    ">",
    "<",
    "sh -c",
    "bash -c",
    "zsh -c",
    "python -c",
    "python3 -c",
    "eval(",
    "exec(",
)

FORBIDDEN_AUTHORITY_TERMS = (
    "patch authority",
    "patch_authority",
    "patch application",
    "patch_application",
    "model execution",
    "model_execution",
    "model provider",
    "mcp",
    "mcp_tool_invocation",
    "goose runtime",
    "goose_runtime",
    "goose start",
    "deepagents",
    "deepagents_runtime",
    "deepagent",
)

RAW_COMMAND_PREFIXES = (
    "uv run",
    "pytest",
    "python ",
    "python3 ",
    "git ",
    "make ",
    "npm ",
    "pnpm ",
    "poetry ",
    "bash ",
    "sh ",
    "zsh ",
    "goose ",
    "curl ",
    "wget ",
)

STRUCTURED_PROFILE_FIELDS = {
    "command_profile_ref",
    "profile",
    "step_id",
}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _default_allowed_command_profiles(verification_profile: str = B1_1_SUPPORTED_VERIFICATION_PROFILE) -> list[dict[str, Any]]:
    if verification_profile != B1_1_SUPPORTED_VERIFICATION_PROFILE:
        # A non-builder target (generic/core/fast) can only run its own test suite; the
        # builder-II self-verification profiles (platform_status/docs_audit/...) do not apply.
        return [
            {
                "profile": "pytest_full",
                "command_profile_ref": f"verification_profiles.{verification_profile}.pytest_full",
                "description": "Bounded approved runner profile for the target repository's full pytest lane.",
                "requires_approval": True,
                "execution_enabled": False,
                "timeout_seconds": 1800,
            }
        ]
    return [
        {
            # Runnable bounded target-code profile: runs the target repo's pytest suite.
            # profile == step_id == ref leaf ("pytest_full") so the runner's
            # _validate_fixed_profile invariant (step_id==profile, ref leaf==profile) holds.
            "profile": "pytest_full",
            "command_profile_ref": "verification_profiles.builder_full.pytest_full",
            "description": "Bounded approved runner profile for the target repository's full pytest lane.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 1800,
        },
        {
            # Runnable bounded target-code profile: full builder foundation lane
            # (pytest plus platform-truth checks) in one bounded invocation.
            "profile": "builder_full",
            "command_profile_ref": "verification_profiles.builder_full.builder_full",
            "description": "Bounded approved runner profile for the full builder foundation verification lane.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 1800,
        },
        {
            "profile": "release_proof",
            "command_profile_ref": "verification_profiles.builder_full.release_proof",
            "description": "Future approved B1 runner profile for release proof checks.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 600,
        },
        {
            "profile": "platform_status",
            "command_profile_ref": "verification_profiles.builder_full.platform_status",
            "description": "Future approved B1 runner profile for platform truth status checks.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
        {
            "profile": "docs_audit",
            "command_profile_ref": "verification_profiles.builder_full.docs_audit",
            "description": "Future approved B1 runner profile for documentation truth audits.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
        {
            "profile": "wrp_doctor_backends",
            "command_profile_ref": "verification_profiles.builder_full.wrp_doctor_backends",
            "description": "V.3 bounded validation_only: WRP backend doctor inventory health.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 60,
        },
        {
            "profile": "wrp_patterns_prove",
            "command_profile_ref": "verification_profiles.builder_full.wrp_patterns_prove",
            "description": "V.3/W.4 bounded validation_only: pure graph_runtime five-pattern proof.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 60,
        },
        {
            "profile": "wrp_fleet_fidelity",
            "command_profile_ref": "verification_profiles.builder_full.wrp_fleet_fidelity",
            "description": "V.3/W.3 bounded validation_only: fleet fidelity on pinned .builder paths.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 60,
        },
        {
            "profile": "semantic_doctor",
            "command_profile_ref": "verification_profiles.builder_full.semantic_doctor",
            "description": "V.3/V.1 bounded validation_only: semantic RO doctor.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
        {
            "profile": "semantic_map",
            "command_profile_ref": "verification_profiles.builder_full.semantic_map",
            "description": "V.3/V.1 bounded validation_only: semantic RO map (fixed max_files).",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 300,
        },
        {
            "profile": "r1_closure_validate",
            "command_profile_ref": "verification_profiles.builder_full.r1_closure_validate",
            "description": "Future approved B1 runner profile for R1 closure artifact validation.",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
    ]


def _default_planned_steps(verification_profile: str = B1_1_SUPPORTED_VERIFICATION_PROFILE) -> list[dict[str, Any]]:
    if verification_profile != B1_1_SUPPORTED_VERIFICATION_PROFILE:
        return [
            {
                "step_id": "pytest_full",
                "profile": "pytest_full",
                "description": "Run the target repository's full pytest suite in the bounded approved runner.",
                "command_profile_ref": f"verification_profiles.{verification_profile}.pytest_full",
                "requires_approval": True,
                "execution_enabled": False,
                "timeout_seconds": 1800,
            }
        ]
    return [
        {
            "step_id": "pytest_full",
            "profile": "pytest_full",
            "description": "Run the target repository's full pytest suite in the bounded approved runner.",
            "command_profile_ref": "verification_profiles.builder_full.pytest_full",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 1800,
        },
        {
            "step_id": "builder_full",
            "profile": "builder_full",
            "description": "Run the full builder foundation verification lane in the bounded approved runner.",
            "command_profile_ref": "verification_profiles.builder_full.builder_full",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 1800,
        },
        {
            "step_id": "release_proof",
            "profile": "release_proof",
            "description": "Run the release proof lane in a future approved B1 runner.",
            "command_profile_ref": "verification_profiles.builder_full.release_proof",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 600,
        },
        {
            "step_id": "platform_status",
            "profile": "platform_status",
            "description": "Render platform completion status in a future approved B1 runner.",
            "command_profile_ref": "verification_profiles.builder_full.platform_status",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
        {
            "step_id": "docs_audit",
            "profile": "docs_audit",
            "description": "Run the documentation truth audit in a future approved B1 runner.",
            "command_profile_ref": "verification_profiles.builder_full.docs_audit",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
        {
            "step_id": "wrp_doctor_backends",
            "profile": "wrp_doctor_backends",
            "description": "Run WRP backend doctor in the bounded approved runner.",
            "command_profile_ref": "verification_profiles.builder_full.wrp_doctor_backends",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 60,
        },
        {
            "step_id": "wrp_patterns_prove",
            "profile": "wrp_patterns_prove",
            "description": "Prove five orchestration patterns via pure graph_runtime.",
            "command_profile_ref": "verification_profiles.builder_full.wrp_patterns_prove",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 60,
        },
        {
            "step_id": "wrp_fleet_fidelity",
            "profile": "wrp_fleet_fidelity",
            "description": "Check fleet fidelity using pinned allocation/plan under .builder/verification/.",
            "command_profile_ref": "verification_profiles.builder_full.wrp_fleet_fidelity",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 60,
        },
        {
            "step_id": "semantic_doctor",
            "profile": "semantic_doctor",
            "description": "Run semantic RO doctor in the bounded approved runner.",
            "command_profile_ref": "verification_profiles.builder_full.semantic_doctor",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
        {
            "step_id": "semantic_map",
            "profile": "semantic_map",
            "description": "Emit semantic RO map in the bounded approved runner.",
            "command_profile_ref": "verification_profiles.builder_full.semantic_map",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 300,
        },
        {
            "step_id": "r1_closure_validate",
            "profile": "r1_closure_validate",
            "description": "Validate R1 closure proof artifacts in a future approved B1 runner.",
            "command_profile_ref": "verification_profiles.builder_full.r1_closure_validate",
            "requires_approval": True,
            "execution_enabled": False,
            "timeout_seconds": 120,
        },
    ]


def _default_plan_scope() -> dict[str, Any]:
    return {
        "scope_id": "b1_1_passive_verification_execution_plan",
        "description": "Passive verification execution planning artifact for a later approved B1 runner.",
        "includes": [
            "structured command profile references",
            "planned verification lane descriptions",
            "disabled authority declarations",
        ],
        "excludes": [
            "test execution",
            "shell or subprocess execution",
            "source writes",
            "patch authority",
            "git mutation",
            "model or tool calls",
            "Goose or deepagents runtime startup",
        ],
    }


def finalize_verification_execution_plan(
    *,
    target_profile: str,
    verification_profile: str,
    target_repo: str,
    artifact_root: str,
    runtime_mode: str = "passive_planning_only",
    plan_scope: dict[str, Any] | None = None,
    requested_by_command: str = "builder-verify plan",
    allowed_command_profiles: list[dict[str, Any]] | None = None,
    planned_steps: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
    isolation_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "kind": VERIFICATION_EXECUTION_PLAN_KIND,
        "schema_version": VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "target_profile": target_profile,
        "verification_profile": verification_profile,
        "target_repo": target_repo,
        "artifact_root": artifact_root,
        "runtime_mode": runtime_mode,
        "plan_mode": "planned_only",
        "plan_scope": plan_scope or _default_plan_scope(),
        "requested_by_command": requested_by_command,
        "allowed_command_profiles": allowed_command_profiles or _default_allowed_command_profiles(verification_profile),
        "planned_steps": planned_steps or _default_planned_steps(verification_profile),
        "disabled_authority": dict(REQUIRED_DISABLED_AUTHORITY),
        "approval_required": True,
        "execution_enabled": False,
        "artifact_is_authority": False,
        "errors": [],
        "valid": True,
    }
    if isolation_policy is not None:
        plan["isolation_policy"] = isolation_policy
    plan = attach_digest(plan, digest_key="verification_execution_plan_digest")
    errors = validate_verification_execution_plan_artifact(plan)
    if errors:
        plan["errors"] = errors
        plan["valid"] = False
        plan = attach_digest(plan, digest_key="verification_execution_plan_digest")
    return plan


def dumps_verification_execution_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def write_verification_execution_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_verification_execution_plan(plan), encoding="utf-8")


def plan_timeout_for_profile(plan: dict[str, Any], profile_name: str) -> int | None:
    """Return the plan-declared timeout (seconds) for a command profile, or None if absent.

    The bounded runner reads the operator-approved timeout from the plan (D7) rather than a
    hardcoded value; it range-checks the result again before use.
    """
    profiles = plan.get("allowed_command_profiles")
    if not isinstance(profiles, list):
        return None
    for item in profiles:
        if isinstance(item, dict) and item.get("profile") == profile_name:
            timeout = item.get("timeout_seconds")
            if isinstance(timeout, int) and not isinstance(timeout, bool):
                return timeout
            return None
    return None


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_timeout_seconds(value: Any, prefix: str) -> list[str]:
    # bool is a subclass of int; reject it explicitly so True/False cannot masquerade as a timeout.
    if not isinstance(value, int) or isinstance(value, bool):
        return [f"{prefix}.timeout_seconds must be an integer number of seconds"]
    if value < MIN_TIMEOUT_SECONDS or value > MAX_TIMEOUT_SECONDS:
        return [f"{prefix}.timeout_seconds must be within [{MIN_TIMEOUT_SECONDS}, {MAX_TIMEOUT_SECONDS}] seconds"]
    return []


def _normalized_leaf_name(path: str) -> str:
    leaf = path.rsplit(".", 1)[-1].lower()
    while leaf.endswith("]") and "[" in leaf:
        leaf = leaf[: leaf.rfind("[")]
    return leaf


def _target_supports_verification_profile(target_profile: Any, verification_profile: Any) -> bool:
    """True when (target, verification_profile) is a compatible pair (B4.2 generic-lane extension).

    The lane originally pinned target=builder/verification=builder_full; it now accepts any pair
    where the verification profile declares the target in its compatible_targets (generic_basic for
    generic, core_smoke/core_focused for core, builder_fast/builder_full for builder). Which command
    profiles are actually runnable is a separate, per-profile decision enforced by the runner.
    """
    for profile in verification_profiles():
        if profile.name == verification_profile and target_profile in profile.compatible_targets:
            return True
    return False


def _validate_profile_consistency(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target_profile = data.get("target_profile")
    verification_profile = data.get("verification_profile")
    if not _target_supports_verification_profile(target_profile, verification_profile):
        errors.append(
            f"verification_profile {verification_profile!r} is not compatible with "
            f"target_profile {target_profile!r}"
        )

    if not isinstance(verification_profile, str) or not verification_profile:
        return errors

    expected_prefix = f"verification_profiles.{verification_profile}."
    for collection_name in ("allowed_command_profiles", "planned_steps"):
        collection = data.get(collection_name)
        if not isinstance(collection, list):
            continue
        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                continue
            ref = item.get("command_profile_ref")
            if isinstance(ref, str) and not ref.startswith(expected_prefix):
                errors.append(f"{collection_name}[{index}].command_profile_ref must begin with {expected_prefix}")
    return errors


def _validate_disabled_authority(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    disabled = data.get("disabled_authority")
    if not isinstance(disabled, dict):
        return ["disabled_authority must be an object"]
    for key, expected in REQUIRED_DISABLED_AUTHORITY.items():
        if disabled.get(key) != expected:
            errors.append(f"disabled_authority.{key} must remain {expected}")
    return errors


def scan_planned_step(value: Any, path: str) -> list[str]:
    return _scan_planned_step(value, path)

def _scan_planned_step(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            if key.lower() in FORBIDDEN_STEP_KEYS:
                errors.append(f"{child_path} must not contain raw shell or subprocess fields")
            errors.extend(_scan_planned_step(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_scan_planned_step(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        leaf = _normalized_leaf_name(path)
        for token in FORBIDDEN_STEP_TOKENS:
            if token in lowered:
                errors.append(f"{path} contains forbidden shell separator or injection token {token!r}")
        if leaf not in STRUCTURED_PROFILE_FIELDS:
            stripped = lowered.strip()
            if any(stripped == prefix.strip() or stripped.startswith(prefix) for prefix in RAW_COMMAND_PREFIXES):
                errors.append(f"{path} contains raw shell string")
        for term in FORBIDDEN_AUTHORITY_TERMS:
            if term in lowered:
                errors.append(f"{path} claims forbidden authority term {term!r}")
    elif isinstance(value, bool) and path:
        leaf = _normalized_leaf_name(path)
        if value is True and leaf in {
            "execution_enabled",
            "patch_authority",
            "model_execution",
            "mcp_tool_invocation",
            "goose_runtime",
            "deepagents_runtime",
        }:
            errors.append(f"{path} must not enable execution or external authority")
    return errors


def _validate_allowed_command_profiles(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profiles = data.get("allowed_command_profiles")
    if not isinstance(profiles, list) or not profiles:
        return ["allowed_command_profiles must be a non-empty list"]
    seen: set[str] = set()
    for index, profile in enumerate(profiles):
        prefix = f"allowed_command_profiles[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{prefix} must be an object")
            continue
        profile_id = profile.get("profile")
        if not isinstance(profile_id, str) or not profile_id.strip():
            errors.append(f"{prefix}.profile must be a non-empty string")
        elif profile_id in seen:
            errors.append(f"{prefix}.profile must be unique")
        else:
            seen.add(profile_id)
        if not _is_non_empty_string(profile.get("command_profile_ref")):
            errors.append(f"{prefix}.command_profile_ref must be a non-empty string")
        if profile.get("requires_approval") is not True:
            errors.append(f"{prefix}.requires_approval must be true")
        if profile.get("execution_enabled") is not False:
            errors.append(f"{prefix}.execution_enabled must be false or NOT_AUTHORIZED")
        errors.extend(_validate_timeout_seconds(profile.get("timeout_seconds"), prefix))
    return errors


def _validate_planned_steps(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    steps = data.get("planned_steps")
    if not isinstance(steps, list) or not steps:
        return ["planned_steps must be a non-empty list"]
    raw_allowed_profiles = data.get("allowed_command_profiles")
    allowed_profile_items = raw_allowed_profiles if isinstance(raw_allowed_profiles, list) else []
    allowed_profiles = {profile.get("profile") for profile in allowed_profile_items if isinstance(profile, dict)}
    seen: set[str] = set()
    for index, step in enumerate(steps):
        prefix = f"planned_steps[{index}]"
        if not isinstance(step, dict):
            errors.append(f"{prefix} must be an object")
            continue
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id.strip():
            errors.append(f"{prefix}.step_id must be a non-empty string")
        elif step_id in seen:
            errors.append(f"{prefix}.step_id must be unique")
        else:
            seen.add(step_id)
        if not _is_non_empty_string(step.get("profile")):
            errors.append(f"{prefix}.profile must be a non-empty string")
        elif step.get("profile") not in allowed_profiles:
            errors.append(f"{prefix}.profile must reference allowed_command_profiles")
        if not _is_non_empty_string(step.get("description")):
            errors.append(f"{prefix}.description must be a non-empty string")
        if not _is_non_empty_string(step.get("command_profile_ref")):
            errors.append(f"{prefix}.command_profile_ref must be a non-empty string")
        if step.get("requires_approval") is not True:
            errors.append(f"{prefix}.requires_approval must be true")
        if step.get("execution_enabled") is not False:
            errors.append(f"{prefix}.execution_enabled must be false or NOT_AUTHORIZED")
        errors.extend(_validate_timeout_seconds(step.get("timeout_seconds"), prefix))
        errors.extend(_scan_planned_step(step, prefix))
    return errors


def validate_verification_execution_plan_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["verification execution plan artifact must be a JSON object"]

    if data.get("kind") != VERIFICATION_EXECUTION_PLAN_KIND:
        errors.append(f"kind must be {VERIFICATION_EXECUTION_PLAN_KIND}")
    if data.get("schema_version") != VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION}")
    if not _is_non_empty_string(data.get("generated_at")):
        errors.append("generated_at must be a non-empty string")
    if data.get("target_profile") not in target_names():
        errors.append("target_profile must be one of: generic, builder, core")
    if data.get("verification_profile") not in verification_profile_names():
        errors.append("verification_profile must be a known verification profile")
    if not _is_non_empty_string(data.get("target_repo")):
        errors.append("target_repo must be a non-empty string")
    if not _is_non_empty_string(data.get("artifact_root")):
        errors.append("artifact_root must be a non-empty string")
    if data.get("runtime_mode") != "passive_planning_only":
        errors.append("runtime_mode must be passive_planning_only")
    if data.get("plan_mode") != "planned_only":
        errors.append("plan_mode must be planned_only")
    if not isinstance(data.get("plan_scope"), dict):
        errors.append("plan_scope must be an object")
    if not _is_non_empty_string(data.get("requested_by_command")):
        errors.append("requested_by_command must be a non-empty string")
    if data.get("approval_required") is not True:
        errors.append("approval_required must be true")
    if data.get("execution_enabled") is not False:
        errors.append("execution_enabled must be false or NOT_AUTHORIZED")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")

    errors.extend(_validate_disabled_authority(data))
    errors.extend(_validate_profile_consistency(data))
    errors.extend(_validate_allowed_command_profiles(data))
    errors.extend(_validate_planned_steps(data))

    if "isolation_policy" in data:
        isolation_policy = data["isolation_policy"]
        if not isinstance(isolation_policy, dict):
            errors.append("isolation_policy must be an object")
        elif isolation_policy.get("kind") != "builder_ii.verification_isolation_policy":
            errors.append("isolation_policy must be a builder_ii.verification_isolation_policy artifact")
        errors.extend(_scan_planned_step(isolation_policy, "isolation_policy"))

    artifact_errors = data.get("errors")
    if not isinstance(artifact_errors, list) or not all(isinstance(e, str) for e in artifact_errors):
        errors.append("errors must be a list of strings")
    valid = data.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif valid is True and artifact_errors:
        errors.append("errors must be empty when valid is true")
    elif valid is False and not artifact_errors:
        errors.append("errors must be non-empty when valid is false")

    digest = data.get("verification_execution_plan_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("verification_execution_plan_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key="verification_execution_plan_digest"):
        errors.append("verification_execution_plan_digest drift detected")

    return errors


def validate_verification_execution_plan_file(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"verification execution plan file could not be read: {exc}"]
    try:
        data = json_lib.loads(raw)
    except json_lib.JSONDecodeError as exc:
        return [f"verification execution plan file is not valid JSON: {exc}"]
    return validate_verification_execution_plan_artifact(data)
