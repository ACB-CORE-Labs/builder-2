"""Characterization pins for `ForgeWizard`, written against unmodified code.

`WizardStep`/`WizardEngine` were extracted *from* `ForgeStep`/`ForgeWizard` in Ladder 5 PR-1,
which re-expressed `builder init` and `builder-setup wizard` on the framework and deliberately
left the forge wizard on its own copy. An extraction whose source still holds a copy is not
finished -- but the forge wizard's state machine has never had a test, so nothing said what it
does before it is moved.

These pins say. They are written to pass against the pre-migration `ForgeWizard`, so that the
migration is provably behaviour-preserving rather than merely believed to be.

Two quirks are pinned here on purpose, because they are current behaviour:

  1. `_next_cursor` auto-skips by hardcoded step id (`next_step.id == "hitl_gates"`) rather than
     by asking `step.is_required(spec)`, which already answers exactly that question.
  2. It inspects only the *immediate* next step, so it can skip at most one step in a row.

Both are invisible today because `hitl_gates` is the only step with `auto_required_if`. The
migration removes the hardcode; `test_forge_wizard_on_framework.py` pins the fixed behaviour.
"""

from __future__ import annotations

import pytest

from builder_ii.deepagents_forge_wizard import FORGE_STEPS, ForgeWizard

STEP_IDS = (
    "identity",
    "persona",
    "target_profile",
    "capabilities",
    "hitl_gates",
    "context_pack",
    "mcp_tools",
    "governance",
    "preview",
)


def _answer_through_capabilities(wizard: ForgeWizard, capabilities: list[str]) -> None:
    assert wizard.apply("pr_reviewer").ok
    assert wizard.apply("You are an agent that reviews pull requests.").ok
    assert wizard.apply("generic").ok
    assert wizard.apply(capabilities).ok


def test_the_nine_steps_and_their_order_are_the_wizards_contract() -> None:
    assert tuple(step.id for step in FORGE_STEPS) == STEP_IDS
    wizard = ForgeWizard()
    assert wizard.get_progress() == (1, 9), "progress is 1-based"
    assert wizard.current_step().id == "identity"
    assert not wizard.is_complete()


def test_a_seed_name_derives_the_slug_before_the_first_prompt() -> None:
    assert ForgeWizard(seed_name="PR Reviewer").spec.slug
    assert ForgeWizard().spec.slug == "", "no seed name, no slug"
    assert ForgeWizard(seed_profile="core").spec.target_profile == "core"


def test_an_invalid_answer_does_not_advance_the_cursor_and_returns_its_error() -> None:
    wizard = ForgeWizard()
    result = wizard.apply("")
    assert not result.ok and result.error
    assert wizard.current_step().id == "identity", "a rejected answer must not advance"
    assert wizard.spec.name == "", "a rejected answer must not reach the spec"

    assert wizard.apply("pr_reviewer").ok
    assert wizard.current_step().id == "persona"
    assert wizard.spec.name == "pr_reviewer"
    assert wizard.spec.slug, "applying the name auto-derives the slug"


def test_hitl_gates_is_skipped_when_no_capability_needs_a_human() -> None:
    """The one branch the wizard has. `read_files` needs no gate, so the step is passed over."""
    wizard = ForgeWizard()
    _answer_through_capabilities(wizard, ["read_files"])
    assert wizard.current_step().id == "context_pack", "hitl_gates must be skipped"
    assert wizard.spec.hitl_gates == []


@pytest.mark.parametrize("capability", ["write_files", "run_shell"])
def test_hitl_gates_is_asked_when_a_capability_needs_a_human(capability: str) -> None:
    wizard = ForgeWizard()
    _answer_through_capabilities(wizard, [capability])
    assert wizard.current_step().id == "hitl_gates", f"{capability} must force the gate step"
    assert wizard.current_step().is_required(wizard.spec)


def test_skip_refuses_a_required_step_and_allows_an_optional_one() -> None:
    wizard = ForgeWizard()
    assert not wizard.skip(), "`identity` is required and must not be skippable"
    assert wizard.current_step().id == "identity"

    _answer_through_capabilities(wizard, ["read_files"])
    assert wizard.current_step().id == "context_pack"
    assert wizard.skip(), "`context_pack` is optional"
    assert wizard.current_step().id == "mcp_tools"


def test_skip_refuses_hitl_gates_exactly_when_a_capability_requires_it() -> None:
    wizard = ForgeWizard()
    _answer_through_capabilities(wizard, ["write_files"])
    assert wizard.current_step().id == "hitl_gates"
    assert not wizard.skip(), "a write capability makes the gate step unskippable"


def test_back_returns_to_the_previous_step_and_refuses_at_the_first() -> None:
    wizard = ForgeWizard()
    assert not wizard.back(), "no history at the first step"

    assert wizard.apply("pr_reviewer").ok
    assert wizard.current_step().id == "persona"
    assert wizard.back()
    assert wizard.current_step().id == "identity"
    assert wizard.spec.name == "pr_reviewer", "back rewinds the cursor, not the spec"


def test_back_across_an_auto_skipped_step_lands_on_the_step_that_caused_the_skip() -> None:
    wizard = ForgeWizard()
    _answer_through_capabilities(wizard, ["read_files"])
    assert wizard.current_step().id == "context_pack"
    assert wizard.back()
    assert wizard.current_step().id == "capabilities", "history records the step answered, not the one skipped"


def test_the_wizard_completes_after_the_final_step() -> None:
    wizard = ForgeWizard()
    _answer_through_capabilities(wizard, ["read_files"])
    assert wizard.skip()  # context_pack
    assert wizard.skip()  # mcp_tools
    assert wizard.apply(
        {
            "verification_profile": "generic_basic",
            "output_artifact": ".builder/agents/pr_reviewer.json",
            "rollback_path": ".builder/rollback",
        }
    ).ok
    assert wizard.current_step().id == "preview"
    assert wizard.get_progress() == (9, 9)
    assert wizard.skip(), "`preview` takes no input"
    assert wizard.is_complete()


def test_a_multi_field_step_writes_every_field_it_names() -> None:
    wizard = ForgeWizard()
    _answer_through_capabilities(wizard, ["read_files"])
    wizard.skip()
    wizard.skip()
    assert wizard.apply(
        {
            "verification_profile": "generic_basic",
            "output_artifact": ".builder/agents/pr_reviewer.json",
            "rollback_path": ".builder/rollback",
        }
    ).ok
    assert wizard.spec.verification_profile == "generic_basic"
    assert wizard.spec.output_artifact == ".builder/agents/pr_reviewer.json"
    assert wizard.spec.rollback_path == ".builder/rollback"


def test_hitl_gates_is_still_the_only_conditionally_required_step() -> None:
    """The premise of the branch. If a second one appears, the pins above stop covering it."""
    auto_required = [step.id for step in FORGE_STEPS if step.auto_required_if is not None]
    assert auto_required == ["hitl_gates"]
