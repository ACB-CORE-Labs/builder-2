from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    validate_registry_invariants,
)
from builder_ii.config import load_settings
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
from builder_ii.demo_loop import (
    dumps_demo_report,
    run_demo_loop,
    validate_demo_report,
)
from builder_ii.onboarding_intent import validate_onboarding_intent_report_artifact
from builder_ii.operator_golden_path import (
    create_operator_golden_path_report,
    dumps_operator_golden_path_report,
    validate_operator_golden_path_report,
    write_operator_golden_path_report,
)
from builder_ii.operator_next import (
    create_operator_next_action_report,
    dumps_operator_next_action_report,
    validate_operator_next_action_report,
    write_operator_next_action_report,
)
from builder_ii.operator_status import (
    create_operator_status_report,
    dumps_operator_status_report,
    validate_operator_status_report,
    write_operator_status_report,
)
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


@platform_app.command("known-limitations")
def known_limitations(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write the rendered document (e.g. docs/KNOWN_LIMITATIONS.md).",
    ),
) -> None:
    """Render the known-limitations document from the completion truth matrix."""
    from builder_ii.known_limitations import render_known_limitations_markdown

    _validate_or_exit(root=Path.cwd())
    text = render_known_limitations_markdown()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        console.print(f"Known-limitations document written to {output}")
    else:
        console.out(text, end="")


@platform_app.command("operator-status")
def operator_status(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write the operator status JSON artifact.",
    ),
) -> None:
    """Generate and validate the B9 governed operator status report."""
    _validate_or_exit(root=Path.cwd())

    report = create_operator_status_report()
    errors = validate_operator_status_report(report)

    if errors:
        for error in errors:
            console.print(f"[red]operator status validation error:[/] {error}")
        raise typer.Exit(1)

    if output:
        write_operator_status_report(report, output.resolve())

    console.out(dumps_operator_status_report(report), end="")


@platform_app.command("next")
def next_action(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write the operator next action JSON artifact.",
    ),
) -> None:
    """Generate and validate the B9 governed operator next action report."""
    _validate_or_exit(root=Path.cwd())

    report = create_operator_next_action_report()
    errors = validate_operator_next_action_report(report)

    if errors:
        for error in errors:
            console.print(f"[red]operator next action validation error:[/] {error}")
        raise typer.Exit(1)

    if output:
        write_operator_next_action_report(report, output.resolve())

    console.out(dumps_operator_next_action_report(report), end="")


@platform_app.command("golden-path")
def golden_path(
    target: str = typer.Option(
        ...,
        "--target",
        "-t",
        help="Target profile name to execute golden path against.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Path to write the operator golden path JSON artifact.",
    ),
) -> None:
    """Generate the B9 governed operator golden path report."""
    _validate_or_exit(root=Path.cwd())

    output_dir = output_dir.resolve()
    report = create_operator_golden_path_report(target_profile=target, output_dir=output_dir)
    errors = validate_operator_golden_path_report(report)

    if errors:
        for error in errors:
            console.print(f"[red]operator golden path validation error:[/] {error}")
        raise typer.Exit(1)

    write_operator_golden_path_report(report, output_dir / "golden-path-report.json")
    console.out(dumps_operator_golden_path_report(report), end="")


