"""W5 repo-state capture for reconstructive replay (commit_id + tree_hash).

Pure helpers: shell=False fixed argv git calls; honest nulls when not a git tree.
Never grants authority. Used by ``subtask_graph.replay_graph_digests`` so
perfect_match requires digest sequence **and** repo identity agreement.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

# Null-git sentinel values (honest: not a git work tree / git unavailable).
NULL_COMMIT: None = None
NULL_TREE: None = None


class RepoStateError(RuntimeError):
    """Raised only for programmer errors (invalid shapes), not missing git."""


def _run_git(args: list[str], *, cwd: Path) -> tuple[int, str, str]:
    completed = subprocess.run(  # noqa: S603 — fixed argv, shell=False
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
        cwd=str(cwd),
    )
    return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()


def capture_repo_state(cwd: Path | str | None = None) -> dict[str, Any]:
    """Capture ``commit_id`` + ``tree_hash`` for the worktree, or honest nulls.

    Returns a dict always::

        {
          "commit_id": str | None,
          "tree_hash": str | None,
          "is_git_tree": bool,
          "capture_error": str | None,
          "grants_authority": False,
        }
    """
    root = Path(cwd) if cwd is not None else Path.cwd()
    base: dict[str, Any] = {
        "commit_id": None,
        "tree_hash": None,
        "is_git_tree": False,
        "capture_error": None,
        "grants_authority": False,
        "cwd": str(root.resolve()) if root.exists() else str(root),
    }
    if not root.exists():
        return {**base, "capture_error": "cwd does not exist"}

    code, inside, err = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=root)
    if code != 0 or inside.strip().lower() != "true":
        return {
            **base,
            "capture_error": err or "not a git work tree",
        }

    code_c, commit, err_c = _run_git(["rev-parse", "HEAD"], cwd=root)
    code_t, tree, err_t = _run_git(["rev-parse", "HEAD^{tree}"], cwd=root)
    if code_c != 0 or code_t != 0 or not commit or not tree:
        return {
            **base,
            "is_git_tree": True,
            "capture_error": err_c or err_t or "failed to resolve HEAD/tree",
        }

    return {
        "commit_id": commit,
        "tree_hash": tree,
        "is_git_tree": True,
        "capture_error": None,
        "grants_authority": False,
        "cwd": str(root.resolve()),
    }


def normalize_repo_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize optional planned/observed repo-state fields for comparison."""
    if raw is None:
        return {
            "commit_id": None,
            "tree_hash": None,
            "is_git_tree": False,
            "source": "null",
        }
    if not isinstance(raw, dict):
        raise TypeError("repo_state must be a dict or None")
    commit = raw.get("commit_id")
    tree = raw.get("tree_hash")
    commit_s = str(commit) if commit not in (None, "") else None
    tree_s = str(tree) if tree not in (None, "") else None
    is_git = bool(raw.get("is_git_tree")) if "is_git_tree" in raw else bool(commit_s or tree_s)
    return {
        "commit_id": commit_s,
        "tree_hash": tree_s,
        "is_git_tree": is_git,
        "source": str(raw.get("source") or "provided"),
    }


def repo_states_match(
    planned: dict[str, Any] | None,
    observed: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare planned vs observed repo identity for W5.

    Rules:
    - Both sides fully null (no commit, no tree) → match=True, mode=null_git
      (honest non-git fixture agreement).
    - Both sides equal non-null commit_id and tree_hash → match=True, mode=bound
    - Any partial/mismatched pair → match=False, mode=mismatch
    """
    p = normalize_repo_state(planned)
    o = normalize_repo_state(observed)
    p_null = p["commit_id"] is None and p["tree_hash"] is None
    o_null = o["commit_id"] is None and o["tree_hash"] is None

    if p_null and o_null:
        return {
            "repo_state_match": True,
            "mode": "null_git",
            "planned": p,
            "observed": o,
            "reasons": ["both planned and observed repo state are null (honest non-git)"],
        }

    commit_ok = p["commit_id"] is not None and p["commit_id"] == o["commit_id"]
    tree_ok = p["tree_hash"] is not None and p["tree_hash"] == o["tree_hash"]
    if commit_ok and tree_ok:
        return {
            "repo_state_match": True,
            "mode": "bound",
            "planned": p,
            "observed": o,
            "reasons": ["commit_id and tree_hash agree"],
        }

    reasons: list[str] = []
    if p["commit_id"] != o["commit_id"]:
        reasons.append(
            f"commit_id mismatch: planned={p['commit_id']!r} observed={o['commit_id']!r}"
        )
    if p["tree_hash"] != o["tree_hash"]:
        reasons.append(
            f"tree_hash mismatch: planned={p['tree_hash']!r} observed={o['tree_hash']!r}"
        )
    if not reasons:
        reasons.append("repo state incomplete or inconsistent")
    return {
        "repo_state_match": False,
        "mode": "mismatch",
        "planned": p,
        "observed": o,
        "reasons": reasons,
    }


__all__ = [
    "NULL_COMMIT",
    "NULL_TREE",
    "RepoStateError",
    "capture_repo_state",
    "normalize_repo_state",
    "repo_states_match",
]
