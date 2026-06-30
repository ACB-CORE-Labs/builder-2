from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

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
from builder_ii.deepagents_work_artifacts import (
    create_deepagents_work_plan,
    create_deepagents_subagent_assignment,
    create_deepagents_subagent_result,
    create_deepagents_subagent_review,
    create_deepagents_human_gate_request,
    create_deepagents_blocked_action_record,
    create_deepagents_proposal_result,
    validate_deepagents_work_plan,
    validate_deepagents_subagent_assignment,
    validate_deepagents_subagent_result,
    validate_deepagents_subagent_review,
    validate_deepagents_human_gate_request,
    validate_deepagents_blocked_action_record,
    validate_deepagents_proposal_result,
    validate_deepagents_work_validation_report,
    write_deepagents_work_plan,
    write_deepagents_subagent_assignment,
    write_deepagents_subagent_result,
    write_deepagents_subagent_review,
    write_deepagents_human_gate_request,
    write_deepagents_blocked_action_record,
    write_deepagents_proposal_result,
    dumps_deepagents_work_plan,
    dumps_deepagents_subagent_assignment,
    dumps_deepagents_subagent_result,
    dumps_deepagents_subagent_review,
    dumps_deepagents_human_gate_request,
    dumps_deepagents_blocked_action_record,
    dumps_deepagents_proposal_result,
)

deepagents_app = typer.Typer(
    help="Create and validate artifact-only governed deepagents JSON."
)
console = Console(width=240)
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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        console.print(f"File not found: {path}")
        raise typer.Exit(1)
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            console.print(f"File must contain a JSON object: {path}")
            raise typer.Exit(1)
        return data
    except Exception as exc:
        console.print(f"Failed to parse JSON file {path}: {exc}")
        raise typer.Exit(1)


