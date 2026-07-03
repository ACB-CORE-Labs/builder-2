import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.platform_status_cli import platform_app
from builder_ii.operator_lane import (
    OPERATOR_LANE_REPORT_KIND,
    run_operator_lane,
    validate_operator_lane_report,
)

runner = CliRunner()


def test_operator_lane_dry_run_composes_evidence(tmp_path: Path) -> None:
    out = tmp_path / "lane"
    report = run_operator_lane(target_name="generic", output_dir=out, dry_run=True)
    errors = validate_operator_lane_report(report)
    assert not errors
    assert report["kind"] == OPERATOR_LANE_REPORT_KIND
    assert report["dry_run"] is True
    assert report["governance"]["model_execution"] == "DISABLED"
    assert (out / "operator-lane-report.json").is_file()
    assert (out / "config-resolution.json").is_file()
    assert (out / "verification-execution-plan.json").is_file()
    assert (out / "handoff.json").is_file()


def test_operator_lane_cli_generic_target(tmp_path: Path) -> None:
    out = tmp_path / "lane-cli"
    result = runner.invoke(
        platform_app,
        ["operator-lane", "--target", "generic", "--output-dir", str(out), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == OPERATOR_LANE_REPORT_KIND
    assert len(data["artifact_refs"]) >= 5