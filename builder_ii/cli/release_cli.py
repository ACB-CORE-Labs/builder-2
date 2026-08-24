from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
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
    canonical_json_sha256,
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
    source_commit: str = typer.Option(..., "--source-commit"),
    source_tree: str = typer.Option(..., "--source-tree"),
    elapsed_seconds: int = typer.Option(..., "--elapsed-seconds", min=0),
    log: list[Path] = typer.Option(..., "--log"),
    skip: list[str] = typer.Option([], "--skip"),
    claims_json: Path = typer.Option(..., "--claims-json"),
) -> None:
    """Record a completed host lane; command results are supplied by the invoking harness."""

    def version(command: list[str], *, unavailable: str = "UNAVAILABLE_RECORDED") -> str:
        if shutil.which(command[0]) is None:
            return unavailable
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        value = (result.stdout or result.stderr).strip().splitlines()
        return value[0] if value else unavailable

    log_refs = []
    constituent_dir = output.parent / "constituents"
    constituent_dir.mkdir(parents=True, exist_ok=True)
    for item in log:
        raw = item.read_bytes()
        import hashlib

        target = constituent_dir / f"{lane}-{item.name}"
        target.write_bytes(raw)
        log_refs.append(
            {
                "kind": "builder_ii.release_log",
                "path": f"evidence/constituents/{target.name}",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    claims = json.loads(claims_json.read_text(encoding="utf-8"))
    for field, value in list(claims.items()):
        if not field.endswith("_ref") or not isinstance(value, dict):
            continue
        source_path = Path(str(value.get("path", "")))
        if not source_path.is_file() or source_path.is_symlink():
            raise typer.BadParameter(f"claims.{field}.path must be a real local artifact file")
        target = constituent_dir / f"{lane}-{field}-{source_path.name}"
        target.write_bytes(source_path.read_bytes())
        claims[field] = {
            "kind": value.get("kind"),
            "path": f"evidence/constituents/{target.name}",
            "sha256": canonical_json_sha256(target),
        }
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
        source={"commit": source_commit, "tree": source_tree},
        runtime_versions={
            "python": platform.python_version(),
            "uv": version(["uv", "--version"]),
            "git": version(["git", "--version"]),
            "goose": version(["goose", "--version"]),
            "container_runtime": os.environ.get(
                "RELEASE_CONTAINER_RUNTIME_VERSION",
                version(["docker", "--version"], unavailable="NOT_APPLICABLE"),
            ),
        },
        elapsed_seconds=elapsed_seconds,
        skips=skip,
        log_refs=log_refs,
        claims=claims,
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
