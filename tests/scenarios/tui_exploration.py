import subprocess
import json
import pytest

def test_semantic_tui_driver_initial_state():
    """
    Verifies the Semantic TUI driver respects Mechanical Sympathy,
    returns valid JSON, and successfully mounts StratumApp.
    """
    payload = json.dumps({"app": "StratumApp", "steps": []})
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
