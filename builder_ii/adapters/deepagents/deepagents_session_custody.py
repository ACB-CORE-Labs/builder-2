"""Canonical persisted custody for governed Deep Agents session lifecycle evidence.

This adapter manages the canonical Deep Agents namespace beneath an admitted
Builder-II artifact root: ``sessions/<session_id>/deepagents/``.

Enforces strict builder-II epistemological invariants:
1. Projection evidence (e.g. PROJECTED_ONLY) is NEVER accepted as execution evidence.
2. End-to-end cryptographic and structural cross-binding:
   work_plan ↔ candidate ↔ approval ↔ run_envelope ↔ receipt ↔ event ledger.
3. Monotonic, hash-chained lifecycle events with exact subject references.
4. Fail-closed no-follow directory traversal and exclusive file creation.
5. Strict single-algorithm digest binding matching the owning artifact contracts.
6. Immediate postflight custody validation before returning success on persist.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from builder_ii.adapters.deepagents.deepagents_execution import (
    DEEPAGENTS_CHECKPOINT_KIND,
    DEEPAGENTS_EVENT_LEDGER_KIND,
    DEEPAGENTS_EVENT_RECORD_KIND,
    DEEPAGENTS_EXECUTION_APPROVAL_KIND,
    DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    DEEPAGENTS_REPLAY_REPORT_KIND,
    DEEPAGENTS_RUN_ENVELOPE_KIND,
    _digest_jsonable,
    validate_deepagents_checkpoint,
    validate_deepagents_event_ledger,
    validate_deepagents_event_record,
    validate_deepagents_execution_approval_against_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_replay_report,
    validate_deepagents_run_envelope,
)
from builder_ii.adapters.deepagents.deepagents_runtime import (
    DEEPAGENTS_RUNTIME_ENVELOPE_KIND,
)
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    DEEPAGENTS_WORK_PLAN_KIND,
    validate_deepagents_runtime_envelope,
    validate_deepagents_work_plan,
)
from builder_ii.governance.ledger.event_ledger import load_event_records, validate_event_chain_integrity
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.lifecycle.candidate.runtime_event_append import (
    append_runtime_event,
    open_directory_nofollow,
)

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("invalid canonical Deep Agents session identity")


def deepagents_session_dir(artifact_root: Path, session_id: str) -> Path:
    _validate_session_id(session_id)
    normalized_root = Path(os.path.abspath(artifact_root))
    return normalized_root / "sessions" / session_id / "deepagents"


def _persist_new_json(path: Path, value: dict[str, Any]) -> None:
    parent_fd = open_directory_nofollow(path.parent)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        output_fd = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        try:
            payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
            with os.fdopen(output_fd, "wb", closefd=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(output_fd)
    finally:
        os.close(parent_fd)


def _require_new(paths: tuple[Path, ...]) -> None:
    existing = [path for path in paths if path.exists() or path.is_symlink()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing canonical Deep Agents evidence: "
            + ", ".join(str(path) for path in existing)
        )


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        if path.is_symlink():
            return None, [f"{label} must not be a symlink"]
        if not path.is_file():
            return None, [f"{label} is missing or not a regular file"]
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{label} is unreadable: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be a JSON object"]
    return value, []


def _validate_identity(value: dict[str, Any], session_id: str, label: str) -> None:
    if value.get("session_id") != session_id:
        raise ValueError(f"{label} session_id does not match governed run")


def _require_exact_ref(
    ref: Any,
    *,
    expected_role: str,
    expected_kind: str,
    expected_path: Path,
    expected_digest: str,
    label: str,
) -> list[str]:
    """Strictly verify expected role, kind, path, and single owning digest."""
    errors: list[str] = []
    if not isinstance(ref, dict):
        return [f"{label}: reference must be a JSON object"]
    if ref.get("role") != expected_role:
        errors.append(f"{label}: role must be '{expected_role}', got '{ref.get('role')}'")
    if ref.get("kind") != expected_kind:
        errors.append(f"{label}: kind must be '{expected_kind}', got '{ref.get('kind')}'")
    ref_path = ref.get("path")
    if not isinstance(ref_path, str) or not ref_path:
        errors.append(f"{label}: path must be a non-empty string")
    else:
        try:
            if Path(ref_path).resolve() != expected_path.resolve():
                errors.append(f"{label}: path '{ref_path}' does not match expected canonical path '{expected_path}'")
        except OSError as exc:
            errors.append(f"{label}: path '{ref_path}' resolution failed: {exc}")
    if ref.get("sha256") != expected_digest:
        errors.append(f"{label}: sha256 '{ref.get('sha256')}' does not match expected digest '{expected_digest}'")
    return errors


def validate_deepagents_session_custody(artifact_root: Path, session_id: str) -> list[str]:
    """Independently reconstruct the complete canonical Deep Agents lifecycle graph and events."""
    try:
        session_dir = deepagents_session_dir(artifact_root, session_id)
        directory_fd = open_directory_nofollow(session_dir, create=False)
        os.close(directory_fd)
    except (OSError, ValueError) as exc:
        return [f"canonical Deep Agents session namespace is invalid: {exc}"]

    errors: list[str] = []
    plan_path = session_dir / "work_plan.json"
    envelope_path = session_dir / "envelope.json"
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"
    receipt_path = session_dir / "receipt.json"
    checkpoint_path = session_dir / "checkpoint.json"

    plan, plan_errors = _load_json(plan_path, "canonical Deep Agents work plan")
    envelope, env_errors = _load_json(envelope_path, "canonical Deep Agents run envelope")
    errors.extend(plan_errors)
    errors.extend(env_errors)

    plan_digest = canonical_digest(plan) if plan is not None else ""

    if plan is not None:
        errors.extend(validate_deepagents_work_plan(plan))
        if plan.get("session_id") and plan.get("session_id") != session_id:
            errors.append("canonical Deep Agents work plan session_id does not match run")

    candidate: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    candidate_digest = ""
    approval_digest = ""
    envelope_digest = ""

    if envelope is not None:
        env_kind = envelope.get("kind")
        if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND:
            errors.extend(validate_deepagents_run_envelope(envelope))
            envelope_digest = _digest_jsonable(envelope)

            # For real run envelope, candidate and approval are mandatory
            candidate, cand_errors = _load_json(candidate_path, "canonical Deep Agents candidate")
            errors.extend(cand_errors)

            approval, app_errors = _load_json(approval_path, "canonical Deep Agents approval")
            errors.extend(app_errors)

            if candidate is not None and approval is not None:
                candidate_digest = _digest_jsonable(candidate)
                approval_digest = _digest_jsonable(approval)

                errors.extend(
                    validate_deepagents_execution_approval_against_candidate(approval, candidate, check_expiry=True)
                )
                if candidate.get("session_id") and candidate.get("session_id") != session_id:
                    errors.append("canonical Deep Agents candidate session_id does not match run")
                if approval.get("session_id") and approval.get("session_id") != session_id:
                    errors.append("canonical Deep Agents approval session_id does not match run")

                if plan is not None:
                    errors.extend(
                        _require_exact_ref(
                            candidate.get("work_plan_ref"),
                            expected_role="work_plan",
                            expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
                            expected_path=plan_path,
                            expected_digest=plan_digest,
                            label="candidate work_plan_ref",
                        )
                    )

                errors.extend(
                    _require_exact_ref(
                        approval.get("candidate_ref"),
                        expected_role="candidate",
                        expected_kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
                        expected_path=candidate_path,
                        expected_digest=candidate_digest,
                        label="approval candidate_ref",
                    )
                )

                errors.extend(
                    _require_exact_ref(
                        envelope.get("candidate_ref"),
                        expected_role="candidate",
                        expected_kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
                        expected_path=candidate_path,
                        expected_digest=candidate_digest,
                        label="envelope candidate_ref",
                    )
                )
                errors.extend(
                    _require_exact_ref(
                        envelope.get("approval_ref"),
                        expected_role="approval",
                        expected_kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND,
                        expected_path=approval_path,
                        expected_digest=approval_digest,
                        label="envelope approval_ref",
                    )
                )

            # Reconstruct and validate event_ledger_ref and replay_report_ref from envelope
            env_ledger_ref = envelope.get("event_ledger_ref")
            if isinstance(env_ledger_ref, dict) and env_ledger_ref.get("path"):
                target_ledger_path = Path(env_ledger_ref["path"])
                ledger_data, ledger_errors = _load_json(target_ledger_path, "envelope event ledger")
                errors.extend(ledger_errors)
                if ledger_data is not None:
                    errors.extend(validate_deepagents_event_ledger(ledger_data))
                    errors.extend(
                        _require_exact_ref(
                            env_ledger_ref,
                            expected_role="event_ledger",
                            expected_kind=DEEPAGENTS_EVENT_LEDGER_KIND,
                            expected_path=target_ledger_path,
                            expected_digest=_digest_jsonable(ledger_data),
                            label="envelope event_ledger_ref",
                        )
                    )
            else:
                errors.append("envelope event_ledger_ref is missing or invalid")

            env_replay_ref = envelope.get("replay_report_ref")
            if isinstance(env_replay_ref, dict) and env_replay_ref.get("path"):
                target_replay_path = Path(env_replay_ref["path"])
                replay_data, replay_errors = _load_json(target_replay_path, "envelope replay report")
                errors.extend(replay_errors)
                if replay_data is not None:
                    errors.extend(validate_deepagents_replay_report(replay_data))
                    errors.extend(
                        _require_exact_ref(
                            env_replay_ref,
                            expected_role="replay_report",
                            expected_kind=DEEPAGENTS_REPLAY_REPORT_KIND,
                            expected_path=target_replay_path,
                            expected_digest=_digest_jsonable(replay_data),
                            label="envelope replay_report_ref",
                        )
                    )
            else:
                errors.append("envelope replay_report_ref is missing or invalid")

        elif env_kind == DEEPAGENTS_RUNTIME_ENVELOPE_KIND:
            errors.extend(validate_deepagents_runtime_envelope(envelope))
            envelope_digest = canonical_digest(envelope)
            if plan is not None:
                errors.extend(
                    _require_exact_ref(
                        envelope.get("work_plan_ref"),
                        expected_role="work_plan",
                        expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
                        expected_path=plan_path,
                        expected_digest=plan_digest,
                        label="envelope work_plan_ref",
                    )
                )
        else:
            errors.append(f"unknown Deep Agents envelope kind: {env_kind}")

        if envelope.get("session_id") != session_id:
            errors.append("canonical Deep Agents run envelope session_id does not match run")

    events_dir = session_dir.parent / "events"
    integrity = validate_event_chain_integrity(events_dir)
    if not integrity.get("valid"):
        errors.extend(str(error) for error in integrity.get("errors", []))

    events = [event for event, _ in load_event_records(events_dir)]

    if plan is not None and envelope is not None:
        start_matches = [event for event in events if event.get("event_type") == "deepagents_runtime_started"]
        if len(start_matches) != 1:
            errors.append("canonical Deep Agents custody requires exactly one deepagents_runtime_started event")
        else:
            start_event = start_matches[0]
            if start_event.get("session_id") != session_id:
                errors.append("deepagents_runtime_started session_id does not match run")
            if start_event.get("command_surface") != "builder delegate":
                errors.append("deepagents_runtime_started command_surface must be 'builder delegate'")

            subject_refs = start_event.get("subject_refs", [])
            plan_refs = [
                ref
                for ref in subject_refs
                if isinstance(ref, dict) and ref.get("role") in ("deepagents_work_plan", "work_plan")
            ]
            if len(plan_refs) != 1:
                errors.append("deepagents_runtime_started must contain exactly one work plan subject ref")
            else:
                errors.extend(
                    _require_exact_ref(
                        plan_refs[0],
                        expected_role="deepagents_work_plan",
                        expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
                        expected_path=plan_path,
                        expected_digest=plan_digest,
                        label="deepagents_runtime_started work plan binding",
                    )
                )

            env_refs = [
                ref
                for ref in subject_refs
                if isinstance(ref, dict)
                and ref.get("role") in ("deepagents_run_envelope", "deepagents_runtime_envelope", "run_envelope")
            ]
            if len(env_refs) != 1:
                errors.append("deepagents_runtime_started must contain exactly one envelope subject ref")
            else:
                env_role = (
                    "deepagents_run_envelope"
                    if envelope.get("kind") == DEEPAGENTS_RUN_ENVELOPE_KIND
                    else "deepagents_runtime_envelope"
                )
                errors.extend(
                    _require_exact_ref(
                        env_refs[0],
                        expected_role=env_role,
                        expected_kind=str(envelope.get("kind")),
                        expected_path=envelope_path,
                        expected_digest=envelope_digest,
                        label="deepagents_runtime_started envelope binding",
                    )
                )

            if candidate is not None:
                cand_refs = [
                    ref
                    for ref in subject_refs
                    if isinstance(ref, dict) and ref.get("role") == "deepagents_execution_candidate"
                ]
                if len(cand_refs) != 1:
                    errors.append("deepagents_runtime_started must bind execution candidate")
                else:
                    errors.extend(
                        _require_exact_ref(
                            cand_refs[0],
                            expected_role="deepagents_execution_candidate",
                            expected_kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
                            expected_path=candidate_path,
                            expected_digest=candidate_digest,
                            label="deepagents_runtime_started candidate binding",
                        )
                    )

            if approval is not None:
                app_refs = [
                    ref
                    for ref in subject_refs
                    if isinstance(ref, dict) and ref.get("role") == "deepagents_execution_approval"
                ]
                if len(app_refs) != 1:
                    errors.append("deepagents_runtime_started must bind execution approval")
                else:
                    errors.extend(
                        _require_exact_ref(
                            app_refs[0],
                            expected_role="deepagents_execution_approval",
                            expected_kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND,
                            expected_path=approval_path,
                            expected_digest=approval_digest,
                            label="deepagents_runtime_started approval binding",
                        )
                    )

    if receipt_path.exists() or receipt_path.is_symlink():
        receipt, rec_errors = _load_json(receipt_path, "canonical Deep Agents execution receipt")
        errors.extend(rec_errors)
        if receipt is not None:
            rec_kind = receipt.get("kind")
            rec_state = receipt.get("receipt_state")

            if rec_state == "PROJECTED_ONLY" or rec_kind == "builder_ii.deepagents_subagent_execution_receipt":
                errors.append("PROJECTED_ONLY subagent receipt must not be promoted to execution receipt")
            else:
                errors.extend(validate_deepagents_execution_receipt(receipt))
                if receipt.get("session_id") != session_id:
                    errors.append("canonical Deep Agents receipt session_id does not match run")

                if envelope is not None:
                    errors.extend(
                        _require_exact_ref(
                            receipt.get("envelope_ref"),
                            expected_role="run_envelope",
                            expected_kind=str(envelope.get("kind")),
                            expected_path=envelope_path,
                            expected_digest=envelope_digest,
                            label="receipt envelope_ref",
                        )
                    )

                if candidate is not None:
                    errors.extend(
                        _require_exact_ref(
                            receipt.get("candidate_ref"),
                            expected_role="candidate",
                            expected_kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
                            expected_path=candidate_path,
                            expected_digest=candidate_digest,
                            label="receipt candidate_ref",
                        )
                    )

                if approval is not None:
                    errors.extend(
                        _require_exact_ref(
                            receipt.get("approval_ref"),
                            expected_role="approval",
                            expected_kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND,
                            expected_path=approval_path,
                            expected_digest=approval_digest,
                            label="receipt approval_ref",
                        )
                    )

                # Reconstruct and validate event_ledger_ref and replay_report_ref from receipt
                rec_ledger_ref = receipt.get("event_ledger_ref")
                if isinstance(rec_ledger_ref, dict) and rec_ledger_ref.get("path"):
                    target_rec_ledger_path = Path(rec_ledger_ref["path"])
                    rec_ledger_data, rec_ledger_errors = _load_json(target_rec_ledger_path, "receipt event ledger")
                    errors.extend(rec_ledger_errors)
                    if rec_ledger_data is not None:
                        errors.extend(validate_deepagents_event_ledger(rec_ledger_data))
                        errors.extend(
                            _require_exact_ref(
                                rec_ledger_ref,
                                expected_role="event_ledger",
                                expected_kind=DEEPAGENTS_EVENT_LEDGER_KIND,
                                expected_path=target_rec_ledger_path,
                                expected_digest=_digest_jsonable(rec_ledger_data),
                                label="receipt event_ledger_ref",
                            )
                        )
                else:
                    errors.append("receipt event_ledger_ref is missing or invalid")

                rec_replay_ref = receipt.get("replay_report_ref")
                if isinstance(rec_replay_ref, dict) and rec_replay_ref.get("path"):
                    target_rec_replay_path = Path(rec_replay_ref["path"])
                    rec_replay_data, rec_replay_errors = _load_json(target_rec_replay_path, "receipt replay report")
                    errors.extend(rec_replay_errors)
                    if rec_replay_data is not None:
                        errors.extend(validate_deepagents_replay_report(rec_replay_data))
                        errors.extend(
                            _require_exact_ref(
                                rec_replay_ref,
                                expected_role="replay_report",
                                expected_kind=DEEPAGENTS_REPLAY_REPORT_KIND,
                                expected_path=target_rec_replay_path,
                                expected_digest=_digest_jsonable(rec_replay_data),
                                label="receipt replay_report_ref",
                            )
                        )
                else:
                    errors.append("receipt replay_report_ref is missing or invalid")

                receipt_digest = _digest_jsonable(receipt)

                if rec_state == "CHECKPOINTED":
                    chk_ref = receipt.get("checkpoint_ref")
                    if not isinstance(chk_ref, dict):
                        errors.append("CHECKPOINTED receipt must contain checkpoint_ref")
                    else:
                        chk_path = Path(chk_ref.get("path", str(checkpoint_path)))
                        checkpoint_data, chk_errors = _load_json(chk_path, "canonical Deep Agents checkpoint")
                        errors.extend(chk_errors)
                        if checkpoint_data is not None:
                            errors.extend(validate_deepagents_checkpoint(checkpoint_data))
                            checkpoint_digest = _digest_jsonable(checkpoint_data)
                            errors.extend(
                                _require_exact_ref(
                                    chk_ref,
                                    expected_role="checkpoint",
                                    expected_kind=DEEPAGENTS_CHECKPOINT_KIND,
                                    expected_path=chk_path,
                                    expected_digest=checkpoint_digest,
                                    label="receipt checkpoint_ref",
                                )
                            )
                            if candidate is not None:
                                errors.extend(
                                    _require_exact_ref(
                                        checkpoint_data.get("candidate_ref"),
                                        expected_role="candidate",
                                        expected_kind=DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
                                        expected_path=candidate_path,
                                        expected_digest=candidate_digest,
                                        label="checkpoint candidate_ref",
                                    )
                                )
                            if approval is not None:
                                errors.extend(
                                    _require_exact_ref(
                                        checkpoint_data.get("approval_ref"),
                                        expected_role="approval",
                                        expected_kind=DEEPAGENTS_EXECUTION_APPROVAL_KIND,
                                        expected_path=approval_path,
                                        expected_digest=approval_digest,
                                        label="checkpoint approval_ref",
                                    )
                                )
                            chk_tail_ref = checkpoint_data.get("event_tail_ref")
                            if isinstance(chk_tail_ref, dict) and chk_tail_ref.get("path"):
                                tail_path = Path(chk_tail_ref["path"])
                                tail_data, tail_errors = _load_json(tail_path, "checkpoint event tail")
                                errors.extend(tail_errors)
                                if tail_data is not None:
                                    errors.extend(validate_deepagents_event_record(tail_data))
                                    errors.extend(
                                        _require_exact_ref(
                                            chk_tail_ref,
                                            expected_role="event",
                                            expected_kind=DEEPAGENTS_EVENT_RECORD_KIND,
                                            expected_path=tail_path,
                                            expected_digest=_digest_jsonable(tail_data),
                                            label="checkpoint event_tail_ref",
                                        )
                                    )
                            else:
                                errors.append("checkpoint event_tail_ref is missing or invalid")

                    exec_events = [
                        event for event in events if event.get("event_type") == "deepagents_runtime_interrupted"
                    ]
                    if len(exec_events) != 1:
                        errors.append("CHECKPOINTED receipt requires exactly one deepagents_runtime_interrupted event")
                    else:
                        exec_event = exec_events[0]
                        if exec_event.get("session_id") != session_id:
                            errors.append("terminal execution event session_id does not match run")
                        rec_matches = [
                            ref
                            for ref in exec_event.get("subject_refs", [])
                            if isinstance(ref, dict)
                            and ref.get("role") in ("deepagents_execution_receipt", "execution_receipt")
                        ]
                        if len(rec_matches) != 1:
                            errors.append("terminal event must bind execution receipt")
                        else:
                            errors.extend(
                                _require_exact_ref(
                                    rec_matches[0],
                                    expected_role="deepagents_execution_receipt",
                                    expected_kind=DEEPAGENTS_EXECUTION_RECEIPT_KIND,
                                    expected_path=receipt_path,
                                    expected_digest=receipt_digest,
                                    label="deepagents_runtime_interrupted receipt binding",
                                )
                            )

                        chk_matches = [
                            ref
                            for ref in exec_event.get("subject_refs", [])
                            if isinstance(ref, dict) and ref.get("role") in ("deepagents_checkpoint", "checkpoint")
                        ]
                        if len(chk_matches) != 1:
                            errors.append("deepagents_runtime_interrupted must bind checkpoint")
                        elif chk_ref and isinstance(chk_ref, dict):
                            chk_path = Path(chk_ref.get("path", str(checkpoint_path)))
                            checkpoint_data, _ = _load_json(chk_path, "checkpoint")
                            if checkpoint_data is not None:
                                errors.extend(
                                    _require_exact_ref(
                                        chk_matches[0],
                                        expected_role="deepagents_checkpoint",
                                        expected_kind=DEEPAGENTS_CHECKPOINT_KIND,
                                        expected_path=chk_path,
                                        expected_digest=_digest_jsonable(checkpoint_data),
                                        label="deepagents_runtime_interrupted checkpoint binding",
                                    )
                                )

                elif rec_state == "COMPLETED":
                    exec_events = [
                        event for event in events if event.get("event_type") == "deepagents_runtime_executed"
                    ]
                    if len(exec_events) != 1:
                        errors.append("COMPLETED receipt requires exactly one deepagents_runtime_executed event")
                    else:
                        exec_event = exec_events[0]
                        if exec_event.get("session_id") != session_id:
                            errors.append("terminal execution event session_id does not match run")
                        rec_matches = [
                            ref
                            for ref in exec_event.get("subject_refs", [])
                            if isinstance(ref, dict)
                            and ref.get("role") in ("deepagents_execution_receipt", "execution_receipt")
                        ]
                        if len(rec_matches) != 1:
                            errors.append("terminal event must bind execution receipt")
                        else:
                            errors.extend(
                                _require_exact_ref(
                                    rec_matches[0],
                                    expected_role="deepagents_execution_receipt",
                                    expected_kind=DEEPAGENTS_EXECUTION_RECEIPT_KIND,
                                    expected_path=receipt_path,
                                    expected_digest=receipt_digest,
                                    label="deepagents_runtime_executed receipt binding",
                                )
                            )

                elif rec_state == "FAILED":
                    exec_events = [event for event in events if event.get("event_type") == "deepagents_runtime_failed"]
                    if len(exec_events) != 1:
                        errors.append("FAILED receipt requires exactly one deepagents_runtime_failed event")
                    else:
                        exec_event = exec_events[0]
                        if exec_event.get("session_id") != session_id:
                            errors.append("terminal execution event session_id does not match run")
                        rec_matches = [
                            ref
                            for ref in exec_event.get("subject_refs", [])
                            if isinstance(ref, dict)
                            and ref.get("role") in ("deepagents_execution_receipt", "execution_receipt")
                        ]
                        if len(rec_matches) != 1:
                            errors.append("terminal event must bind execution receipt")
                        else:
                            errors.extend(
                                _require_exact_ref(
                                    rec_matches[0],
                                    expected_role="deepagents_execution_receipt",
                                    expected_kind=DEEPAGENTS_EXECUTION_RECEIPT_KIND,
                                    expected_path=receipt_path,
                                    expected_digest=receipt_digest,
                                    label="deepagents_runtime_failed receipt binding",
                                )
                            )

                # Refuse any other terminal execution events that contradict the receipt
                all_exec_events = [
                    event
                    for event in events
                    if event.get("event_type")
                    in (
                        "deepagents_runtime_executed",
                        "deepagents_runtime_failed",
                        "deepagents_runtime_interrupted",
                    )
                ]
                if len(all_exec_events) != 1:
                    errors.append("canonical Deep Agents custody requires exactly one terminal execution event")

    return list(dict.fromkeys(errors))


def persist_deepagents_start(
    *,
    artifact_root: Path,
    session_id: str,
    work_plan: dict[str, Any],
    envelope: dict[str, Any],
    candidate: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    event_ledger: dict[str, Any] | None = None,
    replay_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist and event-bind a governed Deep Agents delegation start."""
    plan_errors = validate_deepagents_work_plan(work_plan)
    env_kind = envelope.get("kind")
    if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND:
        env_errors = validate_deepagents_run_envelope(envelope)
    elif env_kind == DEEPAGENTS_RUNTIME_ENVELOPE_KIND:
        env_errors = validate_deepagents_runtime_envelope(envelope)
    else:
        env_errors = [f"invalid envelope kind: {env_kind}"]

    errors = [*plan_errors, *env_errors]

    if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND:
        if candidate is None or approval is None:
            errors.append("candidate and approval are required for DEEPAGENTS_RUN_ENVELOPE_KIND")
        else:
            errors.extend(
                validate_deepagents_execution_approval_against_candidate(approval, candidate, check_expiry=True)
            )

    if errors:
        raise ValueError("invalid Deep Agents start custody: " + "; ".join(errors))

    _validate_identity(envelope, session_id, "Deep Agents run envelope")

    session_dir = deepagents_session_dir(artifact_root, session_id)
    plan_path = session_dir / "work_plan.json"
    envelope_path = session_dir / "envelope.json"
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"
    ledger_path = session_dir / "event_ledger.json"
    replay_path = session_dir / "replay_report.json"

    to_persist: list[tuple[Path, dict[str, Any]]] = [(plan_path, work_plan), (envelope_path, envelope)]
    if candidate is not None:
        to_persist.append((candidate_path, candidate))
    if approval is not None:
        to_persist.append((approval_path, approval))
    if event_ledger is not None:
        to_persist.append((ledger_path, event_ledger))
    if replay_report is not None:
        to_persist.append((replay_path, replay_report))

    _require_new(tuple(p for p, _ in to_persist))
    for p, val in to_persist:
        _persist_new_json(p, val)

    plan_digest = canonical_digest(work_plan)
    env_digest = _digest_jsonable(envelope) if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND else canonical_digest(envelope)

    subject_refs = [
        {
            "role": "deepagents_work_plan",
            "kind": DEEPAGENTS_WORK_PLAN_KIND,
            "path": str(plan_path),
            "sha256": plan_digest,
            "name": "governed work plan",
            "required": True,
        },
        {
            "role": "deepagents_run_envelope"
            if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND
            else "deepagents_runtime_envelope",
            "kind": str(env_kind),
            "path": str(envelope_path),
            "sha256": env_digest,
            "name": "run envelope",
            "required": True,
        },
    ]
    if candidate is not None:
        subject_refs.append(
            {
                "role": "deepagents_execution_candidate",
                "kind": DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
                "path": str(candidate_path),
                "sha256": _digest_jsonable(candidate),
                "name": "execution candidate",
                "required": True,
            }
        )
    if approval is not None:
        subject_refs.append(
            {
                "role": "deepagents_execution_approval",
                "kind": DEEPAGENTS_EXECUTION_APPROVAL_KIND,
                "path": str(approval_path),
                "sha256": _digest_jsonable(approval),
                "name": "execution approval",
                "required": True,
            }
        )

    event = append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type="deepagents_runtime_started",
        message="Governed Deep Agents delegation started",
        command_surface="builder delegate",
        subject_refs=subject_refs,
        decision_result="executed",
    )

    postflight_errors = validate_deepagents_session_custody(artifact_root, session_id)
    if postflight_errors:
        raise ValueError("Deep Agents start custody failed postflight validation: " + "; ".join(postflight_errors))

    return event


