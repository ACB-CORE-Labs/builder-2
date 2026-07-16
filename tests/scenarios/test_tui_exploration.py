import json
import subprocess
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from scripts.semantic_tui_driver import extract_semantic_state


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
    from builder_ii.tui_audit_ledger import validate_ledger

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
