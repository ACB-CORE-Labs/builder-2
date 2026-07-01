from __future__ import annotations

import hashlib
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
    validate_deepagents_runtime_envelope,
    validate_deepagents_subagent_execution_receipt,
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
from builder_ii.deepagents_runtime import DeepAgentsRuntimeHarness
from builder_ii.deepagents_execution import (
    BACKEND_MODES,
    DEEPAGENTS_BACKEND_READINESS_GATE_KIND,
    DEEPAGENTS_CHECKPOINT_KIND,
    DEEPAGENTS_EVENT_LEDGER_KIND,
    DEEPAGENTS_EVENT_RECORD_KIND,
    DEEPAGENTS_EVIDENCE_BUNDLE_KIND,
    DEEPAGENTS_EXECUTION_APPROVAL_KIND,
    DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    DEEPAGENTS_REPLAY_REPORT_KIND,
    DEEPAGENTS_RUN_ENVELOPE_KIND,
    PROTOCOL_FAKE_BACKEND,
    create_deepagents_backend_readiness_gate,
    create_deepagents_execution_approval,
    create_deepagents_execution_candidate,
    create_evidence_bundle_from_files,
    dumps_deepagents_backend_readiness_gate,
    dumps_deepagents_execution_approval,
    dumps_deepagents_execution_candidate,
    replay_deepagents_run,
    resume_deepagents_approved_candidate,
    run_deepagents_approved_candidate,
    validate_deepagents_checkpoint,
    validate_deepagents_backend_readiness_gate,
    validate_deepagents_event_ledger,
    validate_deepagents_event_record,
    validate_deepagents_evidence_bundle,
    validate_deepagents_execution_approval,
    validate_deepagents_execution_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_replay_report,
    validate_deepagents_run_envelope,
    write_deepagents_execution_approval,
    write_deepagents_execution_candidate,
    write_deepagents_backend_readiness_gate,
)

deepagents_app = typer.Typer(
    help="Create and validate artifact-only governed deepagents JSON."
)
console = Console(width=240)
_VALID_TARGETS = set(target_names())
_VALID_MEMORY_MODES = {"disabled", "proposal_only", "approved"}
_VALID_SUBAGENT_MODES = {"trusted", "proposal_only"}
_VALID_READINESS_MODES = {"metadata_only", "import_check"}
_VALID_BACKEND_MODES = set(BACKEND_MODES)


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


def _backend_mode(value: str) -> str:
    if value not in _VALID_BACKEND_MODES:
        console.print(f"backend mode must be one of: {', '.join(BACKEND_MODES)}")
        raise typer.Exit(1)
    return value


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
        "builder_ii.deepagents_runtime_envelope": validate_deepagents_runtime_envelope,
        "builder_ii.deepagents_subagent_execution_receipt": validate_deepagents_subagent_execution_receipt,
        DEEPAGENTS_EXECUTION_CANDIDATE_KIND: validate_deepagents_execution_candidate,
        DEEPAGENTS_EXECUTION_APPROVAL_KIND: validate_deepagents_execution_approval,
        DEEPAGENTS_RUN_ENVELOPE_KIND: validate_deepagents_run_envelope,
        DEEPAGENTS_EVENT_RECORD_KIND: validate_deepagents_event_record,
        DEEPAGENTS_EVENT_LEDGER_KIND: validate_deepagents_event_ledger,
        DEEPAGENTS_REPLAY_REPORT_KIND: validate_deepagents_replay_report,
        DEEPAGENTS_CHECKPOINT_KIND: validate_deepagents_checkpoint,
        DEEPAGENTS_EXECUTION_RECEIPT_KIND: validate_deepagents_execution_receipt,
        DEEPAGENTS_EVIDENCE_BUNDLE_KIND: validate_deepagents_evidence_bundle,
        DEEPAGENTS_BACKEND_READINESS_GATE_KIND: validate_deepagents_backend_readiness_gate,
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


@deepagents_app.command("run-plan")
def run_plan(
    work_plan: Path = typer.Option(..., "--work-plan", help="Path to deepagents work plan JSON"),
    output: Path = typer.Option(..., "--output", help="Write runtime envelope JSON to path"),
    receipts_dir: Path = typer.Option(..., "--receipts-dir", help="Directory to output subagent receipts"),
) -> None:
    """Execute deepagents/subagent planning under HITL without writes."""
    try:
        harness = DeepAgentsRuntimeHarness(load_settings(), work_plan)
        harness.run(output, receipts_dir)
        console.print(f"Deepagents runtime envelope written to {output}")
    except ImportError as exc:
        console.print(f"ImportError: {exc}")
        raise typer.Exit(1)
    except ValueError as exc:
        console.print(f"ValueError: {exc}")
        raise typer.Exit(1)


