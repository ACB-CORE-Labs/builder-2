from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from builder_ii.command_authority import enforce_command_authority
from builder_ii.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
    write_event_record,
    EVENT_RECORD_KIND,
)
from builder_ii.workflow_records import canonical_digest
from builder_ii.mcp_policy import (
    MCP_INVENTORY_KIND,
    INVENTORY_SCHEMA_VERSION,
    MCP_POLICY_KIND,
    POLICY_SCHEMA_VERSION,
    validate_mcp_policy,
)
from builder_ii.tool_invocation_gateway import execute_tool_envelope

mcp_app = typer.Typer(help="Manage MCP (Model Context Protocol) tool policies and execution.")

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

@mcp_app.command("inventory")
def inventory(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON artifact path"),
) -> None:
    """Emits an MCP inventory artifact for known active servers (stub for B7)."""
    enforce_command_authority("builder-mcp inventory", requested_effects=("artifact_write",))
    # For B7, we implement a passive stub inventory.
    # Real implementations would probe active MCP server registries.
    record = {
        "kind": MCP_INVENTORY_KIND,
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "tools": [],
        "servers": [],
        "governance": {
            "artifact_is_authority": False,
        }
    }
    content = json.dumps(record, indent=2) + "\n"
    if output:
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote inventory to {output}")
    else:
        typer.echo(content)


