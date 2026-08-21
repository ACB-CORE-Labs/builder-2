"""Passive, bounded onboarding readiness checks."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Readiness:
    name: str
    status: str
    detail: str
    remediation: str


def check_gh() -> Readiness:
    path = shutil.which("gh")
    if not path:
        return Readiness("github-cli", "unavailable", "gh was not found", "Install GitHub CLI and authenticate separately; builder init never does this.")
    try:
        proc = subprocess.run([path, "--version"], shell=False, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return Readiness("github-cli", "failed", "gh version probe failed", "Run `gh --version` and repair the local installation.")
    return Readiness("github-cli", "ready" if proc.returncode == 0 else "failed", proc.stdout.strip() or proc.stderr.strip(), "Repair `gh --version` before delivery.")


def passive_readiness() -> tuple[Readiness, ...]:
    return (check_gh(),)
