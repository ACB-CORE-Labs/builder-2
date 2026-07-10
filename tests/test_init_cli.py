"""`builder init` unified onboarding orchestrator (plan item 2.2).

init composes the governed onboarding pipeline and never applies: four prompted,
registry-validated wizard decisions; five defaulted decisions echoed with their
override flags; and a rendered follow-up `builder-setup apply` command that
deliberately carries no inline --approve-digest — the process that renders a
digest must not also harvest the confirmation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.cli import app
from builder_ii.onboarding_intent import validate_onboarding_intent_report_file
from builder_ii.setup_overlay import validate_setup_overlay_plan_file
from builder_ii.setup_plan import validate_setup_plan_file
from builder_ii.setup_rollback import validate_setup_rollback_snapshot_file

runner = CliRunner()

# Wizard v2 prompts all nine decisions. These tests name the three they care about and take the
# resolved default for the rest; `--non-interactive` is how a caller says so. `onboarding_mode`
# stays "init" exactly as it did when the same three flags answered all four prompted decisions.
FLAG_ANSWERS = [
    "--non-interactive",
    "--target-profile",
    "generic",
    "--model-backend",
    "mlx-lm",
    "--model-alias",
    "qwen-coder",
]


def _intent(out_dir: Path) -> dict:
    return json.loads((out_dir / "onboarding-intent.json").read_text(encoding="utf-8"))


def _apply_command_line(output: str) -> str:
    lines = [line for line in output.splitlines() if "builder-setup apply " in line]
    assert lines, f"no rendered apply command in output:\n{output}"
    return lines[0]


def test_init_flags_path_emits_artifacts_and_never_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    out_dir = tmp_path / "init-out"
    result = runner.invoke(
        app, ["init", "--root", str(tmp_path), "--output-dir", str(out_dir), *FLAG_ANSWERS]
    )
    assert result.exit_code == 0, result.output

    assert validate_setup_plan_file(out_dir / "setup-plan.json") == []
    assert validate_setup_overlay_plan_file(out_dir / "setup-overlay.json") == []
    assert validate_setup_rollback_snapshot_file(out_dir / "setup-rollback-snapshot.json") == []
    assert validate_onboarding_intent_report_file(out_dir / "onboarding-intent.json") == []
    assert not (out_dir / "setup-receipt.json").exists(), "init must never apply or write a receipt"

    assert "Selected decisions:" in result.output
    assert "target_profile: generic" in result.output

    # Wizard v2: one echo block, all nine decisions, each naming the flag that overrides it. There
    # is no longer a second "Defaulted decisions" section, because no decision is defaulted behind
    # the operator's back -- `--non-interactive` is how this test asks for the defaults out loud.
    from builder_ii.init_decisions import decisions

    for decision in decisions():
        assert f"{decision.name}:" in result.output, f"decision {decision.name} is not echoed"
        assert decision.override_flag in result.output, f"decision must echo its override flag {decision.override_flag}"
    assert "Defaulted decisions" not in result.output
    assert "init never applies" in result.output
    # All answers came from flags: no wizard prompt happened, so mode stays "init".
    assert _intent(out_dir)["onboarding_mode"] == "init"


def test_init_renders_apply_command_without_inline_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    out_dir = tmp_path / "init-out"
    result = runner.invoke(
        app, ["init", "--root", str(tmp_path), "--output-dir", str(out_dir), *FLAG_ANSWERS]
    )
    assert result.exit_code == 0, result.output

    overlay = json.loads((out_dir / "setup-overlay.json").read_text(encoding="utf-8"))
    apply_line = _apply_command_line(result.output)
    assert "--approve-digest" not in apply_line
    assert overlay["overlay_plan_digest"] not in apply_line
    # The digest itself is still shown for review, just never inline in the apply command.
    assert overlay["overlay_plan_digest"] in result.output
    assert "digest-prefix" in result.output or "4-character prefix" in result.output


def test_init_prompts_reprompt_on_invalid_answer_and_record_wizard_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    out_dir = tmp_path / "wizard-out"
    # output_dir, a rejected target profile, then the accepted answers, then an empty line for each
    # of the five decisions wizard v2 promoted from silently-defaulted to prompted.
    inputs = "\n".join([str(out_dir), "not-a-profile", "generic", "mlx-lm", "qwen-coder"]) + "\n" + "\n" * 5
    result = runner.invoke(app, ["init", "--root", str(tmp_path)], input=inputs)
    assert result.exit_code == 0, result.output
    assert "invalid answer" in result.output
    assert validate_onboarding_intent_report_file(out_dir / "onboarding-intent.json") == []
    assert _intent(out_dir)["onboarding_mode"] == "wizard"


def test_init_rejects_invalid_flag_answer_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    out_dir = tmp_path / "invalid-out"
    result = runner.invoke(
        app,
        ["init", "--root", str(tmp_path), "--output-dir", str(out_dir), "--model-backend", "bogus-backend"],
    )
    assert result.exit_code == 2
    assert "invalid decision" in result.output
    assert not out_dir.exists(), "invalid registry answer must fail closed before any artifact write"


def test_init_aborts_after_three_invalid_interactive_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    out_dir = tmp_path / "abort-out"
    inputs = "\n".join([str(out_dir), "bad-one", "bad-two", "bad-three"]) + "\n"
    result = runner.invoke(app, ["init", "--root", str(tmp_path)], input=inputs)
    assert result.exit_code == 2
    assert "no valid answer after 3 attempts" in result.output
    assert not out_dir.exists()


def test_init_non_interactive_uses_documented_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    monkeypatch.chdir(tmp_path)  # DEFAULT_INIT_OUTPUT_DIR is CWD-relative
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--non-interactive"])
    assert result.exit_code == 0, result.output
    out_dir = tmp_path / ".builder" / "setup-artifacts"
    assert validate_onboarding_intent_report_file(out_dir / "onboarding-intent.json") == []
    assert not (out_dir / "setup-receipt.json").exists()
    # Defaults are taken without prompting, so mode stays "init".
    assert _intent(out_dir)["onboarding_mode"] == "init"


def test_the_authority_record_describes_the_output_builder_init_actually_prints(tmp_path) -> None:
    """`output_behavior` is a claim about behaviour, and nothing was checking it against behaviour.

    Wizard v2 merged the "Defaulted decisions" section into one "Selected decisions" block -- and a
    test in this file asserts the old section is gone -- while `builder init`'s authority record went
    on promising "selected decisions, defaulted decisions with override flags". `runtime_boundary`
    four lines above it was updated in the same commit; `output_behavior` was not.
    """
    from builder_ii.command_authority import get_command_record

    record = get_command_record("builder init")
    assert record is not None

    root = tmp_path / "repo"
    root.mkdir()
    result = runner.invoke(
        app,
        ["init", "--root", str(root), "--output-dir", str(root / "out"), "--non-interactive"],
    )
    assert result.exit_code == 0, result.output

    assert "Selected decisions" in result.output
    assert "Defaulted decisions" not in result.output
    assert "defaulted decisions" not in record.output_behavior.lower(), record.output_behavior
    for promised in ("artifact paths", "digests", "apply command"):
        assert promised in record.output_behavior.lower(), promised
