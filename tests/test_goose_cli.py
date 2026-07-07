"""CLI-level governance tests for `builder-goose start-readonly` / `close-readonly`.

These back the CAPABILITY_PROMOTION.md "Autonomous Goose runtime start" boundary: builder-II
never starts a Goose runtime on its own, and the operator-invoked read-only launch path is
gated by denied-action checks and a no-mutation postflight. Goose is never really spawned here
— the denied-action gates run before any launch, and the launch path replaces GooseRuntimeHarness.

The launch/close tests patch attributes on the *imported* goose_cli module object (via
monkeypatch.setattr on `goose_cli`) rather than by dotted-string target, so they stay correct even
if the root LazyGroup re-imports the CLI module under a fresh object elsewhere in the suite.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

import builder_ii.cli.goose_cli as goose_cli
from builder_ii.cli.goose_cli import goose_app

runner = CliRunner()


def _write_manifest(path: Path, *, mode: str = "read_only") -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.goose_session_manifest",
                "schema_version": 1,
                "target": {"name": "builder", "repo": ".", "description": "test"},
                "agent_profile": {"name": "patch_planner", "description": "test", "authority": "user"},
                "task": "readonly session",
                "requested_runtime_mode": mode,
            }
        ),
        encoding="utf-8",
    )


def _settings_at(tmp_path: Path) -> MagicMock:
    settings = MagicMock()
    settings.project_root = tmp_path
    return settings


# --- No autonomous start / denied-action gates (Goose is never launched) ---


def test_start_readonly_requires_explicit_operator_manifest() -> None:
    # There is no autonomous-start path: the command cannot run without an operator-supplied manifest.
    result = runner.invoke(goose_app, ["start-readonly"])
    assert result.exit_code != 0


def test_start_readonly_rejects_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(goose_app, ["start-readonly", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_start_readonly_rejects_invalid_manifest_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    result = runner.invoke(goose_app, ["start-readonly", str(bad)])
    assert result.exit_code == 1
    assert "invalid manifest json" in result.output.lower()


def test_start_readonly_refuses_non_read_only_manifest(tmp_path: Path) -> None:
    # The core denied-action gate: a manifest that does not request read_only mode is refused
    # before any Goose runtime is launched.
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, mode="autonomous")
    result = runner.invoke(goose_app, ["start-readonly", str(manifest)])
    assert result.exit_code == 1
    assert "read_only" in result.output.lower()


# --- Launch path (GooseRuntimeHarness replaced; no real Goose) ---


def _install_fake_harness(monkeypatch: Any, tmp_path: Path, *, postflight: dict[str, Any], session_id: str) -> MagicMock:
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    harness = MagicMock()
    harness.launch_readonly.return_value = {"session_id": session_id, "digest": "a" * 64}
    harness.close.return_value = (
        {"session_id": session_id, "kind": "builder_ii.goose_close_receipt"},
        postflight,
    )
    monkeypatch.setattr(goose_cli, "GooseRuntimeHarness", lambda *a, **k: harness)
    return harness


def test_start_readonly_launches_and_writes_receipts_when_no_mutation(monkeypatch: Any, tmp_path: Path) -> None:
    harness = _install_fake_harness(
        monkeypatch, tmp_path, postflight={"valid": True, "mutations_detected": []}, session_id="goose_1"
    )
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-readonly", str(manifest)])

    assert result.exit_code == 0, result.output
    harness.launch_readonly.assert_called_once()
    harness.close.assert_called_once_with("a" * 64)
    assert (tmp_path / ".builder" / "receipts" / "goose_1_launch.json").exists()
    assert (tmp_path / ".builder" / "receipts" / "goose_1_close.json").exists()


def test_start_readonly_fails_when_mutation_detected_in_postflight(monkeypatch: Any, tmp_path: Path) -> None:
    _install_fake_harness(
        monkeypatch,
        tmp_path,
        postflight={"valid": False, "mutations_detected": ["src/touched.py"]},
        session_id="goose_2",
    )
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-readonly", str(manifest)])

    assert result.exit_code == 1
    assert "mutations detected" in result.output.lower()
    assert "src/touched.py" in result.output


# --- close-readonly lifecycle / interruption recovery messaging ---


def test_close_readonly_rejects_missing_launch_receipt(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    result = runner.invoke(goose_app, ["close-readonly", "goose_absent"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_close_readonly_reports_lifecycle_when_launch_receipt_present(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    receipt_path = tmp_path / ".builder" / "receipts" / "goose_3_launch.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps({"session_id": "goose_3"}), encoding="utf-8")

    result = runner.invoke(goose_app, ["close-readonly", "goose_3"])

    assert result.exit_code == 0
    # interruption recovery guidance for a forcefully-detached session
    assert "manually" in result.output.lower()
