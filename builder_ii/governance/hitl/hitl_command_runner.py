from __future__ import annotations

from pathlib import Path

from builder_ii.core.config import Settings

RUN_COMMAND_DISABLED_MESSAGE = (
    "builder-hitl run-command is fail-closed until rebuilt as a fixed-profile bounded runner. "
    "Use builder-verify run-approved for governed bounded execution."
)


class RunCommandDisabledError(RuntimeError):
    """Raised when operator attempts arbitrary HITL command execution."""


def execute_hitl_command(
    request_path: Path,
    proposal_path: Path,
    approval_path: Path,
    output_dir: Path,
    settings: Settings | None = None,
) -> None:
    """Fail-closed: arbitrary approved command execution is not promoted."""
    _ = (request_path, proposal_path, approval_path, output_dir, settings)
    raise RunCommandDisabledError(RUN_COMMAND_DISABLED_MESSAGE)