@deepagents_app.command("collect-results")
def collect_results(
    work_plan: Path = typer.Option(..., "--work-plan", help="Path to deepagents work plan JSON"),
    envelope: Path = typer.Option(..., "--envelope", help="Path to deepagents runtime envelope JSON"),
    output: Path = typer.Option(..., "--output", help="Write proposal result JSON to path"),
) -> None:
    """Collect deepagents planning results into a proposal result artifact."""
    try:
        harness = DeepAgentsRuntimeHarness(load_settings(), work_plan)
        harness.collect_results(envelope, output)
        console.print(f"Proposal result written to {output}")
    except Exception as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1)


@deepagents_app.command("execution-candidate")
def execution_candidate(
    work_plan: Path = typer.Option(
        ..., "--work-plan", help="Path to passive deepagents work plan JSON"
    ),
    output_root: Path = typer.Option(
        ..., "--output-root", help="Root directory allowed for promoted run artifacts"
    ),
    backend_mode: str = typer.Option(
        PROTOCOL_FAKE_BACKEND,
        "--backend-mode",
        help=f"Backend mode: {', '.join(BACKEND_MODES)}",
    ),
    backend_readiness_gate: Path | None = typer.Option(
        None,
        "--backend-readiness-gate",
        help="Required passing gate JSON when --backend-mode optional_deepagents",
    ),
    allowed_subagents: str | None = typer.Option(
        None,
        "--allowed-subagents",
        help="Comma-separated approved subagents; defaults to work plan proposed_subagents",
    ),
    max_subagents: int = typer.Option(8, "--max-subagents", help="Maximum subagents"),
    max_events: int = typer.Option(256, "--max-events", help="Maximum event records"),
    max_output_bytes: int = typer.Option(
        65536, "--max-output-bytes", help="Maximum bounded output bytes"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write execution candidate JSON to path"
    ),
) -> None:
    """Create a promoted-lane candidate; it does not run deepagents."""
    work_plan_data = _load_json(work_plan)
    readiness_gate_data = _load_json(backend_readiness_gate) if backend_readiness_gate is not None else None
    try:
        artifact = create_deepagents_execution_candidate(
            work_plan=work_plan_data,
            work_plan_path=work_plan,
            output_root=output_root,
            backend_mode=_backend_mode(backend_mode),
            backend_readiness_gate=readiness_gate_data,
            backend_readiness_gate_path=backend_readiness_gate,
            allowed_subagents=_split_csv(allowed_subagents),
            max_subagents=max_subagents,
            max_events=max_events,
            max_output_bytes=max_output_bytes,
        )
    except ValueError as exc:
        console.print(f"ValueError: {exc}")
        raise typer.Exit(1)

    if output is not None:
        write_deepagents_execution_candidate(artifact, output)
        console.print(
            f"Deepagents execution candidate written to {output}. Next: builder-deepagents approve-candidate --candidate {output} --approval-actor <name> --approval-reason <reason> --output <approval.json>"
        )
    else:
        console.out(dumps_deepagents_execution_candidate(artifact), end="")


@deepagents_app.command("backend-readiness")
def backend_readiness(
    module_name: str = typer.Option(
        "deepagents", "--module-name", help="Optional backend module to inspect"
    ),
    package_name: str = typer.Option(
        "deepagents", "--package-name", help="Optional backend package name"
    ),
    capability_gates_passed: bool = typer.Option(
        False,
        "--capability-gates-passed",
        help="Operator assertion that all AGENTS.md promotion gates are covered",
    ),
    model_receipt_ref: list[Path] | None = typer.Option(
        None,
        "--model-receipt-ref",
        help="Repeatable model receipt artifact path when backend performs model work",
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write backend readiness gate JSON to path"
    ),
) -> None:
    """Create an optional_deepagents promotion gate without constructing an agent."""
    refs: list[dict[str, Any]] = []
    for path in model_receipt_ref or []:
        artifact = _load_json(path)
        refs.append(
            {
                "role": "model_call_receipt",
                "kind": str(artifact.get("kind", "")),
                "path": str(path),
                "sha256": hashlib.sha256(
                    json_lib.dumps(
                        artifact,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode("utf-8")
                ).hexdigest(),
                "name": "builder-II model call receipt",
                "required": True,
            }
        )
    try:
        artifact = create_deepagents_backend_readiness_gate(
            module_name=module_name,
            package_name=package_name,
            capability_gates_passed=capability_gates_passed,
            model_call_receipt_refs=refs,
        )
    except ValueError as exc:
        console.print(f"ValueError: {exc}")
        raise typer.Exit(1)

    if output is not None:
        write_deepagents_backend_readiness_gate(artifact, output)
        console.print(
            f"Deepagents backend readiness gate written to {output}. Next: builder-deepagents execution-candidate --backend-mode optional_deepagents --backend-readiness-gate {output} ..."
        )
    else:
        console.out(dumps_deepagents_backend_readiness_gate(artifact), end="")


@deepagents_app.command("approve-candidate")
def approve_candidate(
    candidate: Path = typer.Option(
        ..., "--candidate", help="Path to deepagents execution candidate JSON"
    ),
    approval_actor: str = typer.Option(
        ..., "--approval-actor", help="Human approval actor"
    ),
    approval_reason: str = typer.Option(
        ..., "--approval-reason", help="Human approval reason"
    ),
    expires_at: str | None = typer.Option(
        None, "--expires-at", help="Optional ISO expiry timestamp"
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Write execution approval JSON to path"
    ),
) -> None:
    """Bind HITL approval to the exact candidate digest."""
    candidate_data = _load_json(candidate)
    try:
        artifact = create_deepagents_execution_approval(
            candidate=candidate_data,
            candidate_path=candidate,
            approval_actor=approval_actor,
            approval_reason=approval_reason,
            expires_at=expires_at,
        )
    except ValueError as exc:
        console.print(f"ValueError: {exc}")
        raise typer.Exit(1)

    if output is not None:
        write_deepagents_execution_approval(artifact, output)
        console.print(
            f"Deepagents execution approval written to {output}. Next: builder-deepagents run-approved --candidate {candidate} --approval {output} --output-dir <run-dir>"
        )
    else:
        console.out(dumps_deepagents_execution_approval(artifact), end="")


@deepagents_app.command("run-approved")
def run_approved(
    candidate: Path = typer.Option(
        ..., "--candidate", help="Path to deepagents execution candidate JSON"
    ),
    approval: Path = typer.Option(
        ..., "--approval", help="Path to deepagents execution approval JSON"
    ),
    output_dir: Path = typer.Option(
        ..., "--output-dir", help="Directory for run envelope, events, receipt, and replay"
    ),
    stop_after: int | None = typer.Option(
        None,
        "--stop-after",
        help="Testing/resume hook: checkpoint after N completed subagents",
    ),
) -> None:
    """Run the approved protocol backend lane and write replayable evidence."""
    try:
        summary = run_deepagents_approved_candidate(
            candidate_path=candidate,
            approval_path=approval,
            output_dir=output_dir,
            stop_after=stop_after,
        )
    except Exception as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1)
    console.out(json_lib.dumps(summary, indent=2, sort_keys=True) + "\n", end="")


