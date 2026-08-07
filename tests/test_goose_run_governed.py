"""The headless streamed governed run (`builder-goose run-governed`, ADR-0009 lane B).

`start-governed` hands Goose the operator's terminal and blocks -- governed, but invisible,
which is the "masterful governance, an invisible run" problem ADR-0009 names. A streamed run
writes its lifecycle onto the chain the operator console tails instead, so it is legible while
it happens.

Goose is stood in for by a real executable script rather than a monkeypatched Popen: the thing
under test is the streaming loop, the log cap, the exit-code path and the signal handling, and
a fake that never actually runs would exercise none of them. Every test here works on a host
with no Goose installed.
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

#: The repository these tests run inside. Nothing here may write into it.
_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _no_repo_pollution() -> Any:
    """Fail loudly if a run escapes its tmp_path and writes into the real repository.

    A governed run creates `.builder/sessions/<id>/` wherever it thinks the project root is, so
    a missed patch does not fail the test -- it silently writes real session ledgers into the
    working tree. This asserts the blast radius rather than trusting the patching.
    """
    sessions = _REPO_ROOT / ".builder" / "sessions"
    before = {p.name for p in sessions.iterdir()} if sessions.exists() else set()
    yield
    after = {p.name for p in sessions.iterdir()} if sessions.exists() else set()
    assert after == before, f"a test wrote session dirs into the real repo: {sorted(after - before)}"

#: Help text advertising the flags a headless run needs.
HEADLESS_HELP = "Usage: goose run [OPTIONS]\n  --recipe <PATH>\n  --name <NAME>\n  --with-builtin <B>\n  --text <TEXT>\n"

#: A build that cannot be handed a task headlessly.
NO_HEADLESS_HELP = "Usage: goose run [OPTIONS]\n  --recipe <PATH>\n"


def _write_manifest(path: Path, *, mode: str = "read_only") -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.goose_session_manifest",
                "schema_version": 1,
                "target": {"name": "builder", "repo": ".", "description": "test"},
                "agent_profile": {"name": "patch_planner", "description": "test", "authority": "user"},
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


def _fake_goose(tmp_path: Path, *, body: str, help_text: str = HEADLESS_HELP) -> str:
    """A real executable standing in for Goose, so the streaming loop actually streams."""
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


def _patch_every_instance(monkeypatch: Any, module_basename: str, attr: str, value: Any) -> None:
    """Patch an attribute on every loaded copy of a module.

    The legacy alias shim (`builder_ii.goose_*` -> `builder_ii.adapters.goose.goose_*`) executes
    these modules a *second* time, so `sys.modules` can hold two distinct objects for one source
    file -- distinct enough that their `goose_app` Typer instances are different objects. A test
    that patches only the copy it happens to have imported leaves the other one live, and the
    command under test then runs against real settings. That is not hypothetical: it is how an
    earlier version of this file wrote a governed run into the actual repository under
    `.builder/sessions/`, passing in isolation and polluting the tree in a full-suite run.
    """
    patched = False
    for name, module in list(sys.modules.items()):
        if module is None or not name.endswith(module_basename):
            continue
        if hasattr(module, attr):
            monkeypatch.setattr(module, attr, value)
            patched = True
    assert patched, f"no loaded module named *{module_basename} exposes {attr!r} to patch"


def _install(monkeypatch: Any, tmp_path: Path, goose_path: str) -> None:
    # Import both spellings first so every copy that could serve the CLI is present and patched.
    import builder_ii.adapters.goose.goose_runtime_harness  # noqa: F401
    import builder_ii.cli.goose_cli  # noqa: F401

    _patch_every_instance(monkeypatch, "goose_cli", "load_settings", lambda *a, **k: _settings_at(tmp_path))
    _patch_every_instance(monkeypatch, "goose_runtime_harness", "find_goose_binary", lambda: goose_path)
    _patch_every_instance(
        monkeypatch,
        "goose_runtime_harness",
        "goose_env",
        lambda *a, **k: {**os.environ, "PATH": os.environ.get("PATH", "")},
    )
    monkeypatch.setattr("builder_ii.goose_runtime_harness.time.time", lambda: 777.0)


# --- fail-closed gates ------------------------------------------------------------------


def test_run_governed_refuses_a_non_read_only_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "m.json"
    _write_manifest(manifest, mode="autonomous")
    result = runner.invoke(goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"])
    assert result.exit_code == 1
    assert "read_only" in result.output.lower()


def test_run_governed_fails_closed_when_the_build_cannot_run_headlessly(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """A build with no `--text` cannot be handed the task; silently dropping it would be worse."""
    goose = _fake_goose(tmp_path, body="sys.exit(0)", help_text=NO_HEADLESS_HELP)
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["run-governed", "--manifest", str(manifest), "--task", "x"])

    assert result.exit_code == 1
    assert "headless" in result.output.lower()
    # It names the interactive fallback rather than leaving the operator stuck.
    assert "start-governed" in result.output


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
        goose_app, ["run-governed", "--manifest", str(manifest), "--task", "read the repo"]
    )

    assert result.exit_code == 0, result.output

    log = (tmp_path / ".builder" / "sessions" / "goose_777" / "goose_run.log").read_text(encoding="utf-8")
    assert "line 0" in log and "line 4" in log

    records = load_event_records(tmp_path / ".builder" / "sessions" / "goose_777" / "events")
    types = [event["event_type"] for event, _ in records]
    # Started brackets the child before it exists; completed and closed after it exits.
    assert types[0] == "goose_run_started"
    assert "goose_run_completed" in types
    assert types[-1] == "goose_readonly_closed"
    assert replay_events(records, session_id="goose_777")["valid"]


def test_the_run_log_is_bounded(monkeypatch: Any, tmp_path: Path) -> None:
    """An unbounded log lets a looping agent fill the disk the evidence must be written to."""
    goose = _fake_goose(
        tmp_path,
        body="for i in range(2000):\n    print('x' * 200, flush=True)\nsys.exit(0)",
    )
    _install(monkeypatch, tmp_path, goose)
    monkeypatch.setattr(GooseRuntimeHarness, "RUN_LOG_MAX_BYTES", 4096)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["run-governed", "--manifest", str(manifest), "--task", "t"])

    assert result.exit_code == 0, result.output
    log_path = tmp_path / ".builder" / "sessions" / "goose_777" / "goose_run.log"
    # Bounded, but the run still completed: the cap truncates the transcript, never the run.
    assert log_path.stat().st_size <= 4096 + 512


def test_a_failing_run_propagates_its_exit_code(monkeypatch: Any, tmp_path: Path) -> None:
    goose = _fake_goose(tmp_path, body="print('boom', flush=True)\nsys.exit(3)")
    _install(monkeypatch, tmp_path, goose)
    manifest = tmp_path / "m.json"
    _write_manifest(manifest)

    result = runner.invoke(goose_app, ["run-governed", "--manifest", str(manifest), "--task", "t"])

    # Reported as the child's own failure, never flattened into success.
    assert result.exit_code == 3


def test_a_run_that_mutates_the_target_fails_the_postflight(monkeypatch: Any, tmp_path: Path) -> None:
    """Read-only is proven by content digest after the fact, not asserted by configuration."""
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

    result = runner.invoke(goose_app, ["run-governed", "--manifest", str(manifest), "--task", "t"])

    assert result.exit_code == 1
    assert "mutations detected" in result.output.lower()
    assert "src/app.py" in "".join(result.output.split())


def test_argv_is_built_from_advertised_flags_only(tmp_path: Path) -> None:
    """The repo has been burned once by assuming a CLI shape; nothing here is assumed."""
    settings = _settings_at(tmp_path)
    harness = GooseRuntimeHarness(settings, MagicMock(), tmp_path)  # type: ignore[arg-type]
    recipe = tmp_path / "recipes" / "governed-readonly.yaml"

    full = harness._governed_run_argv("goose", recipe, "do it", HEADLESS_HELP)
    assert full[:2] == ["goose", "run"]
    assert "--recipe" in full and "--text" in full and full[full.index("--text") + 1] == "do it"
    assert full[full.index("--with-builtin") + 1] == ""

    # A build advertising none of them yields a bare argv rather than flags it would reject.
    bare = harness._governed_run_argv("goose", recipe, "do it", "Usage: goose run\n")
    assert bare == ["goose", "run"]


def test_request_stop_records_the_intent_even_when_nothing_is_running(tmp_path: Path) -> None:
    """An operator's intent to stop is evidence even if the process already exited."""
    settings = _settings_at(tmp_path)
    harness = GooseRuntimeHarness(settings, MagicMock(), tmp_path)  # type: ignore[arg-type]
    harness.session_id = "goose_stop"

    assert harness.request_stop() is False  # nothing live to signal

    records = load_event_records(tmp_path / ".builder" / "sessions" / "goose_stop" / "events")
    assert [event["event_type"] for event, _ in records] == ["run_stop_requested"]
    assert records[0][0]["decision_result"] == "stopped"


def test_request_stop_terminates_a_live_child(monkeypatch: Any, tmp_path: Path) -> None:
    """TERM first, and only escalate if the child ignores it -- never kill mid-write unasked."""
    goose = _fake_goose(
        tmp_path,
        body="import time\nprint('working', flush=True)\ntime.sleep(60)\n",
    )
    settings = _settings_at(tmp_path)
    monkeypatch.setattr("builder_ii.goose_runtime_harness.find_goose_binary", lambda: goose)
    monkeypatch.setattr(
        "builder_ii.goose_runtime_harness.goose_env", lambda *a, **k: {**os.environ}
    )
    harness = GooseRuntimeHarness(settings, MagicMock(), tmp_path)  # type: ignore[arg-type]
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
