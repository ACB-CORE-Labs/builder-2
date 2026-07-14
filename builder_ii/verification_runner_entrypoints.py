from __future__ import annotations

import os
import sys
from pathlib import Path

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.platform_completion_audit import (
    render_human_summary,
    scan_docs_for_false_completion,
    validate_command_surfaces,
    validate_completion_matrix,
)

# Fixed relative path under the target repo (cwd for the bounded runner). Always written for
# pytest-bearing profiles so process_results can attach a digest-bound structured outcome.
DEFAULT_JUNIT_RELATIVE_PATH = ".builder/artifacts/verification-junit.xml"


def _junit_path() -> Path:
    override = os.environ.get("BUILDER_VERIFICATION_JUNIT_PATH", "").strip()
    if override:
        return Path(override)
    return Path(DEFAULT_JUNIT_RELATIVE_PATH)


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
    (set by the runner) suppresses `__pycache__`. Writes a junit-xml report under
    ``.builder/artifacts/`` (or ``BUILDER_VERIFICATION_JUNIT_PATH``) for structured outcomes.
    """
    import pytest

    junit_path = _junit_path()
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    return int(
        pytest.main(
            [
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={junit_path.as_posix()}",
            ]
        )
    )


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


def run_wrp_doctor_backends() -> int:
    """Bounded validation_only: WRP backend doctor (inventory health; no engines)."""
    import json

    from builder_ii.wrp.backend_registry import doctor_backends

    report = doctor_backends()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def run_wrp_patterns_prove() -> int:
    """Bounded validation_only: pure graph_runtime five-pattern mastery proof."""
    from builder_ii.wrp.pattern_proof import prove_patterns_entrypoint

    return prove_patterns_entrypoint()


def run_semantic_doctor() -> int:
    """Bounded validation_only: semantic RO doctor (detect-only)."""
    import json

    from builder_ii.semantic_readonly import doctor_semantic

    report = doctor_semantic(repo_path=Path.cwd())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def run_semantic_map() -> int:
    """Bounded validation_only: semantic RO map (create_repo_map, fixed max_files)."""
    import json

    from builder_ii.semantic_readonly import map_semantic

    art = map_semantic(Path.cwd(), target_name="builder", max_files=100)
    print(json.dumps(art, indent=2, sort_keys=True))
    return 0


def run_wrp_fleet_fidelity() -> int:
    """Bounded validation_only: fleet fidelity from pinned paths under .builder/verification/.

    Operator stages:
      .builder/verification/fleet-fidelity/allocation.json
      .builder/verification/fleet-fidelity/plan.json
    before run-approved. No free-form path args (fixed argv envelope).
    """
    import json

    from builder_ii.wrp.allocation_optimizer import fleet_fidelity_report

    base = Path.cwd() / ".builder" / "verification" / "fleet-fidelity"
    alloc_path = base / "allocation.json"
    plan_path = base / "plan.json"
    if not alloc_path.is_file() or not plan_path.is_file():
        print(
            "fleet-fidelity pinned inputs missing: "
            f"{alloc_path} and {plan_path} required",
            file=sys.stderr,
        )
        return 1
    allocation = json.loads(alloc_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = fleet_fidelity_report(allocation, plan)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


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
    if args == ["wrp-doctor-backends"]:
        return run_wrp_doctor_backends()
    if args == ["wrp-patterns-prove"]:
        return run_wrp_patterns_prove()
    if args == ["wrp-fleet-fidelity"]:
        return run_wrp_fleet_fidelity()
    if args == ["semantic-doctor"]:
        return run_semantic_doctor()
    if args == ["semantic-map"]:
        return run_semantic_map()
    print("unsupported verification runner entrypoint", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
