"""G4 in-loop governed patch proposal/apply bridge (deny-by-default).

The MCP surface never gains a second mutation primitive.  A first ``propose_patch`` call
records a passive, content-addressed HITL proposal and a denial event that digest-binds
that exact artifact.  A later call carrying proposal/approval/verification references may
delegate to the already-governed HITL apply lane, but only when the operator has enabled
the candidate path and the proposal's recorded source preimage still matches.

Proposal != approval, approval != execution, and artifact != authority remain load-bearing.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.adapters.mcp.governed_call import build_read_only_policy
from builder_ii.core.readonly_repo_tools import ToolRefusal, resolve_in_jail
from builder_ii.governance.hitl.hitl_patch_apply import apply_hitl_patch
from builder_ii.governance.hitl.hitl_patch_approval import validate_hitl_patch_approval_file
from builder_ii.governance.ledger.session_ledger import artifact_ref, session_event_append
from builder_ii.governance.ledger.workflow_records import canonical_digest

_ENABLE_ENV = "BUILDER_MCP_GOVERNED_APPLY"


def governed_apply_enabled() -> bool:
    return os.environ.get(_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class GatedApplyOutcome:
    status: str  # "applied" | "refused"
    reason: str
    event_path: Path
    receipt_dir: str | None = None


def _append_event(
    builder_root: Path,
    session_id: str,
    event_type: str,
    message: str,
    *,
    subject_refs: list[dict[str, Any]] | None = None,
) -> Path:
    with session_event_append(Path(builder_root), session_id) as appender:
        _, policy_ref = appender.write_policy_snapshot(build_read_only_policy())
        return appender.append(
            event_id=f"evt_mcp_apply_{session_id}_{appender.sequence}",
            event_type=event_type,
            command_surface="builder-mcp serve",
            policy_snapshot_ref=policy_ref,
            subject_refs=list(subject_refs or []),
            message=message,
        )


def _refuse(
    builder_root: Path,
    session_id: str,
    reason: str,
    *,
    subject_refs: list[dict[str, Any]] | None = None,
) -> GatedApplyOutcome:
    event_path = _append_event(
        builder_root,
        session_id,
        "mcp_call_denied",
        f"governed apply refused: {reason}",
        subject_refs=subject_refs,
    )
    return GatedApplyOutcome(
        status="refused",
        reason=f"Governed apply refused: {reason}",
        event_path=event_path,
    )


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _proposal_target_state(target_root: Path, raw_path: str) -> tuple[str, str | None, str]:
    """Return normalized relative path, optional preimage digest, and state.

    A missing target is admissible because a proposal may create a file; an existing target
    must be a non-symlink regular file under the governed read jail.
    """
    candidate = resolve_in_jail(target_root, raw_path)
    relative = candidate.relative_to(Path(target_root).expanduser().resolve(strict=True)).as_posix()
    if not candidate.exists():
        return relative, None, "absent"
    if not candidate.is_file():
        raise ToolRefusal(f"proposal target is not a regular file: {raw_path}")
    return relative, _sha256_file(candidate), "present"


def _mint_proposal(
    *,
    arguments: dict[str, Any],
    session_id: str,
    builder_root: Path,
    target_root: Path,
    settings: Any = None,
) -> GatedApplyOutcome:
    """Persist a reviewable source-bound proposal and deny mutation."""
    diff = str(arguments.get("unified_diff") or arguments.get("diff") or "")
    target_path = str(arguments.get("path") or arguments.get("file") or "").strip()
    if not diff.strip():
        return _refuse(builder_root, session_id, "propose_patch needs a unified_diff to record")
    if not target_path:
        return _refuse(builder_root, session_id, "propose_patch needs a target path to record")

    try:
        normalized_path, preimage_sha256, preimage_state = _proposal_target_state(
            target_root, target_path
        )
    except (ToolRefusal, OSError) as exc:
        return _refuse(builder_root, session_id, f"proposal target refused by path jail: {exc}")

    try:
        from builder_ii.governance.hitl.hitl_patch_proposal import (
            create_hitl_patch_proposal,
            validate_hitl_patch_proposal,
            write_hitl_patch_proposal,
        )

        diff_sha256 = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        proposal = create_hitl_patch_proposal(
            settings,
            patch_description=(
                f"in-loop proposal from governed session {session_id}: {normalized_path}"
            ),
            reason=str(arguments.get("reason") or "proposed by a governed Goose session"),
            patch_digest=diff_sha256,
            unified_diff=diff,
        )
        # Extension metadata is descriptive/binding evidence only.  The v1 validator ignores
        # unknown fields, so older operator lanes can still consume the same proposal kind.
        proposal["in_loop_origin"] = {
            "session_id": session_id,
            "target_path": normalized_path,
            "target_root": str(Path(target_root).expanduser().resolve(strict=True)),
            "target_preimage_state": preimage_state,
            "target_preimage_sha256": preimage_sha256,
            "unified_diff_sha256": diff_sha256,
            "artifact_is_authority": False,
        }
        errors = validate_hitl_patch_proposal(proposal)
        if errors:
            return _refuse(
                builder_root,
                session_id,
                f"could not record a valid proposal: {errors[0]}",
            )

        proposal_digest = canonical_digest(proposal)
        artifacts_dir = Path(builder_root) / "artifacts" / "hitl" / "proposals"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out = artifacts_dir / f"{proposal_digest}.json"
        if out.exists():
            existing = json.loads(out.read_text(encoding="utf-8"))
            if canonical_digest(existing) != proposal_digest:
                return _refuse(
                    builder_root,
                    session_id,
                    "content-addressed proposal path already exists with different bytes",
                )
        else:
            write_hitl_patch_proposal(proposal, out)
        # Verify the persisted artifact before referencing it from the event chain.
        persisted = json.loads(out.read_text(encoding="utf-8"))
        if canonical_digest(persisted) != proposal_digest:
            return _refuse(builder_root, session_id, "persisted proposal digest mismatch")
        proposal_ref = artifact_ref(proposal, out, "hitl_patch_proposal")
    except Exception as exc:
        return _refuse(builder_root, session_id, f"could not record proposal: {exc}")

    event_path = _append_event(
        builder_root,
        session_id,
        "mcp_call_denied",
        "in-loop mutation refused; passive patch proposal recorded for human review",
        subject_refs=[proposal_ref],
    )
    return GatedApplyOutcome(
        status="refused",
        reason=(
            f"Not applied. The proposed change was recorded as a governed patch proposal at {out}. "
            "A human decides next: review the diff and approve or refuse it. To apply an approved "
            "patch in-loop, call propose_patch again with proposal_path, approval_path and "
            "verification_receipt_path."
        ),
        event_path=event_path,
    )


def _validate_recorded_preimage(proposal_path: Path, target_root: Path) -> str | None:
    """Return a refusal reason when an in-loop proposal's source preimage has drifted."""
    try:
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"proposal could not be read for preimage verification: {exc}"
    origin = proposal.get("in_loop_origin")
    if not isinstance(origin, dict):
        # Legacy/operator-authored proposals remain governed by apply_hitl_patch's existing
        # checks.  Only proposals minted by this bridge claim a preimage binding here.
        return None

    raw_path = origin.get("target_path")
    if not isinstance(raw_path, str) or not raw_path:
        return "in-loop proposal is missing its bound target_path"
    try:
        candidate = resolve_in_jail(target_root, raw_path)
    except ToolRefusal as exc:
        return f"bound proposal target is no longer admissible: {exc}"

    expected_state = origin.get("target_preimage_state")
    expected_digest = origin.get("target_preimage_sha256")
    if expected_state == "absent":
        if candidate.exists():
            return "proposal target changed since review: file now exists but preimage was absent"
        return None
    if expected_state != "present" or not isinstance(expected_digest, str):
        return "in-loop proposal carries an invalid preimage binding"
    if not candidate.is_file():
        return "proposal target changed since review: target is no longer a regular file"
    try:
        observed = _sha256_file(candidate)
    except OSError as exc:
        return f"proposal target could not be re-read: {exc}"
    if observed != expected_digest:
        return "proposal target changed since review: source preimage digest no longer matches"
    return None


