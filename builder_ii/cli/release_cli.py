from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import typer

from builder_ii.core.release_manifest import (
    create_release_evidence,
    validate_release_evidence,
    validate_release_proof_bundle_file,
)
from builder_ii.core.release_proof import (
    build_release_proof_bundle_directory,
    validate_release_proof_bundle_directory,
)

release_app = typer.Typer(help="Build and independently validate open-source-v1 release evidence.")


@release_app.command("host-proof")
def host_proof(
    output: Path = typer.Option(..., "--output"),
    lane: str = typer.Option(..., "--lane"),
    wheel: str = typer.Option(..., "--wheel"),
    wheel_sha256: str = typer.Option(..., "--wheel-sha256"),
    command: list[str] = typer.Option(..., "--command"),
    limitation: list[str] = typer.Option([], "--limitation"),
) -> None:
    """Record a completed host lane; command results are supplied by the invoking harness."""
    record = create_release_evidence(
        lane=lane,
        result="PASS",
        platform={
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        candidate={"wheel": wheel, "wheel_sha256": wheel_sha256},
        commands=[{"name": item, "result": "PASS"} for item in command],
        limitations=limitation,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    typer.echo(output)


@release_app.command("validate-evidence")
def validate_evidence(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        typer.echo(f"invalid release evidence: {exc}", err=True)
        raise typer.Exit(1) from exc
    errors = validate_release_evidence(data)
    if errors:
        for error in errors:
            typer.echo(error, err=True)
        raise typer.Exit(1)
    typer.echo("VALID")


@release_app.command("validate-bundle")
def validate_bundle(path: Path) -> None:
    errors = validate_release_proof_bundle_file(path)
    if errors:
        for error in errors:
            typer.echo(error, err=True)
        raise typer.Exit(1)
    typer.echo("VALID")


@release_app.command("build-bundle")
def build_bundle(
    repo: Path = typer.Option(Path("."), "--repo"),
    dist_dir: Path = typer.Option(..., "--dist-dir"),
    evidence_dir: Path = typer.Option(..., "--evidence-dir"),
    output_dir: Path = typer.Option(..., "--output-dir"),
) -> None:
    try:
        path = build_release_proof_bundle_directory(
            repo=repo, dist_dir=dist_dir, evidence_dir=evidence_dir, output_dir=output_dir
        )
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(path)


@release_app.command("validate-bundle-directory")
def validate_bundle_directory(path: Path, repo: Path | None = typer.Option(None, "--repo")) -> None:
    errors = validate_release_proof_bundle_directory(path, repo=repo)
    if errors:
        for error in errors:
            typer.echo(error, err=True)
        raise typer.Exit(1)
    typer.echo("VALID")


if __name__ == "__main__":
    sys.exit(release_app())
