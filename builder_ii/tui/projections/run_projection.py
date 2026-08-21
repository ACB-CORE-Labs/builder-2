"""Validator-backed, read-only STRATUM run projection.

The projection never promotes or authorizes anything. It discovers canonical
artifacts, runs their owning validators, checks identity/binding consistency,
and derives the operator grammar from validated evidence only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.core.artifact_chain_verification import VALIDATORS
from builder_ii.core.canonical_json import canonical_digest
from builder_ii.core.governed_prepare_package import (
    GOVERNED_PREPARE_PACKAGE_KIND,
    validate_governed_prepare_package_directory,
)
from builder_ii.governance.hitl.hitl_patch_approval import approval_binding_errors, approval_is_expired
from builder_ii.governance.hitl.hitl_patch_refusal import validate_hitl_patch_refusal
from builder_ii.governance.ledger.event_ledger import replay_events
from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    validate_verification_execution_receipt_against_plan_and_approval,
)

LIFECYCLE = ("PREPARE", "PLAN", "APPROVE", "EXECUTE", "VERIFY", "DELIVER/PROMOTE")
EvidenceState = Literal["ABSENT", "PENDING", "DENIED", "FAILED", "EXECUTED", "VERIFIED", "PROMOTED", "CORRUPT"]

_PREPARE = GOVERNED_PREPARE_PACKAGE_KIND
_PLAN_KINDS = {
    "builder_ii.deepagents_work_plan",
    "builder_ii.orchestration_plan",
    "builder_ii.verification_execution_plan",
}
_ASSIGNMENT = "builder_ii.deepagents_subagent_assignment"
_PROPOSAL = "builder_ii.hitl_patch_proposal"
_APPROVAL = "builder_ii.hitl_patch_approval"
_REFUSAL = "builder_ii.hitl_patch_refusal"
_EXECUTED_KINDS = {
    "builder_ii.hitl_patch_apply_receipt",
    "builder_ii.hitl_execution_receipt",
    "builder_ii.deepagents_execution_receipt",
    "builder_ii.deepagents_subagent_execution_receipt",
    "builder_ii.governed_run_receipt",
    "builder_ii.goose_close_receipt",
}
_VERIFIED_KINDS = {
    "builder_ii.verification_execution_receipt",
    "builder_ii.verification_evidence_bundle",
    "builder_ii.deepagents_evidence_bundle",
}
_DELIVERY_KINDS = {
    "builder_ii.handoff_artifact",
    "builder_ii.handoff_note",
    "builder_ii.handoff_bundle_record",
}
_MODEL_KINDS = {"builder_ii.run_manifest", "builder_ii.model_call_receipt"}
_TOOL_KINDS = {"builder_ii.tool_call_receipt", "builder_ii.mcp_call_receipt"}
_OBSERVATION = "builder_ii.stratum_invocation_observation"


@dataclass(frozen=True)
class Evidence:
    kind: str
    path: Path
    state: EvidenceState
    digest: str


@dataclass(frozen=True)
class RunProjection:
    task: str
    target: str
    profile: str
    session_id: str
    stage: str
    next_action: str
    agents: tuple[str, ...]
    obligations: tuple[str, ...]
    models: tuple[str, ...]
    tools: tuple[str, ...]
    budgets: dict[str, Any]
    approvals: EvidenceState
    verification: EvidenceState
    delivery: EvidenceState
    evidence_health: EvidenceState
    evidence: tuple[Evidence, ...] = ()
    errors: tuple[str, ...] = ()


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: invalid JSON: {exc}"
    if not isinstance(value, dict):
        return None, f"{path}: canonical artifact must be a JSON object"
    return value, None


def _observation_errors(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(value.get("session_id"), str) or not value.get("session_id"):
        errors.append("session_id is required")
    if value.get("artifact_is_authority") is not False or value.get("grants_authority") is not False:
        errors.append("observation must not grant authority")
    digest = value.get("observation_digest")
    expected = canonical_digest({key: item for key, item in value.items() if key != "observation_digest"})
    if digest != expected:
        errors.append("observation_digest does not match canonical content")
    return errors


def _candidate_paths(root: Path, session_id: str | None) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    session_root = root / "stratum" / "sessions" / session_id if session_id else None
    search_roots = (
        [session_root] if session_root is not None and session_root.exists() else ([] if session_id else [root])
    )
    for search_root in search_roots:
        for path in search_root.rglob("*.json"):
            if path.is_file():
                candidates.add(path.resolve())

    # Observations and canonical artifact refs are explicit invocation/session
    # bindings. Follow them to a fixed point; there is no mutable latest alias.
    pending = list(candidates)
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        value, _ = _load(path)
        if not value:
            continue
        referenced: list[str] = []
        if value.get("kind") == _OBSERVATION:
            output = value.get("output_path")
            if isinstance(output, str):
                referenced.append(output)
            inputs = value.get("input_paths")
            if isinstance(inputs, list):
                referenced.extend(str(item) for item in inputs if isinstance(item, str))
        for key, item in value.items():
            if key.endswith("_ref") and isinstance(item, dict) and isinstance(item.get("path"), str):
                referenced.append(str(item["path"]))
            elif key.endswith("_refs") and isinstance(item, list):
                referenced.extend(
                    str(ref["path"]) for ref in item if isinstance(ref, dict) and isinstance(ref.get("path"), str)
                )
            elif key in {
                "plan_path",
                "approval_path",
                "proposal_ref",
                "rollback_plan_ref",
                "postflight_ref",
                "proposal_path",
            } and isinstance(item, str):
                referenced.append(item)
        for referenced_path in referenced:
            candidate = Path(referenced_path)
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            manifest = candidate / "prepare-package.json" if candidate.is_dir() else candidate
            if manifest.is_file() and manifest.resolve() not in candidates:
                candidates.add(manifest.resolve())
                pending.append(manifest.resolve())
    return tuple(sorted(candidates))


def _field(value: dict[str, Any], *names: str) -> str:
    for name in names:
        found = value.get(name)
        if isinstance(found, str) and found:
            return found
    target = value.get("target")
    if "target" in names and isinstance(target, dict) and isinstance(target.get("name"), str):
        return str(target["name"])
    return ""


def _failed(value: dict[str, Any]) -> bool:
    tokens = {
        str(value.get(name, "")).upper()
        for name in ("status", "state", "result", "decision_result", "execution_state", "receipt_state")
    }
    return bool(tokens & {"FAILED", "FAIL", "ERROR", "DENIED", "REFUSED"})


def _executed(value: dict[str, Any]) -> bool:
    tokens = {
        str(value.get(name, "")).upper()
        for name in ("status", "state", "result", "execution_state", "receipt_state", "receipt_status")
    }
    return bool(tokens & {"SUCCEEDED", "SUCCESS", "COMPLETED", "EXECUTED", "CLOSED"})


def _verified(value: dict[str, Any]) -> bool:
    if str(value.get("receipt_status", "")).upper() != "EXECUTED" or value.get("valid") is not True:
        return False
    results = value.get("process_results")
    return isinstance(results, list) and bool(results) and all(
        isinstance(item, dict) and item.get("status") == "success" for item in results
    )


def project_run(root: Path, *, task: str = "", session_id: str | None = None, target: str = "") -> RunProjection:
    root = root.resolve()
    errors: list[str] = []
    records: list[tuple[Path, dict[str, Any]]] = []
    evidence: list[Evidence] = []
    identities: dict[str, set[str]] = {"session": set(), "target": set(), "profile": set(), "task": set()}

    for path in _candidate_paths(root, session_id):
        value, load_error = _load(path)
        if load_error:
            errors.append(load_error)
            continue
        assert value is not None
        kind = str(value.get("kind", ""))
        validator = VALIDATORS.get(kind)
        if kind == _OBSERVATION:
            native_errors = _observation_errors(value)
        elif kind == _REFUSAL:
            native_errors = validate_hitl_patch_refusal(value)
        elif validator is not None:
            native_errors = list(validator(value))
        else:
            # Non-governed JSON within an artifact root is not lifecycle evidence.
            continue
        if kind == _PREPARE:
            native_errors.extend(validate_governed_prepare_package_directory(path))
        if native_errors:
            errors.extend(f"{path}: {error}" for error in native_errors)
            evidence.append(Evidence(kind, path, "CORRUPT", canonical_digest(value)))
            continue
        record_session = _field(value, "session_id")
        if session_id and record_session and record_session != session_id:
            errors.append(f"{path}: foreign session_id {record_session!r}; expected {session_id!r}")
            evidence.append(Evidence(kind, path, "CORRUPT", canonical_digest(value)))
            continue
        records.append((path, value))
        identities["session"].update([record_session] if record_session else [])
        identities["target"].update(
            [_field(value, "target_name", "target_profile", "target")]
            if _field(value, "target_name", "target_profile", "target")
            else []
        )
        identities["profile"].update(
            [_field(value, "subagent_profile", "agent_profile", "profile_name")]
            if _field(value, "subagent_profile", "agent_profile", "profile_name")
            else []
        )
        identities["task"].update([_field(value, "task")] if _field(value, "task") else [])
        state: EvidenceState = "FAILED" if _failed(value) else "EXECUTED"
        evidence.append(Evidence(kind, path, state, canonical_digest(value)))

    for label, values in identities.items():
        if len(values) > 1 and label in {"session", "target"}:
            errors.append(f"foreign {label} evidence is mixed: {sorted(values)}")
    if target and identities["target"] and target not in identities["target"]:
        errors.append(f"canonical target evidence does not match selected target {target!r}")

    by_kind: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for path, value in records:
        by_kind.setdefault(str(value.get("kind", "")), []).append((path, value))
    by_path = {path.resolve(): value for path, value in records}

    proposals = by_kind.get(_PROPOSAL, [])
    approvals = by_kind.get(_APPROVAL, [])
    refusals = by_kind.get(_REFUSAL, [])
    for _, approval in approvals:
        if not proposals:
            errors.append("approval evidence has no proposal in the selected session")
            continue
        matches = [
            proposal
            for _, proposal in proposals
            if not approval_binding_errors(
                approval, proposal_digest=canonical_digest(proposal), patch_digest=str(proposal.get("patch_digest", ""))
            )
        ]
        if len(matches) != 1 or approval_is_expired(approval, now=__import__("time").time_ns() // 1_000_000_000):
            errors.append("approval is foreign, ambiguous, or expired for the selected proposal")
    for _, refusal in refusals:
        if validate_hitl_patch_refusal(refusal):
            errors.append("refusal evidence is invalid")
        matches = [
            proposal
            for path, proposal in proposals
            if refusal.get("proposal_digest") == canonical_digest(proposal)
            and refusal.get("patch_digest") == proposal.get("patch_digest")
            and Path(str(refusal.get("proposal_path", ""))).resolve() == path.resolve()
        ]
        if len(matches) != 1:
            errors.append("refusal is foreign or ambiguous for the selected proposal")

    for receipt_path, receipt in by_kind.get("builder_ii.verification_execution_receipt", []):
        bound: list[dict[str, Any]] = []
        for field in ("plan_path", "approval_path"):
            value = receipt.get(field)
            if not isinstance(value, str) or not value:
                continue
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = receipt_path.parent / candidate
            artifact = by_path.get(candidate.resolve())
            if artifact is not None:
                bound.append(artifact)
        if len(bound) != 2:
            errors.append("verification receipt plan/approval references are unresolved")
        else:
            errors.extend(validate_verification_execution_receipt_against_plan_and_approval(receipt, bound[0], bound[1]))

    event_records = [(value, path) for path, value in by_kind.get("builder_ii.event_record", [])]
    replay = replay_events(event_records, session_id=session_id) if event_records else None
    if replay is not None and not replay.get("valid"):
        errors.extend(f"event replay: {error}" for error in replay.get("errors", []))

    corrupt = bool(errors)
    has_prepare = _PREPARE in by_kind
    has_plan = bool(_PLAN_KINDS & set(by_kind))
    has_approval = bool(approvals)
    has_refusal = bool(refusals)
    has_execution = any(str(value.get("kind", "")) in _EXECUTED_KINDS and _executed(value) for _, value in records)
    has_verification = any(str(value.get("kind", "")) in _VERIFIED_KINDS and _verified(value) for _, value in records)
    has_execution = has_execution or has_verification
    has_delivery = bool(_DELIVERY_KINDS & set(by_kind))
    promoted = bool(replay and replay.get("valid")) and any(
        value.get("kind") == "builder_ii.event_record" and value.get("event_type") == "workflow_promoted"
        for _, value in records
    )
    failed = any(_failed(value) for _, value in records)

    if corrupt:
        stage, next_action = "PREPARE", "BLOCKED: repair corrupt or foreign canonical evidence"
    elif not has_prepare:
        stage, next_action = "PREPARE", "prepare-package"
    elif not has_plan:
        stage, next_action = "PLAN", "create or select a validated work plan"
    elif has_refusal:
        stage, next_action = "APPROVE", "revise or retire refused proposal"
    elif not has_approval:
        stage, next_action = "APPROVE", "approve or refuse through builder-hitl"
    elif not has_execution:
        stage, next_action = "EXECUTE", "execute only through existing governed authority"
    elif not has_verification:
        stage, next_action = "VERIFY", "run approved verification and record its receipt"
    else:
        stage, next_action = "DELIVER/PROMOTE", "PLAN_SET_6_DELIVERY_AUTHORITY_REQUIRED"

    approval_state: EvidenceState = (
        "CORRUPT"
        if corrupt
        else "DENIED"
        if has_refusal
        else "VERIFIED"
        if has_approval
        else "PENDING"
        if proposals
        else "ABSENT"
    )
    verification_state: EvidenceState = (
        "CORRUPT"
        if corrupt
        else "VERIFIED"
        if has_verification
        else "FAILED"
        if failed
        else "PENDING"
        if has_execution
        else "ABSENT"
    )
    delivery_state: EvidenceState = (
        "CORRUPT"
        if corrupt
        else "PROMOTED"
        if promoted
        else "EXECUTED"
        if has_delivery
        else "PENDING"
        if has_verification
        else "ABSENT"
    )
    agents = tuple(
        sorted(
            {
                _field(value, "subagent_profile", "agent_profile", "profile_name")
                for _, value in records
                if _field(value, "subagent_profile", "agent_profile", "profile_name")
            }
        )
    )
    models = tuple(
        sorted(
            {
                _field(value, "model_id", "model_alias")
                for _, value in records
                if str(value.get("kind", "")) in _MODEL_KINDS and _field(value, "model_id", "model_alias")
            }
        )
    )
    obligations = tuple(
        sorted(
            str(value.get("obligation_id"))
            for _, value in by_kind.get("builder_ii.orchestration_obligation", [])
            if isinstance(value.get("obligation_id"), str)
        )
    )
    tools = tuple(
        sorted(
            {
                _field(value, "tool_name", "command", "service")
                for _, value in records
                if str(value.get("kind", "")) in _TOOL_KINDS and _field(value, "tool_name", "command", "service")
            }
        )
    )
    budgets = next((dict(value.get("budget", {})) for _, value in records if isinstance(value.get("budget"), dict)), {})
    selected_task = task or (sorted(identities["task"])[0] if identities["task"] else "")
    selected_target = target or (sorted(identities["target"])[0] if identities["target"] else "")
    selected_profile = sorted(identities["profile"])[0] if identities["profile"] else ""
    selected_session = session_id or (sorted(identities["session"])[0] if identities["session"] else "")
    health: EvidenceState = "CORRUPT" if corrupt else "FAILED" if failed else "VERIFIED" if records else "ABSENT"
    return RunProjection(
        selected_task,
        selected_target,
        selected_profile,
        selected_session,
        stage,
        next_action,
        agents,
        obligations,
        models,
        tools,
        budgets,
        approval_state,
        verification_state,
        delivery_state,
        health,
        tuple(evidence),
        tuple(errors),
    )
