"""The closed registry of interactive confirmations a standing grant may ever satisfy.

builder-II asks the operator to confirm things at several points in the golden path. Some of
those confirmations are *friction*: the operator authored a plan, reviewed it, and is now
re-typing its digest to prove the artifact about to be consumed is the one they reviewed.
Others are *the decision itself*: the prompt in ``builder-hitl approve-patch`` does not confirm
an approval, it **mints** one, and its output is the evidence a human decided.

THE INVARIANT THIS MODULE EXISTS TO CARRY:

    A standing grant may relocate confirmation friction. It may never originate approval.

Collapsing those two is the whole danger. An "auto-accept everything" switch is governance
removed; a grant scoped to one named point, derived-eligible, revocable and ledgered, is
governance *relocated* -- the authority decision happens once, explicitly, and every later
auto-acceptance cites it. So eligibility is never a field an author sets to ``True``: it is
:func:`grant_eligibility`, recomputed from the live command-authority registry at consult time.

That "at consult time" is load-bearing. A command promoted from
``explicit_operator_invocation`` to ``hitl_artifact_required`` must invalidate every existing
grant against it without anyone remembering to revoke them, and it does, because nothing about
eligibility is stored in the grant artifact.

TWO INDEPENDENT GUARDS, not one derived rule:

1. The point's declared :attr:`RatificationPoint.kind`. Only ``plan_digest_confirmation`` is
   ever grantable.
2. The owning command's live authority record: it may not require HITL artifacts, may not be
   forbidden/unpromoted, may not carry a capability flag outside
   :data:`GRANTABLE_CAPABILITY_ALLOWLIST`, and must pass ``check_command_authority``.

The first guard alone was the original design and it was wrong. ``builder-hitl approve-patch``
carries ``approval_mode=MODE_NONE`` -- it needs no approval *to run*, because running it is how
an approval gets made -- so deriving eligibility from the approval mode alone would have made
patch approval auto-grantable. That is why the HITL points below are **registered** rather than
merely omitted: an absent point refuses by accident, a registered ``human_approval_mint`` point
refuses on the record, and ``tests/test_ratification_points.py`` can pin the refusal.
"""

from __future__ import annotations

from dataclasses import dataclass

from builder_ii.governance.authority import (
    CAPABILITY_FLAGS,
    MODE_FORBIDDEN_UNPROMOTED,
    MODE_HITL_ARTIFACT_REQUIRED,
    check_command_authority,
    get_command_record,
)

#: The operator re-confirms the digest of a plan artifact they already authored and reviewed,
#: before a command consumes it. The decision was made when the plan was reviewed; this prompt
#: only binds *which artifact* is consumed. Relocatable to a standing grant.
KIND_PLAN_DIGEST_CONFIRMATION = "plan_digest_confirmation"

#: The prompt *is* the human decision, and its output is approval evidence. Never grantable:
#: a grant satisfying one of these would forge a human approval.
KIND_HUMAN_APPROVAL_MINT = "human_approval_mint"

#: The confirmation crosses a capability promotion boundary. Never grantable: promotion needs
#: the eight gates and an evidence-backed matrix flip, which no standing grant can supply.
KIND_PROMOTION_DECISION = "promotion_decision"

#: The operator confirms that an already-approved unit of work should start *now*, from a
#: console. The lane it starts is itself fail-closed, receipted, and re-validates its own
#: approvals at its own boundary -- so this prompt schedules governed work, it does not authorize
#: it. Relocatable to a standing grant; see the allowlist below for what that grant may cover.
KIND_GOVERNED_DISPATCH_CONFIRMATION = "governed_dispatch_confirmation"

RATIFICATION_KINDS: tuple[str, ...] = (
    KIND_PLAN_DIGEST_CONFIRMATION,
    KIND_HUMAN_APPROVAL_MINT,
    KIND_PROMOTION_DECISION,
    KIND_GOVERNED_DISPATCH_CONFIRMATION,
)

#: The only kinds a grant may satisfy. Deliberately enumerated rather than a bool on the point:
#: adding a kind forces an explicit decision here instead of defaulting to grantable. Dispatch
#: was added by that route -- the decision, and its cost, are recorded in
#: docs/RATIFICATION_GRANTS.md rather than inferred from a flag someone set.
GRANTABLE_KINDS: tuple[str, ...] = (
    KIND_PLAN_DIGEST_CONFIRMATION,
    KIND_GOVERNED_DISPATCH_CONFIRMATION,
)