@platform_app.command("validate-golden-path")
def validate_golden_path(
    report_file: Path = typer.Argument(
        ...,
        help="Path to the golden-path-report.json artifact to validate.",
    ),
) -> None:
    """Validate a B9 governed operator golden path report."""
    report_file = report_file.resolve()
    if not report_file.is_file():
        console.print(f"[red]report file is not a valid file:[/] {report_file}")
        raise typer.Exit(1)

    try:
        data = json_lib.loads(report_file.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as e:
        console.print(f"[red]report file is not valid JSON:[/] {e}")
        raise typer.Exit(1)

    errors = validate_operator_golden_path_report(data)

    if errors:
        for error in errors:
            console.print(f"[red]operator golden path validation error:[/] {error}")
        raise typer.Exit(1)

    console.out(
        json_lib.dumps({"valid": True, "report_file": str(report_file)}, indent=2, sort_keys=True) + "\n", end=""
    )


@platform_app.command("demo-loop")
def demo_loop(
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Directory where the demo evidence bundle will be written.",
    ),
    target_repo: Path | None = typer.Option(
        None,
        "--target-repo",
        "--core-repo",
        help=(
            "Path to the demo target git checkout. Defaults to configured "
            "BUILDER_TARGET_REPO/CORE_REPO_PATH. (--core-repo is a deprecated alias.)"
        ),
    ),
    target_name: str = typer.Option(
        "generic",
        "--target-name",
        help=(
            'Demo target profile name. "core" enables the AssetOverflow/core identity check and '
            "CORE sensitive-module policy; any other name uses the generic spec."
        ),
    ),
    marker_path: str | None = typer.Option(
        None,
        "--marker-path",
        help="Relative path of the temporary demo marker file (default docs/builder_ii_demo_marker.md).",
    ),
    phase: str = typer.Option(
        "prepare",
        "--phase",
        help="Guided phase: prepare, approve, apply, verify, rollback, finalize, or all.",
    ),
    approve: bool = typer.Option(
        False,
        "--approve",
        help=(
            "Approve the exact demo patch digest for the temporary demo worktree. "
            "Intended for recorded walkthrough checkpoints and tests."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace an existing temporary demo worktree under output-dir.",
    ),
    cleanup_worktree: bool = typer.Option(
        False,
        "--cleanup-worktree",
        help="Remove the temporary demo worktree after a completed finalize/all run.",
    ),
) -> None:
    """Run the guided governed demo loop against a temporary detached worktree of the target repo."""
    _validate_or_exit(root=Path.cwd())
    settings = load_settings()
    selected_target_repo = (target_repo or settings.core_repo).expanduser().resolve()
    try:
        report = run_demo_loop(
            target_repo=selected_target_repo,
            output_dir=output_dir.resolve(),
            target_name=target_name,
            marker_path=marker_path,
            phase=phase,  # type: ignore[arg-type]
            approve=approve,
            force=force,
            cleanup_worktree=cleanup_worktree,
        )
    except Exception as exc:
        console.print(f"[red]demo loop failed:[/] {exc}")
        raise typer.Exit(1)
    console.out(dumps_demo_report(report), end="")


@platform_app.command("validate-demo-loop")
def validate_demo_loop(
    report_file: Path = typer.Argument(
        ...,
        help="Path to demo-loop-report.json.",
    ),
) -> None:
    """Validate a governed demo loop report artifact."""
    report_file = report_file.resolve()
    if not report_file.is_file():
        console.print(f"[red]report file is not a valid file:[/] {report_file}")
        raise typer.Exit(1)
    try:
        data = json_lib.loads(report_file.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        console.print(f"[red]report file is not valid JSON:[/] {exc}")
        raise typer.Exit(1)
    errors = validate_demo_report(data)
    if errors:
        for error in errors:
            console.print(f"[red]demo report validation error:[/] {error}")
        raise typer.Exit(1)
    console.out(
        json_lib.dumps({"valid": True, "report_file": str(report_file)}, indent=2, sort_keys=True) + "\n", end=""
    )


@platform_app.command("wow")
def wow(
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Directory where the demo evidence bundle will be written.",
    ),
    target_repo: Path | None = typer.Option(
        None,
        "--target-repo",
        "--core-repo",
        help="Path to the demo target git checkout. (--core-repo is a deprecated alias.)",
    ),
    target_name: str = typer.Option(
        "generic",
        "--target-name",
        help='Demo target profile name ("core" selects the CORE profile).',
    ),
    approve: bool = typer.Option(False, "--approve", help="Approve the temporary demo worktree patch."),
    force: bool = typer.Option(False, "--force", help="Replace an existing temporary demo worktree."),
) -> None:
    """Alias for the governed demo loop, reserved for recording the product walkthrough."""
    settings = load_settings()
    selected_target_repo = (target_repo or settings.core_repo).expanduser().resolve()
    try:
        report = run_demo_loop(
            target_repo=selected_target_repo,
            output_dir=output_dir.resolve(),
            target_name=target_name,
            phase="all" if approve else "prepare",
            approve=approve,
            force=force,
        )
    except Exception as exc:
        console.print(f"[red]demo loop failed:[/] {exc}")
        raise typer.Exit(1)
    console.out(dumps_demo_report(report), end="")


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
        "digest": onboarding_res.rollback_snapshot.get("snapshot_digest")
        or onboarding_res.rollback_snapshot.get("snapshot_id"),
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
