from __future__ import annotations

import json as json_lib
import time
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.config import load_settings
from builder_ii.core.readonly_inspection_reports import (
    create_readonly_inspection_report,
    dumps_readonly_inspection_report,
    validate_readonly_inspection_report,
    write_readonly_inspection_report,
)
from builder_ii.governance.authority import enforce_command_authority
from builder_ii.governance.authority.readonly_authority import (
    CONTENT_READ_RECEIPT_KIND,
    DEFAULT_MAX_BYTES_PER_FILE,
    DEFAULT_MAX_CONTENT_READ_FILES,
    DENIED_READ_KIND,
    READ_POLICY_KIND,
    READ_RECEIPT_KIND,
    create_read_policy,
    execute_content_read,
    execute_governed_read,
    validate_content_read_receipt,
    validate_read_policy,
    validate_read_receipt,
)
from builder_ii.governance.ledger.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import artifact_ref
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_names, target_profile

readonly_app = typer.Typer(help="Create and validate explicit read-only inspection reports.")
console = Console(width=240)
_VALID_TARGETS = set(target_names())


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@readonly_app.command("report")
def report(
    path: list[Path] = typer.Option(..., "--path", help="Explicit file path to inspect. Repeat for multiple files."),
    target: str = typer.Option("generic", "--target"),
    purpose: str = typer.Option("orientation", "--purpose", help="orientation|review|verification_planning"),
    root: Path | None = typer.Option(None, "--root", help="Optional root boundary; paths outside are rejected."),
    note: str = typer.Option("", "--note"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item = create_readonly_inspection_report(
        target=_target(target),
        purpose=purpose,
        paths=path,
        root=root,
        operator_note=note,
    )
    errors = validate_readonly_inspection_report(item)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_readonly_inspection_report(item, output)
        console.print(f"Readonly inspection report written to {output}")
    else:
        echo_stdout(dumps_readonly_inspection_report(item))


@readonly_app.command("policy")
def policy_cmd(
    target: str = typer.Option("generic", "--target"),
    allowed_path: list[str] = typer.Option(None, "--allowed-path", help="Glob pattern allowed to read. Can repeat."),
    denied_path: list[str] = typer.Option(None, "--denied-path", help="Glob pattern denied to read. Can repeat."),
    budget: int = typer.Option(10 * 1024 * 1024, "--budget", help="Maximum bytes allowed to read."),
    content_capture: bool = typer.Option(False, "--content-capture", help="Allow content capture in receipts."),
    note: str = typer.Option("", "--note"),
    output: Path = typer.Option(..., "--output", help="Output path for read policy JSON."),
) -> None:
    """Create a read policy for B3 governed runtime."""
    enforce_command_authority("builder-readonly policy", requested_effects=("artifact_write",))
    settings = load_settings()
    selected_target = target_profile(settings, _target(target))

    policy = create_read_policy(
        target_name=selected_target.name,
        target_repo=selected_target.repo,
        allowed_paths=allowed_path,
        denied_paths=denied_path,
        max_bytes_budget=budget,
        content_capture_allowed=content_capture,
        operator_note=note,
    )

    errors = validate_read_policy(policy)
    if errors:
        for error in errors:
            console.print(f"Policy validation error: {error}")
        raise typer.Exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json_lib.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    console.print(f"Read policy written to {output}")


@readonly_app.command("read")
def read_cmd(
    policy_path: Path = typer.Option(..., "--policy", help="Path to read policy JSON."),
    file_path: Path = typer.Option(..., "--file", help="Path to file to read."),
    output_dir: Path = typer.Option(..., "--output-dir", help="Directory to write read receipt."),
    session_id: str | None = typer.Option(None, "--session-id", help="Optional workflow session ID to log event to."),
) -> None:
    """Execute a governed read operation, producing a receipt and optional ledger event."""
    enforce_command_authority("builder-readonly read", requested_effects=("artifact_write",))
    if not policy_path.exists():
        console.print(f"Policy file not found: {policy_path}")
        raise typer.Exit(1)

    policy = json_lib.loads(policy_path.read_text(encoding="utf-8"))
    errors = validate_read_policy(policy)
    if errors:
        console.print(f"Invalid policy: {errors}")
        raise typer.Exit(1)

    receipt = execute_governed_read(policy, file_path)

    # Write receipt or denied record
    kind = receipt["kind"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if kind == READ_RECEIPT_KIND:
        receipt_path = output_dir / f"read_receipt_{int(time.time())}.json"
        receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"Read receipt written to {receipt_path}")
    else:
        receipt_path = output_dir / f"denied_read_{int(time.time())}.json"
        receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"Read denied: {receipt['reason']}. Written to {receipt_path}")

    # Log to workflow ledger if session_id is provided
    if session_id:
        sessions_dir = Path(".builder/sessions") / session_id
        events_dir = sessions_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)

        # Load existing events to determine sequence and current stage
        existing_records = load_event_records(events_dir)
        sequence = len(existing_records) + 1

        current_stage = "initialized"
        if existing_records:
            replay_report = replay_events(existing_records, session_id=session_id)
            if replay_report["valid"]:
                current_stage = replay_report["current_stage"]

        event_type = "read_executed" if kind == READ_RECEIPT_KIND else "read_denied"
        event_id = f"evt_read_{int(time.time())}_{sequence}"

        # Build subject refs pointing to receipt
        subject = artifact_ref(receipt, path=receipt_path, role="read_artifact", name="read receipt")
        policy_ref = artifact_ref(policy, path=policy_path, role="read_policy", name="read policy")

        event_record = create_event_record(
            event_id=event_id,
            session_id=session_id,
            sequence=sequence,
            event_type=event_type,
            stage=current_stage,
            subject_refs=[subject],
            command_surface="builder-readonly read",
            policy_snapshot_ref=policy_ref,
            message=f"Governed read of {file_path}",
        )

        event_path = events_dir / f"{sequence:03d}_{event_type}.json"
        write_event_record(event_record, event_path)
        console.print(f"Workflow event logged to {event_path}")

    if kind == DENIED_READ_KIND:
        raise typer.Exit(1)