#: Capability flags a grantable point's owning command may carry, **per kind**. A single shared
#: allowlist would have meant widening it for dispatch also widened it for plan-digest
#: confirmations, which is exactly the silent scope creep this table exists to prevent.
#:
#: `plan_digest_confirmation`: writes are permitted -- the point of `builder-setup apply` is that
#: it writes -- because the write itself was authorized when the operator authored and reviewed
#: the plan.
#:
#: `governed_dispatch_confirmation`: runtime start and external tool invocation are permitted,
#: because starting a governed run is what the point *is*. `allows_process_control` is
#: deliberately excluded: stopping a live run is not a scheduling decision, and a standing grant
#: must never be able to halt work an operator is watching. Shell, model, source writes, git and
#: memory mutation are excluded for the same reason they always were.
#:
#: Anything absent from a kind's set makes a point ineligible no matter what kind it declares.
GRANTABLE_CAPABILITY_ALLOWLIST_BY_KIND: dict[str, frozenset[str]] = {
    KIND_PLAN_DIGEST_CONFIRMATION: frozenset(
        {
            "allows_source_writes",
            "allows_artifact_writes",
            "allows_state_writes",
        }
    ),
    KIND_GOVERNED_DISPATCH_CONFIRMATION: frozenset(
        {
            "allows_runtime_start",
            "allows_external_tool_invocation",
            "allows_readonly_subprocess",
            "allows_artifact_writes",
            "allows_state_writes",
        }
    ),
}

#: Retained for callers that predate the per-kind split; it is the plan-digest set, unchanged.
GRANTABLE_CAPABILITY_ALLOWLIST: frozenset[str] = GRANTABLE_CAPABILITY_ALLOWLIST_BY_KIND[
    KIND_PLAN_DIGEST_CONFIRMATION
]

#: Approval modes that can never be satisfied by a standing grant.
UNGRANTABLE_APPROVAL_MODES: frozenset[str] = frozenset(
    {
        MODE_HITL_ARTIFACT_REQUIRED,
        MODE_FORBIDDEN_UNPROMOTED,
    }
)


@dataclass(frozen=True)
class RatificationPoint:
    """One interactive confirmation in the golden path, named so a grant can scope to it.

    ``what_is_ratified`` and ``consequence_of_auto`` are operator-facing prose shown at the
    prompt: the first explains what this confirmation actually decides, the second states
    plainly what changes if the operator delegates it. A point that cannot say what granting it
    costs has no business offering the grant.
    """

    id: str
    command: str
    kind: str
    what_is_ratified: str
    consequence_of_auto: str


