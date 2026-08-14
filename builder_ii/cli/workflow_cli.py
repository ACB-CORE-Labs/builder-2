from __future__ import annotations

import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.core.workflow_orchestrator import (
    WorkflowError,
    candidate_workflow,
    handoff_workflow,
    plan_workflow,
    promote_workflow,
    verify_chain_workflow,
    workflow_status,
)
from builder_ii.lifecycle.setup.target_profiles import target_names

workflow_app = typer.Typer(help="Governed passive workflow state machine.")
console = Console()

_DEFAULT_WORKFLOWS_DIR = Path(".builder/workflows")


def _new_session_id() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("wf-%Y%m%dT%H%M%SZ")


def _read_session_id(path: Path) -> str | None:
    session_path = path / "artifacts" / "workflow-session.json"
    if not session_path.exists():
        return None
    try:
        data = json_lib.loads(session_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict) and isinstance(data.get("session_id"), str):
        return data["session_id"]
    return None


def _resolve_output_dir(
    *,
    session_id: str | None,
    output_dir: Path | None,
    workflows_dir: Path,
) -> Path:
    if output_dir is not None:
        return output_dir

    candidates = [
        path
        for path in workflows_dir.glob("*")
        if path.is_dir() and (path / "artifacts" / "workflow-session.json").exists()
    ]

    if session_id:
        direct = workflows_dir / session_id
        if (direct / "artifacts" / "workflow-session.json").exists():
            return direct
        as_path = Path(session_id)
        if (as_path / "artifacts" / "workflow-session.json").exists():
            return as_path
        for candidate in candidates:
            if _read_session_id(candidate) == session_id:
                return candidate
        raise WorkflowError(f"workflow session not found: {session_id}")

    if not candidates:
        raise WorkflowError("no workflow sessions found; pass --output-dir or run builder workflow plan first")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _emit_status(status: dict[str, Any]) -> None:
    typer.echo(json_lib.dumps(status, indent=2, sort_keys=True))


def _run(action) -> None:
    try:
        _emit_status(action())
    except WorkflowError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)


def _target(value: str) -> str:
    if value not in target_names():
        names = ", ".join(target_names())
        raise WorkflowError(f"target must be one of: {names}")
    return value


@workflow_app.command("plan")
def plan(
    task: str = typer.Option(..., "--task", "-t", help="Operator intent for the passive workflow."),
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, or core."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Workflow output directory."),
    session_id: str | None = typer.Option(None, "--session-id", help="Stable workflow session id."),
    agent: str | None = typer.Option(None, "--agent", help="Agent profile name."),
    verification: str | None = typer.Option(None, "--verification", help="Verification profile name."),
    repo_path: Path | None = typer.Option(None, "--repo-path", help="Operator-selected target repo path."),
) -> None:
    """Create the passive plan stage: profile pack, routing recommendation, orchestration, and deepagents work plan."""

    def action() -> dict[str, Any]:
        selected_session_id = session_id or _new_session_id()
        selected_output_dir = output_dir or (_DEFAULT_WORKFLOWS_DIR / selected_session_id)
        return plan_workflow(
            target=_target(target),  # type: ignore[arg-type]
            task=task,
            output_dir=selected_output_dir,
            session_id=selected_session_id,
            agent=agent,
            verification=verification,
            repo_path=repo_path,
        )

    _run(action)


@workflow_app.command("promote")
def promote(
    session_id: str | None = typer.Argument(None, help="Workflow session id. Defaults to latest session."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Workflow output directory."),
    workflows_dir: Path = typer.Option(
        _DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."
    ),
    requested_by: str = typer.Option("operator", "--requested-by", help="Promotion requester identity."),
) -> None:
    """Record the passive HITL promotion request/review/decision/boundary stage."""
    _run(
        lambda: promote_workflow(
            output_dir=_resolve_output_dir(session_id=session_id, output_dir=output_dir, workflows_dir=workflows_dir),
            requested_by=requested_by,
        )
    )


@workflow_app.command("candidate")
def candidate(
    session_id: str | None = typer.Argument(None, help="Workflow session id. Defaults to latest session."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Workflow output directory."),
    workflows_dir: Path = typer.Option(
        _DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."
    ),
) -> None:
    """Record the passive execution candidate manifest and validation stage."""
    _run(
        lambda: candidate_workflow(
            output_dir=_resolve_output_dir(session_id=session_id, output_dir=output_dir, workflows_dir=workflows_dir)
        )
    )


@workflow_app.command("verify-chain")
def verify_chain(
    session_id: str | None = typer.Argument(None, help="Workflow session id. Defaults to latest session."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Workflow output directory."),
    workflows_dir: Path = typer.Option(
        _DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."
    ),
) -> None:
    """Create artifact index and chain verification report for the passive workflow."""
    _run(
        lambda: verify_chain_workflow(
            output_dir=_resolve_output_dir(session_id=session_id, output_dir=output_dir, workflows_dir=workflows_dir)
        )
    )


@workflow_app.command("handoff")
def handoff(
    session_id: str | None = typer.Argument(None, help="Workflow session id. Defaults to latest session."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Workflow output directory."),
    workflows_dir: Path = typer.Option(
        _DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."
    ),
) -> None:
    """Create passive handoff note and golden path summary."""
    _run(
        lambda: handoff_workflow(
            output_dir=_resolve_output_dir(session_id=session_id, output_dir=output_dir, workflows_dir=workflows_dir)
        )
    )


@workflow_app.command("status")
def status(
    session_id: str | None = typer.Argument(None, help="Workflow session id. Defaults to latest session."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Workflow output directory."),
    workflows_dir: Path = typer.Option(
        _DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."
    ),
) -> None:
    """Replay events and report current workflow status."""
    _run(
        lambda: workflow_status(
            output_dir=_resolve_output_dir(session_id=session_id, output_dir=output_dir, workflows_dir=workflows_dir)
        )
    )


if __name__ == "__main__":
    workflow_app()
