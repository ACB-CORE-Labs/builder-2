"""Where the human pause goes for a governed dispatch, and the record that it happened.

builder-II's governance strength is auditability, reviewability, determinism and traceability --
not a confirmation wall in front of every action. Every dispatch emits the same artifacts,
receipts and hash-chained events whether or not a human was asked; what a standing grant
relocates is the *pause*, never the emission. Auto-ratified work is exactly as reviewable as
prompted work, and carries one thing prompted work does not: the digest of the grant that
scheduled it, so `builder-govern trace` can walk a receipt back to the decision that allowed it.

This is the non-interactive sibling of `builder_ii.cli.setup_cli._ratify`, which proved the shape
on the setup lane: resolve the level, honour an approval artifact if the policy demands one,
consult a standing grant, and otherwise prompt. Dispatch surfaces need the resolve step separated
from the recording step, because a console must decide whether to raise a confirmation dialog
*before* it does anything, and the process that owns the pause is the one that records it.

Single-writer rule: whichever process owns the pause records the ratification. A console that
prompts records `manual_ratified`; a CLI that consulted the grant records `auto_accepted`. Two
records for one decision would double-count the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from builder_ii.governance.ledger.ratification_ledger import (
    EVENT_AUTO_ACCEPTED,
    EVENT_MANUAL_RATIFIED,
    append_ratification_event,
)
from builder_ii.governance.ratification_grants import (
    consult_ratification_grant,
    resolve_ratification_root,
)
from builder_ii.governance.ratification_points import get_ratification_point
from builder_ii.governance.ratification_policy import (
    LEVEL_REQUIRE_APPROVAL_ARTIFACT,
    effective_level,
)

#: Proceed now: a standing grant covers this point.
STATUS_AUTO = "AUTO"
#: Ask the operator: no grant covers this point, or policy requires a prompt.
STATUS_PROMPT = "PROMPT"
#: Refuse: policy demands a validated approval artifact this surface cannot mint.
STATUS_APPROVAL_ARTIFACT_REQUIRED = "APPROVAL_ARTIFACT_REQUIRED"


@dataclass(frozen=True)
class DispatchRatification:
    """Whether a dispatch may proceed unprompted, and what decided it.

    ``because`` is surfaced verbatim: an operator who is *not* asked deserves to know which grant
    covered it, and one who *is* asked deserves to know why the grant did not apply. "Not allowed"
    would be a worse answer than either.
    """

    point_id: str
    status: str
    because: str
    level: str
    grant_digest: str | None = None
    granted_by: str | None = None

    @property
    def is_auto(self) -> bool:
        return self.status == STATUS_AUTO


def resolve_dispatch_ratification(point_id: str, *, root: Path | None = None) -> DispatchRatification:
    """Decide where the pause goes for one dispatch point. Pure read; writes nothing.

    Fails closed on an unregistered point: an absent point is not an implicit grant, and a typo in
    a point id must not be the thing that skips a confirmation.
    """
    point = get_ratification_point(point_id)
    if point is None:
        return DispatchRatification(
            point_id=point_id,
            status=STATUS_PROMPT,
            because=f"no ratification point is registered as `{point_id}`; asking rather than assuming",
            level=LEVEL_REQUIRE_APPROVAL_ARTIFACT,
        )

    resolved_root = resolve_ratification_root(root)
    decision = effective_level(point_id, root=resolved_root)

    if decision.level == LEVEL_REQUIRE_APPROVAL_ARTIFACT:
        return DispatchRatification(
            point_id=point_id,
            status=STATUS_APPROVAL_ARTIFACT_REQUIRED,
            because=(
                f"{decision.because}. Mint one with "
                f"`builder-govern approve {point_id}` before dispatching."
            ),
            level=decision.level,
        )

    consultation = consult_ratification_grant(point_id, root=resolved_root)
    if consultation.satisfied:
        return DispatchRatification(
            point_id=point_id,
            status=STATUS_AUTO,
            because=consultation.because,
            level=decision.level,
            grant_digest=consultation.grant_digest,
            granted_by=consultation.granted_by,
        )

    return DispatchRatification(
        point_id=point_id,
        status=STATUS_PROMPT,
        because=consultation.because,
        level=decision.level,
    )


def record_auto_ratified(
    ratification: DispatchRatification, *, actor: str, root: Path | None = None
) -> dict:
    """Record that a standing grant, not a human, satisfied this confirmation.

    Refuses to record an auto-acceptance for a decision that was not auto: the ledger's value is
    that `auto_accepted` and `manual_ratified` mean different things.
    """
    if not ratification.is_auto:
        raise ValueError(
            f"refusing to record auto-acceptance for {ratification.point_id!r} with status "
            f"{ratification.status!r}; only an AUTO resolution may be recorded as auto_accepted"
        )
    point = get_ratification_point(ratification.point_id)
    return append_ratification_event(
        resolve_ratification_root(root),
        event=EVENT_AUTO_ACCEPTED,
        point_id=ratification.point_id,
        command=point.command if point else "",
        actor=actor,
        because=ratification.because,
        grant_digest=ratification.grant_digest,
    )


def record_manual_ratified(point_id: str, *, actor: str, because: str, root: Path | None = None) -> dict:
    """Record that a human was asked and answered."""
    point = get_ratification_point(point_id)
    return append_ratification_event(
        resolve_ratification_root(root),
        event=EVENT_MANUAL_RATIFIED,
        point_id=point_id,
        command=point.command if point else "",
        actor=actor,
        because=because,
    )
