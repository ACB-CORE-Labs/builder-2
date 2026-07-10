"""Characterization pins for the two interactive onboarding wizards (Ladder 5 PR-1).

Written BEFORE the wizard-framework extraction and run against unmodified `main`
first. `interactive setup wizard` is OPERATIONALLY_VERIFIED in
`platform_completion_audit.py`, and a refactor that changes observable behavior
invalidates that evidence WITHOUT touching the matrix -- no pinned truth test
would notice. This suite is the evidence that the OV row survives the
extraction: exact prompt order, exact prompt text, exact defaults, the
accept/reject boundary, and the emitted artifact set, for both wizards.

History these pins carry:

- PR-1 pinned `builder-setup wizard`'s prompts verbatim INCLUDING their defect: a
  hard-coded 3-of-8 subset of the backend registry, with nothing validated at the
  prompt. PR-2 fixed exactly that, and the lie-pinning tests failed in the designed
  direction and were updated with it: the backend needle is now composed from the
  live registry, and garbage is refused AT the prompt (three attempts, exit 2, no
  artifacts) instead of surfacing late as an invalid artifact with exit 1.
- `tests/test_setup_onboarding_wizard_cli.py` drives the wizard with positional
  stdin, so nothing asserted prompt ORDER before this file: reorder the steps and
  that test still passed while answering the wrong questions with the wrong
  values. The order pins below (and the order pin added there by PR-2) close that.
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

# The four `builder-setup wizard` prompts as the operator sees them, including typer's
# rendered default. Since PR-2 the profile and backend lines are RENDERED from the live
# registries at prompt time, so their needles are composed from those registries here: a
# registry change updates prompt and pin together, and a transcribed subset is
# unrepresentable. The alias question deliberately renders none of its 50 registry
# entries -- see setup_wizard_step_definitions' presentation decision.
SETUP_WIZARD_PROMPTS = (
    "Enter output directory for onboarding artifacts [.builder/setup-artifacts]:",
    f"Select target profile ({', '.join(target_names())}) [generic]:",
    f"Select local model backend ({', '.join(BACKENDS)}) [rapid-mlx]:",
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


def test_setup_wizard_offers_and_accepts_every_registry_backend(wizard_env: Path) -> None:
    """PR-1 pinned the lie's acceptance half: `openai` was accepted while the prompt text
    never named it. PR-2 closes the gap from the other side -- every registry backend is
    now OFFERED (rendered into the prompt from the registry) and accepted. If this starts
    failing, a backend was dropped from the registry or prompt-time validation grew
    stricter than the registry -- both are behavior changes to an OPERATIONALLY_VERIFIED
    surface."""
    assert "openai" in BACKENDS
    assert "openai" in SETUP_WIZARD_PROMPTS[2], "PR-2 renders the full backend registry into the prompt"
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(
        setup_app, ["wizard", "--root", str(wizard_env)], input=f"{out_dir}\ngeneric\nopenai\nphi-reasoning\n"
    )
    assert result.exit_code == 0, result.output
    intent = json.loads((out_dir / "onboarding-intent.json").read_text(encoding="utf-8"))
    assert "openai" in json.dumps(intent)


def test_setup_wizard_refuses_garbage_at_the_prompt_and_reprompts(wizard_env: Path) -> None:
    """PR-2's rejection boundary: garbage never reaches the pipeline. The prompt itself
    refuses (echoing the full registry), re-asks, and accepts a corrected answer -- this is
    the prompt-time refusal, not the artifact's late `"valid": false`, which PR-1 pinned
    and PR-2 removed."""
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(
        setup_app,
        ["wizard", "--root", str(wizard_env)],
        input=f"{out_dir}\ngeneric\nnot-a-backend\nopenai\nphi-reasoning\n",
    )
    assert result.exit_code == 0, result.output
    assert "invalid answer" in result.output
    assert "model_backend must be one of" in result.output
    assert result.output.count("Select local model backend") == 2, "one refusal, one re-ask"
    assert '"valid": false' not in result.output
    intent = json.loads((out_dir / "onboarding-intent.json").read_text(encoding="utf-8"))
    assert "openai" in json.dumps(intent)


def test_setup_wizard_aborts_after_three_invalid_answers_without_writing(wizard_env: Path) -> None:
    """Exhausting the three attempts fails closed with exit 2 and zero artifacts --
    mirroring `builder init`'s boundary exactly. Before PR-2 the same garbage produced
    exit 1 AFTER running the pipeline."""
    out_dir = wizard_env / "wizard-out"
    result = runner.invoke(
        setup_app,
        ["wizard", "--root", str(wizard_env)],
        input=f"{out_dir}\ngeneric\nbad-one\nbad-two\nbad-three\n",
    )
    assert result.exit_code == 2, result.output
    assert "no valid answer after 3 attempts" in result.output
    assert '"valid": false' not in result.output
    assert not out_dir.exists(), "a refused wizard run must not leave artifacts behind"


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
    without edits -- that property is what the framework extraction must preserve.

    Wizard v2 prompts all nine decisions, so all nine are checked. The five that used to be
    resolved silently -- agent profile, verification profile, artifact root, runtime mode, and
    whether the artifact root may sit inside the target repository -- now render the same way.
    """
    from builder_ii.agent_profiles import agent_profile_names
    from builder_ii.config_sources import RUNTIME_MODES
    from builder_ii.init_decisions import BOOL_ANSWERS, decisions
    from builder_ii.verification_profiles import verification_profiles

    out_dir = wizard_env / "init-out"
    # One answer per decision; an empty line accepts the rendered default.
    answers = f"{out_dir}\n" + "\n" * len(decisions())
    result = runner.invoke(app, ["init", "--root", str(wizard_env)], input=answers)
    assert result.exit_code == 0, result.output

    verification_names = tuple(p.name for p in verification_profiles())
    _assert_appears_in_order_exactly_once(
        result.output,
        (
            "Output directory for onboarding artifacts [.builder/setup-artifacts]:",
            f"Target profile ({', '.join(target_names())})",
            f"Local model backend ({', '.join(BACKENDS)})",
            f"Primary model alias ({', '.join(MODEL_ALIASES)})",
            f"Agent profile ({', '.join(agent_profile_names())})",
            f"Verification profile ({', '.join(verification_names)})",
            "Platform artifact root",
            f"Runtime mode ({', '.join(RUNTIME_MODES)})",
            f"Allow the artifact root inside the target repository ({', '.join(BOOL_ANSWERS)})",
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
            # Wizard v2 prompts all nine decisions. This pin is about the artifact set, not the
            # prompt sequence, so it takes the resolved defaults for the five it does not name.
            "--non-interactive",
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
