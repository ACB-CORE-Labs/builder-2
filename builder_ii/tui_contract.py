"""Shared read-only TUI contract helpers.

The inspection TUI is an observer surface.  Helpers here are deliberately
small: they normalize path discovery, ANSI-safe width accounting, JSON loading,
and artifact-store parse checks without importing Rich or granting authority.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\033\[[0-9;]*m")

PALETTE: dict[str, str] = {
    "pass": "#4ade80",
    "warn": "#fbbf24",
    "fail": "#f87171",
    "hint": "#94a3b8",
    "active": "#38bdf8",
    "dim": "#475569",
    "bold": "#f1f5f9",
    "accent": "#818cf8",
}

GLYPHS: dict[str, str] = {
    "pass": "✔",
    "fail": "✘",
    "warn": "⚠",
    "skip": "–",
    "link": "↳",
    "allowed": "▷",
    "denied": "◁",
}


def builder_dir() -> Path:
    """Return the governed artifact root used by read-only TUI modules."""
    return Path(os.environ.get("BUILDER_DIR", ".builder"))


def load_palette() -> dict[str, str]:
    """Load the active theme palette with a stable fallback."""
    try:
        from builder_ii.tui_theme import theme_palette

        return theme_palette()
    except Exception:
        return dict(PALETTE)


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences for stable width calculations."""
    return ANSI_RE.sub("", text)


def col(text: str, width: int, pad: str = " ") -> str:
    """Left-align text using display width after ANSI escapes are removed."""
    return text + pad * max(0, width - len(strip_ansi(text)))


def row(*cells: tuple[str, int]) -> str:
    """Render a simple fixed-width row."""
    return "  " + "  ".join(col(text, width) for text, width in cells)


def lookup_matches(target: str, *values: object) -> bool:
    """Return true when ``target`` is contained in any candidate value."""
    needle = str(target)
    if not needle:
        return False
    return any(needle in str(value) for value in values if value is not None)


def explicit_lookup_miss(label: str, target: str) -> str:
    """Render a stable explicit-ID miss message."""
    return f"No {label} found matching: {target}"


def load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Load a JSON object from disk without raising."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"not found: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    except OSError as exc:
        return None, f"failed to read {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"not a JSON object: {path}"
    return data, ""


def hex_ansi(hex_colour: str, text: str, is_tty: bool) -> str:
    """Render a 24-bit ANSI foreground colour when stdout is a TTY."""
    if not is_tty:
        return text
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return text
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return text
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def json_files(root: Path) -> list[Path]:
    """Return sorted JSON files below the artifact root."""
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.json") if path.is_file())


def find_artifact(base: Path, *candidates: str) -> tuple[Path | None, dict[str, Any] | None]:
    """Return the first readable JSON object among candidate relative paths."""
    for name in candidates:
        path = base / name
        data, _error = load_json_object(path)
        if data:
            return path, data
    return None, None


def glob_kind(base: Path, kind_fragment: str, *subdirs: str) -> list[tuple[Path, dict[str, Any]]]:
    """Find JSON artifacts whose ``kind`` contains ``kind_fragment``."""
    results: list[tuple[Path, dict[str, Any]]] = []
    search_dirs = [base / segment for segment in subdirs] + [base]
    seen: set[Path] = set()
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            data, _error = load_json_object(path)
            if data and kind_fragment in str(data.get("kind", "")):
                results.append((path, data))
    return results


def invalid_json_files(root: Path) -> list[tuple[Path, str]]:
    """Find unreadable or malformed JSON files under the artifact root."""
    failures: list[tuple[Path, str]] = []
    for path in json_files(root):
        _data, error = load_json_object(path)
        if error:
            failures.append((path, error))
    return failures


def is_status_like(command_path: str) -> bool:
    """Return true for overview commands whose empty stores are healthy."""
    return command_path.split()[-1] in {"status", "history", "approval"}
