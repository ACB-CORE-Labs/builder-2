from __future__ import annotations

import sys
from pathlib import Path

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.platform_completion_audit import (
    render_human_summary,
    scan_docs_for_false_completion,
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


def run_docs_audit() -> int:
    """Run the docs truth audit used by the bounded docs_audit profile."""
    errors = validate_completion_matrix(root=Path.cwd())
    errors.extend(validate_command_surfaces(_registry_names()))
    for violation in scan_docs_for_false_completion(Path.cwd()):
        errors.append(f"false completion claim in {violation.path}:{violation.line_number}: {violation.reason}")
    if errors:
        for error in errors:
            print(f"docs truth validation error: {error}", file=sys.stderr)
        return 1
    print("docs truth audit passed")
    return 0


def run_pytest_full() -> int:
    """Run the target repository's full pytest suite for the bounded pytest_full profile.

    This executes the TARGET repository's own code -- pytest imports and runs its
    conftest.py, plugins, and test modules in this process. It runs only as a fixed-argv
    subprocess under the bounded runner's shell=False / env-allowlist / timeout envelope,
    and only after the operator's explicit D7 execution-risk acknowledgment. `pytest` is
    imported lazily so this dependency is not loaded on the safe profiles' path.
    `-p no:cacheprovider` suppresses the `.pytest_cache` byproduct; `PYTHONDONTWRITEBYTECODE`
    (set by the runner) suppresses `__pycache__`.
    """
    import pytest

    return int(pytest.main(["-q", "-p", "no:cacheprovider"]))


def run_builder_full() -> int:
    """Run the full builder foundation lane: the target pytest suite plus platform-truth checks.

    Like pytest_full this executes target code (the pytest phase), so it is a
    target-code-executing profile and carries the same D7 acknowledgment requirement.
    """
    exit_code = run_pytest_full()
    if run_platform_status() != 0:
        exit_code = exit_code or 1
    if run_docs_audit() != 0:
        exit_code = exit_code or 1
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["platform-status"]:
        return run_platform_status()
    if args == ["docs-audit"]:
        return run_docs_audit()
    if args == ["pytest-full"]:
        return run_pytest_full()
    if args == ["builder-full"]:
        return run_builder_full()
    print("unsupported verification runner entrypoint", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
