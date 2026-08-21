"""Closed, typed last-mile command seam for STRATUM.

This module is deliberately boring: the TUI may select one of these records, but
cannot provide an executable, shell, environment, cwd, timeout, or arbitrary
arguments.  The canonical CLI remains responsible for authority and artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from builder_ii.core.governed_prepare_package import validate_governed_prepare_package_directory
from builder_ii.governance.authority import check_command_authority


@dataclass(frozen=True)
class StratumCommand:
    identity: str
    entrypoint: str
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
    evidence: tuple[tuple[str, str], ...] = ()
    stderr: str = ""

    @property
    def successful(self) -> bool:
        return self.returncode == 0 and not self.cancelled and not self.validation_errors


def _package(path: Path) -> list[str]:
    return list(validate_governed_prepare_package_directory(path))


def _json(path: Path) -> list[str]:
    import json
    if not path.is_file():
        return [f"canonical output does not exist: {path}"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"canonical output is not valid JSON: {exc}"]
    return [] if isinstance(value, dict) else ["canonical output must be a JSON object"]


def command_inventory() -> tuple[str, ...]:
    return tuple(_COMMANDS)


def build_command(identity: str, *, target: str = "builder", task: str = "", output_root: Path,
                  profile: str | None = None, proposal: Path | None = None) -> StratumCommand:
    if identity not in _COMMANDS:
        raise ValueError(f"STRATUM command is not admitted: {identity}")
    if target not in {"generic", "builder", "core"}:
        raise ValueError("target must be generic, builder, or core")
    if task and len(task) > 2000:
        raise ValueError("task must be at most 2000 characters")
    root = output_root.resolve()
    invocation = root / "stratum" / uuid4().hex
    if identity == "builder-session prepare-package":
        output = invocation / "package"
        return StratumCommand(identity, "builder_ii.cli.session_cli", ("prepare-package", target, "--output-dir", str(output), "--task", task), output, _package, identity)
    elif identity == "builder-session validate-prepare-package":
        output = root / "stratum" / "current" / "package"
        return StratumCommand(identity, "builder_ii.cli.session_cli", ("validate-prepare-package", str(output)), output, _package, identity)
    elif identity == "builder-deepagents assign-subagent":
        chosen = profile or "builder_general"
        if chosen not in {"builder_general", "builder_reviewer", "builder_verifier"}:
            raise ValueError(f"invalid governed agent profile: {chosen}")
        output = invocation / "assignment.json"
        return StratumCommand(identity, "builder_ii.cli.deepagents_cli", ("assign-subagent", "--target", target, "--task", task,
                "--subagent-profile", chosen, "--work-plan", str(root / "work-plan.json"), "--output", str(output)), output, _json, identity)
    elif identity == "builder-hitl approve-patch":
        output = invocation / "approval.json"
        proposal = proposal or root / "proposal.json"
        return StratumCommand(identity, "builder_ii.cli.hitl_execution_cli", ("approve-patch", "--proposal", str(proposal), "--output", str(output)), output, _json, identity)
    else:
        output = invocation / "refusal.json"
        proposal = proposal or root / "proposal.json"
        return StratumCommand(identity, "builder_ii.cli.hitl_execution_cli", ("refuse-patch", "--proposal", str(proposal), "--output", str(output)), output, _json, identity)


_COMMANDS = (
    "builder-session prepare-package",
    "builder-session validate-prepare-package",
    "builder-deepagents assign-subagent",
    "builder-hitl approve-patch",
    "builder-hitl refuse-patch",
)


def admit(command: StratumCommand) -> None:
    if command.identity not in _COMMANDS or command.entrypoint not in {
        "builder_ii.cli.session_cli", "builder_ii.cli.deepagents_cli", "builder_ii.cli.hitl_execution_cli"
    }:
        raise PermissionError("command is not admitted by the STRATUM registry")
    decision = check_command_authority(command.authority)
    if not decision.allowed:
        raise PermissionError("command authority denied: " + ", ".join(decision.reasons))
