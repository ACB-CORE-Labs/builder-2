from __future__ import annotations

import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.artifact_chain_verification import VALIDATORS, extract_references
from builder_ii.artifact_memory import (
    ATOM_STATES,
    CLAIM_BOUNDARIES,
    MEMORY_INDEX_KIND,
    REVIEW_STATES,
    SOURCE_TRUTH_STATES,
    SUMMARY_ORIGINS,
    create_memory_atom,
    create_memory_index,
    create_memory_index_entry,
    create_memory_reconstruction,
    create_memory_ref,
    create_memory_search_result,
    dumps_memory_record,
    validate_memory_atom,
    validate_memory_atom_file,
    validate_memory_index,
    validate_memory_index_file,
    validate_memory_reconstruction,
    validate_memory_reconstruction_file,
    validate_memory_search_result,
    validate_memory_search_result_file,
    write_memory_atom,
    write_memory_index,
    write_memory_reconstruction,
    write_memory_search_result,
)
from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.workflow_records import canonical_digest

memory_app = typer.Typer(
    help="Create and validate governed artifact-memory atoms, indexes, reconstructions, and deterministic search results.",
    no_args_is_help=True,
)
console = Console()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        console.print(f"[red]file not found:[/] {path}")
        raise typer.Exit(1)
    except json_lib.JSONDecodeError as exc:
        console.print(f"[red]invalid JSON:[/] {exc}")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]failed to read file:[/] {exc}")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        console.print("[red]artifact must be a JSON object[/]")
        raise typer.Exit(1)
    return data


def _print_or_write(record: dict[str, Any], output: Path | None, writer: Any) -> None:
    if output is None:
        echo_stdout(dumps_memory_record(record))
        return
    writer(record, output)
    console.print(f"{record['kind']} written to {output}")


def _report_validation(errors: list[str]) -> None:
    if not errors:
        return
    for error in errors:
        console.print(f"[red]validation error:[/] {error}")
    raise typer.Exit(1)


def _infer_target_profile(data: dict[str, Any]) -> str:
    if isinstance(data.get("target_profile"), str) and data["target_profile"]:
        return data["target_profile"]
    if isinstance(data.get("target_name"), str) and data["target_name"]:
        return data["target_name"]
    target = data.get("target")
    if isinstance(target, str) and target:
        return target
    if isinstance(target, dict):
        for key in ("name", "target_name", "profile_name"):
            if isinstance(target.get(key), str) and target[key]:
                return target[key]
    return "generic"


