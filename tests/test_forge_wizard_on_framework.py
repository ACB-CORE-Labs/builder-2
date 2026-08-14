"""The forge wizard, re-expressed on `wizard_framework`. What the migration fixed.

`tests/test_forge_wizard_characterization.py` pins the behaviour that must not change, and it was
green against the pre-migration code. These pins are the ones that could *not* have been green
before: they assert that the duplicate state machine is gone and that its two quirks went with it.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from builder_ii.adapters.deepagents.deepagents_forge_wizard import FORGE_STEPS, ForgeWizard
from builder_ii.lifecycle.setup.wizard_framework import WizardEngine, WizardStep


def test_the_forge_wizard_no_longer_owns_a_cursor_history_state_machine() -> None:
    """The extraction is finished when its source no longer holds a copy.

    Asserted structurally, not by grepping source text: these docstrings name `_next_cursor` and
    `hitl_gates` in order to explain them, and a pin that reads source would be satisfied -- or
    defeated -- by a comment.
    """
    assert not hasattr(ForgeWizard, "_next_cursor"), "the duplicate advance logic is gone"

    wizard = ForgeWizard()
    assert isinstance(wizard._engine, WizardEngine)
    assert "cursor" not in vars(wizard), "the cursor is the engine's, not a second copy"
    assert "history" not in vars(wizard), "so is the history"
    assert wizard.cursor == wizard._engine.cursor
    assert wizard.history == wizard._engine.history
    assert wizard.history is not wizard._engine.history, "the engine's list is not handed out"

    wizard.apply("pr_reviewer")
    wizard.history.clear()
    assert wizard._engine.history == [0], "clearing the snapshot must not disarm `back()`"
    assert wizard.back() is True


def _code_without_docstring(func) -> str:
    """The function's code, with its docstring removed.

    A pin that greps `inspect.getsource` is satisfied -- or defeated -- by a comment. This one asks
    only what the code does, so a docstring may name `hitl_gates` in order to explain the rule
    without either passing or failing the pin on that account.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    definition = tree.body[0]
    assert isinstance(definition, ast.FunctionDef)
    if ast.get_docstring(definition):
        definition.body = definition.body[1:]
    return ast.unparse(definition)


def test_the_branch_is_derived_from_the_predicate_that_already_answered_it() -> None:
    """`_next_cursor` matched `next_step.id == "hitl_gates"`. `is_required` already knew."""
    engine_code = _code_without_docstring(WizardEngine._skip_preanswered)
    assert "required_when" in engine_code
    assert "hitl_gates" not in engine_code, "the framework must not know a forge step's name"

    hitl = next(step for step in FORGE_STEPS if step.id == "hitl_gates")
    assert hitl.auto_required_if is not None

    wizard = ForgeWizard()
    framework_step = next(s for s in wizard._engine.steps if s.id == "hitl_gates")
    assert framework_step.required_when is not None, "the branch rides on the step"


def test_a_second_conditionally_required_step_is_auto_skipped_too() -> None:
    """It would not have been. `_next_cursor` only ever recognised `hitl_gates`.

    This is the failure the old code was one step away from: add a second `auto_required_if` and
    it silently prompts forever, because nothing but that one string was ever checked.
    """
    steps = (
        WizardStep(id="first", question="First", free_form=True),
        WizardStep(id="conditional_one", question="?", free_form=True, required_when=lambda _a: False),
        WizardStep(id="conditional_two", question="?", free_form=True, required_when=lambda _a: False),
        WizardStep(id="last", question="Last", free_form=True),
    )
    engine = WizardEngine(steps=steps)
    assert engine.apply("x") == []
    assert engine.current_step().id == "last"


def test_skip_when_is_gone_and_nothing_lost_a_capability() -> None:
    """An engine-level hook with no caller. The forge's branch belongs on the forge's step."""
    assert "skip_when" not in WizardEngine.__dataclass_fields__
    assert "required_when" in WizardStep.__dataclass_fields__, "and the capability it offered survives"

    # What `skip_when` could express, `required_when` expresses -- on the step that owns the branch.
    conditional = WizardStep(id="b", question="?", free_form=True, required_when=lambda a: a.get("first") != "no-b")
    engine = WizardEngine(
        steps=(WizardStep(id="first", question="?", free_form=True), conditional, WizardStep(id="c", question="?"))
    )
    engine.apply("no-b")
    assert engine.current_step().id == "c"


def test_the_wizard_still_refuses_to_skip_hitl_gates_when_a_write_capability_is_granted() -> None:
    """The governance property the branch exists to protect, asserted through the new engine."""
    wizard = ForgeWizard()
    assert wizard.apply("pr_reviewer").ok
    assert wizard.apply("You are an agent that writes patches.").ok
    assert wizard.apply("generic").ok
    assert wizard.apply(["write_files"]).ok

    assert wizard.current_step().id == "hitl_gates"
    assert not wizard.skip(), "a write capability must not reach the spec without a HITL gate"

    framework_step = next(s for s in wizard._engine.steps if s.id == "hitl_gates")
    assert framework_step.required_when is not None
    assert framework_step.is_required(wizard._engine.answers)


def test_going_back_and_granting_one_more_capability_re_asks_for_the_gate_it_requires() -> None:
    """The regression the 13 characterization pins did not notice, because none of them go back.

    Grant `write_files`; answer `hitl_gates`; go back twice; also grant `run_shell` -- the ordinary
    "check one more box and press Next" flow. `_skip_preanswered` saw `hitl_gates` in `answers` and
    passed over it without re-asking `required_when`. The wizard reached `is_complete()` carrying a
    shell capability with no `before_shell` gate. `_next_cursor` had no memory of answers, so it
    asked the predicate every time and never did this.

    `emit_agent` still refuses such a spec, so nothing ungated ever reached disk -- which is exactly
    why this could ship unnoticed. The wizard's own guard is the one under test here.
    """
    wizard = ForgeWizard()
    wizard.apply("pr_reviewer")
    wizard.apply("You are an agent that reviews pull requests carefully and reports findings.")
    wizard.apply("generic")

    assert wizard.current_step().id == "capabilities"
    wizard.apply(["write_files"])
    assert wizard.current_step().id == "hitl_gates", "a write capability requires a gate"
    wizard.apply(["before_write"])
    assert wizard.current_step().id == "context_pack"

    assert wizard.back() and wizard.back()
    assert wizard.current_step().id == "capabilities"
    wizard.apply(["write_files", "run_shell"])

    assert wizard.current_step().id == "hitl_gates", "a newly granted shell capability re-opens the gate"
    assert not wizard.is_complete()


def test_a_step_answered_at_the_prompt_is_not_a_step_answered_by_a_flag() -> None:
    """`_skip_preanswered` passes over preanswered steps. Only those."""
    from builder_ii.lifecycle.setup.wizard_framework import WizardStep

    steps = (
        WizardStep(id="a", question="a?", free_form=True),
        WizardStep(id="b", question="b?", free_form=True),
        WizardStep(id="c", question="c?", free_form=True),
    )

    flagged = WizardEngine(steps=steps)
    flagged.preanswer("b", "from-a-flag")
    flagged.apply("typed-a")
    assert flagged.current_step().id == "c", "a flag answer is passed over"

    typed = WizardEngine(steps=steps)
    typed.apply("typed-a")
    typed.apply("typed-b")
    assert typed.back() and typed.back()
    assert typed.current_step().id == "a"
    typed.apply("typed-a-again")
    assert typed.current_step().id == "b", "an answer given at the prompt is asked again on the way forward"
