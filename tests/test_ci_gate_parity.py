"""Pin: the CI workflow and the local gate battery are ONE definition, not two copies.

The gate battery is `scripts/ci.sh`. `.github/workflows/ci.yml` must provision an
environment and then call it -- never inline a gate of its own. Without this pin the
two drift silently, and "I ran the gates locally" stops meaning "I ran what CI runs".

This is the same shape the rest of the codebase uses: one definition, one paired
validator. Here the validator is a test rather than a `validate-*` command, because
the artifact is a shell script rather than a `kind`-tagged JSON document.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CI_SCRIPT = REPO_ROOT / "scripts" / "ci.sh"
SECRET_SCAN = REPO_ROOT / "scripts" / "secret_scan.py"

# Every blocking gate, as it must appear in scripts/ci.sh.
REQUIRED_GATES: tuple[str, ...] = (
    "cargo build --manifest-path builder_ii_validation_rs/Cargo.toml",
    "compileall -q builder_ii tests",
    "builder-platform audit-docs",
    "builder-platform matrix",
    "scripts/secret_scan.py",
    "ruff check builder_ii tests",
    "uv run mypy",
    "bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607",
    "uv run pytest",
)

# Substrings that must NOT appear in a `run:` line of the workflow: they would mean a
# gate was inlined there instead of living in scripts/ci.sh.
FORBIDDEN_IN_WORKFLOW_RUNS: tuple[str, ...] = (
    "uv run pytest",
    "uv run ruff",
    "uv run mypy",
    "uv run bandit",
    "compileall",
    "builder-platform",
    "cargo build",
)


def _workflow_run_lines() -> list[str]:
    """Lines of ci.yml that are shell, not comments/keys -- i.e. `run:` bodies."""
    lines: list[str] = []
    in_run_block = False
    for raw in CI_WORKFLOW.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("run:"):
            in_run_block = True
            lines.append(stripped.removeprefix("run:").strip())
            continue
        if in_run_block:
            # A new YAML key at list-item level ends the run block.
            if stripped.startswith("- ") or (stripped.endswith(":") and " " not in stripped):
                in_run_block = False
                continue
            lines.append(stripped)
    return [line for line in lines if line and line != "|"]


def test_ci_script_and_secret_scan_exist() -> None:
    assert CI_SCRIPT.is_file(), "scripts/ci.sh is the single source of truth for the gate battery"
    assert SECRET_SCAN.is_file(), "the secret scan must be a file, not an inline workflow heredoc"


def test_workflow_delegates_to_the_gate_battery() -> None:
    body = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/ci.sh" in body, "ci.yml must call scripts/ci.sh"


def test_workflow_inlines_no_gate() -> None:
    run_lines = _workflow_run_lines()
    assert run_lines, "expected at least one `run:` line in ci.yml"
    for line in run_lines:
        for forbidden in FORBIDDEN_IN_WORKFLOW_RUNS:
            assert forbidden not in line, (
                f"ci.yml inlines the gate {forbidden!r} in {line!r}; "
                "add it to scripts/ci.sh instead so local runs match CI"
            )


def test_gate_battery_contains_every_blocking_gate() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for gate in REQUIRED_GATES:
        assert gate in script, f"scripts/ci.sh is missing the blocking gate: {gate!r}"


def test_gate_battery_never_pipes_a_gate_into_a_pager() -> None:
    """Piping a gate into head/tail reports the PAGER's exit status, so a red gate reads green."""
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for line in script.splitlines():
        if line.strip().startswith("#"):
            continue
        assert "| tail" not in line and "| head" not in line, (
            f"scripts/ci.sh pipes a gate into a pager, masking its exit code: {line!r}"
        )


def test_gate_battery_does_not_double_quiet_pytest() -> None:
    """pyproject's addopts already carries -q; a second -q suppresses the pass/fail summary."""
    script = CI_SCRIPT.read_text(encoding="utf-8")
    assert "uv run pytest -q" not in script, "pyproject addopts already sets -q; `-qq` hides the summary line"


def test_gate_battery_sets_strict_shell_flags() -> None:
    script = CI_SCRIPT.read_text(encoding="utf-8")
    for flag in ("set -o errexit", "set -o nounset", "set -o pipefail"):
        assert flag in script, f"scripts/ci.sh must {flag} so a failing gate aborts the battery"
