from __future__ import annotations

import json as json_lib
import os
import signal
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.adapters.goose.goose_command_proposal import (
    create_goose_command_proposal_from_manifest_file,
    dumps_goose_command_proposal,
    validate_goose_command_proposal_file,
    write_goose_command_proposal,
)
from builder_ii.adapters.goose.goose_inspection import (
    DEFAULT_MAX_READ_BYTES,
    create_readonly_inspection_audit_from_manifest_file,
    dumps_readonly_inspection_audit,
    validate_readonly_inspection_audit_file,
    write_readonly_inspection_audit,
)
from builder_ii.adapters.goose.goose_readonly import (
    create_readonly_runtime_audit_from_manifest_file,
    dumps_readonly_runtime_audit,
    validate_readonly_runtime_audit_file,
    write_readonly_runtime_audit,
)
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.adapters.goose.goose_session import (
    GooseRuntimeMode,
    create_goose_session_manifest,
    dumps_goose_session_manifest,
    validate_goose_session_manifest,
    validate_goose_session_manifest_file,
    write_goose_session_manifest,
)
from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.config import load_settings
from builder_ii.governance.authority.policy_evaluator import enforce_command_authority
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_names
from builder_ii.routing.agent_profiles import AgentProfileName, agent_profile_names

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
    verification: Path | None = typer.Option(
        None, "--verification", help="Optional verification profile artifact path"
    ),
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
        echo_stdout(dumps_goose_session_manifest(session_manifest))


@goose_app.command("validate")
def validate(path: Path) -> None:
    """Validate a Goose session manifest artifact without starting Goose."""
    errors = validate_goose_session_manifest_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose session manifest {path} is valid.", soft_wrap=True)


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
        echo_stdout(dumps_readonly_runtime_audit(audit))


@goose_app.command("validate-audit")
def validate_audit(path: Path) -> None:
    """Validate a Goose read-only runtime candidate audit artifact."""
    errors = validate_readonly_runtime_audit_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose read-only audit is valid: {path}", soft_wrap=True)


@goose_app.command("inspect-readonly")
def inspect_readonly(
    manifest_path: Path = typer.Argument(..., help="Goose session manifest path"),
    read_file: list[str] | None = typer.Option(
        None, "--read-file", help="Relative repository file path to inspect; repeatable"
    ),
    max_bytes: int = typer.Option(
        DEFAULT_MAX_READ_BYTES, "--max-bytes", help="Maximum bytes allowed per inspected file"
    ),
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
        echo_stdout(dumps_readonly_inspection_audit(audit))


@goose_app.command("validate-inspection")
def validate_inspection(path: Path) -> None:
    """Validate a Goose read-only inspection audit artifact."""
    errors = validate_readonly_inspection_audit_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose read-only inspection audit is valid: {path}", soft_wrap=True)


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
        echo_stdout(dumps_goose_command_proposal(proposal))


@goose_app.command("validate-command-proposal")
def validate_command_proposal(path: Path) -> None:
    """Validate a Goose command proposal artifact."""
    errors = validate_goose_command_proposal_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Goose command proposal is valid: {path}", soft_wrap=True)


@dataclass(frozen=True)
class GooseReadonlyLaunchPlan:
    """Manifest-derived session identity handed to `GooseRuntimeHarness` for a read-only launch."""

    target_name: str
    agent_profile: str
    recipe_name: str = "core-platform.yaml"
    model_tier: str = "3"
    mode: str = "read_only"


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

    plan = GooseReadonlyLaunchPlan(
        target_name=manifest_data.get("target", {}).get("name", "builder"),
        agent_profile=manifest_data.get("agent_profile", {}).get("name", "patch_planner"),
    )
    harness = GooseRuntimeHarness(settings, plan, settings.project_root)  # type: ignore[arg-type]

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


def _load_read_only_manifest(manifest_path: Path) -> dict:
    """Read a manifest and refuse anything that is not an explicit read_only session."""
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
    return manifest_data


@goose_app.command("start-governed")
def start_governed(
    manifest_path: Path = typer.Argument(..., help="Goose session manifest path"),
) -> None:
    """Launch Goose with the builder-II governed MCP server as its only tool surface.

    The reachable entry point for the governed interposition lane: Goose is pointed at
    `recipes/governed-readonly.yaml`, whose sole extension is `builder-mcp serve`, and its own
    builtins are stripped. Every tool call therefore travels the governed
    envelope -> receipt -> ledger ceremony -- read-only tools execute and are receipted, mutating
    tool classes are refused in-loop and ledgered as denied. This is a read-only runtime
    candidate, not an enabled capability: the in-loop apply path stays deny-by-default, and the
    no-mutation postflight fails the run if anything under the target moved.
    """
    manifest_data = _load_read_only_manifest(manifest_path)

    # Fail closed before anything is spawned.
    enforce_command_authority(
        "builder-goose start-governed",
        requested_effects=("runtime_start", "external_tool", "artifact_write"),
    )

    settings = load_settings()
    plan = GooseReadonlyLaunchPlan(
        target_name=manifest_data.get("target", {}).get("name", "builder"),
        agent_profile=manifest_data.get("agent_profile", {}).get("name", "patch_planner"),
        recipe_name=GooseRuntimeHarness.GOVERNED_RECIPE_NAME,
    )
    harness = GooseRuntimeHarness(settings, plan, settings.project_root)  # type: ignore[arg-type]

    try:
        receipt = harness.launch_governed()
        console.print(f"Launched governed Goose session {receipt['session_id']}")

        receipts_dir = settings.project_root / ".builder" / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = receipts_dir / f"{receipt['session_id']}_launch.json"
        receipt_path.write_text(json_lib.dumps(receipt, indent=2), encoding="utf-8")
        console.print(f"Launch receipt: {receipt_path}", soft_wrap=True)

        if harness._proc:
            harness._proc.wait()

        close_receipt, postflight = harness.close(receipt["digest"])
        close_path = receipts_dir / f"{receipt['session_id']}_close.json"
        close_path.write_text(json_lib.dumps(close_receipt, indent=2), encoding="utf-8")
        console.print(f"Close receipt: {close_path}", soft_wrap=True)

        if not postflight["valid"]:
            console.print("WARNING: Mutations detected during governed session!")
            for m in postflight["mutations_detected"]:
                console.print(f" - {m}")
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"Failed to launch governed Goose: {e}")
        raise typer.Exit(1)


