from __future__ import annotations

import subprocess
from pathlib import Path

from builder_ii.core.config import Settings
from builder_ii.core.context import load_session_context


def _git_branch(repo: Path) -> str:
    """Return current branch name or 'unknown'."""
    if not repo.exists():
        return "unknown"
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _git_diff_stat(repo: Path) -> tuple[int, int]:
    """Return (staged_count, unstaged_count) for repo."""
    if not repo.exists():
        return (0, 0)
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    unstaged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only"],
        capture_output=True,
        text=True,
    )
    staged_count = len([line for line in staged.stdout.splitlines() if line.strip()])
    unstaged_count = len([line for line in unstaged.stdout.splitlines() if line.strip()])
    return staged_count, unstaged_count


def _recent_handoffs(target_repo: Path, limit: int = 3) -> list[str]:
    """Return up to `limit` recent HANDOFF-*.md filenames, newest first."""
    if not target_repo.exists():
        return []
    handoffs = sorted(
        target_repo.glob("HANDOFF-*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [handoff.name for handoff in handoffs[:limit]]


def write_moim_context(settings: Settings) -> Path:
    """Write session-context.md injected via GOOSE_MOIM_MESSAGE_FILE."""
    cache = settings.project_root / ".builder" / "session-context.md"
    cache.parent.mkdir(parents=True, exist_ok=True)
    ctx = load_session_context(settings)

    branch = _git_branch(settings.target_repo)
    staged, unstaged = _git_diff_stat(settings.target_repo)
    recent_handoffs = _recent_handoffs(settings.target_repo)

    lines: list[str] = [
        "# Builder-II Session Context (auto-generated — do not edit)",
        "",
        "## Repository",
        f"CORE repo: {ctx.target_repo}",
        f"Branch: {branch}",
        f"Git status: {ctx.git_status}",
        f"Staged files: {staged}  Unstaged files: {unstaged}",
        "",
        "## Project Structure",
        f"Top-level dirs: {', '.join(ctx.top_level_dirs)}",
        "",
        "## Governance",
    ]
    for name in ctx.governance_snippets:
        lines.append(f"- {name}")

    lines += ["", "## Recent Handoffs"]
    if recent_handoffs:
        for handoff in recent_handoffs:
            lines.append(f"- {handoff}")
    else:
        lines.append("- (none found)")

    lines += [
        "",
        "## Active Constraints",
        f"- model_alias: {settings.model_alias}",
        f"- active_model: {settings.active_model_id}",
        "- temperature: 0.0",
        "- planner_same_as_execution: true  # M1 16GB — one model at a time",
        "- versor_condition(F) < 1e-6 everywhere",
        "- REFUSE: cosine similarity, ANN, HNSW in vault/",
        "- SPECULATIVE label required until `builder verify` PASS",
    ]

    cache.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cache
