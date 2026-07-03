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
# builder_ii/ lives one level below the project root. This import-time root is
# used only as the fallback when callers do not provide an active project_root.
_project_root: Path = Path(__file__).parent.parent.resolve()

# Agent defaults are target-owned data. Repo defaults are derived by
# _default_target_repo_for() so callers can preserve call-time project_root
# semantics while keeping target-specific path policy in this module.
_TARGET_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "generic": {
        "default_agent_profile": "repo_mapper",
    },
    "builder": {
        "default_agent_profile": "patch_planner",
    },
    "core": {
        # CORE target default agent lives here and nowhere in config_sources.py.
        "default_agent_profile": "core.patch_planner",
    },
}

_BUILT_IN_DEFAULT_AGENT: str = "repo_mapper"


def _root_for(project_root: Optional[Path]) -> Path:
    return (project_root or _project_root).expanduser().resolve(strict=False)


def _default_target_repo_for(target: Optional[str], *, project_root: Optional[Path]) -> Path:
    """Return target-owned repo default for *target*.

    The old config resolver derived defaults from its call-time project_root.
    Preserve that behavior here so the generic resolver remains target-agnostic
    while target-specific path policy remains target-owned.
    """
    root = _root_for(project_root)
    if target in {"generic", "builder"}:
        return root
    if target == "core":
        # CORE target default: sibling directory of the active builder-II root.
        # Kept for backward compatibility; lives here and nowhere else.
        return root.parent / "core"
    return root


def get_target_defaults(target: Optional[str], *, project_root: Optional[Path] = None) -> Dict[str, Any]:
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
        defaults = dict(_TARGET_DEFAULTS[target])
        defaults["default_target_repo"] = _default_target_repo_for(target, project_root=project_root)
        return defaults
    return {
        "default_target_repo": _default_target_repo_for(None, project_root=project_root),
        "default_agent_profile": _BUILT_IN_DEFAULT_AGENT,
    }


def list_known_targets() -> list:
    """Return the list of targets that have explicit default entries."""
    return list(_TARGET_DEFAULTS.keys())


def default_agent_profile_for(target: Optional[str], *, project_root: Optional[Path] = None) -> str:
    """Convenience accessor — returns only the default agent profile name."""
    return get_target_defaults(target, project_root=project_root)["default_agent_profile"]


def default_target_repo_for(target: Optional[str], *, project_root: Optional[Path] = None) -> Path:
    """Convenience accessor — returns only the default target repo Path."""
    return get_target_defaults(target, project_root=project_root)["default_target_repo"]
