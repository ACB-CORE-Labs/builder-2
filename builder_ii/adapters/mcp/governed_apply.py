"""G4 — in-loop governed patch apply (deny-by-default, delegated).

The write/shell "unlock" from ADR-0009's Phase 3, realized safely: rather than relaxing the
read-only ``mcp_call_envelope`` schema or minting a new write primitive, the in-loop gate
routes a validated ``propose_patch`` call to the *existing* governed apply lane
(:func:`builder_ii.governance.hitl.hitl_patch_apply.apply_hitl_patch`), which enforces command
authority, a schema-valid unexpired digest-bound approval, a clean tree, and a verification
receipt at the execution boundary itself, and emits a receipt + rollback bundle.

Deny-by-default at two levels:

1. The apply path is OFF unless the operator sets ``BUILDER_MCP_GOVERNED_APPLY`` -- this is what
   ``hitl_runtime_candidate`` honestly means (built, wired, proven, but not silently live).
2. Even with the flag set, a mutation still requires a valid digest-bound approval, and
   ``apply_hitl_patch`` re-validates everything and fails closed. Any failure -> refusal, no
   mutation, an ``mcp_call_denied`` ledger event.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.adapters.mcp.governed_call import (
    _artifact_ref,
    _previous_event_ref,
    _write_json,
    build_read_only_policy,
)
from builder_ii.governance.hitl.hitl_patch_apply import apply_hitl_patch
from builder_ii.governance.hitl.hitl_patch_approval import validate_hitl_patch_approval_file
from builder_ii.governance.ledger.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)

_ENABLE_ENV = "BUILDER_MCP_GOVERNED_APPLY"


def governed_apply_enabled() -> bool:
    """Deny-by-default: the in-loop apply path is off unless the operator sets the flag."""
    return os.environ.get(_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class GatedApplyOutcome:
    status: str  # "applied" | "refused"
    reason: str
    event_path: Path
    receipt_dir: str | None = None


def _append_event(builder_root: Path, session_id: str, event_type: str, message: str) -> Path:
    session_dir = Path(builder_root) / "sessions" / session_id
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    existing = load_event_records(events_dir)
    sequence = len(existing) + 1
    policy = build_read_only_policy()
    policy_path = mcp_dir / f"{sequence:03d}_policy.json"
    _write_json(policy_path, policy)

    current_stage = "initialized"
    if existing:
        replay = replay_events(existing, session_id=session_id)
        if replay.get("valid"):
            current_stage = str(replay.get("current_stage") or "initialized")

    event = create_event_record(
        event_id=f"evt_mcp_apply_{session_id}_{sequence}",
        session_id=session_id,
        sequence=sequence,
        event_type=event_type,
        stage=current_stage,
        subject_refs=[],
        command_surface="builder-mcp serve",
        policy_snapshot_ref=_artifact_ref(policy, policy_path, "mcp_tool_policy"),
        previous_event_ref=_previous_event_ref(existing),
        message=message,
    )
    errors = validate_event_record(event)
    if errors:
        raise ValueError(f"event validation failed: {errors}")
    event_path = events_dir / f"{sequence:03d}_{event_type}.json"
    write_event_record(event, event_path)
    return event_path


def _refuse(builder_root: Path, session_id: str, reason: str) -> GatedApplyOutcome:
    event_path = _append_event(builder_root, session_id, "mcp_call_denied", f"governed apply refused: {reason}")
    return GatedApplyOutcome(status="refused", reason=f"Governed apply refused: {reason}", event_path=event_path)


def run_gated_patch_apply(
    *, arguments: dict[str, Any], session_id: str, builder_root: Path, settings: Any = None
) -> GatedApplyOutcome:
    """Route a validated ``propose_patch`` to the governed apply lane, or refuse. Fail-closed."""
    if not governed_apply_enabled():
        return _refuse(builder_root, session_id, f"in-loop apply not enabled ({_ENABLE_ENV} unset)")

    proposal = arguments.get("proposal_path")
    approval = arguments.get("approval_path")
    verification_receipt = arguments.get("verification_receipt_path")
    if not (proposal and approval and verification_receipt):
        return _refuse(
            builder_root, session_id, "missing proposal_path / approval_path / verification_receipt_path"
        )

    for label, raw in (
        ("proposal", proposal),
        ("approval", approval),
        ("verification_receipt", verification_receipt),
    ):
        if not Path(str(raw)).is_file():
            return _refuse(builder_root, session_id, f"{label} file not found")

    # Sanity: the approval must at least be a schema-valid governed approval before we delegate.
    # apply_hitl_patch does the authoritative binding/expiry/clean-tree/verification/authority checks.
    if validate_hitl_patch_approval_file(Path(str(approval))):
        return _refuse(builder_root, session_id, "approval is not a schema-valid hitl_patch_approval")

    output_dir = Path(builder_root) / "sessions" / session_id / "apply"
    try:
        apply_hitl_patch(
            Path(str(proposal)), Path(str(approval)), Path(str(verification_receipt)), output_dir, settings
        )
    except Exception as exc:  # fail-closed: any refusal/failure from the governed lane -> refuse
        return _refuse(builder_root, session_id, f"governed apply lane refused/failed: {exc}")

    event_path = _append_event(
        builder_root, session_id, "mcp_call_executed", "governed patch apply executed via HITL approval"
    )
    return GatedApplyOutcome(
        status="applied",
        reason="Applied the approved patch via the governed HITL apply lane.",
        event_path=event_path,
        receipt_dir=str(output_dir),
    )