@readonly_app.command("content-read")
def content_read_cmd(
    target: str = typer.Option("generic", "--target"),
    file_path: list[Path] = typer.Option(..., "--file", help="Explicit file path to read. Repeat for multiple files."),
    allowed_path: list[str] = typer.Option(None, "--allowed-path", help="Glob allow pattern. Defaults to explicit --file basenames."),
    output_dir: Path = typer.Option(..., "--output-dir", help="Directory for content-read receipts."),
    max_files: int = typer.Option(DEFAULT_MAX_CONTENT_READ_FILES, "--max-files"),
    max_bytes: int = typer.Option(DEFAULT_MAX_BYTES_PER_FILE, "--max-bytes"),
    session_id: str | None = typer.Option(None, "--session-id", help="Optional workflow session ID."),
) -> None:
    """Execute bounded content-read with redacted excerpt digests."""
    enforce_command_authority("builder-readonly content-read", requested_effects=("artifact_write",))
    if len(file_path) > max_files:
        console.print(f"Too many files: max {max_files}")
        raise typer.Exit(1)

    settings = load_settings()
    selected_target = target_profile(settings, _target(target))
    allowed = allowed_path or [p.name for p in file_path]
    policy = create_read_policy(
        target_name=selected_target.name,
        target_repo=selected_target.repo,
        allowed_paths=allowed,
        content_capture_allowed=True,
        operator_note="builder-readonly content-read",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    failures = 0
    for idx, path in enumerate(file_path):
        receipt = execute_content_read(policy, path, max_bytes_per_file=max_bytes, current_read_bytes=total_bytes)
        receipt_path = output_dir / f"content_read_{idx:03d}.json"
        receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if receipt.get("kind") == CONTENT_READ_RECEIPT_KIND:
            total_bytes += int(receipt.get("bytes_read", 0))
            console.print(f"Content-read receipt written to {receipt_path}")
        else:
            failures += 1
            console.print(f"Content-read denied for {path}: {receipt.get('reason')}")

        if session_id and receipt.get("kind") == CONTENT_READ_RECEIPT_KIND:
            events_dir = Path(".builder/sessions") / session_id / "events"
            events_dir.mkdir(parents=True, exist_ok=True)
            existing_records = load_event_records(events_dir)
            sequence = len(existing_records) + 1
            current_stage = "initialized"
            if existing_records:
                replay_report = replay_events(existing_records, session_id=session_id)
                if replay_report["valid"]:
                    current_stage = replay_report["current_stage"]
            event_record = create_event_record(
                event_id=f"evt_content_read_{int(time.time())}_{sequence}",
                session_id=session_id,
                sequence=sequence,
                event_type="content_read_executed",
                stage=current_stage,
                subject_refs=[artifact_ref(receipt, path=receipt_path, role="content_read_receipt", name="content read")],
                command_surface="builder-readonly content-read",
                policy_snapshot_ref=artifact_ref(policy, path=output_dir / "content-read-policy.json", role="read_policy", name="policy"),
                message=f"Governed content-read of {path}",
            )
            write_event_record(event_record, events_dir / f"{sequence:03d}_content_read_executed.json")

    if failures:
        raise typer.Exit(1)


@readonly_app.command("validate")
def validate(path: Path) -> None:
    """Validate a readonly inspection report, policy, or receipt file."""
    if not path.exists():
        console.print(f"File not found: {path}")
        raise typer.Exit(1)

    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        console.print(f"Invalid JSON: {exc}")
        raise typer.Exit(1)

    kind = data.get("kind")
    if kind == READ_POLICY_KIND:
        errors = validate_read_policy(data)
    elif kind == READ_RECEIPT_KIND:
        errors = validate_read_receipt(data)
    elif kind == CONTENT_READ_RECEIPT_KIND:
        errors = validate_content_read_receipt(data)
    else:
        errors = validate_readonly_inspection_report(data)

    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    console.print(f"File {path} of kind '{kind}' is valid.", soft_wrap=True)
