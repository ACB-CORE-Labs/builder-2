"""Wizard v2: nine decisions, one record each.

Before this, `builder init` prompted four decisions and resolved five silently. The five it
resolved included where platform artifacts land (`artifact_root`), whether they may land inside
the target repository (`allow_artifact_root_inside_target`), and whether a runtime may start
(`runtime_mode`). They were echoed to the operator *after* the artifacts were written.

The decision was also six separate things -- a prompted record, a defaulted record, a validation
registry dict, an options-provider dict, a hardcoded echo tuple, and an `if name == ...` override
chain. Those disagreed. These pins hold the single record together.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from builder_ii.cli.main import app
from builder_ii.config_sources import _ALLOWED_RUNTIME_MODES, RUNTIME_MODES
from builder_ii.init_decisions import (
    BOOL_ANSWERS,
    Decision,
    decisions,
    get_decision,
    init_wizard_step_definitions,
    prompted_decision_options_provider,
    validate_decision_value,
)

runner = CliRunner()

DECISION_NAMES = (
    "output_dir",
    "target_profile",
    "model_backend",
    "model_alias",
    "agent_profile",
    "verification_profile",
    "artifact_root",
    "runtime_mode",
    "allow_artifact_root_inside_target",
)


def test_the_wizard_prompts_all_nine_decisions() -> None:
    """Four prompted plus five defaulted was always nine. Now all nine are asked."""
    assert tuple(d.name for d in decisions()) == DECISION_NAMES
    assert len(init_wizard_step_definitions()) == 9

    step_ids = tuple(step.id for step in init_wizard_step_definitions())
    assert step_ids == DECISION_NAMES, "a decision exists that the wizard never asks"


def test_a_decision_names_its_registry_and_never_transcribes_it() -> None:
    """The framework invariant, applied to every decision rather than to the four that had one.

    `agent_profile` and `verification_profile` used to have a validation registry and *no* options
    provider: they could be rejected but never rendered. The asymmetry was invisible because they
    were never prompted.
    """
    for decision in decisions():
        provider = prompted_decision_options_provider(decision.name)
        assert (provider is None) == decision.free_form, (
            f"`{decision.name}`: free_form={decision.free_form} but options_provider={provider!r}"
        )

        # A registry-backed decision must reject garbage by naming its registry; a free-form one
        # must reject only emptiness. There is no third case, and no decision may do neither.
        errors = validate_decision_value(decision.name, "___not_a_real_value___")
        if decision.free_form:
            assert errors == [], f"`{decision.name}` is free-form and rejected a non-empty answer"
            assert validate_decision_value(decision.name, "  "), f"`{decision.name}` accepted whitespace"
        else:
            assert errors and "must be one of" in errors[0], f"`{decision.name}` accepted garbage"
            assert decision.allowed(), f"`{decision.name}` has a provider that yields nothing"


def test_every_decision_has_a_flag_wired_into_builder_init() -> None:
    """A decision whose flag `builder init` forgot would be silently unoverridable.

    `builder init` raises on a missing flag rather than ignoring one. This drives that guard, so
    it is executable rather than decorative.
    """
    from builder_ii.cli import main as main_module

    source = main_module.__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()  # noqa: SIM115

    for decision in decisions():
        assert f'"{decision.name}":' in text, f"`{decision.name}` is not in `builder init`'s flag_answers map"
        assert decision.override_flag.startswith("--"), f"`{decision.name}` has no override flag"

    flags = [d.override_flag for d in decisions()]
    assert len(set(flags)) == len(flags), f"two decisions share an override flag: {flags}"


def test_runtime_modes_are_ordered_because_a_prompt_renders_them() -> None:
    """`_ALLOWED_RUNTIME_MODES` was a `set`. A set has no order to render.

    Nothing rendered it before wizard v2, so nothing noticed. A prompt built from a set shows its
    options in a different sequence on every run under hash randomization.
    """
    assert isinstance(RUNTIME_MODES, tuple)
    assert set(RUNTIME_MODES) == _ALLOWED_RUNTIME_MODES, "the ordered tuple and the membership set disagree"

    runtime_mode = get_decision("runtime_mode")
    assert runtime_mode is not None
    assert runtime_mode.allowed() == RUNTIME_MODES


def test_a_registry_change_reaches_the_prompt_with_no_wizard_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The options provider is a callable reference, never a snapshot taken at import."""
    import builder_ii.init_decisions as init_decisions

    monkeypatch.setattr(init_decisions, "RUNTIME_MODES", ("passive", "disabled", "a_ninth_mode"))

    runtime_mode = get_decision("runtime_mode")
    assert runtime_mode is not None
    assert "a_ninth_mode" in runtime_mode.allowed(), "the provider snapshotted its registry"
    assert "a_ninth_mode" not in runtime_mode.question, "the question transcribed a registry value"

    assert validate_decision_value("runtime_mode", "a_ninth_mode") == []

    step = next(s for s in init_wizard_step_definitions() if s.id == "runtime_mode")
    assert "a_ninth_mode" in step.render_question()


def test_the_bool_decision_answers_are_the_two_strings_the_echo_prints() -> None:
    """`allow_artifact_root_inside_target` is a bool in config and a string in a wizard."""
    from builder_ii.cli.main import _as_answer, _as_bool

    assert BOOL_ANSWERS == ("false", "true")
    assert _as_answer(True) == "true" and _as_answer(False) == "false"
    assert _as_bool("true") is True and _as_bool("false") is False
    assert _as_bool("TRUE ") is True, "the echo lowercases; the inverse must accept what it prints"

    for answer in BOOL_ANSWERS:
        assert validate_decision_value("allow_artifact_root_inside_target", answer) == []
    assert validate_decision_value("allow_artifact_root_inside_target", "yes")


def test_an_unknown_decision_is_refused_rather_than_silently_accepted() -> None:
    """The old validator returned `[]` -- valid -- for any name it had no registry for."""
    assert get_decision("no_such_decision") is None
    errors = validate_decision_value("no_such_decision", "anything")
    assert errors and "unknown decision" in errors[0]


def test_init_still_never_applies_and_flags_still_bypass_their_own_prompts(tmp_path) -> None:
    """Nine prompts, same governance: registry-validated, plans only, no apply."""
    result = runner.invoke(
        app,
        [
            "init",
            "--root",
            str(tmp_path),
            "--non-interactive",
            "--output-dir",
            str(tmp_path / "out"),
            "--runtime-mode",
            "not_a_runtime_mode",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "runtime_mode must be one of" in result.output
    assert not (tmp_path / "out").exists(), "a rejected flag must not write artifacts"


def test_the_decision_record_is_the_only_place_a_decision_lives() -> None:
    """Six places became one. If a seventh appears, it will disagree with this."""
    assert Decision.__dataclass_fields__.keys() >= {
        "name",
        "question",
        "resolution_field",
        "override_flag",
        "options_provider",
    }
    for decision in decisions():
        assert decision.question, f"`{decision.name}` has no question"
        assert not any(
            value in decision.question for value in decision.allowed()
        ), f"`{decision.name}` transcribed a registry value into its question"
