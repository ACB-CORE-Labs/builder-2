"""Severable U-instrument baseline runner (OUTSIDE ``builder_ii/code_vault/``).

Runs tree / grep / plain context-pack **without** CodeVault fields to establish the
scoreboard zero point. Mirrors ``code_vault_provenance`` / ``code_vault_receipt_bridge``:
repo I/O and optional tool invocation live here; the vault only assembles RECORDED_ONLY
eval records from caller-supplied measurements.

Commit binding uses pure ``.git`` reads via ``code_vault_provenance.resolve_commit_id``
(no ``git`` binary). Grep may use ``rg`` when present; pure-Python walk is the fallback.
"""

from __future__ import annotations

import hashlib
import json as json_lib
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from builder_ii.code_vault_provenance import resolve_commit_id

# Scope tokens that look like paths (for walking / grepping).
_PATHISH = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|md|rs|toml|json)|[A-Za-z0-9_./-]+/")


def _scope_path_hints(scope: str) -> list[str]:
    hints = _PATHISH.findall(scope)
    return sorted(set(hints), key=len, reverse=True)


def run_tree_listing(repo_root: Path, scope: str, *, max_entries: int = 200) -> dict[str, Any]:
    """Non-CodeVault tree arm: list paths under scope hints (filesystem walk)."""
    hints = _scope_path_hints(scope)
    roots: list[Path] = []
    for hint in hints:
        candidate = repo_root / hint
        if candidate.exists():
            roots.append(candidate)
    if not roots:
        roots = [repo_root]

    entries: list[str] = []
    for root in roots:
        if root.is_file():
            rel = str(root.relative_to(repo_root)).replace("\\", "/")
            entries.append(rel)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames if d not in {".git", ".venv", "node_modules", "__pycache__", "target"}
            ]
            for name in filenames:
                full = Path(dirpath) / name
                try:
                    rel = str(full.relative_to(repo_root)).replace("\\", "/")
                except ValueError:
                    continue
                entries.append(rel)
                if len(entries) >= max_entries:
                    break
            if len(entries) >= max_entries:
                break
        if len(entries) >= max_entries:
            break
    entries = sorted(set(entries))[:max_entries]
    payload = "\n".join(entries).encode("utf-8")
    return {
        "arm": "tree",
        "entry_count": len(entries),
        "entries_sample": entries[:20],
        "output_digest": hashlib.sha256(payload).hexdigest(),
        "truncated": len(entries) >= max_entries,
    }


def run_grep_arm(repo_root: Path, scope: str, question: str, *, max_matches: int = 50) -> dict[str, Any]:
    """Non-CodeVault grep arm: rg when available, else pure-Python walk."""
    tokens = [
        t.lower()
        for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", question)
        if t.lower()
        not in {
            "what",
            "which",
            "must",
            "before",
            "after",
            "with",
            "from",
            "this",
            "that",
            "have",
            "does",
            "into",
            "about",
        }
    ][:6]
    if not tokens:
        tokens = ["def", "class"]

    hints = _scope_path_hints(scope)
    search_roots = [str(repo_root / h) for h in hints if (repo_root / h).exists()]
    if not search_roots:
        search_roots = [str(repo_root)]

    matches: list[str] = []
    method = "walk"
    for token in tokens:
        try:
            proc = subprocess.run(
                ["rg", "-n", "--no-heading", "--sort=path", "-m", "10", "-i", token, *search_roots],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode in (0, 1):
                method = "rg"
                for line in proc.stdout.splitlines():
                    matches.append(line[:240])
                    if len(matches) >= max_matches:
                        break
        except (OSError, subprocess.TimeoutExpired):
            method = "walk"
            break
        if len(matches) >= max_matches:
            break

    if method == "walk" and not matches:
        for root_s in search_roots:
            root = Path(root_s)
            paths = [root] if root.is_file() else list(root.rglob("*.py"))[:80]
            for path in paths:
                if not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    lower = line.lower()
                    if any(tok in lower for tok in tokens):
                        rel = str(path.relative_to(repo_root)).replace("\\", "/")
                        matches.append(f"{rel}:{i}:{line.strip()[:160]}")
                        if len(matches) >= max_matches:
                            break
                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break

    matches = sorted(set(matches))[:max_matches]
    payload = "\n".join(matches).encode("utf-8")
    return {
        "arm": "grep",
        "method": method,
        "tokens": tokens,
        "match_count": len(matches),
        "matches_sample": matches[:10],
        "output_digest": hashlib.sha256(payload).hexdigest(),
    }


def run_context_pack_without_codevault(
    repo_root: Path,
    scope: str,
    *,
    max_files: int = 5,
    max_bytes_per_file: int = 4000,
) -> dict[str, Any]:
    """Minimal context pack: read first files under scope as plain text — no CodeVault fields."""
    tree = run_tree_listing(repo_root, scope, max_entries=max_files * 4)
    files_read: list[dict[str, Any]] = []
    for rel in tree["entries_sample"]:
        path = repo_root / rel
        if not path.is_file():
            continue
        try:
            raw = path.read_bytes()[:max_bytes_per_file]
            text = raw.decode("utf-8", errors="replace")
        except OSError:
            continue
        files_read.append(
            {
                "path": rel,
                "byte_length": len(raw),
                "content_digest": hashlib.sha256(raw).hexdigest(),
                "preview_chars": len(text),
            }
        )
        if len(files_read) >= max_files:
            break
    blob = json_lib.dumps(files_read, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "arm": "context_pack_plain",
        "file_count": len(files_read),
        "files": files_read,
        "output_digest": hashlib.sha256(blob).hexdigest(),
        "code_vault_fields_used": False,
    }


def run_baseline_arm(
    *,
    repo_root: Path,
    task_id: str,
    question: str,
    scope: str,
) -> dict[str, Any]:
    """Execute the full baseline arm; return measured outputs + zero-point scores.

    Caller feeds these into ``code_vault.utility_eval_record.build_baseline_arm_record`` —
    the vault package never imports this module.
    """
    repo_root = repo_root.resolve()
    commit_id = resolve_commit_id(repo_root)
    tree = run_tree_listing(repo_root, scope)
    grep = run_grep_arm(repo_root, scope, question)
    context = run_context_pack_without_codevault(repo_root, scope)

    relevance = min(1.0, grep["match_count"] / 10.0) if grep["match_count"] else 0.0
    scores = {
        "relevance": relevance,
        "omission_honesty": 1.0,
        "decomposability": 0.0,
        "baseline_delta": 0.0,
        "tree_entry_count": float(tree["entry_count"]),
        "grep_match_count": float(grep["match_count"]),
        "context_file_count": float(context["file_count"]),
    }

    combined = {
        "tree": tree["output_digest"],
        "grep": grep["output_digest"],
        "context": context["output_digest"],
    }
    arm_digest = hashlib.sha256(
        json_lib.dumps(combined, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return {
        "task_id": task_id,
        "commit_id": commit_id,
        "repo_root": str(repo_root),
        "tree": tree,
        "grep": grep,
        "context_pack": context,
        "scores": scores,
        "artifact_digests": {
            "arm_definition": "tree_grep_context_pack_without_code_vault",
            "tree_output": tree["output_digest"],
            "grep_output": grep["output_digest"],
            "context_pack_output": context["output_digest"],
            "baseline_arm_run": arm_digest,
            "code_vault_fields": "none",
        },
        "omission_honesty": "baseline_declares_no_code_vault_fields",
    }
