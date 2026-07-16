"""Workflow / recipe / Goose lane projection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.workflow_records import WORKFLOW_STAGES


@dataclass(frozen=True)
class RecipeView:
    name: str
    path: str
    title: str
    is_subrecipe: bool


@dataclass(frozen=True)
class GooseManifestView:
    path: str
    mode: str
    valid_enough: bool  # true if JSON loads and requests read_only when claimed
    note: str


@dataclass(frozen=True)
class WorkflowLaneView:
    recipes: tuple[RecipeView, ...]
    stages: tuple[str, ...]
    current_stage: str | None
    session_id: str | None
    task: str | None
    status_kind: str | None
    goose: GooseManifestView | None
    compose_manifest: str
    compose_start_readonly: str
    error: str | None = None


def _recipe_title(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return path.stem
    for line in text.splitlines()[:40]:
        stripped = line.strip()
        if stripped.startswith("title:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
        if stripped.startswith("description:") and len(stripped) > 14:
            return stripped.split(":", 1)[1].strip().strip("\"'")[:60]
    return path.stem


def _discover_recipes(repo_root: Path | None) -> list[RecipeView]:
    recipes: list[RecipeView] = []
    if repo_root is None:
        return recipes
    recipes_dir = repo_root / "recipes"
    if not recipes_dir.is_dir():
        return recipes
    for path in sorted(recipes_dir.glob("*.yaml")):
        recipes.append(
            RecipeView(
                name=path.stem,
                path=str(path),
                title=_recipe_title(path),
                is_subrecipe=False,
            )
        )
    sub = recipes_dir / "subrecipes"
    if sub.is_dir():
        for path in sorted(sub.glob("*.yaml")):
            recipes.append(
                RecipeView(
                    name=f"sub/{path.stem}",
                    path=str(path),
                    title=_recipe_title(path),
                    is_subrecipe=True,
                )
            )
    return recipes


def _load_latest_workflow(artifacts_dir: Path | None) -> dict[str, Any] | None:
    if artifacts_dir is None or not artifacts_dir.exists():
        return None
    candidates: list[tuple[float, dict[str, Any]]] = []
    for path in artifacts_dir.rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        kind = str(data.get("kind", ""))
        if kind in (
            "builder_ii.workflow_session",
            "builder_ii.workflow_status",
        ):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append((mtime, data))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _project_goose(artifacts_dir: Path | None) -> GooseManifestView | None:
    if artifacts_dir is None:
        return None
    goose_dir = artifacts_dir.parent / "goose"
    if not goose_dir.is_dir():
        return None
    candidates = sorted(goose_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    path = candidates[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return GooseManifestView(
            path=str(path),
            mode="—",
            valid_enough=False,
            note="unreadable JSON",
        )
    if not isinstance(data, dict):
        return GooseManifestView(path=str(path), mode="—", valid_enough=False, note="not an object")
    mode = str(data.get("requested_runtime_mode") or data.get("mode") or "—")
    ok = mode == "read_only"
    note = "eligible for STRATUM G hand-off" if ok else "not read_only — G will refuse"
    # Prefer real validator when present
    try:
        from builder_ii.goose_session import validate_goose_session_manifest_file

        errors = validate_goose_session_manifest_file(path)
        if errors:
            ok = False
            note = f"validator: {errors[0]}" if isinstance(errors[0], str) else "validator failed"
        elif mode == "read_only":
            ok = True
            note = "manifest validates · read_only"
    except Exception:
        pass
    return GooseManifestView(path=str(path), mode=mode, valid_enough=ok, note=note)


def project_workflow(
    *,
    artifacts_dir: Path | None,
    repo_root: Path | None = None,
    target: str = "generic",
) -> WorkflowLaneView:
    error: str | None = None
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2].parent

    recipes = _discover_recipes(repo_root)
    current_stage: str | None = None
    session_id: str | None = None
    task: str | None = None
    status_kind: str | None = None
    goose: GooseManifestView | None = None

    try:
        latest = _load_latest_workflow(artifacts_dir)
        if latest:
            status_kind = str(latest.get("kind"))
            current_stage = latest.get("current_stage") or latest.get("stage")
            if current_stage is not None:
                current_stage = str(current_stage)
            session_id = latest.get("session_id")
            if session_id is not None:
                session_id = str(session_id)
            task = latest.get("task")
            if task is not None:
                task = str(task)
        goose = _project_goose(artifacts_dir)
    except Exception as exc:
        error = str(exc)

    out = ".builder/goose/session.json"
    return WorkflowLaneView(
        recipes=tuple(recipes),
        stages=WORKFLOW_STAGES,
        current_stage=current_stage,
        session_id=session_id,
        task=task,
        status_kind=status_kind,
        goose=goose,
        compose_manifest=(
            f"uv run builder-goose manifest --target {target} --mode read_only "
            f'--task "readonly inspect" --output {out}'
        ),
        compose_start_readonly=f"uv run builder-goose start-readonly {out}",
        error=error,
    )
