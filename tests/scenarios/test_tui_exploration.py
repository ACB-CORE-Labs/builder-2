import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from scripts.semantic_tui_driver import extract_semantic_state, run_exploration


def test_semantic_tui_driver_initial_state(tmp_path):
    """
    Verifies the Semantic TUI driver respects Mechanical Sympathy,
    returns valid JSON, and successfully mounts StratumApp.

    Writes its chain to `tmp_path`, not the repo's real `.builder/artifacts/` ledger. Once the
    ledger became a chain, appending to one fixed path made this test's verdict depend on whatever
    that gitignored file had accumulated -- a stale or pre-chain ledger on any developer's disk
    failed it for reasons having nothing to do with the driver, and each run silently grew a file
    the repo never cleans up.
    """
    payload = json.dumps({"app": "StratumApp", "steps": [], "ledger_path": str(tmp_path / "ledger.jsonl")})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Driver failed with stderr: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.stdout}")

    assert "initial_state" in output, "Missing initial_state in semantic output"
    assert "widgets" in output["initial_state"], "Missing widget tree in semantic output"
    assert "active_screen" in output["initial_state"], "Failed to track active screen (modal support missing)"


def test_semantic_tui_driver_observes_stratum_and_not_the_splash(tmp_path):
    """The driver must record the app it was pointed at.

    It did not. `StratumApp.on_mount` pushes `SplashScreen`, `app.screen` is therefore the splash,
    and this driver reads `app.screen` -- so every state it ever recorded was the splash's five
    widgets (Center/Static/Vertical), never STRATUM's. Every ledger entry, and the whole hash chain
    built over them, described a loading screen.

    Nothing above caught it because those assertions ask only whether the *keys* exist, and a
    splash has an `active_screen` and a `widgets` list like anything else. All three pass while the
    instrument stares at the wrong screen. This lane names furniture only StratumApp composes, so a
    splash cannot satisfy it.
    """
    payload = json.dumps({"app": "StratumApp", "steps": [], "ledger_path": str(tmp_path / "ledger.jsonl")})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Driver failed with stderr: {result.stderr[:400]}"
    initial = json.loads(result.stdout)["initial_state"]

    assert initial["active_screen"] != "SplashScreen", "the driver is recording the splash again"

    observed = {w["type"] for w in initial["widgets"]}
    for expected in ("HeaderBanner", "ArtifactSpine", "ActiveStratum", "SignalRail"):
        assert expected in observed, f"{expected} absent -- driver is not observing StratumApp ({sorted(observed)})"


def test_semantic_tui_driver_reports_an_unbound_key_as_unhandled(tmp_path):
    """A key nothing listens for must not be reported as a successful step.

    `pilot.press` raises nothing and returns None for an unbound key, so a phantom keypress
    recorded `status: "success"` -- the instrument claiming it drove something when it drove
    nothing. `f5` is bound nowhere on STRATUM's default screen; `escape` is bound. Both halves are
    asserted, because a check that called every key unhandled would satisfy the first alone.
    """
    steps = [{"action": "press", "target": "f5"}, {"action": "press", "target": "escape"}]
    payload = json.dumps({"app": "StratumApp", "steps": steps, "ledger_path": str(tmp_path / "ledger.jsonl")})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"driver failed: {result.stderr[:400]}"
    log = json.loads(result.stdout)["execution_log"]

    phantom, real = log[0], log[1]
    assert phantom["status"] == "unhandled", f"f5 is bound to nothing but reported {phantom['status']!r}"
    assert "PHANTOM_KEYPRESS" in phantom["error"]
    assert real["status"] == "success", f"escape is bound but reported {real['status']!r}"
    assert real["reception"] == "binding"


def test_semantic_tui_driver_reports_a_click_on_nothing_as_failed(tmp_path):
    """A click at a selector matching no widget is not a success."""
    steps = [{"action": "click", "target": "#no-such-widget-anywhere"}]
    payload = json.dumps({"app": "StratumApp", "steps": steps, "ledger_path": str(tmp_path / "ledger.jsonl")})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"driver failed: {result.stderr[:400]}"
    step = json.loads(result.stdout)["execution_log"][0]
    assert step["status"] == "failed"
    assert "NO_SUCH_TARGET" in step["error"]


