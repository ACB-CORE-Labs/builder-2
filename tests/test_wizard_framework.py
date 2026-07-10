"""Engine and invariant tests for ``builder_ii.wizard_framework`` (Ladder 5 PR-1).

The invariant this file enforces (the crux of the ladder): **a wizard step may never name
its allowed values; it may only reference the registry that owns them.** A prompt string
that transcribes its allowed values is a doc that claims a capability the code may not
back, and ``builder-platform audit-docs`` cannot see it -- that is exactly how
``builder-setup wizard`` came to offer 3 of 8 live backends. The transcription pin below is
the same move as ``tests/test_ci_gate_parity.py``: it makes the drift unrepresentable
rather than merely fixed once.
"""

from __future__ import annotations

import pytest

from builder_ii.cli.setup_cli import setup_wizard_step_definitions
from builder_ii.init_decisions import init_wizard_step_definitions
from builder_ii.wizard_framework import (
    WizardAborted,
    WizardEngine,
    WizardStep,
    known_decision_registries,
    run_typer_prompt_loop,
    transcribed_registry_members,
)

# --- the invariant -------------------------------------------------------------------------


def test_no_wizard_step_transcribes_members_of_any_decision_registry() -> None:
    """No step's literal question text may contain a member of any decision registry.

    Prompt text is rendered FROM the registry at prompt time (`render_question`), never
    transcribed INTO the step definition -- so adding a ninth backend updates every wizard
    automatically and a stale prompt is unrepresentable. Falsifiability is proven in the
    PR bodies: append a registry member to an init question, watch this fail naming it,
    remove it, watch it pass.

    PR-1 carried a named, self-liquidating exemption here for the two `builder-setup
    wizard` steps it ported as-is, lie and all; PR-2 fixed those prompts, the exemption's
    guard test failed exactly as designed, and both were deleted. The sweep is now total:
    every step of every framework wizard, no exceptions.
    """
    registries = tuple(known_decision_registries().values())
    surfaces = (
        ("init", init_wizard_step_definitions()),
        ("setup", setup_wizard_step_definitions()),
    )
    for surface, steps in surfaces:
        for step in steps:
            hits = transcribed_registry_members(step.question, registries)
            assert not hits, (
                f"wizard step {surface}:{step.id} transcribes registry member(s) {hits} into its "
                "literal prompt text; reference the owning registry via options_provider instead"
            )


