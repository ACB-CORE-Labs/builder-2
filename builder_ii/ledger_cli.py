from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.event_ledger import (
    create_event_ledger,
    load_event_records,
    replay_events,
    validate_event_ledger,
    validate_ledger_replay_report,
    write_event_ledger,
    write_ledger_replay_report,
)
from builder_ii.verification_execution_ledger import (
    default_verification_execution_ledger_output,
    index_verification_execution_receipt,
    query_verification_execution_ledger_records,
    validate_verification_execution_ledger_integrity,
    validate_verification_execution_ledger_record,
    write_verification_execution_ledger_record,
)
from builder_ii.workflow_orchestrator import WorkflowError, workflow_status

ledger_app = typer.Typer(help="List, replay, audit, and export governed workflow event ledgers.")
console = Console()

_DEFAULT_WORKFLOWS_DIR = Path(".builder/workflows")
_NEXT_TRANSITION = {
    "initialized": "builder workflow plan",
    "planned": "builder workflow promote",
    "promoted": "builder workflow candidate",
    "candidate": "builder workflow verify-chain",
    "chain_verified": "builder workflow handoff",
    "handoff_ready": "",
}


def _read_json(path: Path) -> dict[str, Any]:
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WorkflowError(f"{path} must contain a JSON object")
    return data


def _workflow_dirs(workflows_dir: Path) -> list[Path]:
    if not workflows_dir.exists():
        return []
    return sorted(
        path
        for path in workflows_dir.glob("*")
        if path.is_dir() and (path / "artifacts" / "workflow-session.json").exists()
    )


def _session_id_for_dir(path: Path) -> str:
    try:
        data = _read_json(path / "artifacts" / "workflow-session.json")
    except Exception:
        return ""
    value = data.get("session_id")
    return value if isinstance(value, str) else ""


def _resolve_output_dir(session_id: str, workflows_dir: Path) -> Path:
    direct = workflows_dir / session_id
    if (direct / "artifacts" / "workflow-session.json").exists():
        return direct
    as_path = Path(session_id)
    if (as_path / "artifacts" / "workflow-session.json").exists():
        return as_path
    for candidate in _workflow_dirs(workflows_dir):
        if _session_id_for_dir(candidate) == session_id:
            return candidate
    raise WorkflowError(f"workflow session not found: {session_id}")


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_ledger_output_path(output: Path, ledger_root: Path) -> list[str]:
    resolved_output = output.expanduser().resolve()
    resolved_root = ledger_root.expanduser().resolve()
    errors: list[str] = []
    if resolved_output.exists() and resolved_output.is_dir():
        errors.append("output path must be a file path, not a directory")
    if not _path_is_relative_to(resolved_output, resolved_root) or resolved_output == resolved_root:
        errors.append("output path must be under the target repo .builder/ledger directory")
    return errors


def _emit(value: dict[str, Any] | list[dict[str, Any]]) -> None:
    console.out(json_lib.dumps(value, indent=2, sort_keys=True), end="\n")


def _run(action) -> None:
    try:
        _emit(action())
    except WorkflowError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)


