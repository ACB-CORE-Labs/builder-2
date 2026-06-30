from __future__ import annotations

import sys
from pathlib import Path

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.platform_completion_audit import (
    render_human_summary,
    validate_command_surfaces,
    validate_completion_matrix,
)


def _registry_names() -> set[str]:
    return {record.name for record in COMMAND_AUTHORITY_REGISTRY}


def run_platform_status() -> int:
    """Run the platform status proof used by the first bounded verification profile."""
    errors = validate_completion_matrix(root=Path.cwd())
    errors.extend(validate_command_surfaces(_registry_names()))
    if errors:
        for error in errors:
            print(f"platform truth validation error: {error}", file=sys.stderr)
        return 1
    print(render_human_summary(), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["platform-status"]:
        return run_platform_status()
    print("unsupported verification runner entrypoint", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