RATIFICATION_POINTS: tuple[RatificationPoint, ...] = (
    RatificationPoint(
        id="setup.apply.overlay_digest",
        command="builder-setup apply",
        kind=KIND_PLAN_DIGEST_CONFIRMATION,
        what_is_ratified=(
            "That the overlay plan about to be written is the one you reviewed. Apply prints the "
            "overlay_plan_digest and you type its first characters back."
        ),
        consequence_of_auto=(
            "Declared setup writes from an already-validated overlay plan proceed without the typed "
            "digest. The plan still has to validate, the rollback snapshot still has to match, and "
            "the receipt records that a grant satisfied it -- not that you typed anything."
        ),
    ),
    RatificationPoint(
        id="setup.rollback.receipt_digest",
        command="builder-setup rollback",
        kind=KIND_PLAN_DIGEST_CONFIRMATION,
        what_is_ratified=(
            "That the setup receipt about to be rolled back is the one you reviewed. Rollback prints "
            "the receipt digest and you type its first characters back."
        ),
        consequence_of_auto=(
            "Rollback of paths recorded in an applied setup receipt proceeds without the typed digest. "
            "It still touches only changed_paths covered by the supplied snapshot."
        ),
    ),
    # Governed dispatch: the operator says "start now" for work whose governance already
    # happened elsewhere. Each of these fronts a lane that fails closed on its own boundary --
    # the manifest must validate, the candidate approval must be digest-bound and unexhausted,
    # the postflight must find no mutation -- so a grant here moves *when* the operator is asked,
    # never *whether* the lane will check.
    RatificationPoint(
        id="stratum.dispatch.goose_run",
        command="builder-goose run-governed",
        kind=KIND_GOVERNED_DISPATCH_CONFIRMATION,
        what_is_ratified=(
            "That this governed Goose run should start now, against the manifest and task shown. "
            "The console prints the manifest digest, the task, and the exact argv."
        ),
        consequence_of_auto=(
            "Governed runs start from the console without the confirmation step. They remain "
            "read-only: builtins stay stripped, tools stay jailed to the repo, the no-mutation "
            "postflight still fails the run on any file that moved, and the launch receipt records "
            "that a grant satisfied this -- not that you confirmed anything."
        ),
    ),
    RatificationPoint(
        id="stratum.dispatch.prepare_package",
        command="builder-session prepare-package",
        kind=KIND_GOVERNED_DISPATCH_CONFIRMATION,
        what_is_ratified=(
            "That the session preparation package described in the console should be built now."
        ),
        consequence_of_auto=(
            "Preparation packages are assembled from the console without confirmation. This reads "
            "the repository and writes one governed artifact; it starts no runtime and approves "
            "nothing."
        ),
    ),
    RatificationPoint(
        id="stratum.dispatch.assign_subagent",
        command="builder-deepagents assign-subagent",
        kind=KIND_GOVERNED_DISPATCH_CONFIRMATION,
        what_is_ratified=(
            "That the selected agent profiles should be assigned to the work plan shown."
        ),
        consequence_of_auto=(
            "Subagent assignments are written from the console without confirmation. Assignment is a "
            "passive artifact: it dispatches no agent and starts no runtime, and running the work "
            "still requires its own digest-bound candidate approval."
        ),
    ),
    # Registered to be refused, not omitted. See the module docstring: omission refuses by
    # accident and cannot be pinned; a declared `human_approval_mint` refuses on the record.
    RatificationPoint(
        id="hitl.approve_patch.patch_digest",
        command="builder-hitl approve-patch",
        kind=KIND_HUMAN_APPROVAL_MINT,
        what_is_ratified=(
            "That you, a human, approve this patch. The typed digest prefix is the approval itself -- "
            "the artifact this command writes is evidence that a person decided."
        ),
        consequence_of_auto=(
            "Nothing: this point can never be granted. Delegating it would manufacture human approval "
            "evidence for a decision no human made."
        ),
    ),
    RatificationPoint(
        id="hitl.refuse_patch.proposal_digest",
        command="builder-hitl refuse-patch",
        kind=KIND_HUMAN_APPROVAL_MINT,
        what_is_ratified="That you, a human, refuse this patch. The refusal record is evidence of your decision.",
        consequence_of_auto="Nothing: this point can never be granted, for the same reason approval cannot.",
    ),
    RatificationPoint(
        id="hitl.approve_rollback.plan_digest",
        command="builder-hitl approve-rollback",
        kind=KIND_HUMAN_APPROVAL_MINT,
        what_is_ratified=(
            "That you, a human, approve rolling back to a machine-generated plan. The typed digest "
            "prefix is the approval itself."
        ),
        consequence_of_auto=(
            "Nothing: this point can never be granted. A rollback approved by no one is a change "
            "nobody decided to make."
        ),
    ),
    RatificationPoint(
        id="hitl.promotion_decision.candidate_digest",
        command="builder-hitl promotion-decision",
        kind=KIND_PROMOTION_DECISION,
        what_is_ratified=(
            "That a capability may cross a promotion boundary. This is the eight-gate operator "
            "decision that flips the completion matrix."
        ),
        consequence_of_auto=(
            "Nothing: this point can never be granted. Promotion needs evidence and an operator, "
            "and a standing grant is neither."
        ),
    ),
)

_POINTS_BY_ID: dict[str, RatificationPoint] = {point.id: point for point in RATIFICATION_POINTS}


@dataclass(frozen=True)
class EligibilityDecision:
    """Whether a point may be satisfied by a standing grant, and the reason either way.

    ``because`` is surfaced verbatim to the operator when a grant is refused, so it must name
    the fact that decided it -- never "not allowed".
    """

    point_id: str
    eligible: bool
    because: str