def persist_deepagents_execution(
    *,
    artifact_root: Path,
    session_id: str,
    execution_receipt: dict[str, Any],
    checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist and event-bind a governed Deep Agents delegation execution outcome.

    Refuses PROJECTED_ONLY subagent receipts.
    Requires strict 1-to-1 matching between receipt status and lifecycle event.
    """
    rec_state = execution_receipt.get("receipt_state")
    rec_kind = execution_receipt.get("kind")
    if rec_state == "PROJECTED_ONLY" or rec_kind == "builder_ii.deepagents_subagent_execution_receipt":
        raise ValueError("PROJECTED_ONLY receipt cannot be persisted as runtime execution evidence")

    receipt_errors = validate_deepagents_execution_receipt(execution_receipt)
    if receipt_errors:
        raise ValueError("invalid Deep Agents execution receipt: " + "; ".join(receipt_errors))

    if execution_receipt.get("session_id") and execution_receipt.get("session_id") != session_id:
        raise ValueError("Deep Agents execution receipt session_id does not match governed run")

    if rec_state == "CHECKPOINTED" and checkpoint is None:
        raise ValueError("checkpoint is required when persisting a CHECKPOINTED receipt")

    chk_errors: list[str] = []
    if checkpoint is not None:
        chk_errors = validate_deepagents_checkpoint(checkpoint)
        if chk_errors:
            raise ValueError("invalid Deep Agents checkpoint: " + "; ".join(chk_errors))

    session_dir = deepagents_session_dir(artifact_root, session_id)
    receipt_path = session_dir / "receipt.json"
    checkpoint_path = session_dir / "checkpoint.json"

    to_persist = [(receipt_path, execution_receipt)]
    if checkpoint is not None:
        to_persist.append((checkpoint_path, checkpoint))

    _require_new(tuple(p for p, _ in to_persist))
    for p, val in to_persist:
        _persist_new_json(p, val)

    if rec_state == "CHECKPOINTED":
        event_type = "deepagents_runtime_interrupted"
        decision_result = "interrupted"
        message = "Governed Deep Agents delegation checkpointed on interrupt"
    elif rec_state == "FAILED":
        event_type = "deepagents_runtime_failed"
        decision_result = "failed"
        message = "Governed Deep Agents delegation failed"
    elif rec_state == "COMPLETED":
        event_type = "deepagents_runtime_executed"
        decision_result = "executed"
        message = "Governed Deep Agents delegation completed"
    else:
        raise ValueError(f"unsupported receipt_state for execution persistence: {rec_state}")

    subject_refs = [
        {
            "role": "deepagents_execution_receipt",
            "kind": DEEPAGENTS_EXECUTION_RECEIPT_KIND,
            "path": str(receipt_path),
            "sha256": _digest_jsonable(execution_receipt),
            "name": "execution receipt",
            "required": True,
        },
    ]
    if checkpoint is not None:
        subject_refs.append(
            {
                "role": "deepagents_checkpoint",
                "kind": DEEPAGENTS_CHECKPOINT_KIND,
                "path": str(checkpoint_path),
                "sha256": _digest_jsonable(checkpoint),
                "name": "execution checkpoint",
                "required": True,
            }
        )

    event = append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type=event_type,
        message=message,
        command_surface="builder delegate",
        subject_refs=subject_refs,
        decision_result=decision_result,
    )

    postflight_errors = validate_deepagents_session_custody(artifact_root, session_id)
    if postflight_errors:
        raise ValueError("Deep Agents execution custody failed postflight validation: " + "; ".join(postflight_errors))

    return event
