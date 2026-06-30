from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    validate_registry_invariants,
)
from builder_ii.config_schema import (
    create_config_schema_artifact,
    validate_config_schema_artifact,
    write_config_schema_artifact,
)
from builder_ii.config_sources import (
    resolve_config_sources,
    validate_config_resolution_artifact,
    write_config_resolution_artifact,
)
from builder_ii.onboarding_intent import validate_onboarding_intent_report_artifact
from builder_ii.platform_completion_audit import (
    dumps_docs_audit,
    dumps_matrix,
    render_docs_audit_jsonable,
    render_human_summary,
    validate_command_surfaces,
    validate_completion_matrix,
)
from builder_ii.r1_closure_report import (
    dumps_r1_closure_report,
    finalize_r1_closure_report,
    format_docs_violation,
    validate_r1_closure_report_artifact,
    validate_r1_closure_report_file,
    write_r1_closure_report,
)
from builder_ii.setup_onboarding import run_onboarding_pipeline
from builder_ii.setup_overlay import validate_setup_overlay_plan_artifact
from builder_ii.setup_plan import validate_setup_plan_artifact
from builder_ii.setup_rollback import validate_setup_rollback_snapshot_artifact


platform_app = typer.Typer(
    help="Render builder-II platform completion truth without runtime, model, tool, Goose, or deepagents execution.",
    no_args_is_help=True,
)
console = Console()


def _registry_names() -> set[str]:
    return {record.name for record in COMMAND_AUTHORITY_REGISTRY}


def _validate_or_exit(root: Path | None = None) -> None:
    errors = validate_completion_matrix(root=root)
    errors.extend(validate_command_surfaces(_registry_names()))
    if errors:
        for error in errors:
            console.print(f"[red]platform truth validation error:[/] {error}")
        raise typer.Exit(1)


@platform_app.command("matrix")
def matrix() -> None:
    """Print the source-derived platform capability matrix as JSON."""
    _validate_or_exit(root=Path.cwd())
    console.out(dumps_matrix(), end="")


@platform_app.command("status")
def status() -> None:
    """Print concise human-readable platform truth state."""
    _validate_or_exit(root=Path.cwd())
    console.out(render_human_summary(), end="")


@platform_app.command("audit-docs")
def audit_docs(
    root: Path = typer.Option(
        Path("."),
        "--root",
        "-r",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Repository root whose README.md and docs/**/*.md files should be audited.",
    ),
) -> None:
    """Scan docs for false operational completion language."""
    root = root.resolve()
    _validate_or_exit(root=root)
    report = render_docs_audit_jsonable(root)
    console.out(dumps_docs_audit(root), end="")
    if not report["valid"]:
        raise typer.Exit(1)


