from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.performance_measurements import (
    create_performance_measurement_record,
    dumps_performance_measurement_record,
    validate_performance_measurement_record,
    validate_performance_measurement_record_file,
    write_performance_measurement_record,
)
from builder_ii.target_profiles import TargetName, target_names
from builder_ii.validation_benchmark import (
    benchmark_validator,
    validate_validation_benchmark,
    generate_parity_report,
    validate_validation_parity_report,
)
import json as json_lib


performance_app = typer.Typer(help="Create and validate explicit performance measurement records.")
console = Console(width=240)
_VALID_TARGETS = set(target_names())


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@performance_app.command("record")
def record(
    target: str = typer.Option("generic", "--target"),
    candidate_name: str = typer.Option(..., "--candidate-name"),
    metric_name: str = typer.Option(..., "--metric-name"),
    metric_value: float = typer.Option(..., "--metric-value"),
    unit: str = typer.Option(..., "--unit"),
    method: str = typer.Option(..., "--method"),
    source_ref: str = typer.Option(..., "--source-ref"),
    status: str = typer.Option("candidate", "--status"),
    baseline_value: float | None = typer.Option(None, "--baseline-value"),
    evidence_ref: list[str] = typer.Option([], "--evidence-ref"),
    note: list[str] = typer.Option([], "--note"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item = create_performance_measurement_record(
        target=_target(target),
        candidate_name=candidate_name,
        metric_name=metric_name,
        metric_value=metric_value,
        unit=unit,
        method=method,
        source_ref=source_ref,
        status=status,
        baseline_value=baseline_value,
        evidence_refs=tuple(evidence_ref),
        notes=tuple(note),
    )
    errors = validate_performance_measurement_record(item)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_performance_measurement_record(item, output)
        console.print(f"Performance measurement record written to {output}")
    else:
        console.out(dumps_performance_measurement_record(item), end="")


@performance_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_performance_measurement_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Performance measurement record {path} is valid.")


@performance_app.command("benchmark-validation")
def benchmark_validation(
    kind: str = typer.Option("builder_ii.goose_session_manifest", "--kind", help="Artifact kind to benchmark"),
    count: int = typer.Option(1000, "--count", help="Number of validation iterations"),
    backend: str = typer.Option("python", "--backend", help="Validation backend: python or rust"),
    output: Path | None = typer.Option(None, "--output", help="Output JSON path for the benchmark record"),
) -> None:
    """Benchmark validation cost for a specific artifact kind and backend."""
    try:
        record_data = benchmark_validator(kind, count, backend=backend)
    except Exception as e:
        console.print(f"Failed to benchmark validator: {e}")
        raise typer.Exit(1)

    errors = validate_validation_benchmark(record_data)
    if errors:
        for error in errors:
            console.print(f"Validation benchmark schema error: {error}")
        raise typer.Exit(1)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(record_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"Validation benchmark record written to {output}")
    else:
        console.out(json_lib.dumps(record_data, indent=2, sort_keys=True) + "\n", end="")


@performance_app.command("parity-report")
def parity_report(
    kind: str = typer.Option("builder_ii.goose_session_manifest", "--kind", help="Artifact kind to verify"),
    count: int = typer.Option(100, "--count", help="Number of test iterations"),
    output: Path | None = typer.Option(None, "--output", help="Output JSON path for the parity report"),
) -> None:
    """Compare Python and Rust validation outputs for correctness/parity."""
    try:
        report_data = generate_parity_report(kind, count)
    except Exception as e:
        console.print(f"Failed to generate parity report: {e}")
        raise typer.Exit(1)

    errors = validate_validation_parity_report(report_data)
    if errors:
        for error in errors:
            console.print(f"Parity report validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(report_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"Validation parity report written to {output}")
    else:
        console.out(json_lib.dumps(report_data, indent=2, sort_keys=True) + "\n", end="")


