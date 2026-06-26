from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names
from builder_ii.config import load_settings
from builder_ii.goose_readonly import (
    create_readonly_runtime_audit_from_manifest_file,
    dumps_readonly_runtime_audit,
    validate_readonly_runtime_audit_file,
    write_readonly_runtime_audit,
)
from builder_ii.goose_inspection import (
    DEFAULT_MAX_READ_BYTES,
    create_readonly_inspection_audit_from_manifest_file,
    dumps_readonly_inspection_audit,
    validate_readonly_inspection_audit_file,
    write_readonly_inspection_audit,
)
from builder_ii.goose_session import (
    GooseRuntimeMode,
    create_goose_session_manifest,
    dumps_goose_session_manifest,
    validate_goose_session_manifest,
    validate_goose_session_manifest_file,
    write_goose_session_manifest,
)
from builder_ii.target_profiles import TargetName, target_names


goose_app = typer.Typer(help="Create and validate governed Goose artifacts without starting Goose.")
console = Console()
_VALID_AGENTS = set(agent_profile_names())
_VALID_TARGETS = set(target_names())
_VALID_MODES = {"disabled", "read_only"}


def _agent(value: str) -> AgentProfileName:
    if value not in _VALID_AGENTS:
        console.print("unknown agent profile")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _mode(value: str) -> GooseRuntimeMode:
    if value not in _VALID_MODES:
        console.print("mode must be disabled or read_only")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@goose_app.command("manifest")
def manifest(
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, core"),
    agent: str = typer.Option("patch_planner", "--agent", help="Agent profile to bind into the manifest"),
    mode: str = typer.Option("disabled", "--mode", help="Requested future runtime mode: disabled or read_only"),
    task: str = typer.Option("", "--task", help="Optional task description"),
    bundle: Path | None = typer.Option(None, "--bundle", help="Optional target bundle artifact path"),
    verification: Path | None = typer.Option(None, "--verification", help="Optional verification profile artifact path"),
    quality_gate: Path | None = typer.Option(None, "--quality-gate", help="Optional quality gate artifact path"),
    research_plan: Path | None = typer.Option(None, "--research-plan", help="Optional research plan artifact path"),
    handoff: Path | None = typer.Option(None, "--handoff", help="Optional handoff artifact path"),
    context_pack: Path | None = typer.Option(None, "--context-pack", help="Optional context pack path"),
    audit_output: Path = typer.Option(
        Path(".builder/artifacts/goose-runtime-audit.json"),
        "--audit-output",
        help="Expected future runtime audit artifact path",
    ),
    output: Path | None = typer.Option(None, "--output", help="Write Goose session manifest JSON to path"),
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
) -> None:
    """Create a Goose session manifest artifact without starting Goose."""
    settings = load_settings()
    session_manifest = create_goose_session_manifest(
        settings,
        target_name=_target(target),
        agent_profile=_agent(agent),
        runtime_mode=_mode(mode),
        task=task,
        target_bundle=bundle,
        verification_profile=verification,
        quality_gate=quality_gate,
        research_plan=research_plan,
        handoff=handoff,
        context_pack=context_pack,
        expected_audit_artifact=audit_output,
        generic_repo=generic_repo,
    )
    errors = validate_goose_session_manifest(session_manifest)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_goose_session_manifest(session_manifest, output)
        console.print(f"Goose session manifest written to {output}")
    else:
        console.out(dumps_goose_session_manifest(session_manifest), end="")


@goose_app.command("validate")
def validate(path: Path) -> None:
    """Validate a Goose session manifest artifact without starting Goose."""
    errors = validate_goose_session_manifest_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose session manifest {path} is valid.")


@goose_app.command("readonly-audit")
def readonly_audit(
    manifest_path: Path = typer.Argument(..., help="Goose session manifest path"),
    output: Path | None = typer.Option(None, "--output", help="Write read-only audit JSON to path"),
) -> None:
    """Create a read-only runtime candidate audit artifact without starting Goose."""
    audit, errors = create_readonly_runtime_audit_from_manifest_file(manifest_path, output_path=output)
    if errors or audit is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_readonly_runtime_audit(audit, output)
        console.print(f"Goose read-only audit written to {output}")
    else:
        console.out(dumps_readonly_runtime_audit(audit), end="")


@goose_app.command("validate-audit")
def validate_audit(path: Path) -> None:
    """Validate a Goose read-only runtime candidate audit artifact."""
    errors = validate_readonly_runtime_audit_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose read-only audit is valid: {path}")

@goose_app.command("inspect-readonly")
def inspect_readonly(
    manifest_path: Path = typer.Argument(..., help="Goose session manifest path"),
    read_file: list[str] | None = typer.Option(None, "--read-file", help="Relative repository file path to inspect; repeatable"),
    max_bytes: int = typer.Option(DEFAULT_MAX_READ_BYTES, "--max-bytes", help="Maximum bytes allowed per inspected file"),
    output: Path | None = typer.Option(None, "--output", help="Write read-only inspection JSON to path"),
) -> None:
    """Create a bounded read-only inspection audit without starting Goose."""
    audit, errors = create_readonly_inspection_audit_from_manifest_file(
        manifest_path,
        read_paths=read_file or [],
        output_path=output,
        max_bytes=max_bytes,
    )
    if errors or audit is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_readonly_inspection_audit(audit, output)
        console.print(f"Goose read-only inspection audit written to {output}")
    else:
        console.out(dumps_readonly_inspection_audit(audit), end="")


@goose_app.command("validate-inspection")
def validate_inspection(path: Path) -> None:
    """Validate a Goose read-only inspection audit artifact."""
    errors = validate_readonly_inspection_audit_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose read-only inspection audit is valid: {path}")