@platform_app.command("r1-closure")
def r1_closure(
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Directory where R1 closure report and evidence chain artifacts will be written.",
    ),
    root: Path = typer.Option(
        Path("."),
        "--root",
        "-r",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Target project root for configuration resolution.",
    ),
) -> None:
    """Generate and validate the R1 closure report and golden-path proof artifacts."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix_errors = validate_completion_matrix(root=root)
    matrix_errors.extend(validate_command_surfaces(_registry_names()))
    platform_matrix_status = {
        "valid": len(matrix_errors) == 0,
        "errors": matrix_errors,
    }

    auth_errors = validate_registry_invariants()
    command_authority_status = {
        "valid": len(auth_errors) == 0,
        "errors": auth_errors,
    }

    docs_report = render_docs_audit_jsonable(root)
    docs_truth_status = {
        "valid": docs_report["valid"],
        "violations": docs_report["violations"],
        "scanned_files": docs_report["scanned_files"],
    }

    resolution = resolve_config_sources(project_root=root)
    res_jsonable = resolution.to_jsonable()
    res_errors = validate_config_resolution_artifact(res_jsonable)
    if not resolution.errors and not res_errors:
        write_config_resolution_artifact(resolution, output_dir / "config-resolution.json")
    config_resolution_status = {
        "valid": len(resolution.errors) == 0 and len(res_errors) == 0,
        "path": str(output_dir / "config-resolution.json"),
        "digest": res_jsonable.get("digest"),
        "errors": list(resolution.errors) + list(res_errors),
    }

    schema_art = create_config_schema_artifact()
    schema_errors = validate_config_schema_artifact(schema_art)
    if not schema_errors:
        write_config_schema_artifact(output_dir / "config-schema.json")
    config_schema_status = {
        "valid": len(schema_errors) == 0,
        "path": str(output_dir / "config-schema.json"),
        "digest": schema_art.get("digest"),
        "errors": list(schema_errors),
    }

    onboarding_res = run_onboarding_pipeline(
        output_dir=output_dir,
        onboarding_mode="init",
        root=root,
        resolution=resolution,
    )

    setup_plan_errors = validate_setup_plan_artifact(onboarding_res.setup_plan)
    setup_plan_status = {
        "valid": len(setup_plan_errors) == 0 and onboarding_res.valid,
        "path": str(onboarding_res.setup_plan_path),
        "digest": onboarding_res.setup_plan.get("plan_digest"),
        "errors": list(setup_plan_errors) + list(onboarding_res.errors),
    }

    overlay_errors = validate_setup_overlay_plan_artifact(onboarding_res.overlay_plan)
    overlay_plan_status = {
        "valid": len(overlay_errors) == 0 and onboarding_res.valid,
        "path": str(onboarding_res.setup_overlay_path),
        "digest": onboarding_res.overlay_plan.get("overlay_plan_digest"),
        "errors": list(overlay_errors) + list(onboarding_res.errors),
    }

    snapshot_errors = validate_setup_rollback_snapshot_artifact(onboarding_res.rollback_snapshot)
    rollback_snapshot_status = {
        "valid": len(snapshot_errors) == 0 and onboarding_res.valid,
        "path": str(onboarding_res.rollback_snapshot_path),
        "digest": onboarding_res.rollback_snapshot.get("snapshot_digest") or onboarding_res.rollback_snapshot.get("snapshot_id"),
        "errors": list(snapshot_errors) + list(onboarding_res.errors),
    }

    intent_errors = validate_onboarding_intent_report_artifact(onboarding_res.onboarding_intent)
    onboarding_intent_status = {
        "valid": len(intent_errors) == 0 and onboarding_res.valid,
        "path": str(onboarding_res.onboarding_intent_path),
        "digest": onboarding_res.onboarding_intent.get("onboarding_intent_digest"),
        "errors": list(intent_errors) + list(onboarding_res.errors),
    }

    deferred_apply = onboarding_res.onboarding_intent.get("apply_command") or ""
    deferred_rollback = onboarding_res.onboarding_intent.get("rollback_command") or ""

    report = finalize_r1_closure_report(
        target_profile=resolution.value("active_target_profile"),
        artifact_root=str(output_dir),
        output_dir=str(output_dir),
        config_schema_status=config_schema_status,
        config_resolution_status=config_resolution_status,
        setup_plan_status=setup_plan_status,
        overlay_plan_status=overlay_plan_status,
        rollback_snapshot_status=rollback_snapshot_status,
        onboarding_intent_status=onboarding_intent_status,
        command_authority_status=command_authority_status,
        platform_matrix_status=platform_matrix_status,
        docs_truth_status=docs_truth_status,
        deferred_apply_command=deferred_apply,
        deferred_rollback_command=deferred_rollback,
    )

    report_errors = validate_r1_closure_report_artifact(report)
    if report_errors:
        report["errors"].extend(report_errors)
        report["valid"] = False

    write_r1_closure_report(report, output_dir / "r1-closure-report.json")
    console.out(dumps_r1_closure_report(report), end="")
    if not report["valid"]:
        raise typer.Exit(1)


@platform_app.command("validate-r1-closure")
def validate_r1_closure(
    report_file: Path = typer.Argument(
        ...,
        help="Path to the r1-closure-report.json artifact to validate.",
    ),
    root: Path = typer.Option(
        Path("."),
        "--root",
        "-r",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Repository root for verifying docs/matrix/authority live status.",
    ),
) -> None:
    """Validate an R1 closure report artifact and its referenced R1 chain evidence files."""
    report_file = report_file.resolve()
    root = root.resolve()
    errors = validate_r1_closure_report_file(report_file, check_evidence_chain=True)

    matrix_errors = validate_completion_matrix(root=root)
    matrix_errors.extend(validate_command_surfaces(_registry_names()))
    errors.extend(f"platform matrix error: {e}" for e in matrix_errors)

    auth_errors = validate_registry_invariants()
    errors.extend(f"command authority error: {e}" for e in auth_errors)

    docs_report = render_docs_audit_jsonable(root)
    if not docs_report["valid"]:
        errors.extend(format_docs_violation(v) for v in docs_report["violations"])

    summary = {
        "valid": len(errors) == 0,
        "report_file": str(report_file),
        "errors": errors,
    }
    console.out(json_lib.dumps(summary, indent=2, sort_keys=True) + "\n", end="")
    if not summary["valid"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    platform_app()
