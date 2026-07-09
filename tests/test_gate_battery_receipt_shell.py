"""Integration tests for the --receipt mechanism scripts/ci.sh gained (scripts/lib/gate_battery_receipt.sh).

These never run the real nine-gate battery -- that would mean running the full pytest suite
recursively from inside itself. Instead each test sources the real, unmodified
scripts/lib/gate_battery_receipt.sh (byte-identical to what ci.sh sources) against a throwaway
git repo with a tiny, fully controlled fake gate list, so the mechanism -- gate()/skip(), the
--receipt flag, the EXIT trap, git-state capture -- is exercised for real, fast and safely.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from builder_ii.gate_battery_receipt import find_absolute_paths

REPO_ROOT = Path(__file__).resolve().parents[1]
GBR_LIB = REPO_ROOT / "scripts" / "lib" / "gate_battery_receipt.sh"
CI_SCRIPT = REPO_ROOT / "scripts" / "ci.sh"


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def _write_battery(tmp_path: Path, repo: Path, body: str) -> Path:
    script = tmp_path / "battery.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -o errexit\n"
        "set -o nounset\n"
        "set -o pipefail\n"
        f'cd "{repo}"\n'
        f'source "{GBR_LIB}"\n'
        '_gbr_parse_args "$@"\n'
        "_gbr_init\n"
        "trap _gbr_emit_receipt EXIT\n"
        f"{body}",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script), *args], capture_output=True, text=True, timeout=120)


def test_scripts_are_syntactically_valid_bash() -> None:
    for script in (CI_SCRIPT, GBR_LIB):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_failing_gate_still_emits_receipt_and_battery_exits_nonzero(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'gate "fake pass" true\n'
        'gate "fake fail" bash -c "exit 7"\n'
        'gate "never runs" true\n',
    )
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 7, result.stderr
    assert receipt_path.exists(), "a FAILED battery must still emit a receipt"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["overall_state"] == "FAILED"
    names = [gate["name"] for gate in receipt["gates"]]
    assert names == ["fake pass", "fake fail"], "the gate after the failure must never have run"
    failed = receipt["gates"][1]
    assert failed["status"] == "FAILED"
    assert failed["exit_code"] == 7


def test_dirty_tree_recorded_but_receipt_still_written(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "stray.txt").write_text("stray\n", encoding="utf-8")
    script = _write_battery(tmp_path, repo, 'gate "fake pass" true\n')
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 0, result.stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["working_tree_clean"] is False
    assert receipt["overall_state"] == "PASSED"
    assert receipt["valid"] is True


def test_moved_head_yields_unstable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(tmp_path, repo, 'gate "moves head" git commit --allow-empty -q -m moved\n')
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 0, result.stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["head_sha_before"] != receipt["head_sha_after"]
    assert receipt["head_sha_stable"] is False


def test_skipped_gate_recorded_with_null_exit_code_not_zero(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'skip "fake tool" "not found on PATH"\n'
        'gate "fake pass" true\n',
    )
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 0, result.stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["skipped"] == ["fake tool"]
    skip_record = next(gate for gate in receipt["gates"] if gate["name"] == "fake tool")
    assert skip_record["status"] == "SKIPPED"
    assert skip_record["exit_code"] is None
    assert skip_record["duration_seconds"] is None
    assert skip_record["argv"] is None
    assert skip_record["skip_reason"] == "not found on PATH"


def test_default_no_receipt_flag_emits_no_receipt_and_preserves_exit_code(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'gate "fake pass" true\n'
        'gate "fake fail" bash -c "exit 5"\n',
    )

    result = _run(script)  # no --receipt: behavior must be unchanged from before this flag existed

    assert result.returncode == 5, result.stderr
    assert not list(tmp_path.glob("*.json")), "no --receipt means no receipt file, ever"
    assert "gate battery receipt written" not in result.stdout


def test_receipt_from_the_real_mechanism_passes_the_paired_validator(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(tmp_path, repo, 'gate "fake pass" true\n')
    receipt_path = tmp_path / "receipt.json"

    _run(script, "--receipt", str(receipt_path))

    validate = subprocess.run(
        ["uv", "run", "python", "-m", "builder_ii.gate_battery_receipt", "--validate", str(receipt_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert validate.returncode == 0, validate.stderr


def test_env_var_absolute_path_never_leaks_into_receipt(tmp_path: Path) -> None:
    """Mirrors ci.sh's own real pattern: PYO3_PYTHON is exported as an absolute path (derived
    from sys.executable) before the cargo gate runs. A receipt only ever records a gate's argv,
    never its environment, so this must never appear in the emitted JSON."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'export PYO3_PYTHON="/Users/nobody/.venv/bin/python3"\n'
        'gate "rust validator build" cargo build --manifest-path builder_ii_validation_rs/Cargo.toml\n',
    )
    receipt_path = tmp_path / "receipt.json"

    # cargo may fail here (no such manifest in this throwaway repo) -- irrelevant; the
    # assertion is only about what the receipt records, never about the gate passing.
    _run(script, "--receipt", str(receipt_path))

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    dumped = json.dumps(receipt)
    assert "/Users/nobody/.venv/bin/python3" not in dumped
    assert str(REPO_ROOT) not in dumped
    assert str(tmp_path) not in dumped
    assert find_absolute_paths(receipt) == []