@deepagents_app.command("policy")
def policy(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    task: str = typer.Option("", "--task", help="Optional task description"),
    memory_mode: str = typer.Option(
        "proposal_only", "--memory-mode", help="disabled, proposal_only, or approved"
    ),
    subagent_result_mode: str = typer.Option(
        "proposal_only", "--subagent-result-mode", help="trusted or proposal_only"
    ),
    allow_tools: str | None = typer.Option(
        None, "--allow-tools", help="Comma-separated override allow list"
    ),
    deny_tools: str | None = typer.Option(
        None, "--deny-tools", help="Comma-separated override deny list"
    ),
    memory_prefix: list[str] | None = typer.Option(
        None, "--memory-prefix", help="Memory path prefix; repeatable"
    ),
    audit_output: Path = typer.Option(
        Path(".builder/artifacts/deepagents-audit-events.json"),
        "--audit-output",
        help="Expected future audit event artifact path",
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write policy JSON to path"
    ),
    generic_repo: Path | None = typer.Option(
        None, "--generic-repo", help="Repo path for the generic target"
    ),
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
    console.print(f"Deepagents policy artifact is valid: {path}")


@deepagents_app.command("readiness")
def readiness(
    mode: str = typer.Option(
        "metadata_only", "--mode", help="metadata_only or import_check"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write readiness JSON to path"
    ),
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
    console.print(f"Deepagents readiness artifact is valid: {path}")


@deepagents_app.command("delegate")
def delegate() -> None:
    """Fail closed for unpromoted active deepagents delegation."""
    console.print(
        "builder-deepagents delegate is forbidden/unpromoted; use passive artifacts only."
    )
    raise typer.Exit(1)


# Goal 3 Commands


@deepagents_app.command("work-plan")
def work_plan(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    task: str = typer.Option(..., "--task", help="Task description"),
    assignment_plan: Path = typer.Option(
        ..., "--assignment-plan", help="Path to agent assignment plan JSON"
    ),
    assignment_dry_run: Path = typer.Option(
        ..., "--assignment-dry-run", help="Path to orchestration dry-run JSON"
    ),
    policy_path: Path = typer.Option(
        ..., "--policy", help="Path to deepagents governed policy JSON"
    ),
    readiness_path: Path = typer.Option(
        ..., "--readiness", help="Path to deepagents dependency readiness JSON"
    ),
    proposed_subagents: str | None = typer.Option(
        None, "--proposed-subagents", help="Comma-separated proposed subagents"
    ),
    expected_outputs: str | None = typer.Option(
        None, "--expected-outputs", help="Comma-separated expected outputs"
    ),
    review_gates: str | None = typer.Option(
        None, "--review-gates", help="Comma-separated review gates"
    ),
    blocked_capabilities: str | None = typer.Option(
        None, "--blocked-capabilities", help="Comma-separated blocked capabilities"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write work plan JSON to path"
    ),
) -> None:
    """Create a passive deepagents work plan artifact."""
    plan_data = _load_json(assignment_plan)
    dry_run_data = _load_json(assignment_dry_run)
    policy_data = _load_json(policy_path)
    readiness_data = _load_json(readiness_path)

    artifact = create_deepagents_work_plan(
        target=_target(target),
        task=task,
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
        orchestration_assignment_plan_path=assignment_plan,
        orchestration_assignment_dry_run_path=assignment_dry_run,
        deepagents_policy_path=policy_path,
        deepagents_readiness_path=readiness_path,
        proposed_subagents=_split_csv(proposed_subagents),
        expected_outputs=_split_csv(expected_outputs),
        review_gates=_split_csv(review_gates),
        blocked_capabilities=_split_csv(blocked_capabilities),
    )

    if output is not None:
        write_deepagents_work_plan(artifact, output)
        console.print(f"Deepagents work plan written to {output}")
    else:
        console.out(dumps_deepagents_work_plan(artifact), end="")


@deepagents_app.command("assign-subagent")
def assign_subagent(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    task: str = typer.Option(..., "--task", help="Task description for subagent"),
    subagent_profile: str = typer.Option(
        ..., "--subagent-profile", help="Subagent profile name"
    ),
    work_plan_path: Path = typer.Option(
        ..., "--work-plan", help="Path to deepagents work plan JSON"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write subagent assignment JSON to path"
    ),
) -> None:
    """Create a passive deepagents subagent assignment artifact."""
    plan_data = _load_json(work_plan_path)

    artifact = create_deepagents_subagent_assignment(
        target=_target(target),
        task=task,
        subagent_profile=subagent_profile,
        work_plan=plan_data,
        work_plan_path=work_plan_path,
    )

    if output is not None:
        write_deepagents_subagent_assignment(artifact, output)
        console.print(f"Subagent assignment written to {output}")
    else:
        console.out(dumps_deepagents_subagent_assignment(artifact), end="")


@deepagents_app.command("record-result")
def record_result(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    subagent_profile: str = typer.Option(
        ..., "--subagent-profile", help="Subagent profile name"
    ),
    summary: str = typer.Option(..., "--summary", help="Result summary text"),
    subagent_assignment_path: Path = typer.Option(
        ..., "--subagent-assignment", help="Path to subagent assignment JSON"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write subagent result JSON to path"
    ),
) -> None:
    """Create a passive deepagents subagent result artifact."""
    assignment_data = _load_json(subagent_assignment_path)

    artifact = create_deepagents_subagent_result(
        target=_target(target),
        subagent_profile=subagent_profile,
        summary=summary,
        subagent_assignment=assignment_data,
        subagent_assignment_path=subagent_assignment_path,
    )

    if output is not None:
        write_deepagents_subagent_result(artifact, output)
        console.print(f"Subagent result written to {output}")
    else:
        console.out(dumps_deepagents_subagent_result(artifact), end="")


@deepagents_app.command("review-result")
def review_result_command(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    disposition: str = typer.Option(
        ..., "--disposition", help="accepted_as_proposal, needs_revision, or rejected"
    ),
    subagent_result_path: Path = typer.Option(
        ..., "--subagent-result", help="Path to subagent result JSON"
    ),
    subagent_assignment_path: Path = typer.Option(
        ..., "--subagent-assignment", help="Path to subagent assignment JSON"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write subagent review JSON to path"
    ),
) -> None:
    """Create a passive deepagents subagent review artifact."""
    result_data = _load_json(subagent_result_path)
    assignment_data = _load_json(subagent_assignment_path)

    artifact = create_deepagents_subagent_review(
        target=_target(target),
        disposition=disposition,
        subagent_result=result_data,
        subagent_assignment=assignment_data,
        subagent_result_path=subagent_result_path,
        subagent_assignment_path=subagent_assignment_path,
    )

    if output is not None:
        write_deepagents_subagent_review(artifact, output)
        console.print(f"Subagent review written to {output}")
    else:
        console.out(dumps_deepagents_subagent_review(artifact), end="")


@deepagents_app.command("request-human-gate")
def request_human_gate(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    reviewed_artifact_path: Path = typer.Option(
        ..., "--reviewed-artifact", help="Path to reviewed artifact JSON"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write human gate request JSON to path"
    ),
) -> None:
    """Create a passive deepagents human gate request artifact."""
    reviewed_data = _load_json(reviewed_artifact_path)

    artifact = create_deepagents_human_gate_request(
        target=_target(target),
        reviewed_artifact=reviewed_data,
        reviewed_artifact_path=reviewed_artifact_path,
    )

    if output is not None:
        write_deepagents_human_gate_request(artifact, output)
        console.print(f"Human gate request written to {output}")
    else:
        console.out(dumps_deepagents_human_gate_request(artifact), end="")


@deepagents_app.command("record-blocked-action")
def record_blocked_action(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    denied_capability: str = typer.Option(
        ..., "--denied-capability", help="Blocked capability name"
    ),
    triggering_artifact_path: Path | None = typer.Option(
        None, "--triggering-artifact", help="Optional triggering artifact JSON path"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write blocked action record JSON to path"
    ),
) -> None:
    """Create a passive deepagents blocked action record artifact."""
    triggering_data = None
    if triggering_artifact_path is not None:
        triggering_data = _load_json(triggering_artifact_path)

    artifact = create_deepagents_blocked_action_record(
        target=_target(target),
        denied_capability=denied_capability,
        triggering_artifact=triggering_data,
        triggering_artifact_path=triggering_artifact_path,
    )

    if output is not None:
        write_deepagents_blocked_action_record(artifact, output)
        console.print(f"Blocked action record written to {output}")
    else:
        console.out(dumps_deepagents_blocked_action_record(artifact), end="")


@deepagents_app.command("proposal-result")
def proposal_result(
    target: str = typer.Option(
        "builder", "--target", help="Target profile: generic, builder, core"
    ),
    work_plan_path: Path = typer.Option(
        ..., "--work-plan", help="Path to deepagents work plan JSON"
    ),
    reviewed_result_path: list[Path] = typer.Option(
        ..., "--reviewed-result", help="Repeatable reviewed result path"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write proposal result JSON to path"
    ),
) -> None:
    """Create a passive deepagents proposal result artifact."""
    plan_data = _load_json(work_plan_path)
    results = [_load_json(p) for p in reviewed_result_path]

    artifact = create_deepagents_proposal_result(
        target=_target(target),
        work_plan=plan_data,
        reviewed_results=results,
        work_plan_path=work_plan_path,
        reviewed_result_paths=reviewed_result_path,
    )

    if output is not None:
        write_deepagents_proposal_result(artifact, output)
        console.print(f"Proposal result written to {output}")
    else:
        console.out(dumps_deepagents_proposal_result(artifact), end="")


@deepagents_app.command("validate-work-artifact")
def validate_work_artifact(path: Path) -> None:
    """Validate any passive deepagents work-output artifact."""
    data = _load_json(path)
    kind = data.get("kind")
    if not kind:
        console.print("Invalid artifact: missing 'kind' field")
        raise typer.Exit(1)

    validators = {
        "builder_ii.deepagents_work_plan": validate_deepagents_work_plan,
        "builder_ii.deepagents_subagent_assignment": validate_deepagents_subagent_assignment,
        "builder_ii.deepagents_subagent_result": validate_deepagents_subagent_result,
        "builder_ii.deepagents_subagent_review": validate_deepagents_subagent_review,
        "builder_ii.deepagents_human_gate_request": validate_deepagents_human_gate_request,
        "builder_ii.deepagents_blocked_action_record": validate_deepagents_blocked_action_record,
        "builder_ii.deepagents_proposal_result": validate_deepagents_proposal_result,
        "builder_ii.deepagents_work_validation_report": validate_deepagents_work_validation_report,
    }

    validator = validators.get(kind)
    if not validator:
        console.print(f"Unknown deepagents work artifact kind: {kind}")
        raise typer.Exit(1)

    errors = validator(data)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Deepagents work artifact is valid: {path}")