def get_ratification_point(point_id: str) -> RatificationPoint | None:
    """The registered point with this id, or None. Absence is never an implicit grant."""
    return _POINTS_BY_ID.get(point_id)


def grantable_point_ids() -> tuple[str, ...]:
    """Every point id currently eligible for a standing grant, recomputed from the live registry."""
    return tuple(point.id for point in RATIFICATION_POINTS if grant_eligibility(point).eligible)


def grant_eligibility(point: RatificationPoint) -> EligibilityDecision:
    """Recompute, from the live command-authority registry, whether ``point`` may be granted.

    Never cached and never stored on the grant artifact: a command whose authority tightens must
    invalidate its outstanding grants without anyone remembering to revoke them.
    """
    if point.kind not in GRANTABLE_KINDS:
        return EligibilityDecision(
            point_id=point.id,
            eligible=False,
            because=f"ratification kind is `{point.kind}`, which no grant may satisfy",
        )

    record = get_command_record(point.command)
    if record is None:
        return EligibilityDecision(
            point_id=point.id,
            eligible=False,
            because=f"no command-authority record names `{point.command}`",
        )

    inherited_from = getattr(record, "inherited_from", None)
    if inherited_from:
        return EligibilityDecision(
            point_id=point.id,
            eligible=False,
            because=(
                f"authority for `{point.command}` is inherited from `{inherited_from}`, not declared; "
                "an inherited record may not license a standing grant"
            ),
        )

    if record.approval_mode in UNGRANTABLE_APPROVAL_MODES:
        return EligibilityDecision(
            point_id=point.id,
            eligible=False,
            because=f"approval mode is `{record.approval_mode}`",
        )

    allowlist = GRANTABLE_CAPABILITY_ALLOWLIST_BY_KIND.get(point.kind, frozenset())
    carried = tuple(flag for flag in CAPABILITY_FLAGS if getattr(record, flag, False))
    disallowed = tuple(flag for flag in carried if flag not in allowlist)
    if disallowed:
        return EligibilityDecision(
            point_id=point.id,
            eligible=False,
            because=(
                f"`{point.command}` carries `{disallowed[0]}`, which is outside the grantable "
                f"capability set for kind `{point.kind}`"
            ),
        )

    decision = check_command_authority(point.command)
    if not decision.allowed:
        return EligibilityDecision(
            point_id=point.id,
            eligible=False,
            because=f"command authority denies `{point.command}`",
        )

    if point.kind == KIND_GOVERNED_DISPATCH_CONFIRMATION:
        return EligibilityDecision(
            point_id=point.id,
            eligible=True,
            because=(
                "scheduling confirmation for a governed lane that re-validates its own approvals at "
                "its own boundary; the grant relocates when work starts, never whether it is allowed"
            ),
        )

    return EligibilityDecision(
        point_id=point.id,
        eligible=True,
        because=(
            "digest confirmation of a plan the operator already authored and validated; the owning "
            "command carries only governed write capability"
        ),
    )


def validate_ratification_point_registry() -> list[str]:
    """Structural errors in the point registry itself. Pinned to be empty.

    The HITL check here is the class-of-danger guard, and it is deliberately by command-name
    prefix rather than by anything the point author writes: a new confirmation added anywhere
    under `builder-hitl` is refused a grantable kind whether or not its author thought about it.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for point in RATIFICATION_POINTS:
        if point.id in seen:
            errors.append(f"duplicate ratification point id: {point.id!r}")
        seen.add(point.id)
        if point.kind not in RATIFICATION_KINDS:
            errors.append(f"{point.id}: unknown ratification kind {point.kind!r}")
        if get_command_record(point.command) is None:
            errors.append(f"{point.id}: no command-authority record names {point.command!r}")
        if point.command.startswith("builder-hitl ") and point.kind in GRANTABLE_KINDS:
            errors.append(
                f"{point.id}: a `builder-hitl` confirmation may never declare a grantable kind "
                f"(declared {point.kind!r})"
            )
        if not point.what_is_ratified.strip() or not point.consequence_of_auto.strip():
            errors.append(f"{point.id}: must state both what is ratified and the consequence of granting it")
    return errors
