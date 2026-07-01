from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.tool_registry import ToolTier, check_tools, missing_required_tools
from builder_ii.tool_invocation_gateway import execute_tool_envelope
import json
from pathlib import Path

from builder_ii.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
    write_event_record,
    EVENT_RECORD_KIND,
)
from builder_ii.workflow_records import canonical_digest

def _artifact_ref(data: dict, path: Path, role: str) -> dict:
    import hashlib
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "kind": data.get("kind"),
        "path": str(path),
        "sha256": digest,
        "role": role,
        "name": role.replace("_", " "),
        "required": True,
    }

def _previous_event_ref(existing_records: list) -> dict | None:
    if not existing_records:
        return None
    last_event, last_path = existing_records[-1]
    return {
        "role": "event",
        "kind": EVENT_RECORD_KIND,
        "path": str(last_path),
        "sha256": canonical_digest(last_event),
        "name": str(last_event.get("event_type", "")),
        "required": True,
    }

tools_app = typer.Typer(help="Inspect builder-II external engineering tool integrations.")
console = Console()
_VALID_TIERS: set[str] = {"tier1", "tier2", "notes"}


def _normalize_tier(value: str | None) -> ToolTier | None:
    if value is None:
        return None
    if value not in _VALID_TIERS:
        console.print("[red]--tier must be one of: tier1, tier2, notes[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@tools_app.command("list")
def list_tools(tier: str | None = typer.Option(None, "--tier", help="tier1, tier2, or notes")) -> None:
    """List external tools and intended builder-II integrations."""
    table = Table("Tool", "Tier", "Category", "Integration", "Required", "Open", "Install")
    for check in check_tools(tier=_normalize_tier(tier)):
        tool = check.tool
        table.add_row(
            tool.name,
            tool.tier,
            tool.category,
            tool.integration,
            "yes" if tool.required else "no",
            "yes" if tool.open_source else "no",
            tool.install,
        )
    console.print(table)


@tools_app.command("check")
def check(tier: str | None = typer.Option(None, "--tier", help="tier1, tier2, or notes")) -> None:
    """Check whether external tools are installed on PATH."""
    table = Table("Tool", "Status", "Path", "Version", "Install")
    checks = check_tools(tier=_normalize_tier(tier))
    for item in checks:
        mark = "PASS" if item.status == "installed" else ("INFO" if item.status == "optional-ui" else "MISS")
        table.add_row(item.tool.name, mark, item.path or "-", item.version or "-", item.tool.install)
    console.print(table)
    missing = [item for item in checks if item.tool.required and item.status == "missing"]
    raise typer.Exit(1 if missing else 0)


@tools_app.command("missing")
def missing() -> None:
    """Print required tools that are missing."""
    checks = missing_required_tools()
    if not checks:
        console.print("[green]All required external tools are available[/]")
        return
    for item in checks:
        console.print(f"[red]{item.tool.name}[/] — install: {item.tool.install}")
    raise typer.Exit(1)
@tools_app.command("invoke")
def invoke(
    envelope: Path = typer.Argument(..., help="Path to the tool call envelope artifact"),
    policy_path: Path = typer.Argument(..., help="Path to the active tool policy artifact"),
    receipt_output: Path = typer.Option(..., "--receipt-output", "-r", help="Path to save the receipt"),
    session_id: str = typer.Option(..., "--session-id", help="Session ID for the operational ledger event"),
) -> None:
    """Executes an approved low-risk tool call defined in an envelope and logs to ledger."""
    try:
        env_data = json.loads(envelope.read_text(encoding="utf-8"))
        pol_data = json.loads(policy_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error loading inputs:[/] {e}")
        raise typer.Exit(1)

    try:
        receipt = execute_tool_envelope(
            envelope=env_data,
            envelope_path=envelope,
            policy=pol_data,
            policy_path=policy_path
        )
    except ValueError as e:
        console.print(f"[red]Execution failed/denied:[/] {e}")

        # Log failure to ledger since session_id is required
        import time
        events_dir = Path(".builder/sessions") / session_id / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        existing_records = load_event_records(events_dir)
        sequence = len(existing_records) + 1
        current_stage = "initialized"
        if existing_records:
            replay_report = replay_events(existing_records, session_id=session_id)
            if replay_report["valid"]:
                current_stage = replay_report["current_stage"]
        event_id = f"evt_tool_fail_{int(time.time())}_{sequence}"
        event_record = create_event_record(
            event_id=event_id,
            session_id=session_id,
            sequence=sequence,
            event_type="tool_call_failed",
            stage=current_stage,
            subject_refs=[],
            command_surface="builder-tools invoke",
            policy_snapshot_ref=_artifact_ref(pol_data, policy_path, "tool_invocation_policy"),
            previous_event_ref=_previous_event_ref(existing_records),
            message=f"Tool call failed: {e}",
        )
        # Validate event before writing
        from builder_ii.event_ledger import validate_event_record
        event_errors = validate_event_record(event_record)
        if event_errors:
            console.print(f"[red]Event record validation failed:[/] {event_errors}")
            raise typer.Exit(1)

        write_event_record(event_record, events_dir / f"{sequence:03d}_tool_call_failed.json")
        raise typer.Exit(1)

    # Validate receipt before writing
    from builder_ii.mcp_policy import validate_mcp_receipt
    receipt_errors = validate_mcp_receipt(receipt)
    if receipt_errors:
        console.print(f"[red]Receipt validation failed:[/] {receipt_errors}")
        raise typer.Exit(1)

    content = json.dumps(receipt, indent=2) + "\n"
    receipt_output.write_text(content, encoding="utf-8")
    console.print(f"Wrote receipt to {receipt_output}")

    # Log success to ledger since session_id is required
    import time
    events_dir = Path(".builder/sessions") / session_id / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    existing_records = load_event_records(events_dir)
    sequence = len(existing_records) + 1
    current_stage = "initialized"
    if existing_records:
        replay_report = replay_events(existing_records, session_id=session_id)
        if replay_report["valid"]:
            current_stage = replay_report["current_stage"]

    env_ref = _artifact_ref(env_data, envelope, "tool_call_envelope")
    rec_ref = _artifact_ref(receipt, receipt_output, "tool_call_receipt")

    event_id = f"evt_tool_exec_{int(time.time())}_{sequence}"
    event_record = create_event_record(
        event_id=event_id,
        session_id=session_id,
        sequence=sequence,
        event_type="tool_call_executed",
        stage=current_stage,
        subject_refs=[env_ref, rec_ref],
        command_surface="builder-tools invoke",
        policy_snapshot_ref=_artifact_ref(pol_data, policy_path, "tool_invocation_policy"),
        previous_event_ref=_previous_event_ref(existing_records),
        message="Tool call executed",
    )
    # Validate event before writing
    from builder_ii.event_ledger import validate_event_record
    event_errors = validate_event_record(event_record)
    if event_errors:
        console.print(f"[red]Event record validation failed:[/] {event_errors}")
        raise typer.Exit(1)

    write_event_record(event_record, events_dir / f"{sequence:03d}_tool_call_executed.json")
    console.print("Workflow event logged to ledger.")


@tools_app.command("standalone-invoke")
def standalone_invoke(
    envelope: Path = typer.Argument(..., help="Path to the tool call envelope artifact"),
    policy_path: Path = typer.Argument(..., help="Path to the active tool policy artifact"),
    receipt_output: Path = typer.Option(..., "--receipt-output", "-r", help="Path to save the receipt"),
) -> None:
    """Executes an approved low-risk tool call defined in an envelope without logging to the ledger."""
    try:
        env_data = json.loads(envelope.read_text(encoding="utf-8"))
        pol_data = json.loads(policy_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error loading inputs:[/] {e}")
        raise typer.Exit(1)

    try:
        receipt = execute_tool_envelope(
            envelope=env_data,
            envelope_path=envelope,
            policy=pol_data,
            policy_path=policy_path
        )
    except ValueError as e:
        console.print(f"[red]Execution failed/denied:[/] {e}")
        raise typer.Exit(1)

    # Validate receipt before writing
    from builder_ii.mcp_policy import validate_mcp_receipt
    receipt_errors = validate_mcp_receipt(receipt)
    if receipt_errors:
        console.print(f"[red]Receipt validation failed:[/] {receipt_errors}")
        raise typer.Exit(1)

    content = json.dumps(receipt, indent=2) + "\n"
    receipt_output.write_text(content, encoding="utf-8")
    console.print(f"Wrote receipt to {receipt_output}")
