import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.platform_status_cli import platform_app
from builder_ii.r1_closure_report import R1_CLOSURE_REPORT_KIND

runner = CliRunner()


def test_r1_closure_and_validate_r1_closure_cli(tmp_path: Path) -> None:
    output_dir = tmp_path / "r1-closure"
    res = runner.invoke(platform_app, ["r1-closure", "--output-dir", str(output_dir)])
    assert res.exit_code == 0, f"r1-closure failed: {res.output}"

    report_path = output_dir / "r1-closure-report.json"
    assert report_path.exists()

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["kind"] == R1_CLOSURE_REPORT_KIND
    assert data["valid"] is True
    assert data["errors"] == []

    # Verify chain artifacts exist on disk inside output_dir
    assert (output_dir / "config-schema.json").exists()
    assert (output_dir / "config-resolution.json").exists()
    assert (output_dir / "setup-plan.json").exists()
    assert (output_dir / "setup-overlay.json").exists()
    assert (output_dir / "setup-rollback-snapshot.json").exists()
    assert (output_dir / "onboarding-intent.json").exists()

    val_res = runner.invoke(platform_app, ["validate-r1-closure", str(report_path)])
    assert val_res.exit_code == 0, f"validate-r1-closure failed: {val_res.output}"
    val_data = json.loads(val_res.output)
    assert val_data["valid"] is True
    assert val_data["errors"] == []

    # Verify no mutation setup/rollback receipts are written to disk
    assert not (output_dir / "setup-receipt.json").exists()
    assert not (output_dir / "setup-rollback-receipt.json").exists()
