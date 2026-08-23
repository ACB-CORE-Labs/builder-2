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
    model: str | None = typer.Option(None, "--model", help="Optional assertion; must equal WRP-selected model."),
    prompt: str | None = typer.Option(None, "--prompt", help="Text prompt to send to the model."),
    prompt_file: Path | None = typer.Option(None, "--prompt-file", help="Path to a file containing the prompt text."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="System prompt to override defaults."),
    max_tokens: int = typer.Option(256, "--max-tokens", help="Maximum tokens to generate."),
    temperature: float | None = typer.Option(None, "--temperature", help="Sampling temperature."),
    registry_path: Path | None = typer.Option(None, "--registry", help="Optional path to model client registry JSON."),
    execution_policy_path: Path | None = typer.Option(
        None, "--execution-policy", help="Path to model execution policy JSON."
    ),
    recommendation_path: Path = typer.Option(..., "--model-recommendation"),
    assignment_path: Path = typer.Option(..., "--model-assignment"),
    budget_path: Path = typer.Option(..., "--model-budget"),
    cloud_approval_path: Path | None = typer.Option(None, "--cloud-approval"),
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
    recommendation = _read_json(recommendation_path, lambda: {})
    assignment = _read_json(assignment_path, lambda: {})
    budget = _read_json(budget_path, lambda: {})
    cloud_approval = _read_json(cloud_approval_path, lambda: {}) if cloud_approval_path is not None else None

    settings = load_settings()
    from builder_ii.routing.gateway_invocation import governed_invocation_engine
    from builder_ii.routing.model_route_binding import build_model_route_binding

    if not session_id:
        console.print(
            "[red]Must specify --session-id for operational call. Use standalone-call if ledger is not required.[/]"
        )
        raise typer.Exit(1)

    route = build_model_route_binding(
        recommendation=recommendation,
        assignment=assignment,
        execution_policy=execution_policy,
        registry=registry,
        budget=budget,
        session_id=session_id,
        run_id=session_id,
        obligation_id=str(((assignment.get("bindings") or {}).get("task") or {}).get("profile_entry_id") or session_id),
        role=str(((assignment.get("bindings") or {}).get("agent") or {}).get("name") or "model_call"),
        temperature=temperature,
        max_tokens=max_tokens,
        cloud_approval=cloud_approval,
    )
    gateway = ModelExecutionGateway(
        settings,
        registry,
        execution_policy,
        invocation_engine=governed_invocation_engine(settings),
    )

    try:
        envelope, receipt, _debited = gateway.run_routed_model_call(
            route=route,
            prompt=actual_prompt,
            system_prompt=system_prompt or "Answer helpfully.",
            envelope_path=output_envelope,
            receipt_path=output_receipt,
            ledger_bound=True,
            budget=budget,
            budget_path=budget_path,
            requested_model_id=model,
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
            message=f"Model call executed: {route.selected_candidate.model_id}",
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


@model_app.command("benchmark")
def benchmark_cmd(
    profile: str = typer.Option("m1-v1", "--profile"),
    output: Path = typer.Option(..., "--output"),
    samples: Path | None = typer.Option(
        None, "--samples", help="Diagnostic/replay raw samples file (cannot qualify canonical m1-v1)."
    ),
    route_digest: str = typer.Option(..., "--route-digest"),
    policy_digest: str = typer.Option(..., "--policy-digest"),
    budget_digest: str = typer.Option(..., "--budget-digest"),
    backend: str = typer.Option("mlx-lm", "--backend"),
    provider: str = typer.Option("mlx_provider", "--provider"),
    client: str = typer.Option("mlx_lm_client", "--client"),
    model: str = typer.Option("mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", "--model"),
    model_pid: int | None = typer.Option(
        None, "--model-pid", help="PID of validated model server for live memory measurement."
    ),
    recommendation_path: Path = typer.Option(..., "--model-recommendation"),
    assignment_path: Path = typer.Option(..., "--model-assignment"),
    execution_policy_path: Path = typer.Option(..., "--execution-policy"),
    registry_path: Path = typer.Option(..., "--registry"),
    budget_path: Path = typer.Option(..., "--model-budget"),
    deepagents_obligation: list[Path] = typer.Option(
        ...,
        "--deepagents-obligation",
        help="Exactly two validated WRP Deep Agents obligation artifacts; repeat twice.",
    ),
) -> None:
    """Execute physical M1-v1 qualification under a frozen manifest and derive benchmark report."""
    enforce_command_authority(
        "builder-model benchmark",
        requested_effects=(
            "artifact_write",
            "model_execution",
            "runtime_start",
            "process_control",
            "readonly_subprocess",
            "external_tool_invocation",
        ),
    )
    if profile != "m1-v1":
        console.print("[red]Only the frozen m1-v1 profile is supported.[/]")
        raise typer.Exit(1)
    import subprocess

    from builder_ii.benchmark.model_runtime import (
        build_manifest,
        build_report,
        collect_canonical_m1_samples,
        validate_manifest,
        validate_report,
        write_json,
    )
    from builder_ii.routing.model_route_binding import build_model_route_binding

    try:
        # 1. Assert committed clean exact HEAD/tree
        status_proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if status_proc.stdout.strip():
            console.print(
                "[red]Working tree has uncommitted changes. Benchmark qualification requires a clean committed HEAD.[/]"
            )
            raise typer.Exit(1)

        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"], capture_output=True, text=True, check=True
        ).stdout.strip()

        recommendation = _read_json(recommendation_path, lambda: {})
        assignment = _read_json(assignment_path, lambda: {})
        execution_policy = _read_json(execution_policy_path, lambda: {})
        registry = _read_json(registry_path, lambda: {})
        budget = _read_json(budget_path, lambda: {})
        if len(deepagents_obligation) != 2:
            raise ValueError("--deepagents-obligation must be supplied exactly twice")
        obligations = [_read_json(path, lambda: {}) for path in deepagents_obligation]
        session_id = str(budget.get("session_id") or "")
        obligation_id = str(
            (((assignment.get("bindings") or {}).get("task") or {}).get("profile_entry_id")) or session_id
        )
        role = str((((assignment.get("bindings") or {}).get("agent") or {}).get("name")) or "benchmark")
        route = build_model_route_binding(
            recommendation=recommendation,
            assignment=assignment,
            execution_policy=execution_policy,
            registry=registry,
            budget=budget,
            session_id=session_id,
            run_id=session_id,
            obligation_id=obligation_id,
            role=role,
            temperature=0.0,
            max_tokens=int(execution_policy["max_tokens"]),
        )
        if route.route_digest != route_digest:
            raise ValueError("--route-digest does not equal the reconstructed WRP route")
        if route.policy_digest != policy_digest:
            raise ValueError("--policy-digest does not equal the validated execution policy")
        if route.budget_digest != budget_digest:
            raise ValueError("--budget-digest does not equal the validated model budget")

        # 2. Build + persist the benchmark manifest BEFORE observation
        manifest = build_manifest(
            git_commit=commit,
            git_tree=tree,
            backend=backend,
            provider=provider,
            client=client,
            model=model,
            route_digest=route_digest,
            policy_digest=policy_digest,
            budget_digest=budget_digest,
        )
        write_json(manifest, output / "model-runtime-benchmark-manifest.json")

        # 3. Execute physical collection or diagnostic replay
        if samples is not None:
            if not samples.is_file():
                console.print(f"[red]Samples file not found: {samples}[/]")
                raise typer.Exit(1)
            raw_samples = json_lib.loads(samples.read_text(encoding="utf-8"))
            raw_samples["qualification_mode"] = "REPLAY"
        else:
            raw_samples = collect_canonical_m1_samples(
                manifest=manifest,
                model_pid=model_pid,
                output_dir=output,
                route=route,
                route_sources={
                    "recommendation": recommendation,
                    "assignment": assignment,
                    "execution_policy": execution_policy,
                    "registry": registry,
                    "budget": budget,
                    "session_id": session_id,
                    "run_id": session_id,
                    "obligation_id": obligation_id,
                    "role": role,
                    "temperature": 0.0,
                    "max_tokens": int(execution_policy["max_tokens"]),
                    "source_paths": {
                        "recommendation": str(recommendation_path),
                        "assignment": str(assignment_path),
                        "execution_policy": str(execution_policy_path),
                        "registry": str(registry_path),
                        "budget": str(budget_path),
                    },
                },
                obligations=obligations,
            )
            write_json(raw_samples, output / "model-runtime-benchmark-raw-samples.json")

        # 4. Derive report from collector-produced samples
        report = build_report(manifest=manifest, samples=raw_samples)
        write_json(report, output / "model-runtime-benchmark-report.json")

        # 5. Independently validate manifest and report
        m_errs = validate_manifest(manifest)
        if m_errs:
            raise ValueError(f"manifest validation failed: {'; '.join(m_errs)}")
        r_errs = validate_report(report, manifest=manifest)
        if r_errs:
            raise ValueError(f"report validation failed: {'; '.join(r_errs)}")

    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Benchmark failed closed: {exc}[/]")
        raise typer.Exit(1)

    console.print(
        json_lib.dumps(
            {
                "overall_state": report["overall_state"],
                "manifest_digest": manifest["manifest_digest"],
                "samples_digest": raw_samples.get("samples_digest"),
                "report_digest": report["report_digest"],
            },
            sort_keys=True,
        )
    )
    if report["overall_state"] != "PASS":
        raise typer.Exit(1)


if __name__ == "__main__":
    model_app()
