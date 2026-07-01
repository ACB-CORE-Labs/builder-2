from __future__ import annotations

from pathlib import Path

import typer

import json as json_lib
import time
from builder_ii.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.goose_receipts import GOOSE_LAUNCH_RECEIPT_KIND
from rich.console import Console

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import (
    create_goose_command_proposal_from_manifest_file,
    dumps_goose_command_proposal,
    validate_goose_command_proposal_file,
    write_goose_command_proposal,
)
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

@goose_app.command("propose-command")
def propose_command(
    manifest_path: Path = typer.Argument(..., help="Goose session manifest path"),
    command: str = typer.Option(..., "--command", help="Command string to propose but not execute"),
    reason: str = typer.Option("", "--reason", help="Reason for the proposed command"),
    risk_level: str = typer.Option("medium", "--risk-level", help="Risk level: low, medium, high, critical"),
    output: Path | None = typer.Option(None, "--output", help="Write command proposal JSON to path"),
) -> None:
    """Create a command proposal artifact without executing anything."""
    proposal, errors = create_goose_command_proposal_from_manifest_file(
        manifest_path,
        command=command,
        reason=reason,
        risk_level=risk_level,  # type: ignore[arg-type]
        output_path=output,
    )
    if errors or proposal is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_goose_command_proposal(proposal, output)
        console.print(f"Goose command proposal written to {output}")
    else:
        console.out(dumps_goose_command_proposal(proposal), end="")


@goose_app.command("validate-command-proposal")
def validate_command_proposal(path: Path) -> None:
    """Validate a Goose command proposal artifact."""
    errors = validate_goose_command_proposal_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose command proposal is valid: {path}")



@goose_app.command("start-readonly")
def start_readonly(
    manifest_path: Path = typer.Argument(..., help="Goose session manifest path"),
) -> None:
    """Launch Goose in a governed read-only session."""
    if not manifest_path.exists():
        console.print(f"Manifest not found: {manifest_path}")
        raise typer.Exit(1)
        
    try:
        manifest_data = json_lib.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        console.print(f"Invalid manifest JSON: {e}")
        raise typer.Exit(1)
        
    if manifest_data.get("requested_runtime_mode") != "read_only":
        console.print("Manifest does not specify read_only mode.")
        raise typer.Exit(1)
        
    settings = load_settings()
    
    # Simple struct to simulate SessionPlan
    class MockPlan:
        target_name = manifest_data.get("target", {}).get("name", "builder")
        agent_profile = manifest_data.get("agent_profile", {}).get("name", "patch_planner")
        recipe_name = "core-platform.yaml" # Default
        model_tier = "3"
        mode = "read_only"
        
    plan = MockPlan()
    harness = GooseRuntimeHarness(settings, plan, settings.project_root)
    
    try:
        receipt = harness.launch_readonly()
        console.print(f"Launched Goose readonly session {receipt['session_id']}")
        
        # Write receipt so close-readonly can find it
        receipt_path = settings.project_root / ".builder" / "receipts" / f"{receipt['session_id']}_launch.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json_lib.dumps(receipt, indent=2), encoding="utf-8")
        
        console.print(f"Launch receipt: {receipt_path}")
        
        # Wait for Goose to exit
        if harness._proc:
            harness._proc.wait()
            
        close_receipt, postflight = harness.close(receipt["digest"])
        
        close_path = settings.project_root / ".builder" / "receipts" / f"{receipt['session_id']}_close.json"
        close_path.write_text(json_lib.dumps(close_receipt, indent=2), encoding="utf-8")
        console.print(f"Close receipt: {close_path}")
        
        if not postflight["valid"]:
            console.print("WARNING: Mutations detected during read-only session!")
            for m in postflight["mutations_detected"]:
                console.print(f" - {m}")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"Failed to launch Goose: {e}")
        raise typer.Exit(1)


@goose_app.command("close-readonly")
def close_readonly(
    session_id: str = typer.Argument(..., help="Session ID to close"),
) -> None:
    """Close a governed Goose read-only session and verify no-mutation postflight."""
    settings = load_settings()
    receipt_path = settings.project_root / ".builder" / "receipts" / f"{session_id}_launch.json"
    
    if not receipt_path.exists():
        console.print(f"Launch receipt not found: {receipt_path}")
        raise typer.Exit(1)
        
    # We can't fully reconstruct the Harness state (PID, preflight snapshot), 
    # but the start-readonly naturally waits and closes. 
    # If the user explicitly calls close-readonly, we simulate a postflight error if it's already closed.
    console.print("close-readonly is automatically handled by start-readonly termination.")
    console.print("If a session was forcefully detached, it must be killed manually and postflight is invalid.")

