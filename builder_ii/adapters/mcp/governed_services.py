"""Thin MCP adapters for existing governed Builder-II services."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from builder_ii.adapters.mcp.governed_call import build_read_only_policy
from builder_ii.core.config import load_settings
from builder_ii.core.config_schema import digest_jsonable
from builder_ii.core.demo_loop import DEMO_VERIFICATION_RECEIPT_KIND, validate_demo_verification_receipt
from builder_ii.core.governed_prepare_package import (
    create_governed_prepare_package,
    validate_governed_prepare_package_directory,
)
from builder_ii.core.mcp_policy import MCP_POLICY_KIND, validate_mcp_policy
from builder_ii.core.orchestration_status import build_obligation_board
from builder_ii.core.repo_map import create_repo_map
from builder_ii.core.repo_search import search_repo_map
from builder_ii.governance.authority.readonly_authority import (
    create_read_policy,
    execute_content_read,
    validate_content_read_receipt,
)
from builder_ii.governance.hitl.hitl_patch_proposal import (
    MAX_UNIFIED_DIFF_BYTES,
    create_bound_hitl_patch_proposal,
    validate_hitl_patch_proposal,
    write_hitl_patch_proposal,
)
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.lifecycle.candidate.execution_postflight_records import (
    validate_execution_postflight_record,
)
from builder_ii.lifecycle.candidate.verification_execution_approval import (
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    validate_verification_execution_plan_artifact,
    write_verification_execution_plan,
)
from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    VERIFICATION_EXECUTION_RECEIPT_KIND,
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.lifecycle.candidate.verification_execution_runner import run_approved_verification

MAX_MAP_FILES = 500
MAX_MAP_FILE_BYTES = 1_000_000
MAX_SEARCH_RESULTS = 100
MAX_READ_BYTES = 256 * 1024
MAX_TASK_BYTES = 4096
MAX_SERVICE_INPUT_BYTES = 8 * 1024
MAX_SERVICE_OUTPUT_BYTES = 4 * 1024 * 1024
SERVICE_TOOLS = {
    "repo_map",
    "repo_search",
    "content_read",
    "prepare_package",
    "validate_prepare_package",
    "delegation_status",
    "verification_plan",
    "verification_execute",
    "patch_proposal",
}
TARGET_PROFILES = {"generic", "builder", "core"}
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_HEAD_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_EVENT_TYPE_BY_STATUS = {
    "succeeded": "mcp_call_executed",
    "denied": "mcp_call_denied",
    "failed": "mcp_call_failed",
}


class ServiceDenied(ValueError):
    """Expected caller/admission denial that must be recorded as denied, not failed."""


class CorruptLedgerError(RuntimeError):
    """Existing session evidence cannot be safely extended."""


def _json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_size(value: Any) -> int:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return len(raw)


def _service_policy(tool_name: str) -> dict[str, Any]:
    """Reuse the canonical deny-by-default policy with truthful bounded service ceilings."""
    policy = build_read_only_policy()
    policy["max_input_bytes"] = (
        MAX_UNIFIED_DIFF_BYTES + MAX_SERVICE_INPUT_BYTES if tool_name == "patch_proposal" else MAX_SERVICE_INPUT_BYTES
    )
    policy["max_output_bytes"] = MAX_SERVICE_OUTPUT_BYTES
    if tool_name == "verification_execute":
        policy["allowed_risk_classes"] = ["medium_risk"]
        policy["timeout_seconds"] = 1800
        policy["governance"]["bounded_subprocess_execution"] = "HITL_APPROVAL_GATED"
    else:
        policy["governance"]["bounded_subprocess_execution"] = "DISABLED"
    return policy


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _controlled_path(raw_value: Any, *, root: Path, field: str) -> Path:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ServiceDenied(f"{field} must be a non-empty string")
    supplied = Path(raw_value.strip())
    candidate = supplied if supplied.is_absolute() else root.resolve() / supplied
    if not _within(candidate, root):
        raise ServiceDenied(f"{field} must remain inside the server-controlled Builder-II artifact root")
    return candidate.resolve()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


def _validate_identity(*, session_id: str, target_name: str, tool_name: str) -> None:
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        raise ServiceDenied("session_id must be a 1-128 character path-safe identifier")
    if target_name not in TARGET_PROFILES:
        raise ServiceDenied("target profile must be one of generic, builder, core")
    if tool_name not in SERVICE_TOOLS:
        raise ServiceDenied("service is not admitted by the governed MCP inventory")


def _assert_mcp_ledger_extendable(
    *, builder_root: Path, session_id: str
) -> tuple[list[tuple[dict[str, Any], Path]], str]:
    """Replay the current MCP session before any new service artifact write."""
    events_dir = builder_root.resolve() / "sessions" / session_id / "events"
    existing = load_event_records(events_dir)
    if not existing:
        return existing, "initialized"
    replay = replay_events(existing, session_id=session_id)
    if not replay.get("valid"):
        detail = "; ".join(str(error) for error in replay.get("errors", [])) or "unknown replay error"
        raise CorruptLedgerError(f"existing MCP session ledger is invalid: {detail}")
    return existing, str(replay.get("current_stage") or "initialized")


def _validate_policy_ref(policy_ref: Any) -> list[str]:
    if not isinstance(policy_ref, dict):
        return ["policy_ref must be an object"]
    errors: list[str] = []
    expected = {
        "role": "mcp_tool_policy",
        "kind": MCP_POLICY_KIND,
        "required": True,
    }
    for key, value in expected.items():
        if policy_ref.get(key) != value:
            errors.append(f"policy_ref.{key} is invalid")
    path_value = policy_ref.get("path")
    if not isinstance(path_value, str) or not path_value:
        errors.append("policy_ref.path must be a non-empty string")
    sha = policy_ref.get("sha256")
    if not _is_sha256(sha):
        errors.append("policy_ref.sha256 must be a SHA-256 hex digest")
    if errors:
        return errors
    policy_path = Path(path_value)
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"policy_ref.path is not a readable policy artifact: {exc}"]
    if canonical_digest(policy) != sha:
        errors.append("policy_ref.sha256 does not bind the persisted policy artifact")
    policy_errors = validate_mcp_policy(policy)
    errors.extend(f"policy_ref policy invalid: {error}" for error in policy_errors)
    return errors


def validate_mcp_service_receipt(record: Any) -> list[str]:
    """Validate the v2 service receipt and its persisted policy binding."""
    if not isinstance(record, dict):
        return ["receipt must be an object"]
    errors = [
        key + " is required"
        for key in (
            "kind",
            "schema_version",
            "target_profile",
            "session_id",
            "service",
            "status",
            "arguments",
            "result",
            "digest",
            "finalized_by",
            "policy_ref",
            "result_digest",
        )
        if key not in record
    ]
    if record.get("kind") != "builder_ii.mcp_service_receipt":
        errors.append("kind is invalid")
    if record.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if record.get("target_profile") not in TARGET_PROFILES:
        errors.append("target_profile is invalid")
    session_id = record.get("session_id")
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        errors.append("session_id is invalid")
    if record.get("service") not in SERVICE_TOOLS:
        errors.append("service is invalid")
    if record.get("status") not in _EVENT_TYPE_BY_STATUS:
        errors.append("status is invalid")
    if not isinstance(record.get("arguments"), dict):
        errors.append("arguments must be an object")
    if record.get("finalized_by") != "builder_ii.adapters.mcp.governed_services":
        errors.append("finalized_by is invalid")
    if not _is_sha256(record.get("result_digest")):
        errors.append("result_digest must be a SHA-256 hex digest")
    elif "result" in record and record["result_digest"] != canonical_digest(record["result"]):
        errors.append("result_digest does not bind result")
    if not _is_sha256(record.get("digest")):
        errors.append("digest must be a SHA-256 hex digest")
    else:
        expected_digest = canonical_digest({key: value for key, value in record.items() if key != "digest"})
        if record["digest"] != expected_digest:
            errors.append("digest does not bind the receipt payload")
    errors.extend(_validate_policy_ref(record.get("policy_ref")))
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        expected_governance = {
            "artifact_is_authority": False,
            "target_repo_writes": "DISABLED",
            "shell_execution": "DISABLED",
            "network_access": "DISABLED",
            "credential_access": "DISABLED",
            "model_execution": "DISABLED",
            "bounded_subprocess_execution": (
                "HITL_APPROVAL_GATED" if record.get("service") == "verification_execute" else "DISABLED"
            ),
        }
        for key, value in expected_governance.items():
            if governance.get(key) != value:
                errors.append(f"governance.{key} is invalid")
    return errors


def _service_receipt(
    *,
    builder_root: Path,
    session_id: str,
    target_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: Any,
    status: str,
) -> tuple[dict[str, Any], Path, Path]:
    """Persist one evidence-complete service outcome, refusing a corrupt prior ledger."""
    _validate_identity(session_id=session_id, target_name=target_name, tool_name=tool_name)
    if status not in _EVENT_TYPE_BY_STATUS:
        raise ValueError("service status is invalid")
    if not isinstance(arguments, dict):
        raise ValueError("service arguments must be an object")

    builder_root = builder_root.resolve()
    session_dir = builder_root / "sessions" / session_id
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    existing, current_stage = _assert_mcp_ledger_extendable(builder_root=builder_root, session_id=session_id)
    sequence = len(existing) + 1

    policy = _service_policy(tool_name)
    policy_errors = validate_mcp_policy(policy)
    if policy_errors:
        raise RuntimeError("generated MCP policy is invalid: " + "; ".join(policy_errors))
    if _canonical_size(arguments) > int(policy["max_input_bytes"]):
        raise ValueError("service arguments exceed the persisted MCP policy input bound")
    if _canonical_size(result) > int(policy["max_output_bytes"]):
        raise ValueError("service result exceeds the persisted MCP policy output bound")

    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)
    policy_path = (mcp_dir / f"{sequence:03d}_mcp_policy.json").resolve()
    _json(policy_path, policy)
    policy_ref = {
        "role": "mcp_tool_policy",
        "kind": policy["kind"],
        "path": str(policy_path),
        "sha256": canonical_digest(policy),
        "name": "Plan Set 3B deny-by-default governed service policy",
        "required": True,
    }
    receipt = {
        "kind": "builder_ii.mcp_service_receipt",
        "schema_version": 2,
        "target_profile": target_name,
        "session_id": session_id,
        "service": tool_name,
        "status": status,
        "arguments": arguments,
        "result": result,
        "policy_ref": policy_ref,
        "result_digest": canonical_digest(result),
        "finalized_by": "builder_ii.adapters.mcp.governed_services",
        "governance": {
            "artifact_is_authority": False,
            "target_repo_writes": "DISABLED",
            "shell_execution": "DISABLED",
            "network_access": "DISABLED",
            "credential_access": "DISABLED",
            "model_execution": "DISABLED",
            "bounded_subprocess_execution": (
                "HITL_APPROVAL_GATED" if tool_name == "verification_execute" else "DISABLED"
            ),
        },
    }
    receipt["digest"] = canonical_digest({key: value for key, value in receipt.items() if key != "digest"})
    errors = validate_mcp_service_receipt(receipt)
    if errors:
        raise RuntimeError("MCP service receipt validation failed: " + "; ".join(errors))
    receipt_path = (mcp_dir / f"{sequence:03d}_{tool_name}_receipt.json").resolve()
    _json(receipt_path, receipt)

    previous = None
    if existing:
        previous_data, previous_path = existing[-1]
        previous = {
            "role": "event",
            "kind": EVENT_RECORD_KIND,
            "path": str(previous_path),
            "sha256": canonical_digest(previous_data),
            "name": str(previous_data.get("event_type", "")),
            "required": True,
        }
    event = create_event_record(
        event_id=f"evt_mcp_service_{session_id}_{sequence}",
        session_id=session_id,
        sequence=sequence,
        event_type=_EVENT_TYPE_BY_STATUS[status],
        stage=current_stage,
        subject_refs=[
            {
                "kind": receipt["kind"],
                "path": str(receipt_path),
                "sha256": canonical_digest(receipt),
                "role": "mcp_service_receipt",
                "name": f"{tool_name} {status} receipt",
                "required": True,
            }
        ],
        command_surface="builder-mcp serve",
        policy_snapshot_ref=policy_ref,
        previous_event_ref=previous,
        message=f"governed MCP service call {status}: {tool_name}",
        decision_result=status,
    )
    errors = validate_event_record(event)
    if errors:
        raise RuntimeError("event validation failed: " + "; ".join(errors))
    event_path = (events_dir / f"{sequence:03d}_mcp_service.json").resolve()
    write_event_record(event, event_path)
    return receipt, receipt_path, event_path


def _bounded_int(arguments: dict[str, Any], key: str, default: int, maximum: int) -> int:
    raw = arguments.get(key, default)
    if isinstance(raw, bool):
        raise ServiceDenied(f"{key} must be an integer")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ServiceDenied(f"{key} must be an integer") from exc
    if not 1 <= value <= maximum:
        raise ServiceDenied(f"{key} must be between 1 and {maximum}")
    return value


def _delegation_status(arguments: dict[str, Any], *, builder_root: Path) -> dict[str, Any]:
    run_output_dir = _controlled_path(arguments.get("run_output_dir"), root=builder_root, field="run_output_dir")
    if not run_output_dir.is_dir():
        raise ServiceDenied("run_output_dir must name an existing run directory")
    try:
        return build_obligation_board(run_output_dir)
    except ValueError as exc:
        raise ServiceDenied(str(exc)) from exc


def _verification_plan(
    arguments: dict[str, Any],
    *,
    builder_root: Path,
    session_id: str,
    target_root: Path,
    target_name: str,
) -> dict[str, Any]:
    verification_profile = arguments.get("verification_profile")
    if not isinstance(verification_profile, str) or not verification_profile.strip():
        raise ServiceDenied("verification_profile must be a non-empty string")
    head_sha = arguments.get("target_head_sha")
    if not isinstance(head_sha, str) or not _HEAD_SHA_RE.fullmatch(head_sha):
        raise ServiceDenied("target_head_sha must be an explicit 40-character Git SHA")
    tree_clean = arguments.get("tree_clean")
    if not isinstance(tree_clean, bool):
        raise ServiceDenied("tree_clean must be an explicit boolean")

    # A passive plan still writes an artifact. Refuse before that write when the current MCP
    # session evidence cannot replay; never leave a plan artifact that has no valid service receipt.
    _assert_mcp_ledger_extendable(builder_root=builder_root, session_id=session_id)
    output_dir = builder_root.resolve() / "sessions" / session_id / "mcp" / "verification-plan" / uuid.uuid4().hex
    plan_scope = {
        "scope_id": "plan_set_3b2_mcp_passive_verification_plan",
        "description": (
            "Passive verification planning over explicit caller-supplied Git-state metadata. "
            "The MCP service does not query Git, approve the plan, or execute verification."
        ),
        "includes": [
            "structured command profile references",
            "planned verification lane descriptions",
            "caller-supplied target_head_sha and tree_clean metadata",
            "disabled authority declarations",
        ],
        "excludes": [
            "independent Git-state observation",
            "Git or subprocess execution",
            "verification approval minting",
            "verification execution",
            "source writes",
            "patch authority",
            "model or tool execution",
            "Goose or Deep Agents runtime startup",
        ],
    }
    plan = finalize_verification_execution_plan(
        target_profile=target_name,
        verification_profile=verification_profile.strip(),
        target_repo=str(target_root.resolve()),
        target_head_sha=head_sha.lower(),
        tree_clean=tree_clean,
        artifact_root=str(output_dir),
        plan_scope=plan_scope,
        requested_by_command="builder-mcp verification_plan",
    )
    errors = validate_verification_execution_plan_artifact(plan)
    if errors or plan.get("valid") is not True:
        detail = "; ".join(errors or [str(error) for error in plan.get("errors", [])])
        raise ServiceDenied("verification plan request is invalid: " + (detail or "unknown validation error"))
    if plan.get("plan_mode") != "planned_only" or plan.get("approval_required") is not True:
        raise RuntimeError("verification plan escaped the passive planned-only authority boundary")
    if plan.get("execution_enabled") is not False or plan.get("artifact_is_authority") is not False:
        raise RuntimeError("verification plan unexpectedly grants execution authority")

    plan_path = output_dir / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)
    return plan


def _controlled_receipt_bytes(raw_value: Any, *, builder_root: Path) -> bytes:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ServiceDenied("verification_receipt_path must be a non-empty string")
    supplied = Path(raw_value.strip())
    if ".." in supplied.parts:
        raise ServiceDenied("verification_receipt_path must not contain traversal segments")
    unresolved = supplied if supplied.is_absolute() else builder_root.resolve() / supplied
    if unresolved.is_symlink():
        raise ServiceDenied("verification_receipt_path must name a non-symlink artifact")
    path = _controlled_path(raw_value, root=builder_root, field="verification_receipt_path")
    if not path.is_file() or path.is_symlink():
        raise ServiceDenied("verification_receipt_path must name an existing non-symlink artifact file")
    try:
        receipt_bytes = path.read_bytes()
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ServiceDenied(f"verification_receipt_path is not a readable UTF-8 JSON artifact: {exc}") from exc
    if not isinstance(receipt, dict):
        raise ServiceDenied("verification_receipt_path must contain a JSON object")
    kind = receipt.get("kind")
    if kind == VERIFICATION_EXECUTION_RECEIPT_KIND:
        errors = validate_verification_execution_receipt_artifact(receipt)
    elif kind == DEMO_VERIFICATION_RECEIPT_KIND:
        errors = validate_demo_verification_receipt(receipt)
    else:
        errors = ["receipt kind is not admitted for HITL patch proposal binding"]
    if errors:
        raise ServiceDenied("verification receipt is invalid: " + "; ".join(errors))
    return receipt_bytes


def _patch_proposal(
    arguments: dict[str, Any],
    *,
    builder_root: Path,
    session_id: str,
    target_root: Path,
    target_name: str,
) -> dict[str, Any]:
    required = {
        "unified_diff",
        "description",
        "reason",
        "target_head_sha",
        "verification_receipt_path",
    }
    if set(arguments) != required:
        raise ServiceDenied("patch_proposal accepts exactly unified_diff, description, reason, target_head_sha, and verification_receipt_path")
    unified_diff = arguments.get("unified_diff")
    if not isinstance(unified_diff, str):
        raise ServiceDenied("unified_diff must be a string")
    try:
        unified_diff_bytes = unified_diff.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ServiceDenied("unified_diff must be valid UTF-8 text") from exc
    if len(unified_diff_bytes) > MAX_UNIFIED_DIFF_BYTES:
        raise ServiceDenied(f"unified_diff exceeds the {MAX_UNIFIED_DIFF_BYTES}-byte limit")

    if _within(builder_root, target_root):
        raise ServiceDenied("patch_proposal artifact root must be outside the target repository")

    _assert_mcp_ledger_extendable(builder_root=builder_root, session_id=session_id)
    receipt_bytes = _controlled_receipt_bytes(arguments.get("verification_receipt_path"), builder_root=builder_root)
    try:
        proposal = create_bound_hitl_patch_proposal(
            target_name=target_name,
            generic_repo=target_root if target_name == "generic" else None,
            bound_target_repo=target_root,
            patch_description=arguments.get("description"),
            reason=arguments.get("reason"),
            unified_diff=unified_diff,
            target_head_sha=arguments.get("target_head_sha"),
            verification_receipt_bytes=receipt_bytes,
        )
    except (TypeError, ValueError) as exc:
        raise ServiceDenied(str(exc)) from exc

    output_dir = builder_root.resolve() / "sessions" / session_id / "mcp" / "patch-proposal" / uuid.uuid4().hex
    proposal_path = output_dir / "hitl-patch-proposal.json"
    write_hitl_patch_proposal(proposal, proposal_path)
    try:
        stored = json.loads(proposal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"persisted patch proposal could not be reloaded: {exc}") from exc
    errors = validate_hitl_patch_proposal(stored)
    if errors:
        raise RuntimeError("persisted patch proposal is invalid: " + "; ".join(errors))
    if stored != proposal:
        raise RuntimeError("persisted patch proposal does not match the canonical proposal")
    proposal_digest = canonical_digest(stored)
    return {
        "proposal_ref": {
            "kind": stored["kind"],
            "path": str(proposal_path.resolve()),
            "sha256": proposal_digest,
            "required": True,
        },
        "proposal_digest": proposal_digest,
        "patch_digest": stored["patch_digest"],
        "target": stored["target"],
        "exact_scope": stored["exact_scope"],
        "decision": "HUMAN_APPROVAL_REQUIRED",
    }


def _load_controlled_json(path: Path, *, field: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ServiceDenied(f"{field} must name an existing non-symlink JSON file")
    if path.suffix.lower() != ".json":
        raise ServiceDenied(f"{field} must name a JSON artifact")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ServiceDenied(f"{field} is not a readable JSON artifact: {exc}") from exc
    if not isinstance(value, dict):
        raise ServiceDenied(f"{field} must contain a JSON object")
    return value


def _load_runner_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"canonical verification {label} is missing or is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"canonical verification {label} is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"canonical verification {label} must contain a JSON object")
    return value


def _validate_runner_receipt_binding(
    receipt: dict[str, Any], *, plan: dict[str, Any], approval: dict[str, Any]
) -> list[str]:
    expected = {
        "plan_digest": plan.get("verification_execution_plan_digest"),
        "approval_digest": approval.get("verification_execution_approval_digest"),
        "target_profile": plan.get("target_profile"),
        "verification_profile": plan.get("verification_profile"),
        "target_repo": plan.get("target_repo"),
        "artifact_root": plan.get("artifact_root"),
    }
    return [f"{field} does not match the caller-validated artifacts" for field, value in expected.items() if receipt.get(field) != value]


def _validate_runner_postflight_binding(
    postflight: dict[str, Any],
    *,
    receipt: dict[str, Any],
    plan: dict[str, Any],
    plan_path: Path,
    approval_path: Path,
    receipt_path: Path,
) -> list[str]:
    errors: list[str] = []
    target = postflight.get("target")
    if not isinstance(target, dict):
        errors.append("target must bind the verified plan")
    else:
        if target.get("name") != plan.get("target_profile"):
            errors.append("target.name does not match the verified plan")
        if target.get("repo") != plan.get("target_repo"):
            errors.append("target.repo does not match the verified plan")
    expected_refs = {
        "request_ref": str(plan_path),
        "approval_ref": str(approval_path),
        "receipt_ref": str(receipt_path),
        "receipt_digest": receipt.get("verification_execution_receipt_digest"),
    }
    errors.extend(
        f"{field} does not match the canonical verification chain"
        for field, value in expected_refs.items()
        if postflight.get(field) != value
    )
    digest = postflight.get("postflight_digest")
    if digest != digest_jsonable(postflight, digest_key="postflight_digest"):
        errors.append("postflight_digest drift detected")
    return errors


def _verification_execute(
    arguments: dict[str, Any],
    *,
    builder_root: Path,
    session_id: str,
    target_root: Path,
    target_name: str,
) -> dict[str, Any]:
    if set(arguments) != {"plan_path", "approval_path"}:
        raise ServiceDenied("verification_execute accepts exactly plan_path and approval_path")
    plan_path = _controlled_path(arguments.get("plan_path"), root=builder_root, field="plan_path")
    approval_path = _controlled_path(arguments.get("approval_path"), root=builder_root, field="approval_path")
    plan = _load_controlled_json(plan_path, field="plan_path")
    approval = _load_controlled_json(approval_path, field="approval_path")

    errors = validate_verification_execution_plan_artifact(plan)
    errors.extend(validate_verification_execution_approval_artifact(approval))
    if not errors:
        errors.extend(validate_verification_execution_approval_against_plan(approval, plan))
    if errors or plan.get("valid") is not True or approval.get("valid") is not True:
        detail = errors or ["plan and approval must both have valid=true"]
        raise ServiceDenied("verification execution artifacts are invalid: " + "; ".join(detail))
    if Path(str(plan.get("target_repo", ""))).expanduser().resolve() != target_root:
        raise ServiceDenied("approved plan target_repo does not match the server target root")
    if plan.get("target_profile") != target_name:
        raise ServiceDenied("approved plan target_profile does not match the server target profile")

    artifact_value = Path(str(plan.get("artifact_root", ""))).expanduser()
    artifact_root = artifact_value.resolve() if artifact_value.is_absolute() else (target_root / artifact_value).resolve()
    if not _within(artifact_root, builder_root):
        raise ServiceDenied("approved plan artifact_root is outside the controlled Builder-II artifact root")
    approved_profiles = approval.get("approved_command_profiles")
    approved_steps = approval.get("approved_step_ids")
    executable = sorted(
        set(approved_profiles if isinstance(approved_profiles, list) else [])
        & set(approved_steps if isinstance(approved_steps, list) else [])
    )
    if len(executable) != 1:
        raise ServiceDenied("approval must bind exactly one executable command profile and matching step")

    _assert_mcp_ledger_extendable(builder_root=builder_root, session_id=session_id)
    output = artifact_root / "mcp-executions" / uuid.uuid4().hex / "verification-execution-receipt.json"
    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=output,
        requested_profile=executable[0],
        expected_plan_digest=str(plan["verification_execution_plan_digest"]),
        expected_approval_digest=str(approval["verification_execution_approval_digest"]),
    )
    stored_receipt = _load_runner_json(output, label="execution receipt")
    if stored_receipt != receipt:
        raise RuntimeError("canonical verification execution receipt bytes do not match the runner result")
    receipt = stored_receipt
    receipt_errors = validate_verification_execution_receipt_artifact(receipt)
    receipt_errors.extend(_validate_runner_receipt_binding(receipt, plan=plan, approval=approval))
    if receipt.get("receipt_status") != "BLOCKED_BEFORE_EXECUTION":
        receipt_errors.extend(
            validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)
        )
    if receipt_errors:
        raise RuntimeError("canonical verification receipt is invalid: " + "; ".join(receipt_errors))
    postflight_path = output.with_name(output.stem + "-postflight.json")
    postflight: dict[str, Any] | None = None
    if receipt.get("receipt_status") != "BLOCKED_BEFORE_EXECUTION":
        if not postflight_path.is_file():
            raise RuntimeError("canonical verification postflight evidence is missing")
        postflight = _load_runner_json(postflight_path, label="postflight evidence")
        postflight_errors = validate_execution_postflight_record(postflight)
        postflight_errors.extend(
            _validate_runner_postflight_binding(
                postflight,
                receipt=receipt,
                plan=plan,
                plan_path=plan_path,
                approval_path=approval_path,
                receipt_path=output,
            )
        )
        if postflight_errors:
            raise RuntimeError("canonical verification postflight evidence is invalid: " + "; ".join(postflight_errors))
    result = {
        "kind": "builder_ii.mcp_verification_execution_result",
        "valid": receipt.get("valid") is True,
        "receipt_status": receipt.get("receipt_status"),
        "requested_profile": executable[0],
        "verification_execution_receipt_ref": {
            "path": str(output),
            "sha256": receipt.get("verification_execution_receipt_digest"),
        },
        "postflight_ref": {
            "path": str(postflight_path) if postflight is not None else None,
            "sha256": canonical_digest(postflight) if postflight is not None else None,
        },
        "executed_steps": receipt.get("executed_steps", []),
        "skipped_steps": receipt.get("skipped_steps", []),
        "preflight_git_state": receipt.get("preflight_git_state"),
        "postflight_git_state": receipt.get("postflight_git_state"),
        "workspace_mutation_detected": receipt.get("workspace_mutation_detected"),
        "errors": receipt.get("errors", []),
    }
    return result


def run_service(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    session_id: str,
    builder_root: Path,
    target_root: Path,
    target_name: str,
    config_root: Path | None = None,
) -> tuple[dict[str, Any], Path, Path]:
    """Dispatch only to existing governed services; no CLI, shell, or subprocess boundary."""
    _validate_identity(session_id=session_id, target_name=target_name, tool_name=tool_name)
    if not isinstance(arguments, dict):
        raise ServiceDenied("arguments must be an object")
    input_limit = MAX_UNIFIED_DIFF_BYTES + MAX_SERVICE_INPUT_BYTES if tool_name == "patch_proposal" else MAX_SERVICE_INPUT_BYTES
    if _canonical_size(arguments) > input_limit:
        raise ServiceDenied(f"service arguments exceed the {input_limit}-byte input limit")
    builder_root = builder_root.resolve()
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise ServiceDenied("target root must be an existing directory")

    if tool_name == "repo_map":
        max_files = _bounded_int(arguments, "max_files", MAX_MAP_FILES, MAX_MAP_FILES)
        max_bytes = _bounded_int(arguments, "max_file_bytes", MAX_MAP_FILE_BYTES, MAX_MAP_FILE_BYTES)
        result = create_repo_map(target_root, target_name=target_name, max_files=max_files, max_file_bytes=max_bytes)
    elif tool_name == "repo_search":
        repo_map = create_repo_map(
            target_root,
            target_name=target_name,
            max_files=MAX_MAP_FILES,
            max_file_bytes=MAX_MAP_FILE_BYTES,
        )
        try:
            result = search_repo_map(repo_map, arguments.get("query"), max_results=MAX_SEARCH_RESULTS)
        except ValueError as exc:
            raise ServiceDenied(str(exc)) from exc
    elif tool_name == "content_read":
        rel_value = arguments.get("path")
        if not isinstance(rel_value, str) or not rel_value.strip():
            raise ServiceDenied("content_read path must be non-empty")
        rel = rel_value.strip()
        path = target_root / rel
        if not _within(path, target_root) or path.is_symlink():
            result = {
                "kind": "builder_ii.denied_read",
                "reason": "path traversal or symlink refused",
                "target_file": str(path),
            }
        else:
            policy = create_read_policy(
                target_name=target_name,
                target_repo=target_root,
                allowed_paths=[rel],
                max_bytes_budget=MAX_READ_BYTES,
                content_capture_allowed=True,
            )
            result = execute_content_read(
                policy,
                path,
                max_bytes_per_file=MAX_READ_BYTES,
                current_read_bytes=0,
            )
            kind = result.get("kind") if isinstance(result, dict) else None
            if kind == "builder_ii.content_read_receipt":
                errors = validate_content_read_receipt(result)
                if errors:
                    raise RuntimeError("content-read receipt validation failed: " + "; ".join(errors))
            elif kind != "builder_ii.denied_read":
                raise RuntimeError("content-read returned an unrecognized governed artifact")
    elif tool_name == "prepare_package":
        if config_root is None:
            raise ServiceDenied("prepare_package requires a trusted Builder-II config root")
        trusted_root = config_root.resolve()
        if not trusted_root.is_dir():
            raise ServiceDenied("trusted Builder-II config root must be an existing directory")
        call_id = uuid.uuid4().hex
        output = builder_root / "sessions" / session_id / "mcp" / "prepare-package" / call_id
        task_value = arguments.get("task")
        if not isinstance(task_value, str) or not task_value.strip():
            raise ServiceDenied("task must be non-empty")
        task = task_value.strip()
        if len(task.encode("utf-8")) > MAX_TASK_BYTES:
            raise ServiceDenied("task exceeds the 4096-byte limit")
        result = create_governed_prepare_package(
            load_settings(trusted_root, load_env_file=False),
            target_name,
            output_dir=output,
            repo_path=str(target_root),
            task=task,
            include_deepagents_readiness=False,
        )
    elif tool_name == "validate_prepare_package":
        supplied_value = arguments.get("path")
        if not isinstance(supplied_value, str) or not supplied_value.strip():
            raise ServiceDenied("package path must be non-empty")
        package_root = (builder_root / "sessions" / session_id / "mcp" / "prepare-package").resolve()
        supplied = Path(supplied_value.strip())
        raw = supplied if supplied.is_absolute() else package_root / supplied
        if not _within(raw, package_root):
            result = {"valid": False, "errors": ["package path is outside server-controlled artifact root"]}
        else:
            errors = validate_governed_prepare_package_directory(raw)
            result = {"valid": not errors, "errors": errors}
    elif tool_name == "delegation_status":
        result = _delegation_status(arguments, builder_root=builder_root)
    elif tool_name == "verification_plan":
        result = _verification_plan(
            arguments,
            builder_root=builder_root,
            session_id=session_id,
            target_root=target_root,
            target_name=target_name,
        )
    elif tool_name == "verification_execute":
        result = _verification_execute(
            arguments,
            builder_root=builder_root,
            session_id=session_id,
            target_root=target_root,
            target_name=target_name,
        )
    elif tool_name == "patch_proposal":
        result = _patch_proposal(
            arguments,
            builder_root=builder_root,
            session_id=session_id,
            target_root=target_root,
            target_name=target_name,
        )
    else:  # pragma: no cover - identity validation makes this unreachable
        raise ServiceDenied("service is not admitted")

    if _canonical_size(result) > MAX_SERVICE_OUTPUT_BYTES:
        raise RuntimeError("service result exceeds the 4194304-byte output limit")
    if tool_name == "verification_execute" and isinstance(result, dict):
        status = "succeeded" if result.get("receipt_status") == "EXECUTED" and result.get("valid") is True else "denied"
    elif tool_name == "delegation_status" and isinstance(result, dict) and result.get("chain_valid") is False:
        status = "failed"
    else:
        status = (
            "succeeded"
            if not (isinstance(result, dict) and result.get("kind") == "builder_ii.denied_read")
            and not (isinstance(result, dict) and result.get("valid") is False)
            else "denied"
        )
    return _service_receipt(
        builder_root=builder_root,
        session_id=session_id,
        target_name=target_name,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
        status=status,
    )