@goose_app.command("run-governed")
def run_governed(
    manifest_path: Path = typer.Option(..., "--manifest", help="Goose session manifest path"),
    task: str = typer.Option(..., "--task", help="The task to hand the governed run"),
    enable_governed_apply: bool = typer.Option(
        False,
        "--enable-governed-apply",
        help="Set BUILDER_MCP_GOVERNED_APPLY for the child only; still requires a digest-bound approval.",
    ),
) -> None:
    """Run a governed Goose task headlessly, streaming its lifecycle onto the session ledger.

    The non-suspending counterpart to `start-governed`: instead of handing Goose the operator's
    terminal and blocking, this streams output to a run log and brackets the child with
    `goose_run_started` / `goose_run_completed` events on the chain the operator console tails.
    A run is therefore legible while it happens rather than only after it ends.

    Same governed boundary as `start-governed`: read-only tools through the MCP server, builtins
    stripped, no-mutation postflight on close. `--enable-governed-apply` sets the deny-by-default
    flag for the child process only and does not by itself permit a write -- the apply lane still
    re-validates a digest-bound approval at its own boundary and fails closed without one.
    """
    manifest_data = _load_read_only_manifest(manifest_path)

    enforce_command_authority(
        "builder-goose run-governed",
        requested_effects=("runtime_start", "external_tool", "artifact_write"),
    )

    settings = load_settings()
    plan = GooseReadonlyLaunchPlan(
        target_name=manifest_data.get("target", {}).get("name", "builder"),
        agent_profile=manifest_data.get("agent_profile", {}).get("name", "patch_planner"),
        recipe_name=GooseRuntimeHarness.GOVERNED_RECIPE_NAME,
    )
    harness = GooseRuntimeHarness(settings, plan, settings.project_root)  # type: ignore[arg-type]

    if enable_governed_apply:
        # Child-scoped only: this process sets it so the spawned MCP server inherits it, and
        # never exports it further. The flag unlocks the *lane*, not any particular write.
        os.environ["BUILDER_MCP_GOVERNED_APPLY"] = "1"

    session_dir = settings.project_root / ".builder" / "sessions" / harness.session_id
    log_path = session_dir / "goose_run.log"

    def _handle_stop(signum: int, _frame: object) -> None:
        # Stopping is always "signal the governed wrapper", never "kill Goose from elsewhere":
        # the wrapper checkpoints the request onto the chain, escalates TERM -> KILL only if
        # the child ignores it, and still runs the postflight below.
        harness.request_stop()

    previous_handler = signal.signal(signal.SIGTERM, _handle_stop)
    try:
        receipt, exit_code = harness.run_governed_streaming(task, log_path=log_path)
        console.print(f"Governed run {receipt['session_id']} exited with code {exit_code}")
        console.print(f"Run log: {log_path}", soft_wrap=True)

        receipts_dir = settings.project_root / ".builder" / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        (receipts_dir / f"{receipt['session_id']}_launch.json").write_text(
            json_lib.dumps(receipt, indent=2), encoding="utf-8"
        )

        close_receipt, postflight = harness.close(receipt["digest"])
        (receipts_dir / f"{receipt['session_id']}_close.json").write_text(
            json_lib.dumps(close_receipt, indent=2), encoding="utf-8"
        )

        if not postflight["valid"]:
            console.print("WARNING: Mutations detected during governed run!")
            for m in postflight["mutations_detected"]:
                console.print(f" - {m}")
            raise typer.Exit(1)
        if exit_code != 0:
            raise typer.Exit(exit_code)

    except typer.Exit:
        raise
    except (RuntimeError, FileNotFoundError) as e:
        # Fail closed and name the fallback rather than degrading into a run that silently
        # dropped the operator's task.
        console.print(f"Cannot start a governed run: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"Governed run failed: {e}")
        raise typer.Exit(1)
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


@goose_app.command("close-readonly")
def close_readonly(
    session_id: str = typer.Argument(..., help="Session ID to close"),
) -> None:
    """Report the close status of a governed Goose read-only session.

    `start-readonly` already waits for Goose to exit and writes both the close receipt and the
    no-mutation postflight before returning, so this command only matters for a session that was
    forcefully detached from its `start-readonly` process. It cannot reconstruct that process's
    in-memory preflight snapshot, so it never fabricates a postflight verdict for a detached
    session — it reports the close receipt already on disk, or says plainly that none exists.
    """
    settings = load_settings()
    receipts_dir = settings.project_root / ".builder" / "receipts"
    launch_path = receipts_dir / f"{session_id}_launch.json"
    close_path = receipts_dir / f"{session_id}_close.json"

    if not launch_path.exists():
        console.print(f"Launch receipt not found: {launch_path}")
        raise typer.Exit(1)

    if close_path.exists():
        try:
            close_receipt = json_lib.loads(close_path.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"Close receipt at {close_path} is unreadable: {e}", soft_wrap=True)
            raise typer.Exit(1) from e
        console.print(f"Session {session_id} was already closed by start-readonly.")
        # soft_wrap: a filesystem path is one token, and Rich's default word-wrap will break it
        # mid-filename at the console width (80 when stdout is not a terminal). A path split
        # across lines is unusable -- an operator cannot click or copy it, and a caller cannot
        # grep it. Whether it wrapped depended on the length of the host's temp directory, which
        # is why this only ever failed off my machine.
        console.print(f"Close receipt: {close_path}", soft_wrap=True)
        console.print(f"Exit code: {close_receipt.get('exit_code')}")
        return

    console.print(f"No close receipt found for session {session_id}; it did not exit through start-readonly.")
    console.print(
        "This process cannot reconstruct the original preflight snapshot, so it will not fabricate "
        "a no-mutation verdict. Confirm the Goose process is stopped and inspect the target tree "
        "manually (e.g. `git status`) before trusting it."
    )


@goose_app.command("env")
def env_cmd() -> None:
    """Print redacted Goose launch environment report."""
    from builder_ii.adapters.goose.goose_launcher import derive_goose_environment

    settings = load_settings()
    _, report = derive_goose_environment(settings)
    console.print(f"selected backend: {report['selected_backend']}")
    console.print(f"selected model alias: {report['selected_model_alias']}")
    console.print(f"Goose provider: {report['goose_provider']}")
    console.print(f"Goose model: {report['goose_model']}")
    console.print(f"provider host: {report['provider_host']}")
    console.print(f"key present: {report['key_present']}")
    console.print(f"recipe path: {report['recipe_path']}")
    console.print(f"MOIM file: {report['moim_file']}")
    console.print(f"whether launch is ready: {'yes' if report['launch_ready'] else 'no'}")


@goose_app.command("status")
def status_cmd(env_flag: bool = typer.Option(False, "--env", help="Print redacted environment report")) -> None:
    """Print Goose status or environment report."""
    if env_flag:
        env_cmd()
    else:
        from builder_ii.adapters.goose.goose_launcher import goose_status

        console.print(goose_status())


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess, not imported
    # Module entry point so a caller can invoke this governed CLI with a fixed argv
    # `(sys.executable, "-m", "builder_ii.cli.goose_cli", ...)` rather than relying on a
    # console script's location on PATH. Mirrors `builder_ii.verification_runner_entrypoints`,
    # which `verification_execution_runner` invokes the same way. Adds no command surface, so it
    # needs no `command_authority.py` record.
    goose_app()
