from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.config import load_settings
from builder_ii.deepagents_policy import (
    DeepAgentsMemoryMode,
    DeepAgentsSubagentResultMode,
    create_deepagents_policy_artifact,
    dumps_deepagents_policy_artifact,
    validate_deepagents_policy_artifact,
    validate_deepagents_policy_artifact_file,
    write_deepagents_policy_artifact,
)
from builder_ii.deepagents_readiness import (
    DeepAgentsReadinessMode,
    create_deepagents_readiness_artifact,
    dumps_deepagents_readiness_artifact,
    validate_deepagents_readiness_artifact,
    validate_deepagents_readiness_artifact_file,
    write_deepagents_readiness_artifact,
)
from builder_ii.target_profiles import TargetName, target_names


deepagents_app = typer.Typer(help="Create and validate artifact-only governed deepagents JSON.")
console = Console()
_VALID_TARGETS = set(target_names())
_VALID_MEMORY_MODES = {"disabled", "proposal_only", "approved"}
_VALID_SUBAGENT_MODES = {"trusted", "proposal_only"}
_VALID_READINESS_MODES = {"metadata_only", "import_check"}


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _memory_mode(value: str) -> DeepAgentsMemoryMode:
    if value not in _VALID_MEMORY_MODES:
        console.print("memory mode must be disabled, proposal_only, or approved")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _subagent_mode(value: str) -> DeepAgentsSubagentResultMode:
    if value not in _VALID_SUBAGENT_MODES:
        console.print("subagent result mode must be trusted or proposal_only")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _readiness_mode(value: str) -> DeepAgentsReadinessMode:
    if value not in _VALID_READINESS_MODES:
        console.print("readiness mode must be metadata_only or import_check")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _split_csv(value: str | None) -> list[str] | None:
    if value is None or not value.strip():
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


@deepagents_app.command("policy")
def policy(
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, core"),
    task: str = typer.Option("", "--task", help="Optional task description"),
    memory_mode: str = typer.Option("proposal_only", "--memory-mode", help="disabled, proposal_only, or approved"),
    subagent_result_mode: str = typer.Option("proposal_only", "--subagent-result-mode", help="trusted or proposal_only"),
    allow_tools: str | None = typer.Option(None, "--allow-tools", help="Comma-separated override allow list"),
    deny_tools: str | None = typer.Option(None, "--deny-tools", help="Comma-separated override deny list"),
    memory_prefix: list[str] | None = typer.Option(None, "--memory-prefix", help="Memory path prefix; repeatable"),
    audit_output: Path = typer.Option(
        Path(".builder/artifacts/deepagents-audit-events.json"),
        "--audit-output",
        help="Expected future audit event artifact path",
    ),
    output: Path | None = typer.Option(None, "--output", help="Write policy JSON to path"),
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
) -> None:
    """Create a governed deepagents policy artifact without constructing deepagents."""
    artifact = create_deepagents_policy_artifact(
        load_settings(),
        target_name=_target(target),
        task=task,
        memory_mode=_memory_mode(memory_mode),
        subagent_result_mode=_subagent_mode(subagent_result_mode),
        allow_tools=_split_csv(allow_tools),
        deny_tools=_split_csv(deny_tools),
        memory_prefixes=tuple(memory_prefix or ["/memories/"]),
        expected_audit_artifact=audit_output,
        generic_repo=generic_repo,
    )
    errors = validate_deepagents_policy_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_deepagents_policy_artifact(artifact, output)
        console.print(f"Deepagents policy artifact written to {output}")
    else:
        console.out(dumps_deepagents_policy_artifact(artifact), end="")


@deepagents_app.command("validate")
def validate(path: Path) -> None:
    """Validate a governed deepagents policy artifact without constructing deepagents."""
    errors = validate_deepagents_policy_artifact_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Deepagents policy artifact {path} is valid.")


@deepagents_app.command("readiness")
def readiness(
    mode: str = typer.Option("metadata_only", "--mode", help="metadata_only or import_check"),
    output: Path | None = typer.Option(None, "--output", help="Write readiness JSON to path"),
) -> None:
    """Create a deepagents dependency-readiness artifact without constructing an agent."""
    artifact = create_deepagents_readiness_artifact(mode=_readiness_mode(mode))
    errors = validate_deepagents_readiness_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_deepagents_readiness_artifact(artifact, output)
        console.print(f"Deepagents readiness artifact written to {output}")
    else:
        console.out(dumps_deepagents_readiness_artifact(artifact), end="")


@deepagents_app.command("validate-readiness")
def validate_readiness(path: Path) -> None:
    """Validate a deepagents dependency-readiness artifact without constructing an agent."""
    errors = validate_deepagents_readiness_artifact_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Deepagents readiness artifact {path} is valid.")