def _infer_task(data: dict[str, Any], *, source_path: Path) -> str:
    for key in ("task", "summary", "topic", "reason", "bundle_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{data.get('kind', 'artifact')} from {source_path.name}"


def _infer_summary(data: dict[str, Any], *, source_path: Path) -> str:
    for key in ("summary", "task", "topic", "reason", "task_summary"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{data.get('kind', 'artifact')} @ {source_path.name}"


def _default_claim_boundary(kind: str) -> str:
    if kind in {
        "builder_ii.verification_execution_receipt",
        "builder_ii.execution_verification_record",
        "builder_ii.verification_profile_report",
    }:
        return "verification_result"
    if kind in {
        "builder_ii.handoff_note",
        "builder_ii.handoff_artifact",
        "builder_ii.handoff_bundle_record",
    }:
        return "reviewed_handoff"
    if "proposal" in kind or "plan" in kind or "candidate" in kind:
        return "proposal_only"
    return "metadata_only"


def _validate_source_artifact(data: dict[str, Any], *, source_path: Path) -> None:
    kind = str(data.get("kind", ""))
    if not kind:
        console.print(f"[red]{source_path} is missing kind[/]")
        raise typer.Exit(1)
    validator = VALIDATORS.get(kind)
    if validator is None:
        console.print(f"[red]unknown source artifact kind:[/] {kind}")
        raise typer.Exit(1)
    errors = validator(data)
    if errors:
        for error in errors:
            console.print(f"[red]source artifact validation error:[/] {error}")
        raise typer.Exit(1)


def _source_refs_from_artifact(data: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in extract_references(data):
        expected_kind = ref.get("expected_kind")
        path = ref.get("path")
        sha256 = ref.get("sha256")
        if not isinstance(expected_kind, str) or not expected_kind:
            continue
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(sha256, str) or not sha256:
            continue
        field = str(ref.get("field", "source_ref")).replace("[", "_").replace("]", "").replace(".", "_")
        refs.append(
            create_memory_ref(
                kind=expected_kind,
                path=path,
                sha256=sha256,
                role=f"source_ref.{field}",
                name=Path(path).name,
            )
        )
    return refs


def _load_validated_atom(path: Path) -> dict[str, Any]:
    atom = _load_json(path)
    _report_validation(validate_memory_atom(atom))
    return atom


def _load_validated_index(path: Path) -> dict[str, Any]:
    index = _load_json(path)
    _report_validation(validate_memory_index(index))
    return index


@memory_app.command("atom")
def atom(
    source_artifact: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Validated source artifact to wrap as a governed memory atom.",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional output path for the memory atom JSON artifact."
    ),
    target_profile: str | None = typer.Option(None, "--target-profile", help="Override inferred target profile."),
    task: str | None = typer.Option(None, "--task", help="Override inferred task label."),
    summary: str | None = typer.Option(None, "--summary", help="Optional reviewable summary text."),
    tag: list[str] = typer.Option([], "--tag", help="Repeatable tag for deterministic search."),
    claim_boundary: str | None = typer.Option(
        None, "--claim-boundary", help=f"Claim boundary override: {', '.join(CLAIM_BOUNDARIES)}"
    ),
    review_state: str = typer.Option("validated", "--review-state", help=f"Review state: {', '.join(REVIEW_STATES)}"),
    atom_state: str = typer.Option("ACTIVE", "--atom-state", help=f"Atom state: {', '.join(ATOM_STATES)}"),
    source_truth_state: str = typer.Option(
        "SOURCE_BOUND", "--source-truth-state", help=f"Source truth state: {', '.join(SOURCE_TRUTH_STATES)}"
    ),
    summary_origin: str | None = typer.Option(
        None, "--summary-origin", help=f"Summary origin: {', '.join(SUMMARY_ORIGINS)}"
    ),
    created_at: str | None = typer.Option(
        None, "--created-at", help="RFC3339 UTC timestamp for deterministic fixtures."
    ),
) -> None:
    """Wrap a validated source artifact as a governed memory atom."""
    source_artifact = source_artifact.resolve()
    data = _load_json(source_artifact)
    _validate_source_artifact(data, source_path=source_artifact)

    artifact_ref = create_memory_ref(
        kind=str(data.get("kind", "")),
        path=source_artifact,
        sha256=canonical_digest(data),
        role="source_artifact",
        name=source_artifact.name,
    )
    atom_record = create_memory_atom(
        artifact_ref=artifact_ref,
        target_profile=target_profile or _infer_target_profile(data),
        task=task or _infer_task(data, source_path=source_artifact),
        created_at_utc=created_at or _utc_now(),
        claim_boundary=claim_boundary or _default_claim_boundary(str(data.get("kind", ""))),
        review_state=review_state,
        atom_state=atom_state,
        source_truth_state=source_truth_state,
        summary_text=summary or _infer_summary(data, source_path=source_artifact),
        summary_origin=summary_origin or ("operator" if summary else "artifact_projection"),
        tags=tag,
        source_refs=_source_refs_from_artifact(data),
    )
    _report_validation(validate_memory_atom(atom_record))
    _print_or_write(atom_record, output, write_memory_atom)


@memory_app.command("index")
def index(
    atom_paths: list[Path] = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Memory atom artifact paths to include in the index."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional output path for the memory index artifact."
    ),
    index_name: str = typer.Option("", "--index-name", help="Optional name for the generated memory index."),
    task_scope: str = typer.Option("", "--task-scope", help="Optional task scope label."),
    created_at: str | None = typer.Option(
        None, "--created-at", help="RFC3339 UTC timestamp for deterministic fixtures."
    ),
) -> None:
    """Build a deterministic governed memory index from explicit memory atoms."""
    atoms = [_load_validated_atom(path.resolve()) for path in atom_paths]
    target_profiles = {atom.get("target_profile") for atom in atoms}
    if len(target_profiles) != 1:
        console.print("[red]all indexed atoms must share a single target_profile[/]")
        raise typer.Exit(1)
    entries = [
        create_memory_index_entry(atom, path=path.resolve()) for atom, path in zip(atoms, atom_paths, strict=True)
    ]
    record = create_memory_index(
        entries=entries,
        target_profile=str(next(iter(target_profiles))),
        created_at_utc=created_at or _utc_now(),
        index_name=index_name,
        task_scope=task_scope,
    )
    _report_validation(validate_memory_index(record))
    _print_or_write(record, output, write_memory_index)


@memory_app.command("search")
def search(
    index_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Memory index artifact path."
    ),
    query: str = typer.Option(
        "", "--query", "-q", help="Deterministic lexical query. Empty query replays active atoms in stable order."
    ),
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum number of matches to emit."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional output path for the memory search result artifact."
    ),
    created_at: str | None = typer.Option(
        None, "--created-at", help="RFC3339 UTC timestamp for deterministic fixtures."
    ),
) -> None:
    """Search an explicit memory index with deterministic lexical scoring only."""
    index_path = index_path.resolve()
    index_record = _load_validated_index(index_path)
    index_ref = create_memory_ref(
        kind=MEMORY_INDEX_KIND,
        path=index_path,
        sha256=canonical_digest(index_record),
        role="memory_index",
        name=index_path.name,
    )
    result = create_memory_search_result(
        index_record,
        index_ref=index_ref,
        query=query,
        created_at_utc=created_at or _utc_now(),
        limit=limit,
    )
    _report_validation(validate_memory_search_result(result))
    _print_or_write(result, output, write_memory_search_result)


