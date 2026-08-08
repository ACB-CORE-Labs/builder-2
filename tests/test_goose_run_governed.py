"""Headless governed Goose runtime tests (ADR-0009 lane B).

The fake Goose is a real executable so streaming, byte bounds, child environment, exit
codes, and signal behavior are exercised rather than mocked away.  No host Goose binary
is required.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.cli.goose_cli import goose_app
from builder_ii.governance.ledger.event_ledger import load_event_records, replay_events

runner = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _no_repo_pollution() -> Any:
    sessions = _REPO_ROOT / ".builder" / "sessions"
    before = {path.name for path in sessions.iterdir()} if sessions.exists() else set()
    yield
    after = {path.name for path in sessions.iterdir()} if sessions.exists() else set()
    assert after == before, f"a test wrote session dirs into the real repo: {sorted(after - before)}"


HEADLESS_HELP = """Usage: goose run [OPTIONS]
  --recipe <PATH>
  --name <NAME>
  --with-builtin <B>
  --text <TEXT>
"""
NO_HEADLESS_HELP = "Usage: goose run [OPTIONS]\n  --recipe <PATH>\n"


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
                "task": "governed run",
                "requested_runtime_mode": mode,
            }
        ),
        encoding="utf-8",
    )


def _settings_at(tmp_path: Path) -> MagicMock:
    settings = MagicMock()
    settings.project_root = tmp_path
    return settings


def _write_recipe(tmp_path: Path) -> Path:
    directory = tmp_path / "recipes"
    directory.mkdir(exist_ok=True)
    path = directory / GooseRuntimeHarness.GOVERNED_RECIPE_NAME
    path.write_text("version: '1.0.0'\nextensions: []\n", encoding="utf-8")
    return path


def _fake_goose(tmp_path: Path, *, body: str, help_text: str = HEADLESS_HELP) -> str:
    script = tmp_path / "fake_goose"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"HELP = {help_text!r}\n"
        "if '--help' in sys.argv:\n"
        "    sys.stdout.write(HELP)\n"
        "    sys.exit(0)\n"
        f"{body}\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IRWXU)
    return str(script)


def _patch_every_instance(
    monkeypatch: Any, module_basename: str, attr: str, value: Any
) -> None:
    patched = False
    for name, module in list(sys.modules.items()):
        if module is None or not name.endswith(module_basename):
            continue
        if hasattr(module, attr):
            monkeypatch.setattr(module, attr, value)
            patched = True
    assert patched, f"no loaded module named *{module_basename} exposes {attr!r} to patch"


def _install(
    monkeypatch: Any,
    tmp_path: Path,
    goose_path: str,
    *,
    create_recipe: bool = True,
) -> None:
    import builder_ii.adapters.goose.goose_runtime_harness  # noqa: F401
    import builder_ii.cli.goose_cli  # noqa: F401

    _patch_every_instance(
        monkeypatch, "goose_cli", "load_settings", lambda *a, **k: _settings_at(tmp_path)
    )
    _patch_every_instance(
        monkeypatch, "goose_runtime_harness", "find_goose_binary", lambda: goose_path
    )
    _patch_every_instance(
        monkeypatch,
        "goose_runtime_harness",
        "goose_env",
        lambda *a, **k: {**os.environ, "PATH": os.environ.get("PATH", "")},
    )
    monkeypatch.setattr("builder_ii.goose_runtime_harness.time.time", lambda: 777.0)
    if create_recipe:
        _write_recipe(tmp_path)


# --- fail-closed gates ------------------------------------------------------------------


def test_run_governed_refuses_a_non_read_only_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    _write_manifest(manifest, mode="autonomous")
    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"]
    )
    assert result.exit_code == 1
    assert "read_only" in result.output.lower()


def test_run_governed_fails_closed_when_the_build_cannot_run_headlessly(
    monkeypatch: Any, tmp_path: Path
) -> None:
    goose = _fake_goose(tmp_path, body="sys.exit(0)", help_text=NO_HEADLESS_HELP)
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"]
    )

    assert result.exit_code == 1
    assert "governed headless contract" in result.output.lower()
    assert "start-governed" in result.output


@pytest.mark.parametrize("missing", ["--recipe", "--with-builtin", "--text"])
def test_each_authority_bearing_flag_is_required_before_spawn(
    monkeypatch: Any, tmp_path: Path, missing: str
) -> None:
    lines = [line for line in HEADLESS_HELP.splitlines() if missing not in line]
    goose = _fake_goose(tmp_path, body="sys.exit(0)", help_text="\n".join(lines) + "\n")
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"]
    )

    assert result.exit_code == 1
    assert missing in result.output


def test_missing_governed_recipe_refuses_before_child_execution(
    monkeypatch: Any, tmp_path: Path
) -> None:
    marker = tmp_path / "child-ran"
    goose = _fake_goose(
        tmp_path,
        body=f"import pathlib; pathlib.Path({str(marker)!r}).write_text('bad'); sys.exit(0)",
    )
    _install(monkeypatch, tmp_path, goose, create_recipe=False)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"]
    )

    assert result.exit_code == 1
    assert "recipe not found" in result.output.lower()
    assert not marker.exists()


def test_lifecycle_evidence_failure_prevents_spawn(
    monkeypatch: Any, tmp_path: Path
) -> None:
    marker = tmp_path / "child-ran"
    goose = _fake_goose(
        tmp_path,
        body=f"import pathlib; pathlib.Path({str(marker)!r}).write_text('bad'); sys.exit(0)",
    )
    _install(monkeypatch, tmp_path, goose)
    _patch_every_instance(
        monkeypatch,
        "goose_runtime_harness",
        "append_session_event",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("ledger unavailable")),
    )
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"]
    )

    assert result.exit_code == 1
    assert "ledger unavailable" in result.output.lower()
    assert not marker.exists()


# --- the streamed run -------------------------------------------------------------------


def test_run_governed_streams_output_to_a_log_and_chains_its_lifecycle(
    monkeypatch: Any, tmp_path: Path
) -> None:
    goose = _fake_goose(
        tmp_path,
        body="for i in range(5):\n    print(f'line {i}', flush=True)\nsys.exit(0)",
    )
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app,
        ["run-governed", "--manifest", str(manifest), "--task", "read the repo"],
    )

    assert result.exit_code == 0, result.output
    log = (
        tmp_path / ".builder" / "sessions" / "goose_777" / "goose_run.log"
    ).read_text(encoding="utf-8")
    assert "line 0" in log and "line 4" in log

    records = load_event_records(tmp_path / ".builder" / "sessions" / "goose_777" / "events")
    types = [event["event_type"] for event, _ in records]
    assert types[0] == "goose_run_started"
    assert "goose_run_completed" in types
    assert types[-1] == "goose_readonly_closed"
    assert replay_events(records, session_id="goose_777")["valid"]
    # Raw task prose is intentionally not copied into the evidence-chain message.
    assert "read the repo" not in records[0][0].get("message", "")
    assert "task_sha256=" in records[0][0].get("message", "")


def test_the_run_log_is_strictly_byte_bounded(monkeypatch: Any, tmp_path: Path) -> None:
    goose = _fake_goose(
        tmp_path,
        body="for i in range(2000):\n    print('x' * 200, flush=True)\nsys.exit(0)",
    )
    _install(monkeypatch, tmp_path, goose)
    monkeypatch.setattr(GooseRuntimeHarness, "RUN_LOG_MAX_BYTES", 4096)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "t"]
    )

    assert result.exit_code == 0, result.output
    log_path = tmp_path / ".builder" / "sessions" / "goose_777" / "goose_run.log"
    assert log_path.stat().st_size <= 4096


def test_child_environment_overrides_are_child_scoped(
    monkeypatch: Any, tmp_path: Path
) -> None:
    goose = _fake_goose(
        tmp_path,
        body=(
            "import os\n"
            "print(os.environ.get('BUILDER_MCP_GOVERNED_APPLY', '<missing>'), flush=True)\n"
            "sys.exit(0)"
        ),
    )
    _install(monkeypatch, tmp_path, goose)
    monkeypatch.delenv("BUILDER_MCP_GOVERNED_APPLY", raising=False)
    harness = GooseRuntimeHarness(_settings_at(tmp_path), MagicMock(), tmp_path)  # type: ignore[arg-type]
    harness.session_id = "goose_child_env"
    log_path = tmp_path / "child-env.log"

    _receipt, exit_code = harness.run_governed_streaming(
        "inspect",
        log_path=log_path,
        child_env_overrides={"BUILDER_MCP_GOVERNED_APPLY": "1"},
    )

    assert exit_code == 0
    assert log_path.read_text(encoding="utf-8").strip() == "1"
    assert "BUILDER_MCP_GOVERNED_APPLY" not in os.environ


def test_a_failing_run_propagates_its_exit_code(monkeypatch: Any, tmp_path: Path) -> None:
    goose = _fake_goose(tmp_path, body="print('boom', flush=True)\nsys.exit(3)")
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "t"]
    )
    assert result.exit_code == 3


def test_a_run_that_mutates_the_target_fails_the_postflight(
    monkeypatch: Any, tmp_path: Path
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("original\n", encoding="utf-8")
    goose = _fake_goose(
        tmp_path,
        body=(
            "import pathlib\n"
            f"pathlib.Path({str(tmp_path / 'src' / 'app.py')!r}).write_text('tampered', encoding='utf-8')\n"
            "sys.exit(0)"
        ),
    )
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "t"]
    )

    assert result.exit_code == 1
    assert "mutations detected" in result.output.lower()
    assert "src/app.py" in "".join(result.output.split())


def test_compatibility_argv_projection_uses_only_advertised_flags(tmp_path: Path) -> None:
    harness = GooseRuntimeHarness(_settings_at(tmp_path), MagicMock(), tmp_path)  # type: ignore[arg-type]
    recipe = tmp_path / "recipes" / "governed-readonly.yaml"

    full = harness._governed_run_argv("goose", recipe, "do it", HEADLESS_HELP)
    assert full[:2] == ["goose", "run"]
    assert "--recipe" in full and "--text" in full
    assert full[full.index("--with-builtin") + 1] == ""
    bare = harness._governed_run_argv("goose", recipe, "do it", "Usage: goose run\n")
    assert bare == ["goose", "run"]


def test_request_stop_records_the_intent_even_when_nothing_is_running(tmp_path: Path) -> None:
    harness = GooseRuntimeHarness(_settings_at(tmp_path), MagicMock(), tmp_path)  # type: ignore[arg-type]
    harness.session_id = "goose_stop"

    assert harness.request_stop() is False
    records = load_event_records(tmp_path / ".builder" / "sessions" / "goose_stop" / "events")
    assert [event["event_type"] for event, _ in records] == ["run_stop_requested"]
    assert records[0][0]["decision_result"] == "stopped"


def test_request_stop_terminates_a_live_child(monkeypatch: Any, tmp_path: Path) -> None:
    _write_recipe(tmp_path)
    harness = GooseRuntimeHarness(_settings_at(tmp_path), MagicMock(), tmp_path)  # type: ignore[arg-type]
    harness.session_id = "goose_live"

    import subprocess
    import threading

    harness._proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    stopped: list[bool] = []
    thread = threading.Thread(target=lambda: stopped.append(harness.request_stop()))
    thread.start()
    thread.join(timeout=30)

    assert stopped == [True]
    assert harness._proc.poll() is not None
