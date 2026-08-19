"""Fail-closed admission for the installed Goose runtime and governed recipe."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

GOOSE_MIN_VERSION = (1, 45, 0)
GOOSE_MAX_VERSION = (1, 46, 99)
_VERSION_RE = re.compile(r"^\s*(?:(?:goose\s+)?version\s+|goose\s+)?v?(\d+)\.(\d+)\.(\d+)\s*$", re.IGNORECASE)
_PROBE_TIMEOUT_SECONDS = 10.0
_REVIEWED_EXTENSION_KEYS = frozenset({"type", "name", "cmd", "args"})


@dataclass(frozen=True)
class GooseCompatibility:
    binary: str
    version: str
    policy: str


def parse_goose_version(output: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(output.strip())
    if not match:
        raise ValueError(f"Could not parse a semantic Goose version from: {output.strip()!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def probe_goose(binary: str | None = None, state_root: Path | None = None) -> GooseCompatibility:
    resolved = binary or shutil.which("goose")
    if not resolved:
        raise RuntimeError("Goose CLI not found. Install a tested Goose release; do not auto-install or update it.")
    if state_root is None:
        raise RuntimeError("Goose compatibility probe requires an explicitly writable isolated state root.")
    state_root.mkdir(parents=True, exist_ok=True)
    env = {"GOOSE_PATH_ROOT": str(state_root)}
    import os
    probe_env = os.environ.copy()
    probe_env.update(env)
    try:
        result = subprocess.run([resolved, "--version"], capture_output=True, text=True, env=probe_env, check=False, timeout=_PROBE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Goose version probe timed out after {_PROBE_TIMEOUT_SECONDS:g}s for {resolved}.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Goose version probe failed for {resolved}: {detail}")
    observed = (result.stdout or result.stderr).strip()
    version = parse_goose_version(observed)
    if not (GOOSE_MIN_VERSION <= version <= GOOSE_MAX_VERSION):
        raise RuntimeError(
            f"Unsupported Goose version {'.'.join(map(str, version))}; tested policy is {GOOSE_POLICY}. "
            "Install or select a tested release manually; no automatic update/downgrade is performed."
        )
    version_text = ".".join(map(str, version))
    return GooseCompatibility(resolved, version_text, GOOSE_POLICY)


GOOSE_POLICY = ">=1.45.0,<1.47.0"


def validate_governed_recipe(recipe: Path) -> str:
    if not recipe.is_file():
        raise FileNotFoundError(f"Missing governed Goose recipe: {recipe}")
    try:
        data = yaml.safe_load(recipe.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid governed Goose recipe: {exc}") from exc
    extensions = data.get("extensions") if isinstance(data, dict) else None
    expected = [{"type": "stdio", "name": "builder_ii_governed", "cmd": "builder-mcp", "args": ["serve"]}]
    if not isinstance(extensions, list) or len(extensions) != 1:
        raise ValueError("Governed recipe must expose exactly one extension: builder-mcp serve")
    extension = extensions[0]
    if not isinstance(extension, dict):
        raise ValueError("Governed recipe extension must be a mapping")
    unexpected = set(extension) - _REVIEWED_EXTENSION_KEYS
    if unexpected:
        raise ValueError(f"Governed recipe extension has unreviewed keys: {sorted(unexpected)!r}")
    actual = {key: extension.get(key) for key in expected[0]}
    if actual != expected[0]:
        raise ValueError(f"Governed recipe tool inventory drift: {actual!r}")
    if shutil.which("builder-mcp") is None:
        raise FileNotFoundError("builder-mcp executable not found; refusing to spawn Goose.")
    return _recipe_digest(recipe)


def _recipe_digest(recipe: Path) -> str:
    import hashlib
    return hashlib.sha256(recipe.read_bytes()).hexdigest()