def test_semantic_tui_driver_bounds_extracted_text_without_going_blind(tmp_path):
    """Text is capped, and the cap does not cost the driver its ability to detect change.

    `EpistemicMatrix` renders 345 characters on the default screen, so the truncation branch is
    live rather than theoretical. A bare cap would let two renders sharing a 250-character prefix
    record identically and diff as "unchanged"; the digest is taken over the whole string, so a
    change past the cut still moves it.
    """
    payload = json.dumps({"app": "StratumApp", "steps": [], "ledger_path": str(tmp_path / "ledger.jsonl")})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"driver failed: {result.stderr[:400]}"
    widgets = json.loads(result.stdout)["initial_state"]["widgets"]

    assert all(len(w.get("text", "")) <= 250 for w in widgets), "an extracted text field exceeded the cap"

    truncated = [w for w in widgets if w.get("text_truncated")]
    assert truncated, "nothing truncated -- lane is vacuous; has EpistemicMatrix shrunk below 250?"
    for widget in truncated:
        assert len(widget["text"]) == 250
        assert widget["text_full_chars"] > 250
        assert len(widget["text_sha256"]) == 64, "truncated text must carry a digest of the whole string"


class _Exploding(Static):
    """Renders normally for Textual's paint pass, then raises once armed.

    The arming is not a contrivance to dodge an inconvenience -- it is what makes the test model
    the real path. Textual calls `render()` itself while painting and does not tolerate it raising:
    the app tears down and `run_test()` re-raises, so a widget that raises from the first paint
    never reaches the driver at all. The branch under test is the driver's *own* direct
    `widget.render()` call in `extract_semantic_state`, and arming is how that call, and only that
    call, is made to fail.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.armed = False

    def render(self) -> str:
        if self.armed:
            raise RuntimeError("boom from render")
        return "not yet"


class _ExplodingHarness(App):
    def compose(self) -> ComposeResult:
        yield _Exploding(id="exploding")
        yield Static("intact", id="intact")


@pytest.mark.asyncio
async def test_semantic_tui_driver_records_a_render_crash_instead_of_hiding_it():
    """A widget whose render() raises must be recorded as a crash, not as an empty widget.

    `except Exception: pass` wrote the crashed widget out with no `text` key -- byte-identical to a
    widget that legitimately renders nothing -- and the run still exited 0. The single most
    interesting thing this instrument can find was the one thing it deleted, and a driver that
    hides crashes is worse than no driver, because it is believed.

    A sibling that renders fine is asserted alongside, so a change breaking *all* extraction could
    not satisfy this lane by reporting errors everywhere.
    """
    app = _ExplodingHarness()
    async with app.run_test():
        app.query_one("#exploding", _Exploding).armed = True
        state = await extract_semantic_state(app)

    widgets = {w["id"]: w for w in state["widgets"]}

    crashed = widgets["exploding"]
    assert "RuntimeError: boom from render" in crashed["render_error"]
    assert "text" not in crashed, "a crashed render must not masquerade as extracted text"
    # The innermost frame, basename only: a traceback's actual payload without the absolute path
    # that would make `state_digest` differ between two checkouts of the same code.
    assert crashed["render_error_at"].startswith("test_tui_exploration.py:")

    assert widgets["intact"]["text"] == "intact"
    assert "render_error" not in widgets["intact"]

def test_semantic_tui_driver_records_hidden_widgets_instead_of_skipping_them(tmp_path):
    """A mounted-but-hidden widget must be recorded, marked hidden -- not omitted.

    The extractor skipped `display = False`, which quietly excluded the widgets most worth
    asserting on: `ThirdDoorGate` -- the HITL gate -- is mounted hidden and revealed by mode, so
    "is the gate mounted and waiting?" was unanswerable, and a gate deleted from the DOM entirely
    looked exactly like one merely hidden. Measured: 37 of 39 mounted widgets reported.

    Both polarities are asserted. A change that marked every widget hidden would satisfy the first
    half alone, and would be just as blind.
    """
    payload = json.dumps({"app": "StratumApp", "steps": [], "ledger_path": str(tmp_path / "ledger.jsonl")})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"driver failed: {result.stderr[:400]}"
    widgets = json.loads(result.stdout)["initial_state"]["widgets"]
    by_type = {w["type"]: w for w in widgets}

    gate = by_type.get("ThirdDoorGate")
    assert gate is not None, f"ThirdDoorGate is mounted but absent from the state ({sorted(by_type)})"
    assert gate["visible"] is False, "ThirdDoorGate is display=False on the default screen"
    assert gate["id"] == "third-door-gate", "the gate must stay addressable by id"

    # The other half: STRATUM's furniture is on screen and must not be reported hidden.
    assert by_type["HeaderBanner"]["visible"] is True
    assert any(w["visible"] for w in widgets), "every widget reported hidden -- the flag is stuck"


@pytest.mark.asyncio
async def test_the_notify_hook_neither_imposes_a_timeout_nor_widens_the_signature(tmp_path, capsys):
    """Observing notifications must not change how notifications work.

    The hook restated Textual's signature and got it wrong in both directions at once: it defaulted
    `timeout` to a hardcoded `5.0` where `App.notify` defaults to `None` and resolves it to
    `NOTIFICATION_TIMEOUT` (so an app that tuned that attribute was silently overridden the moment
    it was watched), and it took `title`/`severity`/`timeout` positionally where Textual makes them
    keyword-only (so a call that is a `TypeError` in production succeeded under the driver).

    `NOTIFICATION_TIMEOUT` here is deliberately neither Textual's default (5) nor the old hardcoded
    literal (5.0): if either were reinstated, the recorded value could not be 1.5.
    """

    class _NotifyProbe(App):
        NOTIFICATION_TIMEOUT = 1.5

        def compose(self) -> ComposeResult:
            yield Static("probe")

        def on_mount(self) -> None:
            self.notify("inherits the app's configured default")
            self.notify("carries its own", timeout=9.0)
            try:
                self.notify("positional", "title")  # type: ignore[misc]
            except TypeError:
                self.positional_rejected = True
            else:
                self.positional_rejected = False

    built: list[_NotifyProbe] = []

    def factory() -> App:
        app = _NotifyProbe()
        built.append(app)
        return app

    await run_exploration(factory, [], str(tmp_path / "ledger.jsonl"))
    recorded = json.loads(capsys.readouterr().out)["initial_state"]["notifications"]
    timeouts = {note["message"]: note["timeout"] for note in recorded}

    assert timeouts["inherits the app's configured default"] == 1.5, (
        "the hook imposed a timeout instead of letting App.notify resolve NOTIFICATION_TIMEOUT"
    )
    assert timeouts["carries its own"] == 9.0, "an explicit per-notification timeout was not preserved"
    assert built[0].positional_rejected is True, (
        "the hook accepted a positional argument Textual rejects -- it makes an invalid call valid"
    )


@pytest.mark.asyncio
async def test_the_default_ledger_is_scoped_to_one_run(tmp_path, monkeypatch, capsys):
    """Two runs must not write the same chain.

    One shared default file was not untidy, it was wrong: both runs read the same chain head and
    wrote from it. Measured -- two concurrent runs produced four events whose every link after the
    first was broken, so the validator reported deletion or reordering on a file nobody had
    touched. Concurrency corrupted the evidence and disguised it as tampering.

    `chdir` into `tmp_path` because the path under test is the *default*; the override is what
    every other lane here exercises, and it is precisely the default that was shared.
    """
    from builder_ii.governance.ledger.tui_audit_ledger import validate_ledger

    class _Trivial(App):
        def compose(self) -> ComposeResult:
            yield Static("trivial")

    monkeypatch.chdir(tmp_path)

    await run_exploration(lambda: _Trivial(), [], None)
    first = json.loads(capsys.readouterr().out)
    await run_exploration(lambda: _Trivial(), [], None)
    second = json.loads(capsys.readouterr().out)

    assert first["ledger_path"] != second["ledger_path"], "two runs shared one ledger file"
    assert first["run_id"] in first["ledger_path"], "the ledger must be locatable from the run id"
    assert first["run_id"] != second["run_id"]

    # Each is a complete, independently valid chain -- not a fragment of a larger one.
    for run in (first, second):
        assert validate_ledger(Path(run["ledger_path"])) == [], f"{run['ledger_path']} is not a valid chain"


def test_concurrent_driver_runs_do_not_corrupt_each_others_chains(tmp_path):
    """The measured defect, pinned end to end: two real runs at once, both ledgers intact.

    This is the lane that would have caught it. With a shared default path the two processes
    interleave into one file and the validator reports every link after the first as broken.

    It now also covers the master index, which is the one place those two processes still share a
    file -- so this is the only lane where the index's lock is exercised by real concurrent driver
    *processes* rather than by threads. Both halves of the concurrency story, one fixture.
    """
    from builder_ii.governance.ledger.tui_audit_ledger import (
        MASTER_INDEX_FILENAME,
        validate_ledger,
        validate_master_index,
    )

    artifacts = tmp_path / ".builder" / "artifacts"
    procs = [
        subprocess.Popen(
            ["uv", "run", "python", str(Path.cwd() / "scripts" / "semantic_tui_driver.py"),
             json.dumps({"app": "StratumApp", "steps": []})],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=tmp_path,
        )
        for _ in range(2)
    ]
    outs = [p.communicate() for p in procs]

    for stdout, stderr in outs:
        assert stdout, f"driver produced no output: {stderr[:300]}"

    # Excluded by name, not by a cleverer glob. The index shares the ledgers' prefix, so the plain
    # `tui_audit_ledger_*.jsonl` this lane used to run counted it as a third ledger the moment the
    # index existed -- and would then have fed it to `validate_ledger`, which reports every field of
    # a perfectly good index as missing. Same trap `scripts/validate_tui_audit_ledger.py` sidesteps.
    ledgers = sorted(p for p in artifacts.glob("tui_audit_ledger_*.jsonl") if p.name != MASTER_INDEX_FILENAME)
    assert len(ledgers) == 2, f"two concurrent runs produced {len(ledgers)} ledger(s), expected one each"

    for ledger in ledgers:
        assert validate_ledger(ledger) == [], f"{ledger.name} was corrupted by the concurrent run"

    # The shared file. Two processes, one index, one chain -- or the lock is not doing its job.
    index = artifacts / MASTER_INDEX_FILENAME
    assert index.exists(), "neither run anchored itself; a deleted ledger would now be invisible again"

    entries = [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entries) == 2, f"two runs produced {len(entries)} index entries; an append was lost to the race"
    assert [e["seq"] for e in entries] == [0, 1], "the index chain forked: both runs read the same head"
    assert {e["run_id"] for e in entries} == {json.loads(stdout)["run_id"] for stdout, _ in outs}
    assert validate_master_index(index) == [], "the index does not verify against the runs it anchors"


def test_semantic_tui_driver_invalid_app():
    """Verifies Semantic Rigor by gracefully failing on unknown targets."""
    payload = json.dumps({"app": "NonExistentApp", "steps": []})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True
    )

    # Should exit 1 with a clean JSON error
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["error"] == "UNKNOWN_APP"


def test_semantic_tui_driver_refuses_a_legacy_ledger_with_clean_json(tmp_path):
    """A pre-chain ledger must produce one line of JSON, not a traceback.

    Every ledger written before `builder_ii.tui_audit_ledger` existed lacks `entry_digest`, so
    `read_chain_head` cannot continue the chain from it. Refusing is correct -- appending would
    leave a gap no later verification could detect -- but it must arrive as the structured error
    this driver emits everywhere else. An uncaught ValueError would break the driver's "always
    emits JSON" contract on the first run after upgrade for every developer already holding a
    ledger.

    Uses the `ledger_path` override rather than the repo's real `.builder/` file: the chain made a
    run's outcome depend on that file's accumulated state, and a test must not be decided by it.
    """
    ledger = tmp_path / "legacy.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "kind": "builder_ii.tui_audit_ledger_event",
                "run_id": "legacy",
                "timestamp": 1.0,
                "event": "MOUNT",
                "state": {},
                "digest": "legacy-format-had-no-entry_digest",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = json.dumps({"app": "StratumApp", "steps": [], "ledger_path": str(ledger)})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, f"expected a clean refusal, got {result.returncode}: {result.stderr[:400]}"
    output = json.loads(result.stdout)  # must be JSON, not a traceback
    assert output["error"] == "LEDGER_CHAIN_UNREADABLE"
    assert "Move or delete" in output["remedy"]


def test_semantic_tui_driver_writes_a_valid_chain(tmp_path):
    """The driver's own output must satisfy the validator that ships beside it."""
    from builder_ii.governance.ledger.tui_audit_ledger import validate_ledger

    ledger = tmp_path / "chain.jsonl"
    payload = json.dumps({"app": "StratumApp", "steps": [{"action": "press", "target": "escape"}],
                          "ledger_path": str(ledger)})
    result = subprocess.run(
        ["uv", "run", "python", "scripts/semantic_tui_driver.py", payload],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"driver failed: {result.stderr[:400]}"
    assert validate_ledger(ledger) == []