def run_gated_patch_apply(
    *,
    arguments: dict[str, Any],
    session_id: str,
    builder_root: Path,
    target_root: Path | None = None,
    settings: Any = None,
) -> GatedApplyOutcome:
    """Route proposal/apply calls through passive proposal or governed HITL apply lanes."""
    proposal = arguments.get("proposal_path")
    approval = arguments.get("approval_path")
    verification_receipt = arguments.get("verification_receipt_path")
    resolved_target_root = (
        Path(target_root).expanduser().resolve()
        if target_root is not None
        else Path(builder_root).expanduser().resolve().parent
    )

    if not (proposal or approval or verification_receipt):
        return _mint_proposal(
            arguments=arguments,
            session_id=session_id,
            builder_root=builder_root,
            target_root=resolved_target_root,
            settings=settings,
        )

    if not governed_apply_enabled():
        return _refuse(
            builder_root,
            session_id,
            f"in-loop apply not enabled ({_ENABLE_ENV} unset)",
        )
    if not (proposal and approval and verification_receipt):
        return _refuse(
            builder_root,
            session_id,
            "missing proposal_path / approval_path / verification_receipt_path",
        )

    for label, raw in (
        ("proposal", proposal),
        ("approval", approval),
        ("verification_receipt", verification_receipt),
    ):
        if not Path(str(raw)).is_file():
            return _refuse(builder_root, session_id, f"{label} file not found")

    proposal_path = Path(str(proposal))
    drift = _validate_recorded_preimage(proposal_path, resolved_target_root)
    if drift:
        return _refuse(builder_root, session_id, drift)

    if validate_hitl_patch_approval_file(Path(str(approval))):
        return _refuse(
            builder_root,
            session_id,
            "approval is not a schema-valid hitl_patch_approval",
        )

    output_dir = Path(builder_root) / "sessions" / session_id / "apply"
    try:
        apply_hitl_patch(
            proposal_path,
            Path(str(approval)),
            Path(str(verification_receipt)),
            output_dir,
            settings,
        )
    except Exception as exc:
        return _refuse(
            builder_root,
            session_id,
            f"governed apply lane refused/failed: {exc}",
        )

    event_path = _append_event(
        builder_root,
        session_id,
        "mcp_call_executed",
        "governed patch apply executed via HITL approval",
    )
    return GatedApplyOutcome(
        status="applied",
        reason="Applied the approved patch via the governed HITL apply lane.",
        event_path=event_path,
        receipt_dir=str(output_dir),
    )