@mcp_app.command("policy")
def policy(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON artifact path"),
    validate: Optional[Path] = typer.Option(None, "--validate", "-v", help="Path to policy artifact to validate"),
) -> None:
    """Emits or validates an MCP tool policy artifact."""
    requested_effects = ("artifact_write",) if output else ()
    enforce_command_authority("builder-mcp policy", requested_effects=requested_effects)
    if validate:
        try:
            data = json.loads(validate.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            typer.echo(f"Error loading {validate}: {e}", err=True)
            raise typer.Exit(1)

        errors = validate_mcp_policy(data)
        if errors:
            typer.echo(f"Validation failed for {validate}:", err=True)
            for err in errors:
                typer.echo(f" - {err}", err=True)
            raise typer.Exit(1)
        typer.echo(f"{validate} is a valid MCP policy.")
        return

    record = {
        "kind": MCP_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_state": "ACTIVE",
        "allowed_servers": [],
        "allowed_operations": [],
        "denied_by_default": True,
        "allowed_risk_classes": ["low_risk"],
        "max_input_bytes": 1024,
        "max_output_bytes": 1024,
        "timeout_seconds": 30,
        "network_allowed": False,
        "mutation_allowed": False,
        "credential_access_allowed": False,
        "cost_allowed": False,
        "requires_approval_for_mutation": True,
        "requires_approval_for_external_network": True,
        "requires_approval_for_credentials": True,
        "grants_authority": False,
        "governance": {
            "artifact_is_authority": False
        }
    }
    content = json.dumps(record, indent=2) + "\n"
    if output:
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote policy to {output}")
    else:
        typer.echo(content)


@mcp_app.command("call")
def call(
    envelope: Path = typer.Argument(..., help="Path to the MCP call envelope artifact"),
    policy_path: Path = typer.Argument(..., help="Path to the active MCP policy artifact"),
    receipt_output: Path = typer.Option(..., "--receipt-output", "-r", help="Path to save the receipt"),
    session_id: str = typer.Option(..., "--session-id", help="Session ID for the operational ledger event"),
) -> None:
    """Executes an MCP call defined in an envelope, validated against a policy and logs to ledger."""
    enforce_command_authority("builder-mcp call", requested_effects=("external_tool", "artifact_write", "state_write"))
    try:
        env_data = json.loads(envelope.read_text(encoding="utf-8"))
        pol_data = json.loads(policy_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        typer.echo(f"Error loading inputs: {e}", err=True)
        raise typer.Exit(1)

    try:
        receipt = execute_tool_envelope(
            envelope=env_data,
            envelope_path=envelope,
            policy=pol_data,
            policy_path=policy_path
        )
    except ValueError as e:
        typer.echo(f"Execution failed/denied: {e}", err=True)

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
        event_id = f"evt_mcp_fail_{int(time.time())}_{sequence}"
        event_record = create_event_record(
            event_id=event_id,
            session_id=session_id,
            sequence=sequence,
            event_type="mcp_call_failed",
            stage=current_stage,
            subject_refs=[],
            command_surface="builder-mcp call",
            policy_snapshot_ref=_artifact_ref(pol_data, policy_path, "mcp_tool_policy"),
            previous_event_ref=_previous_event_ref(existing_records),
            message=f"MCP call failed: {e}",
        )
        # Validate event before writing
        from builder_ii.event_ledger import validate_event_record
        event_errors = validate_event_record(event_record)
        if event_errors:
            typer.echo(f"Event record validation failed: {event_errors}", err=True)
            raise typer.Exit(1)

        write_event_record(event_record, events_dir / f"{sequence:03d}_mcp_call_failed.json")
        raise typer.Exit(1)

    # Validate receipt before writing
    from builder_ii.mcp_policy import validate_mcp_receipt
    receipt_errors = validate_mcp_receipt(receipt)
    if receipt_errors:
        typer.echo(f"Receipt validation failed: {receipt_errors}", err=True)
        raise typer.Exit(1)

    content = json.dumps(receipt, indent=2) + "\n"
    receipt_output.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote receipt to {receipt_output}")

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

    env_ref = _artifact_ref(env_data, envelope, "mcp_call_envelope")
    rec_ref = _artifact_ref(receipt, receipt_output, "mcp_call_receipt")

    event_id = f"evt_mcp_exec_{int(time.time())}_{sequence}"
    event_record = create_event_record(
        event_id=event_id,
        session_id=session_id,
        sequence=sequence,
        event_type="mcp_call_executed",
        stage=current_stage,
        subject_refs=[env_ref, rec_ref],
        command_surface="builder-mcp call",
        policy_snapshot_ref=_artifact_ref(pol_data, policy_path, "mcp_tool_policy"),
        previous_event_ref=_previous_event_ref(existing_records),
        message="MCP call executed",
    )
    # Validate event before writing
    from builder_ii.event_ledger import validate_event_record
    event_errors = validate_event_record(event_record)
    if event_errors:
        typer.echo(f"Event record validation failed: {event_errors}", err=True)
        raise typer.Exit(1)

    write_event_record(event_record, events_dir / f"{sequence:03d}_mcp_call_executed.json")
    typer.echo("Workflow event logged to ledger.")


@mcp_app.command("standalone-call")
def standalone_call(
    envelope: Path = typer.Argument(..., help="Path to the MCP call envelope artifact"),
    policy_path: Path = typer.Argument(..., help="Path to the active MCP policy artifact"),
    receipt_output: Path = typer.Option(..., "--receipt-output", "-r", help="Path to save the receipt"),
) -> None:
    """Executes an MCP call defined in an envelope without logging to the ledger."""
    enforce_command_authority("builder-mcp standalone-call", requested_effects=("external_tool", "artifact_write"))
    try:
        env_data = json.loads(envelope.read_text(encoding="utf-8"))
        pol_data = json.loads(policy_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        typer.echo(f"Error loading inputs: {e}", err=True)
        raise typer.Exit(1)

    try:
        receipt = execute_tool_envelope(
            envelope=env_data,
            envelope_path=envelope,
            policy=pol_data,
            policy_path=policy_path
        )
    except ValueError as e:
        typer.echo(f"Execution failed/denied: {e}", err=True)
        raise typer.Exit(1)

    # Validate receipt before writing
    from builder_ii.mcp_policy import validate_mcp_receipt
    receipt_errors = validate_mcp_receipt(receipt)
    if receipt_errors:
        typer.echo(f"Receipt validation failed: {receipt_errors}", err=True)
        raise typer.Exit(1)

    content = json.dumps(receipt, indent=2) + "\n"
    receipt_output.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote receipt to {receipt_output}")
