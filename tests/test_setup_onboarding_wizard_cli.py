from __future__ import annotations

from pathlib import Path

import pytest
from builder_ii.setup_cli import setup_app
from typer.testing import CliRunner

from builder_ii.onboarding_intent import validate_onboarding_intent_report_file

runner = CliRunner()


def test_wizard_emits_artifacts_and_instructions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORE_REPO_PATH", raising=False)
    out_dir = tmp_path / "wizard-out"
    inputs = f"{out_dir}\ngeneric\nrapid-mlx\nphi-reasoning\n"
    result = runner.invoke(setup_app, ["wizard", "--root", str(tmp_path)], input=inputs)
    assert result.exit_code == 0, f"wizard failed: {result.output}"

    # These positional stdin answers are only meaningful if the prompts arrive in this
    # order -- which nothing asserted before Ladder 5: a reordering answered the wrong
    # questions with the wrong values and this test stayed green. Pin the order the
    # answers assume (exact text lives in tests/test_wizard_characterization.py).
    position = -1
    for prompt_prefix in (
        "Enter output directory for onboarding artifacts",
        "Select target profile",
        "Select local model backend",
        "Select primary model alias",
    ):
        found = result.output.find(prompt_prefix)
        assert found != -1, f"missing prompt: {prompt_prefix!r}\n{result.output}"
        assert found > position, f"prompt out of order: {prompt_prefix!r}\n{result.output}"
        position = found

    plan_path = out_dir / "setup-plan.json"
    overlay_path = out_dir / "setup-overlay.json"
    snapshot_path = out_dir / "setup-rollback-snapshot.json"
    intent_path = out_dir / "onboarding-intent.json"
    receipt_path = out_dir / "setup-receipt.json"

    assert plan_path.exists()
    assert overlay_path.exists()
    assert snapshot_path.exists()
    assert intent_path.exists()
    assert not receipt_path.exists(), "wizard must not write setup-receipt.json"

    assert validate_onboarding_intent_report_file(intent_path) == []

    assert "To apply, run the printed builder-setup apply command after reviewing the overlay digest." in result.output
    assert "Exact next commands:" in result.output
    assert "builder-setup apply " in result.output
    assert "builder-setup validate-receipt " in result.output
