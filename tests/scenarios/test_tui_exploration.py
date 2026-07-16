import json
import subprocess

import pytest


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
