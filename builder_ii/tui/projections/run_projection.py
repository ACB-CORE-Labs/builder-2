"""Canonical read-only STRATUM lifecycle projection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

LIFECYCLE = ("PREPARE", "PLAN", "APPROVE", "EXECUTE", "VERIFY", "DELIVER/PROMOTE")


@dataclass(frozen=True)
class RunProjection:
    task: str
    stage: str
    next_action: str
    agents: tuple[str, ...]
    models: tuple[str, ...]
    budgets: dict[str, Any]
    approvals: str
    verification: str
    delivery: str
    evidence_health: str
    errors: tuple[str, ...] = ()


def _state(root: Path, name: str) -> tuple[bool, str | None]:
    path = root / name
    if not path.exists():
        return False, None
    if path.is_file():
        try:
            import json
            value = json.loads(path.read_text(encoding="utf-8"))
            return True, str(value.get("task", "")) if isinstance(value, dict) else None
        except (OSError, UnicodeError, ValueError):
            return False, "corrupt"
    return True, None


def project_run(root: Path, *, task: str = "") -> RunProjection:
    errors: list[str] = []
    prep, _ = _state(root, "prepare-package/prepare-package.json")
    plan, _ = _state(root, "work-plan.json")
    approval, _ = _state(root, "approval.json")
    verified, _ = _state(root, "verification.json")
    if any(value == "corrupt" for value in (_,)):
        errors.append("canonical evidence is corrupt")
    if not prep:
        stage, next_action = "PREPARE", "prepare-package"
    elif not plan:
        stage, next_action = "PLAN", "create-plan"
    elif not approval:
        stage, next_action = "APPROVE", "approve-patch"
    elif not verified:
        stage, next_action = "EXECUTE", "verify"
    else:
        stage, next_action = "VERIFY", "inspect-delivery-boundary"
    return RunProjection(task, stage, next_action, (), (), {}, "present" if approval else "absent",
                         "verified" if verified else "absent", "not-authorized", "corrupt" if errors else "healthy", tuple(errors))
