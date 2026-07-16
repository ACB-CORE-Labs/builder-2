"""Phase 3 – Deterministic Harness: Proposer/Verifier execution loop.

run_verification() is the Verifier. It:
  1. Maps the modified module to the correct CORE test suite (via routing.py).
  2. Invokes the CORE CLI test runner with precise, targeted arguments.
  3. Returns a VerifyResult with full stdout/stderr for upstream diagnosis.

format_verify_report() renders the result for CLI display:
  - PASS: single-line summary
  - FAIL: suite + command + 30-line tail for upstream diagnosis
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.config import Settings
from builder_ii.routing import suite_for_module, suite_rationale

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyResult:
    suite: str
    module: str | None
    rationale: str
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    summary_line: str | None
    elapsed_seconds: float | None  # None if timing not available


# ---------------------------------------------------------------------------
# Pytest output parsing
# ---------------------------------------------------------------------------

_PYTEST_SUMMARY = re.compile(r"^(=+\s*)?(\d+)\s+(passed|failed|error|skipped).*$", re.MULTILINE)
_PYTEST_DURATION = re.compile(r"(\d+\.\d+)s", re.IGNORECASE)


def parse_pytest_summary(output: str) -> tuple[bool, str | None, float | None]:
    """Return (passed, summary_line, elapsed_seconds)."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary: str | None = None
    elapsed: float | None = None

    for line in reversed(lines):
        # Duration extraction
        if elapsed is None and "passed" in line:
            m = _PYTEST_DURATION.search(line)
            if m:
                elapsed = float(m.group(1))

        if "passed" in line and "failed" not in line and "error" not in line:
            if _PYTEST_SUMMARY.match(line) or line.endswith("passed"):
                return True, line, elapsed
        if "failed" in line or "error" in line:
            summary = line

    return False, summary, elapsed


# ---------------------------------------------------------------------------
# CORE CLI invocation
# ---------------------------------------------------------------------------


def _core_invocation(settings: Settings, suite: str, extra_args: list[str]) -> list[str]:
    core_bin = shutil.which("core")
    base = ["test", "--suite", suite, *extra_args]
    if core_bin:
        return [core_bin, *base]

    repo = settings.core_repo
    uv = shutil.which("uv")
    if uv and (repo / "pyproject.toml").exists():
        return [uv, "run", "--project", str(repo), "python", "-m", "core.cli", *base]

    return ["python", "-m", "core.cli", *base]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def run_verification(
    settings: Settings,
    *,
    module: str | None = None,
    suite: str | None = None,
    extra_args: list[str] | None = None,
    cwd: Path | None = None,
    fail_fast: bool = False,
) -> VerifyResult:
    """Run the CORE test suite targeted to the modified module.

    Args:
        module:     Path of the changed file (relative to CORE root).
                    Drives automatic suite selection via routing table.
        suite:      Override suite name directly (skips routing).
        extra_args: Additional pytest flags.
        cwd:        Working directory (defaults to settings.core_repo).
        fail_fast:  If True, passes -x to pytest to stop on first failure.
    """
    resolved_suite = suite or (suite_for_module(module) if module else "smoke")
    rationale = suite_rationale(module) if module and not suite else "explicit suite override"
    base_args = ["-q", "--tb=short"]
    if fail_fast:
        base_args.append("-x")
    args = extra_args or base_args
    command = tuple(_core_invocation(settings, resolved_suite, args))
    workdir = cwd or settings.core_repo

    proc = subprocess.run(
        list(command),
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    passed, summary, elapsed = parse_pytest_summary(combined)
    if proc.returncode != 0:
        passed = False

    return VerifyResult(
        suite=resolved_suite,
        module=module,
        rationale=rationale,
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        passed=passed,
        summary_line=summary,
        elapsed_seconds=elapsed,
    )


def format_verify_report(result: VerifyResult) -> str:
    """Render a VerifyResult for CLI display."""
    status = "PASS ✓" if result.passed else "FAIL ✗"
    lines = [
        f"VERIFICATION {status}",
        f"suite    : {result.suite}",
        f"command  : {' '.join(result.command)}",
    ]
    if result.module:
        lines.append(f"module   : {result.module}")
        lines.append(f"rationale: {result.rationale}")
    if result.elapsed_seconds is not None:
        lines.append(f"elapsed  : {result.elapsed_seconds:.2f}s")
    if result.summary_line:
        lines.append(f"summary  : {result.summary_line}")
    if not result.passed:
        tail = (result.stdout + result.stderr).strip().splitlines()[-30:]
        lines.append("--- tail (last 30 lines) ---")
        lines.extend(tail)
    return "\n".join(lines)
