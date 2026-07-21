"""`builder-profile-pack wizard`: the scaffold decisions, asked, from the live registry.

`builder-profile-pack scaffold` takes its decisions as flags and nothing else. An operator who did
not already know the target-profile registry had to read the source, because the CLI transcribed it
three times -- as a `set` literal, inside an error message, and inside a `--target` help string --
and never once read `target_names()`.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.profile_pack_cli import profile_pack_app
from builder_ii.governance.authority import get_command_record
from builder_ii.lifecycle.setup.profile_pack_decisions import DECISION_IDS, profile_pack_wizard_steps, validate_target
from builder_ii.lifecycle.setup.target_profiles import target_names

runner = CliRunner()


def test_the_wizard_asks_the_decisions_scaffold_takes_as_flags() -> None:
    assert tuple(step.id for step in profile_pack_wizard_steps()) == DECISION_IDS


def test_the_target_prompt_renders_the_live_registry_and_never_transcribes_it() -> None:
    target = next(step for step in profile_pack_wizard_steps() if step.id == "target")
    assert target.options_provider is not None
    assert target.allowed_values() == tuple(target_names())

    rendered = target.render_question()
    for name in target_names():
        assert name in rendered, f"the prompt must offer {name}"
    assert all(name not in target.question for name in target_names()), "the question transcribed a value"


def test_a_registry_change_reaches_the_prompt_and_the_error_message(monkeypatch) -> None:
    """Both transcriptions are gone: the set literal and the sentence that repeated it."""
    import builder_ii.lifecycle.setup.profile_pack_decisions as decisions

    monkeypatch.setattr(decisions, "target_names", lambda: ("generic", "builder", "core", "a_fourth_profile"))

    target = next(step for step in profile_pack_wizard_steps() if step.id == "target")
    assert "a_fourth_profile" in target.render_question()
    assert validate_target("a_fourth_profile") == []

    errors = validate_target("nonsense")
    assert errors and "a_fourth_profile" in errors[0], "the error message is composed from the registry"


def test_the_wizard_prompts_and_writes_the_same_manifest_scaffold_writes(tmp_path: Path) -> None:
    wizard_out = tmp_path / "wizard.json"
    scaffold_out = tmp_path / "scaffold.json"

    result = runner.invoke(
        profile_pack_app,
        ["wizard", "--project-root", str(Path.cwd())],
        input=f"my-pack\ngeneric\nsome task\n{wizard_out}\n",
    )
    assert result.exit_code == 0, result.output
    assert "Target profile (generic, builder, core)" in result.output

    scaffolded = runner.invoke(
        profile_pack_app,
        ["scaffold", "--pack-id", "my-pack", "--target", "generic", "--task", "some task",
         "--project-root", str(Path.cwd()), "--output", str(scaffold_out)],
    )
    assert scaffolded.exit_code == 0, scaffolded.output

    assert json.loads(wizard_out.read_text()) == json.loads(scaffold_out.read_text()), (
        "the wizard must emit exactly what scaffold emits"
    )


def test_a_rejected_flag_exits_two_and_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "never.json"
    result = runner.invoke(profile_pack_app, ["wizard", "--target", "not_a_profile", "--output", str(out)])
    assert result.exit_code == 2, result.output
    assert "target must be one of" in result.output
    assert not out.exists(), "a rejected flag must not write an artifact"


def test_three_invalid_answers_abort_without_writing(tmp_path: Path) -> None:
    out = tmp_path / "never.json"
    result = runner.invoke(
        profile_pack_app,
        ["wizard", "--pack-id", "p", "--task", "t", "--output", str(out)],
        input="bad\nworse\nworst\n",
    )
    assert result.exit_code == 2, result.output
    assert "aborting without writing artifacts" in result.output
    assert not out.exists()


def test_flags_bypass_exactly_their_own_prompts(tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    result = runner.invoke(
        profile_pack_app,
        ["wizard", "--pack-id", "p", "--target", "core", "--task", "t", "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert "Target profile" not in result.output, "an answered decision must not be prompted"
    assert json.loads(out.read_text())["target_profile"] == "core"


def test_non_interactive_takes_the_defaults(tmp_path: Path) -> None:
    out = tmp_path / "m.json"
    result = runner.invoke(profile_pack_app, ["wizard", "--non-interactive", "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert json.loads(out.read_text())["target_profile"] == "builder"


def test_the_wizard_holds_no_authority_scaffold_does_not() -> None:
    """A new command surface is a new authority claim. This one claims exactly its sibling's."""
    from builder_ii.governance.authority import CAPABILITY_FLAGS

    wizard = get_command_record("builder-profile-pack wizard")
    scaffold = get_command_record("builder-profile-pack scaffold")
    assert wizard is not None and scaffold is not None

    assert not wizard.authority_is_inherited, "the wizard is declared, not a prefix-clone"
    assert wizard.tier == scaffold.tier
    assert wizard.promotion_state == scaffold.promotion_state
    assert wizard.approval_mode == scaffold.approval_mode
    assert [f for f in CAPABILITY_FLAGS if getattr(wizard, f)] == [f for f in CAPABILITY_FLAGS if getattr(scaffold, f)]


def test_the_cli_no_longer_transcribes_the_target_registry() -> None:
    """Three copies: a set literal, an error message, and a `--target` help string."""
    import builder_ii.cli.profile_pack_cli as cli

    source = Path(cli.__file__).read_text(encoding="utf-8")
    assert "_VALID_TARGETS" not in source, "the set literal is gone"
    assert 'help="Target profile: generic, builder, core"' not in source, "the help string is gone"
    assert "must be one of: generic, builder, core" not in source, "the error message is gone"


def test_two_commands_that_share_an_emitter_name_the_same_failures() -> None:
    """A record is a claim about behaviour. `wizard` and `scaffold` run the *same* emitter.

    The equality pin beside this one compares tier, promotion state, approval mode and the eleven
    capability flags -- every field except the prose. So the wizard's newly authored `failure_mode`
    could drop a clause its sibling names for the identical code, and nothing noticed:
    `_emit_manifest` -> `create_profile_pack_manifest` -> `_source_ref` reads a dozen `builder_ii/*.py`
    files under `project_root` and raises when one is absent. `scaffold` says so. The wizard did not.
    """
    scaffold = get_command_record("builder-profile-pack scaffold")
    wizard = get_command_record("builder-profile-pack wizard")
    assert scaffold is not None and wizard is not None

    for phrase in ("source refs", "manifest validation fails"):
        assert phrase in scaffold.failure_mode.lower(), f"this pin is vacuous if scaffold stops saying {phrase!r}"
        assert phrase in wizard.failure_mode.lower(), f"the wizard runs the same code and must say {phrase!r}"


def test_the_named_source_ref_failure_is_a_failure_both_commands_really_have(tmp_path) -> None:
    """Named, and true of both: a project root with no `builder_ii/` source tree fails either one."""
    empty = tmp_path / "no-source-tree"
    empty.mkdir()

    for argv in (
        ["wizard", "--project-root", str(empty), "--non-interactive"],
        ["scaffold", "--project-root", str(empty)],
    ):
        result = runner.invoke(profile_pack_app, argv)
        assert result.exit_code != 0, argv
        assert not list(empty.iterdir()), "no artifact is written when the source refs are missing"
