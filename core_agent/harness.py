from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core_agent.config import Settings
from core_agent.routing import suite_for_module


@dataclass(frozen=True)
class VerifyResult:
    suite: str
    module: str | None
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    summary_line: str | None


_PYTEST_SUMMARY = re.compile(
    r"^(=+\s*)?(\d+)\s+(passed|failed|error|skipped).*$", re.MULTILINE
)


def parse_pytest_summary(output: str) -> tuple[bool, str | None]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in reversed(lines):
        if "passed" in line and "failed" not in line and "error" not in line:
            if _PYTEST_SUMMARY.match(line) or line.endswith("passed"):
                return True, line
        if "failed" in line or "error" in line:
            return False, line
    return False, None


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


def run_verification(
    settings: Settings,
    *,
    module: str | None = None,
    suite: str | None = None,
    extra_args: list[str] | None = None,
    cwd: Path | None = None,
) -> VerifyResult:
    resolved_suite = suite or (suite_for_module(module) if module else "smoke")
    args = extra_args or ["-q", "--tb=short"]
    command = tuple(_core_invocation(settings, resolved_suite, args))
    workdir = cwd or settings.core_repo

    proc = subprocess.run(
        list(command),
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    passed, summary = parse_pytest_summary(combined)
    if proc.returncode != 0:
        passed = False

    return VerifyResult(
        suite=resolved_suite,
        module=module,
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        passed=passed,
        summary_line=summary,
    )


def format_verify_report(result: VerifyResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"VERIFICATION {status}",
        f"suite: {result.suite}",
        f"command: {' '.join(result.command)}",
    ]
    if result.module:
        lines.append(f"module: {result.module}")
    if result.summary_line:
        lines.append(f"summary: {result.summary_line}")
    if not result.passed:
        tail = (result.stdout + result.stderr).strip().splitlines()[-20:]
        lines.append("--- tail ---")
        lines.extend(tail)
    return "\n".join(lines)