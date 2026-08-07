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

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.adapters.mcp.governed_call import build_read_only_policy
from builder_ii.governance.hitl.hitl_patch_apply import apply_hitl_patch
from builder_ii.governance.hitl.hitl_patch_approval import validate_hitl_patch_approval_file
from builder_ii.governance.ledger.session_ledger import session_event_append

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
    with session_event_append(Path(builder_root), session_id) as appender:
        _, policy_ref = appender.write_policy_snapshot(build_read_only_policy())
        return appender.append(
            event_id=f"evt_mcp_apply_{session_id}_{appender.sequence}",
            event_type=event_type,
            command_surface="builder-mcp serve",
            policy_snapshot_ref=policy_ref,
            subject_refs=[],
            message=message,
        )


def _refuse(builder_root: Path, session_id: str, reason: str) -> GatedApplyOutcome:
    event_path = _append_event(builder_root, session_id, "mcp_call_denied", f"governed apply refused: {reason}")
    return GatedApplyOutcome(status="refused", reason=f"Governed apply refused: {reason}", event_path=event_path)


def _mint_proposal(
    *, arguments: dict[str, Any], session_id: str, builder_root: Path, settings: Any = None
) -> GatedApplyOutcome:
    """Record what the agent wanted to change, as a reviewable proposal. Applies nothing.

    The in-loop gate used to refuse a mutating call by writing a ledger line and returning a
    sentence. That is fail-closed, and it is also a dead end: the operator watching the run never
    saw *what* was proposed, and the agent had nowhere to put it. The work simply evaporated at
    the boundary.

    A refusal that produces a reviewable artifact is strictly better than one that produces only
    a denial. This mints a schema-valid ``hitl_patch_proposal`` into ``.builder/artifacts`` --
    where the operator console's gate scanner already looks -- so the gate lights up, ``D`` renders
    the diff, and ``A``/``R`` reach the governed decision. Nothing is applied, and the denial event
    is still written: proposing is not applying, and this path never becomes the one that mutates.
    """
    diff = str(arguments.get("unified_diff") or arguments.get("diff") or "")
    target_path = str(arguments.get("path") or arguments.get("file") or "")
    if not diff.strip():
        return _refuse(builder_root, session_id, "propose_patch needs a unified_diff to record")

    try:
        from builder_ii.governance.hitl.hitl_patch_proposal import (
            create_hitl_patch_proposal,
            validate_hitl_patch_proposal,
            write_hitl_patch_proposal,
        )

        proposal = create_hitl_patch_proposal(
            settings,
            patch_description=f"in-loop proposal from governed session {session_id}: {target_path}".strip(),
            reason=str(arguments.get("reason") or "proposed by a governed Goose session"),
            patch_digest=hashlib.sha256(diff.encode("utf-8")).hexdigest(),
            unified_diff=diff,
        )
        errors = validate_hitl_patch_proposal(proposal)
        if errors:
            return _refuse(builder_root, session_id, f"could not record a valid proposal: {errors[0]}")

        artifacts_dir = Path(builder_root) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out = artifacts_dir / f"hitl-patch-proposal-{session_id}.json"
        write_hitl_patch_proposal(proposal, out)
    except Exception as exc:  # fail-closed: a proposal we cannot record is a refusal, not a write
        return _refuse(builder_root, session_id, f"could not record proposal: {exc}")

    event_path = _append_event(
        builder_root,
        session_id,
        "mcp_call_denied",
        f"in-loop write refused; recorded a reviewable patch proposal at {out}",
    )
    return GatedApplyOutcome(
        status="refused",
        reason=(
            f"Not applied. The proposed change was recorded as a governed patch proposal at {out}. "
            "A human decides next: review the diff and approve or refuse it (in the operator "
            "console, or with `builder-hitl approve-patch` / `refuse-patch`). To apply an approved "
            "patch in-loop, call propose_patch again with proposal_path, approval_path and "
            "verification_receipt_path."
        ),
        event_path=event_path,
    )


def run_gated_patch_apply(
    *, arguments: dict[str, Any], session_id: str, builder_root: Path, settings: Any = None
) -> GatedApplyOutcome:
    """Route a validated ``propose_patch`` to the governed apply lane, or refuse. Fail-closed."""
    proposal = arguments.get("proposal_path")
    approval = arguments.get("approval_path")
    verification_receipt = arguments.get("verification_receipt_path")

    # A call carrying a diff but no approval refs is an agent *proposing*, not applying. Record it
    # so a human can see it. Deliberately not behind the enablement flag: that flag gates writing
    # to the target, and this writes only a passive proposal artifact.
    if not (proposal or approval or verification_receipt):
        return _mint_proposal(
            arguments=arguments, session_id=session_id, builder_root=builder_root, settings=settings
        )

    if not governed_apply_enabled():
        return _refuse(builder_root, session_id, f"in-loop apply not enabled ({_ENABLE_ENV} unset)")

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
