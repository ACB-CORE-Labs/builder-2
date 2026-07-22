"""Integration tests for the --receipt mechanism scripts/ci.sh gained (scripts/lib/gate_battery_receipt.sh).

These never run the real nine-gate battery -- that would mean running the full pytest suite
recursively from inside itself. Instead each test sources the real, unmodified
scripts/lib/gate_battery_receipt.sh (byte-identical to what ci.sh sources) against a throwaway
git repo with a tiny, fully controlled fake gate list, so the mechanism -- gate()/skip(), the
--receipt flag, the EXIT trap, git-state capture -- is exercised for real, fast and safely.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from builder_ii.governance.ledger.gate_battery_receipt import find_absolute_paths, validate_gate_battery_receipt

_ROOT_SKIP = pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses permission bits")

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


def test_second_run_still_reports_a_clean_tree_when_the_receipt_path_is_gitignored(tmp_path: Path) -> None:
    """The footgun the workflow's receipt path exists to avoid, proven in both directions.

    `_gbr_emit_receipt` computes `working_tree_clean` before writing the receipt, so a
    receipt never sees ITSELF -- but `git status --porcelain` does see the untracked
    receipt left by a PREVIOUS run. Direction one: a receipt inside a gitignored directory
    (the workflow's `.builder/artifacts/` path) leaves the second run clean and stable.
    Direction two: park a receipt at the repo root and the very next run truthfully -- and
    uselessly -- reports `working_tree_clean: false`, poisoned by its own recorder. The
    second direction is asserted too, so if git or the lib ever changes how ignored files
    are reported, the property this pin protects is re-examined rather than assumed.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitignore").write_text(".builder/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "ignore .builder"], cwd=repo, check=True)
    script = _write_battery(tmp_path, repo, 'gate "fake pass" true\n')
    ignored_receipt = repo / ".builder" / "artifacts" / "gate-battery-receipt.json"

    for run_index in (1, 2):
        result = _run(script, "--receipt", str(ignored_receipt))
        assert result.returncode == 0, result.stderr
        receipt = json.loads(ignored_receipt.read_text(encoding="utf-8"))
        assert receipt["working_tree_clean"] is True, f"run {run_index} must not see the previous receipt"
        assert receipt["head_sha_stable"] is True
        assert validate_gate_battery_receipt(receipt) == []

    # Contrast: the same second run over a repo-root receipt reports a dirty tree.
    root_receipt = repo / "gate-battery-receipt.json"
    assert _run(script, "--receipt", str(root_receipt)).returncode == 0
    second = _run(script, "--receipt", str(root_receipt))
    assert second.returncode == 0, second.stderr
    receipt = json.loads(root_receipt.read_text(encoding="utf-8"))
    assert receipt["working_tree_clean"] is False, (
        "a repo-root receipt must dirty the next run's tree; if this ever flips, the "
        "gitignored-path requirement in ci.yml needs re-justifying, not deleting"
    )


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


# --- review round 1 must-fix: a receipt that cannot be written must never look like success ---
#
# Reproduced against the pre-fix code before writing these: an unwritable parent directory
# exited 0 with no receipt (the PermissionError was buried in stderr); a pre-existing read-only
# receipt file also exited 0, leaving a *stale* receipt on disk -- naming a commit that was
# never run -- untouched, because `output.write_text(...)` raised before writing anything and
# the shell wrapped the whole call in `|| true`. Fixed by making the Python-side write atomic
# (temp file + os.replace, which only needs directory write permission) and replacing `|| true`
# with an explicit non-zero exit whenever a requested receipt was not produced, without ever
# overwriting a real gate failure's own exit code.


