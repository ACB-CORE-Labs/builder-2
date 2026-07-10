"""Characterization pins for the two interactive onboarding wizards (Ladder 5 PR-1).

Written BEFORE the wizard-framework extraction and run against unmodified `main`
first. `interactive setup wizard` is OPERATIONALLY_VERIFIED in
`platform_completion_audit.py`, and a refactor that changes observable behavior
invalidates that evidence WITHOUT touching the matrix -- no pinned truth test
would notice. This suite is the evidence that the OV row survives the
extraction: exact prompt order, exact prompt text, exact defaults, the
accept/reject boundary, and the emitted artifact set, for both wizards.

Two of these pins are pins on defects, held open deliberately:

- `builder-setup wizard`'s prompts hard-code a 3-entry subset of the 8-entry
  backend registry and validate nothing at the prompt. PR-1 ports that behavior
  unchanged (one change per commit); PR-2 fixes it and is REQUIRED to update the
  lie-pinning tests here -- failing in that direction is these pins doing their
  job. Do not "fix" a pin below without the behavior change it pins.
- `tests/test_setup_onboarding_wizard_cli.py:18` drives the wizard with
  positional stdin, so nothing asserted prompt ORDER before this file: reorder
  the steps and that test still passes while answering the wrong questions with
  the wrong values. The order pins below close that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from builder_ii.setup_cli import setup_app
from typer.testing import CliRunner

from builder_ii.cli import app
from builder_ii.config import BACKENDS, MODEL_ALIASES
from builder_ii.target_profiles import target_names

runner = CliRunner()

# The four `builder-setup wizard` prompts, verbatim, including typer's rendered
# default. The backend line names 3 of the 8 registry backends: that is the lie
# PR-2 exists to fix, pinned here exactly as the operator sees it today.
SETUP_WIZARD_PROMPTS = (
    "Enter output directory for onboarding artifacts [.builder/setup-artifacts]:",
    "Select target profile (generic, builder, core) [generic]:",
    "Select local model backend (rapid-mlx, mlx-lm, ollama) [rapid-mlx]:",
    "Select primary model alias [phi-reasoning]:",
)

SETUP_WIZARD_ARTIFACTS = (
    "setup-plan.json",
    "setup-overlay.json",
    "setup-rollback-snapshot.json",
    "onboarding-intent.json",
)


def _assert_appears_in_order_exactly_once(output: str, needles: tuple[str, ...]) -> None:
    position = -1
    for needle in needles:
        count = output.count(needle)
        assert count == 1, f"expected exactly one occurrence of {needle!r}, found {count}\n--- output ---\n{output}"
        found = output.find(needle)
        assert found > position, f"prompt out of order: {needle!r}\n--- output ---\n{output}"
        position = found


@pytest.fixture()
def wizard_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fixed environment so prompt defaults are deterministic across hosts."""
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- builder-setup wizard ----------------------------------------------------------------


def test_setup_wizard_prompt_text_order_and_defaults_are_pinned_verbatim(wizard_env: Path) -> None:
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(setup_app, ["wizard", "--root", str(wizard_env)], input=f"{out_dir}\n\n\n\n")
    assert result.exit_code == 0, result.output
    _assert_appears_in_order_exactly_once(result.output, SETUP_WIZARD_PROMPTS)


def test_setup_wizard_default_answers_land_in_the_intent_artifact(wizard_env: Path) -> None:
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(setup_app, ["wizard", "--root", str(wizard_env)], input=f"{out_dir}\n\n\n\n")
    assert result.exit_code == 0, result.output
    intent = json.loads((out_dir / "onboarding-intent.json").read_text(encoding="utf-8"))
    decisions = json.dumps(intent)
    assert "generic" in decisions
    assert "rapid-mlx" in decisions
    assert "phi-reasoning" in decisions
    for name in SETUP_WIZARD_ARTIFACTS:
        assert (out_dir / name).exists(), f"missing artifact: {name}"
    assert not (out_dir / "setup-receipt.json").exists(), "wizard must never apply"


