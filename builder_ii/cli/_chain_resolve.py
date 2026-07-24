import json
from pathlib import Path
from typing import Any, Optional

from builder_ii.core.config import load_settings
from builder_ii.tui.projections.chain import artifact_search_roots


def _load_artifacts(artifacts_dir: Path | None) -> dict[str, tuple[Path, dict[str, Any]]]:
    if artifacts_dir is None:
        try:
            settings = load_settings()
            artifacts_dir = settings.project_root / ".builder" / "artifacts"
        except Exception:
            pass

    found: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root in artifact_search_roots(artifacts_dir):
        for path in sorted(root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            kind = str(data.get("kind", ""))
            if kind:
                prev = found.get(kind)
                if prev is not None:
                    try:
                        if path.stat().st_mtime < prev[0].stat().st_mtime:
                            continue
                    except OSError:
                        pass
                found[kind] = (path, data)
    return found

def find_artifact_path_for_kind(artifacts_dir: Path | None, kind: str) -> Path | None:
    found = _load_artifacts(artifacts_dir)
    hit = found.get(kind)
    return hit[0] if hit else None

def resolve_path_or_last(
    explicit_path: Optional[Path],
    from_last: bool,
    kind: str,
    arg_name: str
) -> Path:
    import typer
    if explicit_path:
        return explicit_path
    if not from_last:
        print(f"Error: Missing --{arg_name} or --from-last flag")
        raise typer.Exit(1)

    path = find_artifact_path_for_kind(None, kind)
    if not path:
        print(f"Error: Could not find last artifact of kind {kind} for auto-resolve.")
        raise typer.Exit(1)
    print(f"Auto-resolved --{arg_name} to {path}")
    return path