@_ROOT_SKIP
def test_unwritable_parent_directory_yields_nonzero_exit_loud_stderr_no_receipt(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(tmp_path, repo, 'gate "fake pass" true\n')
    unwritable_parent = tmp_path / "locked"
    unwritable_parent.mkdir()
    unwritable_parent.chmod(0o000)
    receipt_path = unwritable_parent / "receipt.json"

    try:
        result = _run(script, "--receipt", str(receipt_path))
    finally:
        unwritable_parent.chmod(0o755)  # tmp_path cleanup needs this back

    assert result.returncode != 0, "a green battery whose requested receipt is missing must not exit 0"
    assert "could NOT be written" in result.stderr
    assert not receipt_path.exists()


def test_readonly_preexisting_receipt_no_stale_content_survives_a_green_battery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(tmp_path, repo, 'gate "fake pass" true\n')
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps({"head_sha_before": "deadbeef" * 5, "overall_state": "FAILED", "note": "seeded stale receipt"}),
        encoding="utf-8",
    )
    receipt_path.chmod(0o444)

    try:
        result = _run(script, "--receipt", str(receipt_path))
    finally:
        receipt_path.chmod(0o644)  # tmp_path cleanup needs this back

    # os.replace only needs directory write permission, so the atomic write succeeds even
    # though the pre-existing file was read-only -- the exact case that used to leave the stale
    # "deadbeef" receipt behind next to exit 0.
    assert result.returncode == 0, result.stderr
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["head_sha_before"] != "deadbeef" * 5
    assert receipt["overall_state"] == "PASSED"
    assert "seeded stale receipt" not in receipt_path.read_text(encoding="utf-8")


