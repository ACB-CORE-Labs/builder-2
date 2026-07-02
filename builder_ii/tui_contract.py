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


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences for stable width calculations."""
    return ANSI_RE.sub("", text)


def col(text: str, width: int, pad: str = " ") -> str:
    """Left-align text using display width after ANSI escapes are removed."""
    return text + pad * max(0, width - len(strip_ansi(text)))


def row(*cells: tuple[str, int]) -> str:
    """Render a simple fixed-width row."""
    return "  " + "  ".join(col(text, width) for text, width in cells)


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


def json_files(root: Path) -> list[Path]:
    """Return sorted JSON files below the artifact root."""
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.json") if path.is_file())


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
