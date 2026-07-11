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


def test_start_readonly_builds_launch_plan_from_manifest_fields(monkeypatch: Any, tmp_path: Path) -> None:
    # Regression test for MockPlan removal: the named GooseReadonlyLaunchPlan must carry the
    # manifest's actual target/agent-profile names through to GooseRuntimeHarness, not just the
    # hardcoded defaults a throwaway mock happened to use.
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    captured: dict[str, Any] = {}

    class _RecordingHarness:
        def __init__(self, settings: Any, plan: Any, target_root: Any) -> None:
            captured["plan"] = plan
            self._proc = None

        def launch_readonly(self) -> dict[str, Any]:
            return {"session_id": "goose_plan", "digest": "b" * 64}

        def close(self, digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
            return (
                {"session_id": "goose_plan", "kind": "builder_ii.goose_close_receipt"},
                {"valid": True, "mutations_detected": []},
            )

    monkeypatch.setattr(goose_cli, "GooseRuntimeHarness", _RecordingHarness)

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "kind": "builder_ii.goose_session_manifest",
                "schema_version": 1,
                "target": {"name": "core", "repo": ".", "description": "test"},
                "agent_profile": {"name": "reviewer", "description": "test", "authority": "user"},
                "task": "readonly session",
                "requested_runtime_mode": "read_only",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(goose_app, ["start-readonly", str(manifest)])

    assert result.exit_code == 0, result.output
    assert captured["plan"].target_name == "core"
    assert captured["plan"].agent_profile == "reviewer"


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
    # interruption recovery guidance for a forcefully-detached session; no fabricated postflight
    assert "manually" in result.output.lower()
    assert "cannot reconstruct" in result.output.lower()


def test_close_readonly_reports_existing_close_receipt_when_already_closed(monkeypatch: Any, tmp_path: Path) -> None:
    # A session that start-readonly already closed normally has a real close receipt on disk;
    # close-readonly must surface it instead of printing the same detached-session guidance.
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    receipts_dir = tmp_path / ".builder" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (receipts_dir / "goose_4_launch.json").write_text(json.dumps({"session_id": "goose_4"}), encoding="utf-8")
    (receipts_dir / "goose_4_close.json").write_text(
        json.dumps({"session_id": "goose_4", "kind": "builder_ii.goose_close_receipt", "exit_code": 0}),
        encoding="utf-8",
    )

    result = runner.invoke(goose_app, ["close-readonly", "goose_4"])

    assert result.exit_code == 0, result.output
    assert "already closed" in result.output.lower()
    assert "goose_4_close.json" in result.output


def test_close_readonly_receipt_path_survives_a_path_longer_than_the_console(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """The close-receipt path must render intact even when it exceeds the console width.

    Rich word-wraps at the console width (80 when stdout is not a terminal), and a filesystem
    path is a single unbreakable token, so the default renderer splits it *mid-filename*:
    `.../receipts/g\\noose_4_close.json`. Whether that happened depended on how long the host's
    temp directory was: it passed on a short `tmp_path` and failed on CI's
    `/tmp/pytest-of-root/...`. That host-dependence is precisely what makes a locally-green
    battery worthless as evidence, so the sibling test above is not enough -- it only fails on
    hosts with long temp paths.

    This one forces the condition through the real CLI on ANY host by nesting the target root
    deep enough that the receipt path must exceed the console width. Without `soft_wrap=True` at
    the print site it fails everywhere; with it, it passes everywhere.
    """
    deep_root = tmp_path / ("nested_" * 8) / ("deeper_" * 8)
    deep_root.mkdir(parents=True)
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(deep_root))

    receipts_dir = deep_root / ".builder" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    (receipts_dir / "goose_4_launch.json").write_text(json.dumps({"session_id": "goose_4"}), encoding="utf-8")
    close_path = receipts_dir / "goose_4_close.json"
    close_path.write_text(
        json.dumps({"session_id": "goose_4", "kind": "builder_ii.goose_close_receipt", "exit_code": 0}),
        encoding="utf-8",
    )
    assert len(str(close_path)) > 80, "fixture must exceed the non-tty console width to have teeth"

    result = runner.invoke(goose_app, ["close-readonly", "goose_4"])

    assert result.exit_code == 0, result.output
    # The filename must not be broken across lines, and the whole path must be recoverable.
    assert "goose_4_close.json" in result.output
    assert str(close_path) in result.output