@_ROOT_SKIP
def test_failing_gate_with_unwritable_receipt_keeps_the_gates_own_exit_code(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(tmp_path, repo, 'gate "fake fail" bash -c "exit 42"\n')
    unwritable_parent = tmp_path / "locked"
    unwritable_parent.mkdir()
    unwritable_parent.chmod(0o000)
    receipt_path = unwritable_parent / "receipt.json"

    try:
        result = _run(script, "--receipt", str(receipt_path))
    finally:
        unwritable_parent.chmod(0o755)

    assert result.returncode == 42, "the gate's own code must survive, never the receipt writer's"
    assert "could NOT be written" in result.stderr


def test_lib_refuses_to_load_without_pipefail(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = tmp_path / "no_pipefail.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -o errexit\n"
        "set -o nounset\n"
        "# deliberately no pipefail\n"
        f'cd "{repo}"\n'
        f'source "{GBR_LIB}"\n'
        'echo "should not reach here"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)

    result = _run(script)

    assert result.returncode != 0
    assert "pipefail" in result.stderr
    assert "should not reach here" not in result.stdout


# --- review round 1 note (deliberate decision, not a must-fix): record-gate can fail too -------
#
# `_gbr_run_receipt_tool record-gate ...` used to run as a bare command inside gate()/skip(),
# under errexit. If it failed (full disk, a bug in the tool), the shell would abort right there
# with the RECORDER's exit code, masking the real gate's result -- a battery whose "fake fail"
# gate genuinely exits 42 would instead report exit 1 (record-gate's own failure), and a fully
# green battery could abort mid-run for a reason with nothing to do with the code under test.
# Decision: never let receipt bookkeeping override the battery's real verdict. `_gbr_record_gate`
# warns loudly on stderr and carries on; the affected gate is then honestly missing from
# gates[] (never fabricated) rather than corrupting the battery's exit code.


def test_failing_record_gate_does_not_mask_the_real_gates_exit_code(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = tmp_path / "battery.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -o errexit\n"
        "set -o nounset\n"
        "set -o pipefail\n"
        f'cd "{repo}"\n'
        f'source "{GBR_LIB}"\n'
        # Redefines the sourced function: record-gate always fails, build still runs for real.
        "_gbr_run_receipt_tool() {\n"
        '  if [ "$1" = "record-gate" ]; then\n'
        "    return 1\n"
        "  fi\n"
        '  command uv run --project "$_GBR_REPO_ROOT" python -m builder_ii.gate_battery_receipt "$@"\n'
        "}\n"
        '_gbr_parse_args "$@"\n'
        "_gbr_init\n"
        "trap _gbr_emit_receipt EXIT\n"
        'gate "fake fail" bash -c "exit 42"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 42, "the gate's own exit code must survive a failing recorder, not the recorder's"
    assert "could not record gate" in result.stderr

    # And the receipt must not quietly report a green battery just because the one gate that
    # failed never made it into gates[]. Reproduced against the pre-fix code: exit 42, and a
    # fully-valid receipt stamped `overall_state: PASSED`.
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["overall_state"] == "INCOMPLETE"
    assert receipt["dropped_gate_records"] == ["fake fail"]
    assert receipt["gates"] == []
    assert validate_gate_battery_receipt(receipt) == []


def test_one_dropped_record_among_several_gates_still_forces_incomplete(tmp_path: Path) -> None:
    """The narrow, realistic case: the gate log becomes unwritable partway through a battery.

    Everything recorded so far passed, so `gates[]` alone would say PASSED. Only
    `dropped_gate_records` knows a gate is missing, and it is what drags the verdict to
    INCOMPLETE. The battery's own exit code is untouched -- the receipt merely stops corroborating
    a verdict it cannot see.

    The recorder failure is injected by redefining `_gbr_run_receipt_tool` for `record-gate`
    only, NOT by `chmod 444` on the gate log. Permission bits do not stop root, and CI runs the
    suite as root -- so under `chmod` the append quietly SUCCEEDED there, `second` was recorded,
    and this test failed on CI while passing on every developer laptop (the defect that made a
    locally-green battery worthless as independent evidence).

    Making the log structurally unwritable instead (a directory) is root-proof but also makes it
    unREADable, so the trap could not build the receipt this test needs to inspect. Injecting at
    the recorder is the only mechanism that is simultaneously root-proof, portable, and leaves
    the log readable -- and it simulates precisely what is under test: a gate ran, and its record
    could not be appended. `build` still runs through the real tool.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'gate "first" true\n'
        # Fail every later record-gate append -- for root too (a chmod would not).
        "_gbr_real_tool() { uv run --project \"$_GBR_REPO_ROOT\" python -m builder_ii.gate_battery_receipt \"$@\"; }\n"
        "_gbr_run_receipt_tool() {\n"
        '  if [ "$1" = "record-gate" ]; then return 1; fi\n'
        '  _gbr_real_tool "$@"\n'
        "}\n"
        'gate "second" bash -c "exit 9"\n',
    )
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 9, "the failing gate's exit code, never the recorder's, never 3"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert [gate["name"] for gate in receipt["gates"]] == ["first"]
    assert receipt["dropped_gate_records"] == ["second"]
    assert receipt["overall_state"] == "INCOMPLETE", "gates[] alone said PASSED; the drop must override it"
    assert validate_gate_battery_receipt(receipt) == []


def test_cleanup_failure_cannot_change_the_batterys_exit_code(tmp_path: Path) -> None:
    """The receipt's own cleanup must never overwrite the battery's verdict.

    `_gbr_emit_receipt` ends by removing the temp gate log. Under `set -o errexit` a failing `rm`
    inside the trap aborts the handler *before* `exit "$final_rc"`, so the shell exits with rm's
    status instead of the battery's -- turning a red battery (exit 9) into exit 1, and a green one
    into a false red. That is exactly the failure this module exists to prevent ("the battery's
    pass/fail verdict must never depend on whether its own bookkeeping succeeded"), reintroduced
    by its own cleanup.

    Provoked by leaving the gate log as something `rm -f` refuses (a directory). The verdict must
    still be the gate's own exit code.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'gate "first" true\n'
        'rm -f "$GATE_LOG" && mkdir "$GATE_LOG"\n'  # cleanup will now fail
        'gate "second" bash -c "exit 9"\n',
    )
    receipt_path = tmp_path / "receipt.json"

    result = _run(script, "--receipt", str(receipt_path))

    assert result.returncode == 9, (
        "cleanup failure must not rewrite the verdict "
        f"(got {result.returncode}; 1 means the trap's rm aborted the handler)"
    )


def test_env_var_absolute_path_never_leaks_into_receipt(tmp_path: Path) -> None:
    """Mirrors ci.sh's own real pattern: PYO3_PYTHON is exported as an absolute path (derived
    from sys.executable) before the cargo gate runs. A receipt only ever records a gate's argv,
    never its environment, so this must never appear in the emitted JSON."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    script = _write_battery(
        tmp_path,
        repo,
        'export PYO3_PYTHON="<user_home>/.venv/bin/python3"\n'
        'gate "rust validator build" cargo build --manifest-path builder_ii_validation_rs/Cargo.toml\n',
    )
    receipt_path = tmp_path / "receipt.json"

    # cargo may fail here (no such manifest in this throwaway repo) -- irrelevant; the
    # assertion is only about what the receipt records, never about the gate passing.
    _run(script, "--receipt", str(receipt_path))

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    dumped = json.dumps(receipt)
    assert "<user_home>/.venv/bin/python3" not in dumped
    assert str(REPO_ROOT) not in dumped
    assert str(tmp_path) not in dumped
    assert find_absolute_paths(receipt) == []