def test_registry_drift_reaches_both_wizards_with_no_wizard_code_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add a ninth backend to the registry; both wizards offer and accept it, untouched.

    This is the payoff of the invariant, asserted directly. Under PR-1 this test held the
    opposite contrast for the setup wizard (its transcribed prompt did NOT pick up the new
    backend); PR-2 landed and the assertion inverted, exactly as its docstring promised.
    The alias step renders no options by presentation choice, but the registry reference
    still carries drift: the new alias validates with no code change.
    """
    from builder_ii import init_decisions

    monkeypatch.setattr(init_decisions, "BACKENDS", (*init_decisions.BACKENDS, "fake-backend-nine"))
    monkeypatch.setattr(init_decisions, "MODEL_ALIASES", (*init_decisions.MODEL_ALIASES, "fake-alias"))

    init_backend = {s.id: s for s in init_wizard_step_definitions()}["model_backend"]
    assert "fake-backend-nine" in init_backend.allowed_values()
    assert "fake-backend-nine" in init_backend.render_question()
    assert init_backend.validate("fake-backend-nine") == []

    setup_steps = {s.id: s for s in setup_wizard_step_definitions()}
    assert "fake-backend-nine" in setup_steps["model_backend"].allowed_values()
    assert "fake-backend-nine" in setup_steps["model_backend"].render_question()
    assert setup_steps["model_backend"].validate("fake-backend-nine") == []

    alias_step = setup_steps["model_alias"]
    assert "fake-alias" in alias_step.allowed_values()
    assert "fake-alias" not in alias_step.render_question(), "the alias question renders no options by design"
    assert alias_step.validate("fake-alias") == []


def test_word_boundary_matching_does_not_false_positive_on_substrings() -> None:
    """`llama` is a model alias and a substring of the backend `ollama`; the sweep must
    flag only whole-token transcriptions or the pin would be unsatisfiable."""
    registries = (("llama", "core"),)
    assert transcribed_registry_members("Select local model backend (rapid-mlx, mlx-lm, ollama)", registries) == []
    assert transcribed_registry_members("Try llama for a local run", registries) == ["llama"]
    assert transcribed_registry_members("'core' is for AssetOverflow/core only.", registries) == ["core"]


# --- the engine ----------------------------------------------------------------------------


def _steps() -> tuple[WizardStep, ...]:
    return (
        WizardStep(id="a", question="Question A", default="a-default", free_form=True),
        WizardStep(
            id="b",
            question="Question B",
            options_provider=lambda: ("one", "two"),
            validator=lambda value: [] if value in ("one", "two") else [f"b must be one of: one, two (got {value!r})"],
        ),
        WizardStep(id="c", question="Question C", free_form=True),
    )


def test_engine_applies_valid_answers_and_advances() -> None:
    engine = WizardEngine(steps=_steps())
    assert engine.current_step().id == "a"
    assert engine.get_progress() == (1, 3)
    assert engine.apply("anything") == []
    assert engine.current_step().id == "b"
    assert engine.apply("garbage") != []
    assert engine.current_step().id == "b", "an invalid answer must not advance the cursor"
    assert engine.apply("two") == []
    assert engine.apply("done") == []
    assert engine.is_complete()
    assert engine.answers == {"a": "anything", "b": "two", "c": "done"}


def test_engine_back_returns_to_the_previous_step() -> None:
    engine = WizardEngine(steps=_steps())
    engine.apply("x")
    assert engine.back() is True
    assert engine.current_step().id == "a"
    assert WizardEngine(steps=_steps()).back() is False


def test_engine_skip_applies_only_to_free_form_steps() -> None:
    engine = WizardEngine(steps=_steps())
    assert engine.skip() is True
    assert engine.current_step().id == "b"
    assert engine.skip() is False, "a registry-validated step must not be skippable"


def test_engine_preanswered_steps_are_never_prompted() -> None:
    engine = WizardEngine(steps=_steps())
    engine.preanswer("a", "flag-a")
    engine.preanswer("b", "one")
    assert engine.current_step().id == "c"
    with pytest.raises(KeyError):
        engine.preanswer("nope", "x")


def test_engine_rejects_duplicate_step_ids() -> None:
    step = WizardStep(id="dup", question="Q", free_form=True)
    with pytest.raises(ValueError):
        WizardEngine(steps=(step, step))


def test_engine_skip_when_branching_hook() -> None:
    engine = WizardEngine(
        steps=_steps(),
        skip_when=lambda step, answers: step.id == "b" and answers.get("a") == "no-b",
    )
    engine.apply("no-b")
    assert engine.current_step().id == "c", "the branching hook generalizes the forge hitl_gates auto-skip"


def test_render_question_composes_from_the_provider_at_call_time() -> None:
    live = ["one", "two"]
    step = WizardStep(id="s", question="Pick", options_provider=lambda: tuple(live))
    assert step.render_question() == "Pick (one, two)"
    live.append("three")
    assert step.render_question() == "Pick (one, two, three)", "options must be read at prompt time, never earlier"


def test_render_options_is_all_from_the_registry_or_nothing() -> None:
    """A large registry may opt out of enumerating into the prompt line, but the step keeps
    its registry reference: values and validation stay live. There is no mechanism for
    rendering a subset -- a prompt can never claim fewer values than exist."""
    step = WizardStep(
        id="s", question="Pick", options_provider=lambda: ("one", "two"), render_options_in_question=False
    )
    assert step.render_question() == "Pick"
    assert step.allowed_values() == ("one", "two")


def test_prompt_loop_retries_then_aborts_at_max_attempts() -> None:
    engine = WizardEngine(steps=_steps())
    engine.preanswer("a", "flag-a")
    fed = iter(["bad-1", "bad-2", "bad-3"])
    seen_errors: list[str] = []
    with pytest.raises(WizardAborted) as aborted:
        run_typer_prompt_loop(
            engine,
            prompt_fn=lambda question, default=None: next(fed),
            invalid_echo=seen_errors.append,
            max_attempts=3,
        )
    assert aborted.value.step_id == "b"
    assert len(seen_errors) == 3, "every failed attempt must echo its validation errors"


def test_prompt_loop_reports_whether_anything_was_actually_prompted() -> None:
    engine = WizardEngine(steps=_steps())
    engine.preanswer("a", "1")
    engine.preanswer("b", "one")
    engine.preanswer("c", "3")
    answers, prompted_any = run_typer_prompt_loop(engine, prompt_fn=lambda *a, **k: pytest.fail("must not prompt"))
    assert prompted_any is False
    assert answers == {"a": "1", "b": "one", "c": "3"}

    engine2 = WizardEngine(steps=_steps())
    answers2, prompted_any2 = run_typer_prompt_loop(
        engine2, prompt_fn=lambda question, default=None: {"Question A": "x", "Question B (one, two)": "one", "Question C": "y"}[question]
    )
    assert prompted_any2 is True
    assert answers2 == {"a": "x", "b": "one", "c": "y"}


def test_prompt_loop_strip_behavior_is_opt_out() -> None:
    """`builder init` strips answers; `builder-setup wizard` historically does not."""
    engine = WizardEngine(steps=(WizardStep(id="a", question="Q", free_form=True),))
    answers, _ = run_typer_prompt_loop(engine, prompt_fn=lambda q, default=None: "  padded  ")
    assert answers == {"a": "padded"}
    engine2 = WizardEngine(steps=(WizardStep(id="a", question="Q", free_form=True),))
    answers2, _ = run_typer_prompt_loop(engine2, prompt_fn=lambda q, default=None: "  padded  ", strip_answers=False)
    assert answers2 == {"a": "  padded  "}
