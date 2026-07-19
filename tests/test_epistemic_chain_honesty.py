"""Epistemic honesty: `executed` means an execution happened, not that a planned artifact's kind
merely contains the word "execution".

TUI/UX red-team audit H3. `epistemic_from_chain` greened the executed state from any kind containing
"execution" -- including `verification_execution_plan` / `_approval` and `execution_candidate_manifest`
(the exec-req pipeline stage), all planned-only. That conflates planned != executed, the very
distinction the epistemic matrix exists to display. Digests stay absent ("—") throughout; STRATUM
never invents them (that is pinned in test_stratum_projections.py). This pins the *state* honesty.
"""

from __future__ import annotations

from builder_ii.tui.projections.chain import ChainView, epistemic_from_chain


def _chain(kinds: set[str], *, chain_valid: bool | None = None, file_count: int = 1) -> ChainView:
    return ChainView(stages=(), chain_valid=chain_valid, file_count=file_count, found_kinds=tuple(sorted(kinds)))


def test_a_planned_execution_artifact_does_not_green_the_executed_state() -> None:
    """A plan/approval/candidate contains "execution" but is planned-only -- executed must not green."""
    for planned_kind in (
        "builder_ii.verification_execution_plan",
        "builder_ii.verification_execution_approval",
        "builder_ii.execution_candidate_manifest",
    ):
        epi = epistemic_from_chain(_chain({planned_kind}))
        assert epi["state_executed"] != "completed", (
            f"{planned_kind} is planned-only; it must not green the executed state"
        )


def test_real_execution_evidence_greens_the_executed_state() -> None:
    """A receipt / postflight / genuine execution record is real evidence that it ran."""
    for executed_kind in (
        "builder_ii.execution_postflight_record",
        "builder_ii.verification_execution_receipt",
        "builder_ii.hitl_command_execution",
    ):
        epi = epistemic_from_chain(_chain({executed_kind}))
        assert epi["state_executed"] == "completed", f"{executed_kind} is real execution evidence"


def test_verified_greens_only_on_an_explicitly_valid_chain() -> None:
    """verified is the one state already bound to real evidence (verify_artifact_chain); keep it so."""
    unverified = epistemic_from_chain(_chain({"builder_ii.verification_execution_receipt"}, chain_valid=None))
    assert unverified["state_verified"] != "completed"

    verified = epistemic_from_chain(_chain({"builder_ii.verification_execution_receipt"}, chain_valid=True))
    assert verified["state_verified"] == "completed"


def test_promoted_never_greens_without_a_promotion_decision_kind() -> None:
    epi = epistemic_from_chain(_chain({"builder_ii.execution_postflight_record"}, chain_valid=True))
    assert epi["state_promoted"] != "completed"

    promoted = epistemic_from_chain(
        _chain({"builder_ii.promotion_decision_record"}, chain_valid=True)
    )
    assert promoted["state_promoted"] == "completed"


def test_digests_are_always_absent_regardless_of_state() -> None:
    epi = epistemic_from_chain(_chain({"builder_ii.execution_postflight_record"}, chain_valid=True))
    for key in ("digest_planned", "digest_executed", "digest_verified", "digest_promoted"):
        assert epi[key] == "—"
