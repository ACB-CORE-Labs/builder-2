from __future__ import annotations

import hashlib
import json as json_lib
import time
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.core.config import load_settings
from builder_ii.governance.authority import enforce_command_authority
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    replay_events,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.routing.model_client_registry import (
    create_model_client_registry,
)
from builder_ii.routing.model_execution_gateway import (
    ModelExecutionGateway,
    validate_model_call_receipt_file,
)

model_app = typer.Typer(help="Governed model/provider execution gateway CLI.")
console = Console()


def _read_json(path: Path | None, default_func) -> dict:
    if path is None:
        return default_func()
    if not path.is_file():
        console.print(f"[red]File not found: {path}[/]")
        raise typer.Exit(1)
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        console.print(f"[red]Failed to read JSON from {path}: {exc}[/]")
        raise typer.Exit(1)
    return data


def _artifact_ref(data: dict, path: Path, role: str) -> dict:
    """Build a canonical artifact ref dict with compact JSON SHA-256 digest."""
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
    """Compute previous_event_ref from the last record in an existing session.

    existing_records is a list of (event_dict, path) tuples as returned by
    load_event_records. Returns None when there are no prior events.
    """
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


@model_app.command("call")
def call_cmd(
    model: str = typer.Option(..., "--model", help="Model ID (e.g. gpt-4o-stub) to call."),
    prompt: str | None = typer.Option(None, "--prompt", help="Text prompt to send to the model."),
    prompt_file: Path | None = typer.Option(None, "--prompt-file", help="Path to a file containing the prompt text."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="System prompt to override defaults."),
    max_tokens: int = typer.Option(256, "--max-tokens", help="Maximum tokens to generate."),
    temperature: float | None = typer.Option(None, "--temperature", help="Sampling temperature."),
    registry_path: Path | None = typer.Option(None, "--registry", help="Optional path to model client registry JSON."),
    execution_policy_path: Path | None = typer.Option(
        None, "--execution-policy", help="Path to model execution policy JSON."
    ),
    output_envelope: Path = typer.Option(..., "--output-envelope", help="Path to write the generated envelope JSON."),
    output_receipt: Path = typer.Option(..., "--output-receipt", help="Path to write the execution receipt JSON."),
    session_id: str | None = typer.Option(None, "--session-id", help="Optional workflow session ID to log the event."),
) -> None:
    """Execute a governed model call, generating an envelope and a receipt."""
    enforce_command_authority("builder-model call", requested_effects=("model_execution", "artifact_write"))
    # Resolve prompt
    actual_prompt = ""
    if prompt is not None:
        actual_prompt = prompt
    elif prompt_file is not None:
        if not prompt_file.is_file():
            console.print(f"[red]Prompt file not found: {prompt_file}[/]")
            raise typer.Exit(1)
        actual_prompt = prompt_file.read_text(encoding="utf-8")
    else:
        console.print("[red]Must specify either --prompt or --prompt-file[/]")
        raise typer.Exit(1)

    if not actual_prompt.strip():
        console.print("[red]Prompt must not be empty[/]")
        raise typer.Exit(1)

    # Load registry and policy
    registry = _read_json(registry_path, create_model_client_registry)
    if execution_policy_path is None:
        console.print("[red]Must specify --execution-policy[/]")
        raise typer.Exit(1)
    if not execution_policy_path.is_file():
        console.print(f"[red]Execution policy file not found: {execution_policy_path}[/]")
        raise typer.Exit(1)
    import json as json_lib

    execution_policy = json_lib.loads(execution_policy_path.read_text(encoding="utf-8"))

    settings = load_settings()
    gateway = ModelExecutionGateway(settings, registry, execution_policy)

    if not session_id:
        console.print(
            "[red]Must specify --session-id for operational call. Use standalone-call if ledger is not required.[/]"
        )
        raise typer.Exit(1)

    try:
        envelope, receipt, _debited = gateway.run_model_call(
            model_id=model,
            prompt=actual_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            envelope_path=output_envelope,
            receipt_path=output_receipt,
            ledger_bound=True,
        )
    except Exception as exc:
        console.print(f"[red]Model execution failed: {exc}[/]")

        # Log failure to ledger if session_id is provided
        if session_id:
            events_dir = Path(".builder/sessions") / session_id / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            existing_records = load_event_records(events_dir)
            sequence = len(existing_records) + 1

            current_stage = "initialized"
            if existing_records:
                replay_report = replay_events(existing_records, session_id=session_id)
                if replay_report["valid"]:
                    current_stage = replay_report["current_stage"]

            event_id = f"evt_model_fail_{int(time.time())}_{sequence}"
            event_record = create_event_record(
                event_id=event_id,
                session_id=session_id,
                sequence=sequence,
                event_type="model_call_failed",
                stage=current_stage,
                subject_refs=[],
                command_surface="builder-model call",
                policy_snapshot_ref=_artifact_ref(execution_policy, execution_policy_path, "model_execution_policy")
                if execution_policy and execution_policy_path
                else {},
                previous_event_ref=_previous_event_ref(existing_records),
                message=f"Model call failed: {exc}",
            )
            write_event_record(event_record, events_dir / f"{sequence:03d}_model_call_failed.json")

        raise typer.Exit(1)

    console.print("[green]Model call executed successfully.[/]")
    console.print(f"Envelope written to: {output_envelope}")
    console.print(f"Receipt written to: {output_receipt}")

    # Log success to ledger if session_id is provided
    if session_id:
        events_dir = Path(".builder/sessions") / session_id / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        existing_records = load_event_records(events_dir)
        sequence = len(existing_records) + 1

        current_stage = "initialized"
        if existing_records:
            replay_report = replay_events(existing_records, session_id=session_id)
            if replay_report["valid"]:
                current_stage = replay_report["current_stage"]

        envelope_ref = _artifact_ref(envelope, output_envelope, "model_call_envelope")
        receipt_ref = _artifact_ref(receipt, output_receipt, "model_call_receipt")

        event_id = f"evt_model_exec_{int(time.time())}_{sequence}"
        event_record = create_event_record(
            event_id=event_id,
            session_id=session_id,
            sequence=sequence,
            event_type="model_call_executed",
            stage=current_stage,
            subject_refs=[envelope_ref, receipt_ref],
            command_surface="builder-model call",
            policy_snapshot_ref=_artifact_ref(execution_policy, execution_policy_path, "model_execution_policy"),
            previous_event_ref=_previous_event_ref(existing_records),
            message=f"Model call executed: {model}",
        )
        write_event_record(event_record, events_dir / f"{sequence:03d}_model_call_executed.json")
        console.print("Workflow event logged to ledger.")


