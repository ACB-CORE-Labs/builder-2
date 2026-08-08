"""CLI-level governance tests for ``builder-goose start-governed``.

The interactive lane is only governed when the builder-II recipe is actually present and
selected as Goose's sole extension.  These tests therefore treat a missing recipe as a
pre-spawn refusal, not as an optional configuration detail.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

import builder_ii.cli.goose_cli as goose_cli
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.cli.goose_cli import goose_app
from builder_ii.governance.ledger.event_ledger import load_event_records, replay_events

runner = CliRunner()


def _write_manifest(path: Path, *, mode: str = "read_only") -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.goose_session_manifest",
                "schema_version": 1,
                "target": {"name": "builder", "repo": ".", "description": "test"},
                "agent_profile": {
                    "name": "patch_planner",
                    "description": "test",
                    "authority": "user",
                },
                "task": "governed session",
                "requested_runtime_mode": mode,
            }
        ),
        encoding="utf-8",
    )


def _settings_at(tmp_path: Path) -> MagicMock:
    settings = MagicMock()
    settings.project_root = tmp_path
    return settings


def _write_governed_recipe(tmp_path: Path) -> Path:
    directory = tmp_path / "recipes"
    directory.mkdir(exist_ok=True)
    path = directory / GooseRuntimeHarness.GOVERNED_RECIPE_NAME
    path.write_text("version: '1.0.0'\nextensions: []\n", encoding="utf-8")
    return path


# --- Fail-closed gates: nothing is spawned -------------------------------------------------


def test_start_governed_requires_an_operator_supplied_manifest() -> None:
    result = runner.invoke(goose_app, ["start-governed"])
    assert result.exit_code != 0


def test_start_governed_refuses_a_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(goose_app, ["start-governed", str(tmp_path / "nope.json")])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_start_governed_refuses_unreadable_manifest_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    result = runner.invoke(goose_app, ["start-governed", str(bad)])
    assert result.exit_code == 1
    assert "invalid manifest json" in result.output.lower()


def test_start_governed_refuses_a_non_read_only_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, mode="autonomous")
    result = runner.invoke(goose_app, ["start-governed", str(manifest)])
    assert result.exit_code == 1
    assert "read_only" in result.output.lower()


def test_start_governed_refuses_when_command_authority_denies(
    monkeypatch: Any, tmp_path: Path
) -> None:
    from builder_ii.governance.authority.policy_evaluator import CommandAuthorityError

    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)
    spawned: list[Any] = []
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    monkeypatch.setattr(
        goose_cli,
        "enforce_command_authority",
        lambda *a, **k: (_ for _ in ()).throw(CommandAuthorityError("denied for test")),
    )
    monkeypatch.setattr(
        "builder_ii.goose_runtime_harness.find_goose_binary",
        lambda: spawned.append("resolved") or "/fake/goose",
    )

    result = runner.invoke(goose_app, ["start-governed", str(manifest)])
    assert result.exit_code != 0
    assert spawned == []


def test_start_governed_refuses_a_missing_governed_recipe_before_spawn(
    monkeypatch: Any, tmp_path: Path
) -> None:
    launches = _install_launch_mocks(monkeypatch, tmp_path, create_recipe=False)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-governed", str(manifest)])

    assert result.exit_code == 1
    assert "recipe not found" in result.output.lower()
    assert launches == []


# --- Launch path (no real Goose) -----------------------------------------------------------


def _install_launch_mocks(
    monkeypatch: Any,
    tmp_path: Path,
    *,
    mutate_file: str | None = None,
    create_recipe: bool = True,
) -> list[Any]:
    monkeypatch.setattr(goose_cli, "load_settings", lambda *a, **k: _settings_at(tmp_path))
    monkeypatch.setattr(
        "builder_ii.goose_runtime_harness.find_goose_binary", lambda: "/fake/goose"
    )
    monkeypatch.setattr("builder_ii.goose_runtime_harness.time.time", lambda: 4242.0)
    if create_recipe:
        _write_governed_recipe(tmp_path)

    class FakeProc:
        def __init__(self, args: Any, cwd: Any, env: Any, *, is_launch: bool):
            self.pid = 4242
            self.returncode = 0
            self.args = args
            self.cwd = cwd
            self.env = env
            if mutate_file and is_launch:
                (Path(cwd) / mutate_file).write_text("mutated", encoding="utf-8")

        def poll(self) -> int | None:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            pass

        def communicate(self, input: Any = None, timeout: float | None = None) -> tuple[Any, Any]:
            return (None, None)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    import subprocess

    real_popen = subprocess.Popen
    launches: list[Any] = []

    def fake_popen(*args: Any, **kwargs: Any) -> Any:
        cmd_args = args[0] if args else kwargs.get("args")
        if isinstance(cmd_args, list) and cmd_args and "/fake/goose" in str(cmd_args[0]):
            is_launch = "export" not in cmd_args
            proc = FakeProc(
                cmd_args, kwargs.get("cwd"), kwargs.get("env"), is_launch=is_launch
            )
            if is_launch:
                launches.append(proc)
            return proc
        return real_popen(*args, **kwargs)

    monkeypatch.setattr("builder_ii.goose_runtime_harness.subprocess.Popen", fake_popen)
    return launches


def test_start_governed_launches_with_the_governed_recipe_and_no_builtins(
    monkeypatch: Any, tmp_path: Path
) -> None:
    launches = _install_launch_mocks(monkeypatch, tmp_path)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-governed", str(manifest)])

    assert result.exit_code == 0, result.output
    assert len(launches) == 1
    argv = launches[0].args
    assert "--with-builtin" in argv and argv[argv.index("--with-builtin") + 1] == ""
    assert GooseRuntimeHarness.GOVERNED_RECIPE_NAME in argv[argv.index("--recipe") + 1]
    assert launches[0].env["BUILDER_MCP_SESSION_ID"] == "goose_4242"


def test_start_governed_writes_launch_and_close_receipts(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _install_launch_mocks(monkeypatch, tmp_path)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-governed", str(manifest)])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".builder" / "receipts" / "goose_4242_launch.json").exists()
    assert (tmp_path / ".builder" / "receipts" / "goose_4242_close.json").exists()


def test_start_governed_chains_start_and_close_onto_the_session_ledger(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _install_launch_mocks(monkeypatch, tmp_path)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-governed", str(manifest)])
    assert result.exit_code == 0, result.output

    events_dir = tmp_path / ".builder" / "sessions" / "goose_4242" / "events"
    records = load_event_records(events_dir)
    types = [event.get("event_type") for event, _ in records]
    assert types == ["goose_readonly_started", "goose_readonly_closed"]
    assert [event["sequence"] for event, _ in records] == [1, 2]
    assert records[0][0]["previous_event_sha256"] is None
    assert records[1][0]["previous_event_sha256"] is not None
    assert replay_events(records, session_id="goose_4242")["valid"]


def test_start_governed_fails_the_run_when_the_postflight_detects_a_mutation(
    monkeypatch: Any, tmp_path: Path
) -> None:
    (tmp_path / "src").mkdir()
    _install_launch_mocks(monkeypatch, tmp_path, mutate_file="src/touched.py")
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["start-governed", str(manifest)])

    assert result.exit_code == 1
    assert "mutations detected" in result.output.lower()
    assert "src/touched.py" in "".join(result.output.split())