@deepagents_app.command("resume-approved")
def resume_approved(
    candidate: Path = typer.Option(
        ..., "--candidate", help="Path to deepagents execution candidate JSON"
    ),
    approval: Path = typer.Option(
        ..., "--approval", help="Path to deepagents execution approval JSON"
    ),
    checkpoint: Path = typer.Option(
        ..., "--checkpoint", help="Path to deepagents checkpoint JSON"
    ),
    output_dir: Path = typer.Option(
        ..., "--output-dir", help="Directory for resumed run artifacts"
    ),
) -> None:
    """Resume a checkpoint only when candidate and approval still bind exactly."""
    try:
        summary = resume_deepagents_approved_candidate(
            candidate_path=candidate,
            approval_path=approval,
            checkpoint_path=checkpoint,
            output_dir=output_dir,
        )
    except Exception as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1)
    console.out(json_lib.dumps(summary, indent=2, sort_keys=True) + "\n", end="")


@deepagents_app.command("replay-run")
def replay_run(
    events_dir: Path = typer.Option(
        ..., "--events-dir", help="Directory containing deepagents event records"
    ),
    output: Path = typer.Option(
        ..., "--output", help="Write replay report JSON to path"
    ),
) -> None:
    """Reconstruct run state from events only; never reruns backend/model/tool work."""
    try:
        replay = replay_deepagents_run(events_dir=events_dir, output=output)
    except Exception as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1)
    console.out(json_lib.dumps({"valid": replay["valid"], "status": replay["status"], "output": str(output)}, indent=2, sort_keys=True) + "\n", end="")
    if replay["valid"] is not True:
        raise typer.Exit(1)


@deepagents_app.command("evidence-bundle")
def evidence_bundle(
    candidate: Path = typer.Option(..., "--candidate", help="Candidate JSON path"),
    approval: Path = typer.Option(..., "--approval", help="Approval JSON path"),
    envelope: Path = typer.Option(..., "--envelope", help="Run envelope JSON path"),
    receipt: Path = typer.Option(..., "--receipt", help="Execution receipt JSON path"),
    event_ledger: Path = typer.Option(
        ..., "--event-ledger", help="Event ledger JSON path"
    ),
    replay_report: Path = typer.Option(
        ..., "--replay-report", help="Replay report JSON path"
    ),
    checkpoint: Path | None = typer.Option(
        None, "--checkpoint", help="Optional checkpoint JSON path"
    ),
    output: Path = typer.Option(
        ..., "--output", help="Write evidence bundle JSON to path"
    ),
) -> None:
    """Bundle candidate, approval, run, receipt, ledger, and replay evidence."""
    try:
        bundle = create_evidence_bundle_from_files(
            candidate_path=candidate,
            approval_path=approval,
            envelope_path=envelope,
            receipt_path=receipt,
            event_ledger_path=event_ledger,
            replay_report_path=replay_report,
            checkpoint_path=checkpoint,
            output_path=output,
        )
    except Exception as exc:
        console.print(f"Error: {exc}")
        raise typer.Exit(1)
    console.out(json_lib.dumps({"status": bundle["status"], "output": str(output)}, indent=2, sort_keys=True) + "\n", end="")