@ledger_app.command("list")
def list_ledgers(
    workflows_dir: Path = typer.Option(_DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."),
) -> None:
    """List known workflow ledgers and event counts."""

    def action() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for workflow_dir in _workflow_dirs(workflows_dir):
            session_id = _session_id_for_dir(workflow_dir)
            events = load_event_records(workflow_dir / "events")
            replay = replay_events(events, session_id=session_id)
            rows.append(
                {
                    "session_id": session_id,
                    "output_dir": str(workflow_dir),
                    "event_count": len(events),
                    "current_stage": replay.get("current_stage", ""),
                    "valid_replay": replay.get("valid", False),
                }
            )
        return rows

    _run(action)


@ledger_app.command("replay")
def replay(
    session_id: str = typer.Argument(..., help="Workflow session id."),
    workflows_dir: Path = typer.Option(_DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional replay report output path."),
) -> None:
    """Replay a workflow ledger from event records, not mutable status."""

    def action() -> dict[str, Any]:
        workflow_dir = _resolve_output_dir(session_id, workflows_dir)
        events = load_event_records(workflow_dir / "events")
        report = replay_events(events, session_id=_session_id_for_dir(workflow_dir))
        errors = validate_ledger_replay_report(report)
        if errors:
            raise WorkflowError("invalid replay report: " + "; ".join(errors))
        write_ledger_replay_report(report, output or (workflow_dir / "artifacts" / "ledger-replay-report.json"))
        return report

    _run(action)


@ledger_app.command("audit")
def audit(
    artifact_sha: str = typer.Argument(..., help="Artifact SHA-256 digest to audit."),
    session_id: str | None = typer.Option(None, "--session-id", help="Optional workflow session id."),
    workflows_dir: Path = typer.Option(_DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."),
) -> None:
    """Find ledger events that reference an artifact SHA-256 digest."""

    def action() -> dict[str, Any]:
        workflow_dirs = [_resolve_output_dir(session_id, workflows_dir)] if session_id else _workflow_dirs(workflows_dir)
        matches: list[dict[str, Any]] = []
        for workflow_dir in workflow_dirs:
            for event, path in load_event_records(workflow_dir / "events"):
                for ref in event.get("subject_refs", []):
                    if isinstance(ref, dict) and ref.get("sha256") == artifact_sha:
                        stage = str(event.get("stage", ""))
                        matches.append(
                            {
                                "session_id": event.get("session_id", ""),
                                "event_id": event.get("event_id", ""),
                                "event_path": str(path),
                                "who": event.get("actor", ""),
                                "when": event.get("recorded_at", ""),
                                "what": event.get("event_type", ""),
                                "command_surface": event.get("command_surface", ""),
                                "why": event.get("message", ""),
                                "decision_result": event.get("decision_result", ""),
                                "status": stage,
                                "evidence": ref,
                                "policy_snapshot_ref": event.get("policy_snapshot_ref"),
                                "next_allowed_transitions": event.get("next_allowed_transitions", []),
                                "fallback_next_allowed_transition": _NEXT_TRANSITION.get(stage, ""),
                            }
                        )
        if not matches:
            raise WorkflowError(f"no ledger events reference artifact sha {artifact_sha}")
        return {"artifact_sha": artifact_sha, "matches": matches}

    _run(action)


@ledger_app.command("export")
def export(
    session_id: str = typer.Argument(..., help="Workflow session id."),
    workflows_dir: Path = typer.Option(_DEFAULT_WORKFLOWS_DIR, "--workflows-dir", help="Directory containing workflow sessions."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional ledger export path."),
) -> None:
    """Refresh and export the event ledger artifact."""

    def action() -> dict[str, Any]:
        workflow_dir = _resolve_output_dir(session_id, workflows_dir)
        workflow_status(output_dir=workflow_dir)
        events = load_event_records(workflow_dir / "events")
        replay_path = workflow_dir / "artifacts" / "ledger-replay-report.json"
        replay_report = _read_json(replay_path)
        ledger = create_event_ledger(
            session_id=_session_id_for_dir(workflow_dir),
            event_records=events,
            replay_report=replay_report,
            replay_report_path=replay_path,
        )
        errors = validate_event_ledger(ledger)
        if errors:
            raise WorkflowError("invalid event ledger: " + "; ".join(errors))
        write_event_ledger(ledger, output or (workflow_dir / "artifacts" / "event-ledger.json"))
        return ledger

    _run(action)


@ledger_app.command("index-receipt")
def index_receipt(
    receipt: Path = typer.Option(..., "--receipt", help="B1.3 verification execution receipt JSON."),
    plan: Path = typer.Option(..., "--plan", help="Referenced verification execution plan JSON."),
    approval: Path = typer.Option(..., "--approval", help="Referenced verification execution approval JSON."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional ledger record output path under .builder/ledger."),
) -> None:
    """Passively index a validated B1.3 receipt chain as a ledger record without replay execution."""

    def action() -> dict[str, Any]:
        try:
            record = index_verification_execution_receipt(
                receipt_path=receipt,
                plan_path=plan,
                approval_path=approval,
            )
        except (OSError, ValueError, json_lib.JSONDecodeError) as exc:
            raise WorkflowError(f"failed to load receipt chain: {exc}") from exc
        if record.get("valid") is not True:
            raise WorkflowError("invalid verification execution receipt chain: " + "; ".join(record.get("errors") or []))
        errors = validate_verification_execution_ledger_record(record)
        if errors:
            raise WorkflowError("invalid verification execution ledger record: " + "; ".join(errors))
        target_repo = Path(str(record.get("target_repo", "."))).expanduser().resolve()
        ledger_root = target_repo / ".builder" / "ledger"
        output_path = output or default_verification_execution_ledger_output(record)
        path_errors = _validate_ledger_output_path(output_path, ledger_root)
        if path_errors:
            raise WorkflowError("invalid ledger output path: " + "; ".join(path_errors))
        write_verification_execution_ledger_record(record, output_path)
        return record

    _run(action)


@ledger_app.command("query-receipts")
def query_receipts(
    target_repo: Path = typer.Option(Path("."), "--target-repo", help="Target repository whose .builder/ledger directory should be read."),
    ledger_root: Path | None = typer.Option(None, "--ledger-root", help="Explicit verification execution ledger root; defaults to --target-repo/.builder/ledger."),
    receipt_digest: str | None = typer.Option(None, "--receipt-digest", help="Filter by referenced verification execution receipt digest."),
    chain_digest: str | None = typer.Option(None, "--chain-digest", help="Filter by verification execution chain digest."),
    receipt_status: str | None = typer.Option(None, "--receipt-status", help="Filter by receipt_status."),
    runner_mode: str | None = typer.Option(None, "--runner-mode", help="Filter by runner_mode."),
) -> None:
    """Read existing verification execution ledger records without replay, execution, or writes."""

    root = ledger_root or (target_repo / ".builder" / "ledger")
    report = query_verification_execution_ledger_records(
        ledger_root=root,
        receipt_digest=receipt_digest,
        chain_digest=chain_digest,
        receipt_status=receipt_status,
        runner_mode=runner_mode,
    )
    _emit(report)
    if report.get("valid") is not True:
        raise typer.Exit(1)


@ledger_app.command("validate-receipts")
def validate_receipts(
    target_repo: Path = typer.Option(Path("."), "--target-repo", help="Target repository whose .builder/ledger directory should be read."),
    ledger_root: Path | None = typer.Option(None, "--ledger-root", help="Explicit verification execution ledger root; defaults to --target-repo/.builder/ledger."),
) -> None:
    """Validate verification execution ledger record integrity without execution or writes."""

    root = ledger_root or (target_repo / ".builder" / "ledger")
    report = validate_verification_execution_ledger_integrity(ledger_root=root)
    _emit(report)
    if report.get("valid") is not True:
        raise typer.Exit(1)


if __name__ == "__main__":
    ledger_app()
