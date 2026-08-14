from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.core.config import Settings
from builder_ii.lifecycle.setup.init_content import CORE_INIT_SYSTEM_PROMPT

GOVERNANCE_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "docs/runtime_contracts.md",
)


@dataclass(frozen=True)
class SessionContext:
    target_repo: Path
    governance_snippets: dict[str, str]
    recent_handoff: str | None
    git_status: str
    top_level_dirs: tuple[str, ...]
    system_prompt: str


def _read_text(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return f"[missing: {path}]"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def _recent_handoff(target_repo: Path) -> str | None:
    if not target_repo.exists():
        return None
    candidates = sorted(target_repo.glob("HANDOFF-*.md"), reverse=True)
    return _read_text(candidates[0], max_chars=6000) if candidates else None


def _git_status(target_repo: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=target_repo,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.stdout.strip() or proc.stderr.strip() or "(empty)"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "[git unavailable]"


def _top_level_dirs(target_repo: Path) -> tuple[str, ...]:
    if not target_repo.exists():
        return ()
    return tuple(sorted(p.name for p in target_repo.iterdir() if p.is_dir() and not p.name.startswith(".")))


def load_session_context(settings: Settings) -> SessionContext:
    repo = settings.target_repo
    snippets = {name: _read_text(repo / name) for name in GOVERNANCE_FILES}
    return SessionContext(
        target_repo=repo,
        governance_snippets=snippets,
        recent_handoff=_recent_handoff(repo),
        git_status=_git_status(repo),
        top_level_dirs=_top_level_dirs(repo),
        system_prompt=CORE_INIT_SYSTEM_PROMPT,
    )


def context_brief(ctx: SessionContext) -> str:
    lines = [
        f"target repo: {ctx.target_repo}",
        f"dirs: {', '.join(ctx.top_level_dirs[:20])}",
        f"git: {ctx.git_status}",
        "governance loaded: " + ", ".join(ctx.governance_snippets),
    ]
    if ctx.recent_handoff:
        lines.append("recent handoff: present")
    return "\n".join(lines)
