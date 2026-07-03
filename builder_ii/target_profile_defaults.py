"""target_profile_defaults.py

Immutable per-target default resolver for builder-II.

This module is the single source of truth for target-owned default
configuration values (default_target_repo, default_agent_profile).

config_sources.py MUST NOT contain target-specific repo paths or
agent names. It asks this module for defaults instead.

Governance
----------
* No model execution.
* No commit/push authority.
* No shell execution.
* No CORE Workbench coupling.
* Read-only data module — no side effects.

SUPPORTED TARGETS
-----------------
  generic  – for any normal software repo
  builder  – for builder-II self-development
  core     – for AssetOverflow/core development (target profile only)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Immutable default table
# ---------------------------------------------------------------------------
# project_root is resolved at import time relative to this file's location.
# builder_ii/ lives one level below the project root.
_project_root: Path = Path(__file__).parent.parent.resolve()

# Each entry: {target_name: {"default_target_repo": Path, "default_agent_profile": str}}
# CORE-specific values (repo path and agent name) live ONLY here.
_TARGET_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "generic": {
        "default_target_repo": _project_root,
        "default_agent_profile": "repo_mapper",
    },
    "builder": {
        "default_target_repo": _project_root,
        "default_agent_profile": "patch_planner",
    },
    "core": {
        # CORE target default: sibling directory of the builder-II project root.
        # Kept for backward compatibility; lives here and nowhere else.
        "default_target_repo": _project_root.parent / "core",
        "default_agent_profile": "core.patch_planner",
    },
}

_BUILT_IN_DEFAULT_AGENT: str = "repo_mapper"
_BUILT_IN_DEFAULT_REPO: Path = _project_root


def get_target_defaults(target: Optional[str]) -> Dict[str, Any]:
    """Return the immutable defaults for *target*.

    Falls back to the generic built-in defaults when *target* is None or
    unknown so that the config resolver always receives a valid dict.

    Returns a shallow copy — callers must not mutate the returned dict.

    Keys
    ----
    default_target_repo : Path
    default_agent_profile : str
    """
    if target and target in _TARGET_DEFAULTS:
        return dict(_TARGET_DEFAULTS[target])
    return {
        "default_target_repo": _BUILT_IN_DEFAULT_REPO,
        "default_agent_profile": _BUILT_IN_DEFAULT_AGENT,
    }


def list_known_targets() -> list:
    """Return the list of targets that have explicit default entries."""
    return list(_TARGET_DEFAULTS.keys())


def default_agent_profile_for(target: Optional[str]) -> str:
    """Convenience accessor — returns only the default agent profile name."""
    return get_target_defaults(target)["default_agent_profile"]


def default_target_repo_for(target: Optional[str]) -> Path:
    """Convenience accessor — returns only the default target repo Path."""
    return get_target_defaults(target)["default_target_repo"]