def test_setup_wizard_accepts_a_real_backend_its_prompt_does_not_offer(wizard_env: Path) -> None:
    """The acceptance half of the prompt lie: `openai` is a real registry backend the
    prompt text does not name, and the wizard takes it with exit 0. PR-2 keeps this
    passing (openai becomes an *offered* value); if it ever starts failing, a backend
    was dropped from the registry or prompt-time validation grew stricter than the
    registry -- both are behavior changes to an OPERATIONALLY_VERIFIED surface."""
    assert "openai" in BACKENDS
    assert "openai" not in SETUP_WIZARD_PROMPTS[2]
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(
        setup_app, ["wizard", "--root", str(wizard_env)], input=f"{out_dir}\ngeneric\nopenai\nphi-reasoning\n"
    )
    assert result.exit_code == 0, result.output
    intent = json.loads((out_dir / "onboarding-intent.json").read_text(encoding="utf-8"))
    assert "openai" in json.dumps(intent)


def test_setup_wizard_surfaces_garbage_late_as_an_invalid_artifact_not_a_prompt_refusal(wizard_env: Path) -> None:
    """The rejection half of the defect PR-2 fixes, pinned as it behaves today: garbage
    is NOT refused at the prompt -- every prompt is asked exactly once, the pipeline
    runs, and the failure surfaces afterwards as `"valid": false` with exit 1 and no
    artifacts on disk. PR-2 must flip this to a prompt-time refusal and update this pin;
    failing in that direction is the pin working."""
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(
        setup_app,
        ["wizard", "--root", str(wizard_env)],
        input=f"{out_dir}\ngeneric\nnot-a-backend\nphi-reasoning\n",
    )
    assert result.exit_code == 1, result.output
    _assert_appears_in_order_exactly_once(result.output, SETUP_WIZARD_PROMPTS)
    assert '"valid": false' in result.output
    assert "model_backend must be one of" in result.output
    assert not out_dir.exists(), "an invalid wizard run must not leave artifacts behind"


def test_setup_wizard_flags_bypass_exactly_their_own_prompts(wizard_env: Path) -> None:
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(
        setup_app,
        ["wizard", "--root", str(wizard_env), "--model-backend", "mlx-lm"],
        input=f"{out_dir}\n\n\n",
    )
    assert result.exit_code == 0, result.output
    assert SETUP_WIZARD_PROMPTS[2] not in result.output, "a flag-provided decision must not be prompted"
    _assert_appears_in_order_exactly_once(
        result.output, (SETUP_WIZARD_PROMPTS[0], SETUP_WIZARD_PROMPTS[1], SETUP_WIZARD_PROMPTS[3])
    )


# --- builder init ------------------------------------------------------------------------


def test_init_prompts_render_their_allowed_values_from_the_live_registries(wizard_env: Path) -> None:
    """`builder init` is the wizard that already does it right: its prompt text is
    composed from the live registries at prompt time, so these needles are themselves
    composed from the registries. If a ninth backend is added, this test keeps passing
    without edits -- that property is what the framework extraction must preserve."""
    out_dir = wizard_env / "init-out"
    result = runner.invoke(app, ["init", "--root", str(wizard_env)], input=f"{out_dir}\n\n\n\n")
    assert result.exit_code == 0, result.output
    _assert_appears_in_order_exactly_once(
        result.output,
        (
            "Output directory for onboarding artifacts [.builder/setup-artifacts]:",
            f"Target profile ({', '.join(target_names())})",
            f"Local model backend ({', '.join(BACKENDS)})",
            f"Primary model alias ({', '.join(MODEL_ALIASES)})",
        ),
    )


def test_init_and_setup_wizard_agree_on_the_emitted_artifact_set(wizard_env: Path) -> None:
    init_out = wizard_env / "init-out"
    wizard_out = wizard_env / "wizard-out"
    init_result = runner.invoke(
        app,
        [
            "init",
            "--root",
            str(wizard_env),
            "--output-dir",
            str(init_out),
            "--target-profile",
            "generic",
            "--model-backend",
            "rapid-mlx",
            "--model-alias",
            "phi-reasoning",
        ],
    )
    assert init_result.exit_code == 0, init_result.output
    wizard_result = runner.invoke(setup_app, ["wizard", "--root", str(wizard_env)], input=f"{wizard_out}\n\n\n\n")
    assert wizard_result.exit_code == 0, wizard_result.output
    init_names = sorted(p.name for p in init_out.glob("*.json"))
    wizard_names = sorted(p.name for p in wizard_out.glob("*.json"))
    assert init_names == wizard_names == sorted(SETUP_WIZARD_ARTIFACTS)
