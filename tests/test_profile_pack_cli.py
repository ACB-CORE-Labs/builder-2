from __future__ import annotations

import json as json_lib
from pathlib import Path

from builder_ii.profile_pack_cli import profile_pack_app
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def test_profile_pack_cli_lifecycle(tmp_path: Path) -> None:
    runner = CliRunner()
    manifest_path = tmp_path / "manifest.json"
    render_path = tmp_path / "render-plan.json"
    dry_run_path = tmp_path / "dry-run.json"
    report_path = tmp_path / "validation-report.json"

    result = runner.invoke(
        profile_pack_app,
        [
            "scaffold",
            "--pack-id",
            "cli-profile-pack",
            "--target",
            "builder",
            "--task",
            "cli lifecycle",
            "--project-root",
            str(ROOT),
            "--output",
            str(manifest_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert manifest_path.exists()
    assert json_lib.loads(manifest_path.read_text(encoding="utf-8"))["kind"] == "builder_ii.profile_pack_manifest"

    result = runner.invoke(
        profile_pack_app,
        ["render", str(manifest_path), "--output", str(render_path)],
    )
    assert result.exit_code == 0, result.output
    assert json_lib.loads(render_path.read_text(encoding="utf-8"))["kind"] == "builder_ii.profile_pack_render_plan"

    result = runner.invoke(
        profile_pack_app,
        ["dry-run", str(manifest_path), "--render-plan", str(render_path), "--output", str(dry_run_path)],
    )
    assert result.exit_code == 0, result.output
    dry_run = json_lib.loads(dry_run_path.read_text(encoding="utf-8"))
    assert dry_run["kind"] == "builder_ii.profile_pack_dry_run"
    assert dry_run["summary"]["verification_status"] == "NOT_RUN"

    result = runner.invoke(
        profile_pack_app,
        ["validate", str(manifest_path), "--output", str(report_path)],
    )
    assert result.exit_code == 0, result.output
    report = json_lib.loads(report_path.read_text(encoding="utf-8"))
    assert report["kind"] == "builder_ii.profile_pack_validation_report"
    assert report["valid"] is True
    assert report["claims"]["executed"] is False
    assert report["claims"]["authorized"] is False
    assert report["claims"]["promoted"] is False


def test_profile_pack_cli_validate_fails_closed(tmp_path: Path) -> None:
    runner = CliRunner()
    bad_path = tmp_path / "bad-manifest.json"
    report_path = tmp_path / "bad-report.json"
    bad_path.write_text(
        json_lib.dumps({"kind": "builder_ii.profile_pack_manifest", "schema_version": 1}),
        encoding="utf-8",
    )

    result = runner.invoke(profile_pack_app, ["validate", str(bad_path), "--output", str(report_path)])

    assert result.exit_code == 1
    assert "Validation error:" in result.output
    report = json_lib.loads(report_path.read_text(encoding="utf-8"))
    assert report["valid"] is False
    assert report["status"] == "invalid"
