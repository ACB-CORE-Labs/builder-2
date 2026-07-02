from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli import app


runner = CliRunner()


def _env(builder_dir: Path) -> dict[str, str]:
    return {"BUILDER_DIR": str(builder_dir)}


def test_readonly_tui_empty_status_commands_exit_zero(tmp_path: Path) -> None:
    commands = [
        ["hitl", "status"],
        ["profile", "status"],
        ["model", "routing", "show"],
        ["model", "registry", "show"],
        ["promote", "status"],
        ["postflight", "status"],
        ["goose", "status"],
    ]
    for command in commands:
        result = runner.invoke(app, command, env=_env(tmp_path))
        assert result.exit_code == 0, (command, result.output)
        assert "Traceback" not in result.output


def test_readonly_tui_invalid_json_fails_before_rendering(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    result = runner.invoke(app, ["goose", "status"], env=_env(tmp_path))

    assert result.exit_code == 1
    assert "invalid JSON artifact" in result.output
    assert "broken.json" in result.output
    assert "Traceback" not in result.output


def test_readonly_tui_explicit_missing_id_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["postflight", "record", "missing-record"], env=_env(tmp_path))

    assert result.exit_code == 1
    assert "No execution_postflight_record artifacts found" in result.output
    assert "Traceback" not in result.output


def test_readonly_tui_valid_postflight_status_passes(tmp_path: Path) -> None:
    postflight = {
        "kind": "builder_ii.execution_postflight_record",
        "postflight_state": "RUN_COMPLETE",
        "target": {"name": "demo"},
        "performed_actions": ["captured bounded output"],
    }
    verification = {
        "kind": "builder_ii.execution_verification_record",
        "verification_state": "PASS",
        "target": {"name": "demo"},
        "verification_summary": "bounded verification passed",
        "evidence_refs": ["sha256:demo"],
    }
    (tmp_path / "execution_postflight_record.json").write_text(json.dumps(postflight), encoding="utf-8")
    (tmp_path / "execution_verification_record.json").write_text(json.dumps(verification), encoding="utf-8")

    result = runner.invoke(app, ["postflight", "status"], env=_env(tmp_path))

    assert result.exit_code == 0, result.output
    assert "RUN_COMPLETE" in result.output
    assert "PASS" in result.output
    assert "Traceback" not in result.output


def test_readonly_tui_goose_hint_uses_real_artifact_cli(tmp_path: Path) -> None:
    result = runner.invoke(app, ["goose", "status"], env=_env(tmp_path))

    assert result.exit_code == 0
    assert "builder-goose manifest" in result.output
    assert "builder goose init" not in result.output
