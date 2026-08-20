from __future__ import annotations

import datetime
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    TARGET_CODE_EXECUTING_PROFILES,
    VERIFICATION_EXECUTION_PLAN_KIND,
    VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION,
    validate_verification_execution_plan_artifact,
)
from builder_ii.lifecycle.candidate.verification_profiles import verification_profile_names
from builder_ii.lifecycle.setup.target_profiles import target_names

VERIFICATION_EXECUTION_APPROVAL_KIND = "builder_ii.verification_execution_approval"
# Schema v2 (D9 hard cut, in lockstep with the plan and receipt): adds the D7
# execution-risk acknowledgment fields required when a target-code-executing profile
# (pytest_full/builder_full) is approved.
VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION = 3
APPROVAL_MODE = "hitl_plan_digest_approval"

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
    "direct_execution": "disabled",
}

FORBIDDEN_SHELL_TOKENS = (
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
)

RAW_COMMAND_PATTERNS = (
    re.compile(r"\buv run\b", re.IGNORECASE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bpython3?\s+-m\s+pytest\b", re.IGNORECASE),
    re.compile(r"\bgit\s+\S+", re.IGNORECASE),
    re.compile(r"\bmake\s+\S+", re.IGNORECASE),
    re.compile(r"\bnpm\s+\S+", re.IGNORECASE),
    re.compile(r"\bpnpm\s+\S+", re.IGNORECASE),
    re.compile(r"\bpoetry\s+\S+", re.IGNORECASE),
    re.compile(r"\bbash\s+-c\b", re.IGNORECASE),
    re.compile(r"\bsh\s+-c\b", re.IGNORECASE),
    re.compile(r"\bzsh\s+-c\b", re.IGNORECASE),
)

CLAIM_VERB_PATTERN = re.compile(
    r"\b(approve|approved|approves|authorize|authorized|authorizes|grant|grants|granted|allow|allows|allowed|enable|enables|enabled|permit|permits|permitted)\b",
    re.IGNORECASE,
)

FORBIDDEN_AUTHORITY_TERMS = {
    "patch": ("patch", "patch authority", "patching"),
    "model": ("model", "model execution", "provider"),
    "mcp": ("mcp", "tool invocation", "tool call"),
    "goose": ("goose", "goose runtime"),
    "deepagents": ("deepagents", "deepagent"),
}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def parse_approval_timestamp(value: Any, *, field: str) -> tuple[datetime.datetime | None, list[str]]:
    """Parse one approval timestamp without accepting local/ambiguous time."""
    if not _is_non_empty_string(value):
        return None, [f"{field} must be a non-empty timezone-aware timestamp"]
    raw = value.strip()
    try:
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, [f"{field} must be a valid ISO-8601 timestamp"]
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None, [f"{field} must be timezone-aware"]
    return parsed.astimezone(datetime.timezone.utc), []


def validate_approval_time_window(
    approval: Any, *, now: datetime.datetime | None = None
) -> list[str]:
    """Validate the signed approval interval and, when requested, current expiry."""
    if not isinstance(approval, dict):
        return ["verification execution approval artifact must be a JSON object"]
    generated, errors = parse_approval_timestamp(approval.get("generated_at"), field="generated_at")
    expires, expiry_errors = parse_approval_timestamp(approval.get("expires_at"), field="expires_at")
    errors.extend(expiry_errors)
    if generated is not None and expires is not None and expires <= generated:
        errors.append("expires_at must be after generated_at")
    if now is not None:
        if now.tzinfo is None or now.utcoffset() is None:
            errors.append("execution-time now must be timezone-aware")
        else:
            observed = now.astimezone(datetime.timezone.utc)
            if generated is not None and observed < generated:
                errors.append("verification execution approval is not yet effective")
            if expires is not None and observed >= expires:
                errors.append("verification execution approval is expired")
    return _dedupe_errors(errors)


def _dedupe_errors(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def _plan_allowed_command_profiles(plan: dict[str, Any]) -> list[str]:
    profiles = plan.get("allowed_command_profiles")
    if not isinstance(profiles, list):
        return []
    result: list[str] = []
    for item in profiles:
        if isinstance(item, dict) and _is_non_empty_string(item.get("profile")):
            result.append(item["profile"].strip())
    return result


def _plan_step_ids(plan: dict[str, Any]) -> list[str]:
    steps = plan.get("planned_steps")
    if not isinstance(steps, list):
        return []
    result: list[str] = []
    for item in steps:
        if isinstance(item, dict) and _is_non_empty_string(item.get("step_id")):
            result.append(item["step_id"].strip())
    return result


def _safe_default(names: list[str]) -> list[str]:
    """Drop target-code-executing profiles/steps from an auto-approval default.

    A default approval (no explicit selection) approves only the safe builder-II-argv
    profiles, so the safe verification lane never carries a risk acknowledgment it does
    not need (D7 / craft-doctrine #3). Approving pytest_full/builder_full requires an
    explicit selection plus the execution-risk acknowledgment.
    """
    return [name for name in names if name not in TARGET_CODE_EXECUTING_PROFILES]


def _approves_target_code(approved_profiles: list[str], approved_steps: list[str]) -> bool:
    selected = set(approved_profiles) | set(approved_steps)
    return bool(selected & set(TARGET_CODE_EXECUTING_PROFILES))


def _default_approval_scope() -> dict[str, Any]:
    return {
        "scope_kind": "plan_digest_binding_only",
        "description": "Binds human approval to the exact passive verification plan digest for future B1.3 consideration only.",
        "future_execution_path": "b1_3_runner_required",
        "grants_execution_authority": False,
    }


def _approval_id_basis(
    *,
    generated_at: str,
    plan_digest: str,
    approval_actor: str,
    approval_reason: str,
    approval_statement: str,
    approved_command_profiles: list[str],
    approved_step_ids: list[str],
    execution_risk_acknowledged: bool,
    acknowledged_risk: str | None,
) -> str:
    return digest_jsonable(
        {
            "generated_at": generated_at,
            "plan_digest": plan_digest,
            "approval_actor": approval_actor,
            "approval_reason": approval_reason,
            "approval_statement": approval_statement,
            "approved_command_profiles": approved_command_profiles,
            "approved_step_ids": approved_step_ids,
            "execution_risk_acknowledged": execution_risk_acknowledged,
            "acknowledged_risk": acknowledged_risk,
            "approval_mode": APPROVAL_MODE,
        }
    )


def finalize_verification_execution_approval(
    *,
    plan: dict[str, Any],
    plan_path: str,
    approval_actor: str,
    approval_reason: str,
    approved_command_profiles: list[str] | None = None,
    approved_step_ids: list[str] | None = None,
    approval_statement: str | None = None,
    approval_scope: dict[str, Any] | None = None,
    generated_at: str | None = None,
    expires_at: str = "2099-01-01T00:00:00Z",
    execution_risk_acknowledged: bool = False,
    acknowledged_risk: str | None = None,
) -> dict[str, Any]:
    plan_digest = str(plan.get("verification_execution_plan_digest", ""))
    generated = generated_at or _utc_now()
    # A default (unselected) approval binds only the safe builder-II-argv profiles.
    # Approving a target-code-executing profile requires an explicit selection plus the
    # execution-risk acknowledgment (validated below and enforced by the bounded runner).
    selected_profiles = (
        list(approved_command_profiles)
        if approved_command_profiles is not None
        else _safe_default(_plan_allowed_command_profiles(plan))
    )
    selected_steps = (
        list(approved_step_ids) if approved_step_ids is not None else _safe_default(_plan_step_ids(plan))
    )
    statement = approval_statement or (
        f"Human approval binds only to verification execution plan digest {plan_digest} for future B1.3 runner consideration."
    )

    approval: dict[str, Any] = {
        "kind": VERIFICATION_EXECUTION_APPROVAL_KIND,
        "schema_version": VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION,
        "generated_at": generated,
        "approval_id": _approval_id_basis(
            generated_at=generated,
            plan_digest=plan_digest,
            approval_actor=approval_actor,
            approval_reason=approval_reason,
            approval_statement=statement,
            approved_command_profiles=selected_profiles,
            approved_step_ids=selected_steps,
            execution_risk_acknowledged=bool(execution_risk_acknowledged),
            acknowledged_risk=acknowledged_risk,
        ),
        "approval_mode": APPROVAL_MODE,
        "approved": True,
        "target_profile": plan.get("target_profile"),
        "verification_profile": plan.get("verification_profile"),
        "target_repo": plan.get("target_repo"),
        "artifact_root": plan.get("artifact_root"),
        "plan_path": plan_path,
        "plan_digest": plan_digest,
        "plan_kind": plan.get("kind"),
        "plan_schema_version": plan.get("schema_version"),
        "approved_command_profiles": selected_profiles,
        "approved_step_ids": selected_steps,
        "approval_statement": statement,
        "approval_actor": approval_actor,
        "approval_reason": approval_reason,
        "approval_scope": approval_scope or _default_approval_scope(),
        "expires_at": expires_at,
        "execution_enabled": False,
        "approval_enables_execution": False,
        "artifact_is_authority": False,
        "requires_b1_3_runner": True,
        # D7 execution-risk acknowledgment. Required (True + non-empty acknowledged_risk)
        # only when a target-code-executing profile is approved; the ack authorizes
        # nothing on its own -- it records that the operator understood the profile runs
        # the target repo's own code on this host before the runner would ever spawn it.
        "execution_risk_acknowledged": bool(execution_risk_acknowledged),
        "acknowledged_risk": acknowledged_risk,
        "disabled_authority": dict(REQUIRED_DISABLED_AUTHORITY),
        "errors": [],
        "valid": True,
    }
    approval = attach_digest(approval, digest_key="verification_execution_approval_digest")
    errors = _dedupe_errors(
        validate_verification_execution_approval_artifact(approval)
        + validate_verification_execution_approval_against_plan(approval, plan)
    )
    if errors:
        approval["errors"] = errors
        approval["valid"] = False
        approval = attach_digest(approval, digest_key="verification_execution_approval_digest")
    return approval


def dumps_verification_execution_approval(approval: dict[str, Any]) -> str:
    return json_lib.dumps(approval, indent=2, sort_keys=True) + "\n"


def write_verification_execution_approval(approval: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_verification_execution_approval(approval), encoding="utf-8")


def _validate_disabled_authority(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    disabled = data.get("disabled_authority")
    if not isinstance(disabled, dict):
        return ["disabled_authority must be an object"]
    for key, expected in REQUIRED_DISABLED_AUTHORITY.items():
        if disabled.get(key) != expected:
            errors.append(f"disabled_authority.{key} must remain {expected}")
    return errors


def _validate_string_list(field: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not _is_non_empty_string(item):
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        cleaned = item.strip()
        if cleaned in seen:
            errors.append(f"{field}[{index}] must be unique")
        else:
            seen.add(cleaned)
    return errors


def _claims_forbidden_authority(text: str) -> bool:
    if not CLAIM_VERB_PATTERN.search(text):
        return False
    lowered = text.lower()
    return any(any(term in lowered for term in terms) for terms in FORBIDDEN_AUTHORITY_TERMS.values())


def _scan_approval_text(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            errors.extend(_scan_approval_text(item, child_path))
        return errors
    if isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_scan_approval_text(item, f"{path}[{index}]"))
        return errors
    if not isinstance(value, str):
        return errors

    for token in FORBIDDEN_SHELL_TOKENS:
        if token in value:
            errors.append(f"{path} contains forbidden shell separator or injection token {token!r}")
    if any(pattern.search(value) for pattern in RAW_COMMAND_PATTERNS):
        errors.append(f"{path} contains raw shell string")
    if _claims_forbidden_authority(value):
        errors.append(f"{path} claims forbidden authority")
    return errors


def _scan_ack_text(value: str, path: str) -> list[str]:
    """Scan the human execution-risk acknowledgment for injection separators and authority claims.

    Unlike the general approval-text scan, this deliberately does NOT reject raw-command
    words: an honest acknowledgment must be free to name the test runner (e.g. "pytest")
    and imported "conftest"/plugin code (D7). The ack is a stored consent string, never
    an executed command, so it is guarded only against shell-injection separators and
    forbidden-authority claims.
    """
    errors: list[str] = []
    for token in FORBIDDEN_SHELL_TOKENS:
        if token in value:
            errors.append(f"{path} contains forbidden shell separator or injection token {token!r}")
    if _claims_forbidden_authority(value):
        errors.append(f"{path} claims forbidden authority")
    return errors


def _validate_execution_risk_acknowledgment(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ack = data.get("execution_risk_acknowledged")
    acknowledged_risk = data.get("acknowledged_risk")
    if not isinstance(ack, bool):
        errors.append("execution_risk_acknowledged must be a boolean")
    if acknowledged_risk is not None and not _is_non_empty_string(acknowledged_risk):
        errors.append("acknowledged_risk must be null or a non-empty string")

    approved_profiles = [p for p in (data.get("approved_command_profiles") or []) if isinstance(p, str)]
    approved_steps = [s for s in (data.get("approved_step_ids") or []) if isinstance(s, str)]
    if _approves_target_code(approved_profiles, approved_steps):
        plan = data.get("plan")
        if isinstance(plan, dict) and plan.get("tree_clean") is not True:
            errors.append("target-code approval requires referenced plan.tree_clean=true")
        if ack is not True:
            errors.append(
                "execution_risk_acknowledged must be true when a target-code-executing profile "
                "(pytest_full/builder_full) is approved"
            )
        if not _is_non_empty_string(acknowledged_risk):
            errors.append(
                "acknowledged_risk must name the target-code execution risk when a "
                "target-code-executing profile is approved"
            )
    if isinstance(acknowledged_risk, str):
        errors.extend(_scan_ack_text(acknowledged_risk, "acknowledged_risk"))
    return errors


def _validate_approval_scope(scope: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(scope, dict):
        return ["approval_scope must be an object"]
    if scope.get("scope_kind") != "plan_digest_binding_only":
        errors.append("approval_scope.scope_kind must be plan_digest_binding_only")
    if not _is_non_empty_string(scope.get("description")):
        errors.append("approval_scope.description must be a non-empty string")
    if scope.get("future_execution_path") != "b1_3_runner_required":
        errors.append("approval_scope.future_execution_path must be b1_3_runner_required")
    if scope.get("grants_execution_authority") is not False:
        errors.append("approval_scope.grants_execution_authority must be false or NOT_AUTHORIZED")
    return errors


def validate_verification_execution_approval_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["verification execution approval artifact must be a JSON object"]

    if data.get("kind") != VERIFICATION_EXECUTION_APPROVAL_KIND:
        errors.append(f"kind must be {VERIFICATION_EXECUTION_APPROVAL_KIND}")
    if data.get("schema_version") != VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION}")
    errors.extend(validate_approval_time_window(data))
    if not _is_sha256_hex(data.get("approval_id")):
        errors.append("approval_id must be a SHA-256 hex string")
    if data.get("approval_mode") != APPROVAL_MODE:
        errors.append(f"approval_mode must be {APPROVAL_MODE}")
    if data.get("approved") is not True:
        errors.append("approved must be true")
    if data.get("target_profile") not in target_names():
        errors.append("target_profile must be one of: generic, builder, core")
    if data.get("verification_profile") not in verification_profile_names():
        errors.append("verification_profile must be a known verification profile")
    if not _is_non_empty_string(data.get("target_repo")):
        errors.append("target_repo must be a non-empty string")
    if not _is_non_empty_string(data.get("artifact_root")):
        errors.append("artifact_root must be a non-empty string")
    if not _is_non_empty_string(data.get("plan_path")):
        errors.append("plan_path must be a non-empty string")
    if not _is_sha256_hex(data.get("plan_digest")):
        errors.append("plan_digest must be a SHA-256 hex string")
    if data.get("plan_kind") != VERIFICATION_EXECUTION_PLAN_KIND:
        errors.append(f"plan_kind must be {VERIFICATION_EXECUTION_PLAN_KIND}")
    if data.get("plan_schema_version") != VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION:
        errors.append(f"plan_schema_version must be {VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION}")

    errors.extend(_validate_string_list("approved_command_profiles", data.get("approved_command_profiles")))
    errors.extend(_validate_string_list("approved_step_ids", data.get("approved_step_ids")))

    if not _is_non_empty_string(data.get("approval_statement")):
        errors.append("approval_statement must be a non-empty string")
    if not _is_non_empty_string(data.get("approval_actor")):
        errors.append("approval_actor must be a non-empty string")
    if not _is_non_empty_string(data.get("approval_reason")):
        errors.append("approval_reason must be a non-empty string")
    errors.extend(_validate_approval_scope(data.get("approval_scope")))

    if data.get("execution_enabled") is not False:
        errors.append("execution_enabled must be false or NOT_AUTHORIZED")
    if data.get("approval_enables_execution") is not False:
        errors.append("approval_enables_execution must be false or NOT_AUTHORIZED")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    if data.get("requires_b1_3_runner") is not True:
        errors.append("requires_b1_3_runner must be true")

    errors.extend(_validate_execution_risk_acknowledgment(data))
    errors.extend(_validate_disabled_authority(data))
    errors.extend(_scan_approval_text(data.get("approval_statement"), "approval_statement"))
    errors.extend(_scan_approval_text(data.get("approval_reason"), "approval_reason"))
    errors.extend(_scan_approval_text(data.get("approval_scope"), "approval_scope"))

    artifact_errors = data.get("errors")
    if not isinstance(artifact_errors, list) or not all(isinstance(item, str) for item in artifact_errors):
        errors.append("errors must be a list of strings")
    valid = data.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif valid is True and artifact_errors:
        errors.append("errors must be empty when valid is true")
    elif valid is False and not artifact_errors:
        errors.append("errors must be non-empty when valid is false")

    digest = data.get("verification_execution_approval_digest")
    if not _is_sha256_hex(digest):
        errors.append("verification_execution_approval_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key="verification_execution_approval_digest"):
        errors.append("verification_execution_approval_digest drift detected")

    return _dedupe_errors(errors)


def validate_verification_execution_approval_against_plan(
    approval: Any,
    plan: Any,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(approval, dict):
        return ["verification execution approval artifact must be a JSON object"]
    if not isinstance(plan, dict):
        return ["referenced verification execution plan must be a JSON object"]

    plan_errors = validate_verification_execution_plan_artifact(plan)
    if plan_errors:
        return [f"referenced verification execution plan invalid: {error}" for error in plan_errors]

    if approval.get("plan_digest") != plan.get("verification_execution_plan_digest"):
        errors.append("plan_digest does not match referenced plan")
    if approval.get("plan_kind") != plan.get("kind"):
        errors.append("plan_kind does not match referenced plan")
    if approval.get("plan_schema_version") != plan.get("schema_version"):
        errors.append("plan_schema_version does not match referenced plan")
    if approval.get("target_profile") != plan.get("target_profile"):
        errors.append("target_profile does not match referenced plan")
    if approval.get("verification_profile") != plan.get("verification_profile"):
        errors.append("verification_profile does not match referenced plan")
    if approval.get("target_repo") != plan.get("target_repo"):
        errors.append("target_repo does not match referenced plan")
    if approval.get("artifact_root") != plan.get("artifact_root"):
        errors.append("artifact_root does not match referenced plan")

    approved_profiles = approval.get("approved_command_profiles")
    approved_steps = approval.get("approved_step_ids")
    if _approves_target_code(
        [p for p in approved_profiles or [] if isinstance(p, str)],
        [s for s in approved_steps or [] if isinstance(s, str)],
    ) and plan.get("tree_clean") is not True:
        errors.append("target-code approval requires referenced plan.tree_clean=true")

    allowed_profiles = set(_plan_allowed_command_profiles(plan))
    approved_profiles = approval.get("approved_command_profiles")
    if isinstance(approved_profiles, list):
        extras = sorted(profile for profile in approved_profiles if profile not in allowed_profiles)
        if extras:
            errors.append("approved_command_profiles must be a subset of the referenced plan allowed_command_profiles")

    planned_step_ids = set(_plan_step_ids(plan))
    approved_step_ids = approval.get("approved_step_ids")
    if isinstance(approved_step_ids, list):
        extras = sorted(step_id for step_id in approved_step_ids if step_id not in planned_step_ids)
        if extras:
            errors.append("approved_step_ids must be a subset of the referenced plan planned_steps")

    return _dedupe_errors(errors)


def validate_verification_execution_approval_file(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"verification execution approval file could not be read: {exc}"]
    try:
        data = json_lib.loads(raw)
    except json_lib.JSONDecodeError as exc:
        return [f"verification execution approval file is not valid JSON: {exc}"]
    return validate_verification_execution_approval_artifact(data)
