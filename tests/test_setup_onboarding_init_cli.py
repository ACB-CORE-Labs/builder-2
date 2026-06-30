from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.onboarding_intent import validate_onboarding_intent_report_file
from builder_ii.setup_cli import setup_app
from builder_ii.setup_overlay import validate_setup_overlay_plan_file
from builder_ii.setup_plan import validate_setup_plan_file
from builder_ii.setup_rollback import validate_setup_rollback_snapshot_file


runner = CliRunner()


def test_init_emits_all_artifacts_and_validates(tmp_path: Path):
    out_dir = tmp_path / "init-artifacts"
    result = runner.invoke(setup_app, ["init", "--output-dir", str(out_dir), "--root", str(tmp_path)])
    assert result.exit_code == 0, f"init failed: {result.output}"

    plan_path = out_dir / "setup-plan.json"
    overlay_path = out_dir / "setup-overlay.json"
    snapshot_path = out_dir / "setup-rollback-snapshot.json"
    intent_path = out_dir / "onboarding-intent.json"
    receipt_path = out_dir / "setup-receipt.json"

    assert plan_path.exists()
    assert overlay_path.exists()
    assert snapshot_path.exists()
    assert intent_path.exists()
    assert not receipt_path.exists(), "init must not write setup-receipt.json"

    assert validate_setup_plan_file(plan_path) == []
    assert validate_setup_overlay_plan_file(overlay_path) == []
    assert validate_setup_rollback_snapshot_file(snapshot_path) == []
    assert validate_onboarding_intent_report_file(intent_path) == []

    assert "Exact next commands:" in result.output
    assert "builder-setup apply " in result.output
    assert "builder-setup validate-receipt " in result.output


def test_init_rejects_apply_flag(tmp_path: Path):
    out_dir = tmp_path / "init-apply-fail"
    result = runner.invoke(setup_app, ["init", "--output-dir", str(out_dir), "--root", str(tmp_path), "--apply"])
    assert result.exit_code != 0
    assert not (out_dir / "setup-receipt.json").exists()