@model_app.command("standalone-call")
def standalone_call_cmd(
    model: str = typer.Option(..., "--model", help="Model ID (e.g. gpt-4o-stub) to call."),
    prompt: str | None = typer.Option(None, "--prompt", help="Text prompt to send to the model."),
    prompt_file: Path | None = typer.Option(None, "--prompt-file", help="Path to a file containing the prompt text."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="System prompt to override defaults."),
    max_tokens: int = typer.Option(256, "--max-tokens", help="Maximum tokens to generate."),
    temperature: float | None = typer.Option(None, "--temperature", help="Sampling temperature."),
    registry_path: Path | None = typer.Option(None, "--registry", help="Optional path to model client registry JSON."),
    execution_policy_path: Path | None = typer.Option(
        None, "--execution-policy", help="Path to model execution policy JSON."
    ),
    output_envelope: Path = typer.Option(..., "--output-envelope", help="Path to write the generated envelope JSON."),
    output_receipt: Path = typer.Option(..., "--output-receipt", help="Path to write the execution receipt JSON."),
) -> None:
    """Execute a governed model call without logging to the ledger."""
    enforce_command_authority("builder-model standalone-call", requested_effects=("model_execution", "artifact_write"))
    # Resolve prompt
    actual_prompt = ""
    if prompt is not None:
        actual_prompt = prompt
    elif prompt_file is not None:
        if not prompt_file.is_file():
            console.print(f"[red]Prompt file not found: {prompt_file}[/]")
            raise typer.Exit(1)
        actual_prompt = prompt_file.read_text(encoding="utf-8")
    else:
        console.print("[red]Must specify either --prompt or --prompt-file[/]")
        raise typer.Exit(1)

    if not actual_prompt.strip():
        console.print("[red]Prompt must not be empty[/]")
        raise typer.Exit(1)

    # Load registry and policy
    registry = _read_json(registry_path, create_model_client_registry)
    if execution_policy_path is None:
        console.print("[red]Must specify --execution-policy[/]")
        raise typer.Exit(1)
    if not execution_policy_path.is_file():
        console.print(f"[red]Execution policy file not found: {execution_policy_path}[/]")
        raise typer.Exit(1)
    import json as json_lib

    execution_policy = json_lib.loads(execution_policy_path.read_text(encoding="utf-8"))

    settings = load_settings()
    gateway = ModelExecutionGateway(settings, registry, execution_policy)

    try:
        envelope, receipt, _debited = gateway.run_model_call(
            model_id=model,
            prompt=actual_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            envelope_path=output_envelope,
            receipt_path=output_receipt,
            ledger_bound=False,
        )
    except Exception as exc:
        console.print(f"[red]Model execution failed: {exc}[/]")
        raise typer.Exit(1)

    if receipt.get("ledger_bound"):
        console.print("[yellow]Warning: standalone-call must not set ledger_bound[/]")
        raise typer.Exit(1)

    console.print("[green]Standalone model call executed successfully.[/]")
    console.print(f"Envelope written to: {output_envelope}")
    console.print(f"Receipt written to: {output_receipt}")


@model_app.command("validate-receipt")
def validate_receipt_cmd(
    path: Path = typer.Argument(..., help="Path to model call receipt JSON file to validate."),
) -> None:
    """Validate a model call receipt artifact against its schema."""
    errors = validate_model_call_receipt_file(path)
    if errors:
        for err in errors:
            console.print(f"[red]Validation error: {err}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Receipt {path} is valid.[/]", soft_wrap=True)


if __name__ == "__main__":
    model_app()
