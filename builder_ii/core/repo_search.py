"""Bounded repository-map search service."""

from __future__ import annotations

from typing import Any

from builder_ii.governance.ledger.workflow_records import canonical_digest


def search_repo_map(repo_map: dict[str, Any], query: str, *, max_results: int = 100) -> dict[str, Any]:
    """Search one exact bounded repository map without re-reading the repository."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty")
    if max_results < 1:
        raise ValueError("max_results must be positive")
    needle = query.strip().lower()
    files = repo_map.get("files")
    if not isinstance(files, list):
        raise ValueError("repo map files must be a list")
    matches = [
        item
        for item in files
        if isinstance(item, dict)
        and (needle in str(item.get("path", "")).lower() or needle in str(item.get("role", "")).lower())
    ]
    return {
        "matches": matches[:max_results],
        "bounded": True,
        "repo_map_digest": canonical_digest(repo_map),
    }
