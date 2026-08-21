"""Closed, typed last-mile command seam for STRATUM.

This module is deliberately boring: the TUI may select one of these records, but
cannot provide an executable, shell, environment, cwd, timeout, or arbitrary
arguments.  The canonical CLI remains responsible for authority and artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from builder_ii.governance.authority import check_command_authority


@dataclass(frozen=True)
class StratumCommand:
    identity: str
    argv: tuple[str, ...]
    output: Path
    validator: Callable[[Path], list[str]]
    authority: str


@dataclass(frozen=True)
class InvocationObservation:
    command: str
    returncode: int | None
    cancelled: bool
    output: Path
    validation_errors: tuple[str, ...]

    @property
    def successful(self) -> bool:
        return self.returncode == 0 and not self.cancelled and not self.validation_errors


def _exists(path: Path) -> list[str]:
    return [] if path.exists() else [f"canonical output does not exist: {path}"]


def command_inventory() -> tuple[str, ...]:
    return tuple(_COMMANDS)


def build_command(identity: str, *, target: str, task: str, output_root: Path) -> StratumCommand:
    if identity not in _COMMANDS:
        raise ValueError(f"STRATUM command is not admitted: {identity}")
    if target not in {"generic", "builder", "core"}:
        raise ValueError("target must be generic, builder, or core")
    if not task or len(task) > 2000:
        raise ValueError("task must be non-empty and at most 2000 characters")
    root = output_root.resolve()
    if identity == "builder-session prepare-package":
        output = root / "prepare-package"
        argv = ("builder-session", "prepare-package", target, "--output-dir", str(output), "--task", task)
    elif identity == "builder-session validate-prepare-package":
        output = root / "prepare-package"
        argv = ("builder-session", "validate-prepare-package", str(output))
    elif identity == "builder-deepagents assign-subagent":
        output = root / "subagent-assignment.json"
        argv = ("builder-deepagents", "assign-subagent", "--target", target, "--task", task,
                "--subagent-profile", "builder_full", "--work-plan", str(root / "work-plan.json"),
                "--output", str(output))
    elif identity == "builder-hitl approve-patch":
        output = root / "approval.json"
        argv = ("builder-hitl", "approve-patch", "--proposal", str(root / "proposal.json"), "--output", str(output))
    else:
        output = root / "refusal.json"
        argv = ("builder-hitl", "refuse-patch", "--proposal", str(root / "proposal.json"), "--output", str(output))
    return StratumCommand(identity, argv, output, _exists, identity)


_COMMANDS = (
    "builder-session prepare-package",
    "builder-session validate-prepare-package",
    "builder-deepagents assign-subagent",
    "builder-hitl approve-patch",
    "builder-hitl refuse-patch",
)


def admit(command: StratumCommand) -> None:
    if command.identity not in _COMMANDS or command.argv[:2] != tuple(command.identity.split()):
        raise PermissionError("command is not admitted by the STRATUM registry")
    decision = check_command_authority(command.authority)
    if not decision.allowed:
        raise PermissionError("command authority denied: " + ", ".join(decision.reasons))
