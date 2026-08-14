from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from builder_ii.core.config import Settings


def validate_recipes(settings: Settings) -> list[tuple[Path, bool, str]]:
    """Run `goose recipe validate` against every *.yaml in recipes/."""
    goose = shutil.which("goose")
    if not goose:
        return []
    results: list[tuple[Path, bool, str]] = []
    for recipe in sorted((settings.project_root / "recipes").rglob("*.yaml")):
        proc = subprocess.run(
            [goose, "recipe", "validate", str(recipe)],
            capture_output=True,
            text=True,
        )
        ok = proc.returncode == 0
        msg = (proc.stdout or proc.stderr).strip()
        results.append((recipe, ok, msg))
    return results