@memory_app.command("reconstruct")
def reconstruct(
    index_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, readable=True, help="Memory index artifact path."
    ),
    query: str = typer.Option(
        "", "--query", "-q", help="Deterministic lexical query. Empty query replays active atoms in stable order."
    ),
    max_atoms: int = typer.Option(
        5, "--max-atoms", min=1, help="Maximum number of selected atoms in the reconstruction."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional output path for the memory reconstruction artifact."
    ),
    created_at: str | None = typer.Option(
        None, "--created-at", help="RFC3339 UTC timestamp for deterministic fixtures."
    ),
) -> None:
    """Reconstruct reviewable context from an explicit memory index without hidden retrieval."""
    index_path = index_path.resolve()
    index_record = _load_validated_index(index_path)
    index_ref = create_memory_ref(
        kind=MEMORY_INDEX_KIND,
        path=index_path,
        sha256=canonical_digest(index_record),
        role="memory_index",
        name=index_path.name,
    )
    record = create_memory_reconstruction(
        index_record,
        index_ref=index_ref,
        query=query,
        created_at_utc=created_at or _utc_now(),
        max_atoms=max_atoms,
    )
    _report_validation(validate_memory_reconstruction(record))
    _print_or_write(record, output, write_memory_reconstruction)


@memory_app.command("validate-atom")
def validate_atom(path: Path) -> None:
    """Validate a memory atom artifact."""
    _report_validation(validate_memory_atom_file(path))
    console.print(f"memory atom valid: {path}")


@memory_app.command("validate-index")
def validate_index(path: Path) -> None:
    """Validate a memory index artifact."""
    _report_validation(validate_memory_index_file(path))
    console.print(f"memory index valid: {path}")


@memory_app.command("validate-reconstruction")
def validate_reconstruction(path: Path) -> None:
    """Validate a memory reconstruction artifact."""
    _report_validation(validate_memory_reconstruction_file(path))
    console.print(f"memory reconstruction valid: {path}")


@memory_app.command("validate-search-result")
def validate_search_result(path: Path) -> None:
    """Validate a memory search result artifact."""
    _report_validation(validate_memory_search_result_file(path))
    console.print(f"memory search result valid: {path}")
