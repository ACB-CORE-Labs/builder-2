"""Frontend-neutral, validator-backed read model for one governed run.

The view never promotes or authorizes anything. It discovers canonical
artifacts, runs their owning validators, checks identity/binding consistency,
and derives the operator grammar from validated evidence only. Frontends may
render or navigate this state, but they do not become a second interpreter of
run truth.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.adapters.mcp.governed_services import validate_mcp_service_receipt
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
_SET6_PLAN = "builder_ii.delivery_plan"
_SET6_RECEIPT = "builder_ii.delivery_receipt"
_DELIVERY_KINDS = {
    "builder_ii.handoff_artifact",
    "builder_ii.handoff_note",
    "builder_ii.handoff_bundle_record",
    "builder_ii.delivery_plan",
    "builder_ii.delivery_action_request",
    "builder_ii.delivery_approval",
    "builder_ii.delivery_receipt",
}
_MCP_RECEIPT = "builder_ii.mcp_service_receipt"
_MODEL_KINDS = {"builder_ii.run_manifest", "builder_ii.model_call_receipt"}
_TOOL_KINDS = {"builder_ii.tool_call_receipt", "builder_ii.mcp_call_receipt"}
_OBSERVATION = "builder_ii.stratum_invocation_observation"
_MCP_RESULT_REF_FIELDS = (
    "patch_apply_receipt_ref",
    "postflight_ref",
    "rollback_plan_ref",
    "rollback_bundle_ref",
    "patch_ledger_ref",
    "proposal_ref",
    "approval_ref",
    "verification_receipt_ref",
    "rollback_patch_ref",
)


@dataclass(frozen=True)
class Evidence:
    kind: str
    path: Path
    state: EvidenceState
    digest: str


@dataclass(frozen=True)
class RunView:
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

    @property
    def goal(self) -> str:
        """Human-facing alias for the canonical task binding."""
        return self.task

    @property
    def canonical_stage(self) -> str:
        """The exact internal lifecycle stage; never inferred by a frontend."""
        return self.stage

    @property
    def activity_label(self) -> str:
        """Calm operator language without weakening the canonical stage."""
        return {
            "PREPARE": "orienting the run",
            "PLAN": "planning the work",
            "APPROVE": "reviewing the proposed decision",
            "EXECUTE": "performing admitted work",
            "VERIFY": "verifying the result",
            "DELIVER/PROMOTE": "preparing the reviewed handoff",
        }.get(self.stage, "inspecting run state")

    @property
    def attention_items(self) -> tuple[str, ...]:
        """Ranked blocking/decision items derived only from validated state."""
        if self.errors:
            return tuple(self.errors)
        if self.approvals == "PENDING":
            return ("review the pending exact proposal",)
        if self.verification == "FAILED":
            return ("verification failed; inspect evidence and replan",)
        return ()

    @property
    def recommended_action(self) -> str:
        return self.next_action

    @property
    def admissible_actions(self) -> tuple[str, ...]:
        """Compatibility seed for the typed governed-action catalog."""
        return (self.next_action,) if self.next_action else ()

    @property
    def model_route(self) -> tuple[str, ...]:
        return self.models

    @property
    def budget(self) -> dict[str, Any]:
        return dict(self.budgets)

    @property
    def approval(self) -> EvidenceState:
        return self.approvals

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(self.errors)

    @property
    def recovery(self) -> str:
        if self.errors:
            return "repair or retire corrupt/foreign evidence before continuing"
        if self.verification == "FAILED":
            return "inspect failed verification and create a revised plan"
        if self.approvals == "DENIED":
            return "revise or retire the refused proposal"
        return ""

    @property
    def validated_evidence(self) -> tuple[Evidence, ...]:
        return tuple(item for item in self.evidence if item.state != "CORRUPT")

    @property
    def projection_errors(self) -> tuple[str, ...]:
        return tuple(self.errors)

    def to_jsonable(self) -> dict[str, Any]:
        """Return a stable frontend payload without changing evidence meaning."""
        payload = asdict(self)
        payload["evidence"] = [
            {
                "digest": item.digest,
                "kind": item.kind,
                "path": str(item.path),
                "state": item.state,
            }
            for item in self.evidence
        ]
        payload.update(
            {
                "activity": self.activity_label,
                "admissible_actions": list(self.admissible_actions),
                "artifact_is_authority": False,
                "attention_items": list(self.attention_items),
                "canonical_stage": self.canonical_stage,
                "failures": list(self.failures),
                "goal": self.goal,
                "grants_authority": False,
                "kind": "builder_ii.run_view",
                "recovery": self.recovery,
                "schema_version": 1,
            }
        )
        return payload


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
    output = value.get("output_path")
    if isinstance(output, str) and output:
        output_path = Path(output)
        if not output_path.is_file():
            errors.append("observation output_path is missing")
        else:
            if value.get("artifact_sha256") and hashlib.sha256(output_path.read_bytes()).hexdigest() != value.get("artifact_sha256"):
                errors.append("observation output bytes do not match artifact_sha256")
            try:
                output_value = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                output_value = None
            if isinstance(output_value, dict) and value.get("canonical_digest") and canonical_digest(output_value) != value.get("canonical_digest"):
                errors.append("observation output does not match canonical_digest")
    return errors


def _candidate_paths(root: Path, session_id: str | None) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    if session_id:
        # The two namespaces are canonical and intentionally explicit.  A
        # selected session never falls back to global or latest evidence.
        search_roots = [
            candidate
            for candidate in (
                root / "stratum" / "sessions" / session_id,
                root / "sessions" / session_id,
            )
            if candidate.exists()
        ]
    else:
        search_roots = [root]
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
        if value.get("kind") == _MCP_RECEIPT and isinstance(value.get("result"), dict):
            for field in _MCP_RESULT_REF_FIELDS:
                ref = value["result"].get(field)
                if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                    referenced.append(str(ref["path"]))
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
            if manifest.is_file() and manifest.suffix == ".json" and manifest.resolve() not in candidates:
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
    return bool(tokens & {"FAILED", "FAIL", "ERROR", "DENIED", "REFUSED"}) or (
        value.get("successful") is False
        or value.get("cancelled") is True
        or value.get("returncode") not in (0, None)
    )


def _mcp_result_ref_errors(receipt: dict[str, Any], receipt_path: Path, by_path: dict[Path, dict[str, Any]]) -> list[str]:
    """Validate the bounded, canonical result refs emitted by MCP services."""
    result = receipt.get("result")
    if not isinstance(result, dict):
        return []
    errors: list[str] = []
    for field in _MCP_RESULT_REF_FIELDS:
        ref = result.get(field)
        if ref is None:
            continue
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
            errors.append(f"{field} is malformed")
            continue
        candidate = Path(ref["path"])
        if not candidate.is_absolute():
            candidate = receipt_path.parent / candidate
        candidate = candidate.resolve()
        artifact = by_path.get(candidate)
        if artifact is None:
            if candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest() == ref["sha256"]:
                continue
            errors.append(f"{field} is missing from the selected session")
            continue
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != ref["sha256"]:
            errors.append(f"{field} digest does not bind persisted artifact")
        if ref.get("kind") and artifact.get("kind") != ref["kind"]:
            errors.append(f"{field} kind does not bind persisted artifact")
    return errors


def _mcp_event_binding_errors(
    receipts: list[tuple[Path, dict[str, Any]]], events: list[tuple[Path, dict[str, Any]]], session_id: str | None
) -> list[str]:
    """Require one exact canonical event binding for each consumed MCP receipt."""
    bindings: dict[Path, list[dict[str, Any]]] = {}
    for _, event in events:
        for ref in event.get("subject_refs", []) if isinstance(event.get("subject_refs"), list) else []:
            if isinstance(ref, dict) and ref.get("role") == "mcp_service_receipt" and isinstance(ref.get("path"), str):
                bindings.setdefault(Path(ref["path"]).resolve(), []).append(event)
    errors: list[str] = []
    for path, receipt in receipts:
        matches = bindings.get(path.resolve(), [])
        if len(matches) != 1:
            errors.append(f"{path}: MCP receipt must have exactly one canonical event binding")
            continue
        event = matches[0]
        ref = next(ref for ref in event["subject_refs"] if isinstance(ref, dict) and ref.get("role") == "mcp_service_receipt" and Path(str(ref.get("path"))).resolve() == path.resolve())
        if event.get("session_id") != receipt.get("session_id") or ref.get("kind") != receipt.get("kind") or ref.get("sha256") != canonical_digest(receipt):
            errors.append(f"{path}: MCP event binding does not match receipt custody")
        if event.get("command_surface") != "builder-mcp serve":
            errors.append(f"{path}: MCP event command surface is not canonical")
    return errors


def _goose_event_binding_errors(
    by_kind: dict[str, list[tuple[Path, dict[str, Any]]]],
    events: list[tuple[Path, dict[str, Any]]],
) -> list[str]:
    """Require exact lifecycle events for canonical persisted Goose evidence."""
    requirements = (
        ("builder_ii.goose_launch_receipt", "goose_launch_receipt", "goose_session_started"),
        ("builder_ii.no_mutation_postflight", "goose_postflight", "goose_session_closed"),
        ("builder_ii.goose_close_receipt", "goose_close_receipt", "goose_session_closed"),
    )
    errors: list[str] = []
    for kind, role, event_type in requirements:
        for path, artifact in by_kind.get(kind, []):
            matches = []
            for _, event in events:
                if event.get("event_type") != event_type:
                    continue
                for ref in event.get("subject_refs", []):
                    if (
                        isinstance(ref, dict)
                        and ref.get("role") == role
                        and isinstance(ref.get("path"), str)
                        and Path(ref["path"]).resolve() == path.resolve()
                    ):
                        matches.append((event, ref))
            if len(matches) != 1:
                errors.append(f"{path}: Goose evidence must have exactly one canonical {event_type} binding")
                continue
            event, ref = matches[0]
            if (
                event.get("session_id") != artifact.get("session_id")
                or ref.get("kind") != artifact.get("kind")
                or ref.get("sha256") != canonical_digest(artifact)
                or event.get("command_surface") != "builder start"
            ):
                errors.append(f"{path}: Goose lifecycle event binding does not match persisted custody")
    return errors


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


def project_run_view(root: Path, *, task: str = "", session_id: str | None = None, target: str = "") -> RunView:
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
        elif kind == _MCP_RECEIPT:
            native_errors = validate_mcp_service_receipt(value)
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
        if len(values) > 1 and label in {"session", "target", "task"}:
            errors.append(f"foreign {label} evidence is mixed: {sorted(values)}")
    if target and identities["target"] and target not in identities["target"]:
        errors.append(f"canonical target evidence does not match selected target {target!r}")

    by_kind: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for path, value in records:
        by_kind.setdefault(str(value.get("kind", "")), []).append((path, value))
    by_path = {path.resolve(): value for path, value in records}

    for receipt_path, receipt in by_kind.get(_MCP_RECEIPT, []):
        errors.extend(_mcp_result_ref_errors(receipt, receipt_path, by_path))
    mcp_receipts = by_kind.get(_MCP_RECEIPT, [])
    mcp_events = by_kind.get("builder_ii.event_record", [])
    if mcp_receipts:
        errors.extend(_mcp_event_binding_errors(mcp_receipts, mcp_events, session_id))
    errors.extend(_goose_event_binding_errors(by_kind, mcp_events))

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

    # A patch proposal records the exact bytes of the verification receipt it
    # was allowed to bind.  Never advance on a merely valid, unrelated receipt.
    for proposal_path, proposal in proposals:
        expected_file_sha = proposal.get("verification_receipt_file_sha256")
        if not isinstance(expected_file_sha, str):
            errors.append(f"{proposal_path}: proposal verification receipt digest is missing")
            continue
        matching_receipts = [
            receipt_path
            for receipt_path, receipt in by_kind.get("builder_ii.verification_execution_receipt", [])
            if receipt.get("receipt_status") == "EXECUTED"
            and hashlib.sha256(receipt_path.read_bytes()).hexdigest() == expected_file_sha
        ]
        if not by_kind.get("builder_ii.verification_execution_receipt"):
            # A proposal may legitimately be pending before verification is
            # executed. Once receipts exist, ambiguity or a digest mismatch
            # is corruption, never an implicit binding.
            continue
        if len(matching_receipts) != 1:
            errors.append(f"{proposal_path}: proposal is not bound to exactly one persisted verification receipt")

    event_records = [(value, path) for path, value in by_kind.get("builder_ii.event_record", [])]
    replay = replay_events(event_records, session_id=session_id) if event_records else None
    if replay is not None and not replay.get("valid"):
        errors.extend(f"event replay: {error}" for error in replay.get("errors", []))

    has_prepare = _PREPARE in by_kind
    has_plan = bool(_PLAN_KINDS & set(by_kind))
    has_set6_plan = _SET6_PLAN in by_kind
    has_approval = bool(approvals)
    has_refusal = bool(refusals)
    generic_execution = any(str(value.get("kind", "")) in _EXECUTED_KINDS and _executed(value) for _, value in records)
    has_verification = any(str(value.get("kind", "")) in _VERIFIED_KINDS and _verified(value) for _, value in records)
    # Verification is not execution.  Patch execution requires the canonical
    # apply receipt (and its postflight chain), not any successful verification.
    mcp_patch_execution = any(
        value.get("service") == "patch_apply"
        and value.get("status") == "succeeded"
        and isinstance(value.get("result"), dict)
        and value["result"].get("status") == "succeeded"
        and all(value["result"].get(field) for field in ("patch_apply_receipt_ref", "postflight_ref", "rollback_plan_ref", "rollback_bundle_ref", "patch_ledger_ref", "rollback_patch_ref"))
        for _, value in by_kind.get(_MCP_RECEIPT, [])
    )
    # An active patch path can only be discharged by the validated, event-bound
    # Plan Set 3 MCP apply chain.  Generic execution receipts and standalone
    # hitl_patch_apply_receipts are evidence, not patch authority.
    has_execution = mcp_patch_execution if proposals else generic_execution
    delivery_receipts = [
        value for _, value in by_kind.get(_MCP_RECEIPT, [])
        if value.get("service") in {"delivery_prepare", "delivery"}
        and value.get("status") in {"succeeded", "denied"}
        and isinstance(value.get("result"), dict)
    ]
    has_delivery_prepare = any(
        value.get("service") == "delivery_prepare"
        and value.get("result", {}).get("status") == "HANDOFF_PREPARED"
        for value in delivery_receipts
    )
    has_delivery_call = any(
        value.get("service") == "delivery"
        and value.get("result", {}).get("status") == "HUMAN_APPROVAL_REQUIRED"
        for value in delivery_receipts
    )
    for _, value in delivery_receipts:
        result = value.get("result", {})
        if value.get("service") == "delivery" and result.get("status") == "HUMAN_APPROVAL_REQUIRED":
            if result.get("performed_actions") != []:
                errors.append("delivery boundary performed_actions must be empty")
    has_delivery = has_delivery_prepare and has_delivery_call
    event_sequence = {
        Path(str(ref.get("path"))).resolve(): int(event.get("sequence", 0))
        for _, event in mcp_events
        for ref in event.get("subject_refs", []) if isinstance(event.get("subject_refs"), list)
        if isinstance(ref, dict) and ref.get("role") == "mcp_service_receipt" and isinstance(ref.get("path"), str)
    }
    prepare_sequences = [event_sequence.get(path.resolve(), 0) for path, value in mcp_receipts if value.get("service") == "delivery_prepare" and value.get("result", {}).get("status") == "HANDOFF_PREPARED"]
    delivery_sequences = [event_sequence.get(path.resolve(), 0) for path, value in mcp_receipts if value.get("service") == "delivery" and value.get("result", {}).get("status") == "HUMAN_APPROVAL_REQUIRED"]
    if has_delivery and (not prepare_sequences or not delivery_sequences or min(prepare_sequences) >= min(delivery_sequences)):
        errors.append("delivery MCP event ordering is invalid")
        has_delivery = False
    corrupt = bool(errors)
    promoted = False
    failed = any(_failed(value) for _, value in records)
    set6_receipts = [value for _, value in by_kind.get(_SET6_RECEIPT, [])]
    set6_successes = {value.get("action") for value in set6_receipts if value.get("status") == "SUCCEEDED"}

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
    elif has_verification and has_set6_plan and "pr_create" not in set6_successes and "pr_update" not in set6_successes and "push" not in set6_successes and "commit" not in set6_successes:
        stage, next_action = "DELIVER/PROMOTE", "DELIVERY_COMMIT_APPROVAL_REQUIRED"
    elif has_verification and has_set6_plan and "commit" in set6_successes and "push" not in set6_successes:
        stage, next_action = "DELIVER/PROMOTE", "DELIVERY_PUSH_REQUIRES_EXACT_TIP_VERIFICATION_AND_APPROVAL"
    elif has_verification and has_set6_plan and "push" in set6_successes and "pr_create" not in set6_successes and "pr_update" not in set6_successes:
        stage, next_action = "DELIVER/PROMOTE", "DELIVERY_PR_APPROVAL_REQUIRED"
    elif has_verification and has_set6_plan and ("pr_create" in set6_successes or "pr_update" in set6_successes):
        stage, next_action = "DELIVER/PROMOTE", "DELIVERY_COMPLETE_REVIEW_REMAINS_SEPARATE"
    elif has_verification and not has_delivery_prepare:
        stage, next_action = "DELIVER/PROMOTE", "PLAN_SET_3_DELIVERY_PREPARE_REQUIRED"
    elif has_verification and has_delivery_prepare and not has_delivery_call:
        stage, next_action = "DELIVER/PROMOTE", "PLAN_SET_3_DELIVERY_BOUNDARY_REQUIRED"
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
        if has_delivery or bool(set6_successes)
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
    return RunView(
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
