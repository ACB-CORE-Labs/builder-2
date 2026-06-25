"""Phase 1 – Dynamic Context Injection (Pre-Boot Sequence).

This module is the bootstrap loader for the builder-II harness.
It runs before Goose processes a single token and gives the agent
absolute situational awareness of the project.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from builder_ii.config import Settings, load_settings
from builder_ii.context import load_session_context


# ---------------------------------------------------------------------------
# Goose configuration directory
# ---------------------------------------------------------------------------

def goose_config_dir() -> Path:
    return Path.home() / ".config" / "goose"


# ---------------------------------------------------------------------------
# Skill bridging
# ---------------------------------------------------------------------------

def skills_source(settings: Settings) -> Path:
    return settings.project_root / ".agents" / "skills"


def install_skills_to_core(settings: Settings) -> list[Path]:
    """Atomically copy builder-II skills into CORE repo .agents/skills.

    Uses a .partial staging directory so a crash never leaves Goose
    in a broken discovery state.
    """
    src = skills_source(settings)
    dest = settings.core_repo / ".agents" / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    if not src.exists():
        return installed
    for skill_dir in src.iterdir():
        if not skill_dir.is_dir():
            continue
        target = dest / skill_dir.name
        partial = dest / (skill_dir.name + ".partial")
        # Stage to partial first
        if partial.exists():
            shutil.rmtree(partial)
        shutil.copytree(skill_dir, partial)
        # Atomic swap
        if target.exists():
            shutil.rmtree(target)
        partial.rename(target)
        installed.append(target)
    return installed


# ---------------------------------------------------------------------------
# .goosehints
# ---------------------------------------------------------------------------

def write_goosehints(settings: Settings) -> Path:
    """Top-of-mind hints file written to CORE repo root."""
    path = settings.core_repo / ".goosehints"
    content = (
        "# CORE + builder-II local agent hints\n"
        "- temperature 0 everywhere; planner_same_as_execution=true on M1 16GB\n"
        "- Read AGENTS.md, GROK.md, docs/runtime_contracts.md before edits\n"
        "- Proposals are SPECULATIVE until `builder verify` passes\n"
        "- Skills: core-governed-coding, core-verify-loop, core-pre-edit-sweep, core-handoff\n"
        "- Slash: /explore /implement /review /verify /handoff /plan /coding /platform\n"
        "- Switch model: builder switch-model fast|primary (one model on M1 16GB)\n"
        "- versor_condition(F) < 1e-6 — refuse cosine/ANN/HNSW in vault\n"
        "- Local roster: gemma-4-e4b (fast), gemma-4-12b (primary),\n"
        "  qwen2.5-coder-7b (fast-alt), deepseek-coder-v2-lite (primary-alt),\n"
        "  llama-3.1-8b (primary-alt)\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# MOIM context injection
# ---------------------------------------------------------------------------

def _git_branch(repo: Path) -> str:
    """Return current branch name or 'detached'."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _git_diff_stat(repo: Path) -> tuple[int, int]:
    """Return (staged_count, unstaged_count) for repo."""
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
    )
    unstaged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only"],
        capture_output=True, text=True,
    )
    s = len([l for l in staged.stdout.splitlines() if l.strip()])
    u = len([l for l in unstaged.stdout.splitlines() if l.strip()])
    return s, u


def _recent_handoffs(core_repo: Path, limit: int = 3) -> list[str]:
    """Return up to `limit` recent HANDOFF-*.md filenames, newest first."""
    handoffs = sorted(
        core_repo.glob("HANDOFF-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [h.name for h in handoffs[:limit]]


def write_moim_context(settings: Settings) -> Path:
    """Write session-context.md injected via GOOSE_MOIM_MESSAGE_FILE.

    Every agent session gets absolute situational awareness:
    - Git branch + staged/unstaged counts
    - All top-level directories
    - Governance snippets loaded
    - Recent HANDOFF documents listed explicitly
    """
    cache = settings.project_root / ".builder" / "session-context.md"
    cache.parent.mkdir(parents=True, exist_ok=True)
    ctx = load_session_context(settings)

    branch = _git_branch(settings.core_repo)
    staged, unstaged = _git_diff_stat(settings.core_repo)
    recent_handoffs = _recent_handoffs(settings.core_repo)

    lines: list[str] = [
        "# Builder-II Session Context (auto-generated — do not edit)",
        "",
        "## Repository",
        f"CORE repo: {ctx.core_repo}",
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
        for hf in recent_handoffs:
            lines.append(f"- {hf}")
    else:
        lines.append("- (none found)")

    lines += [
        "",
        "## Active Constraints",
        "- temperature: 0.0",
        "- planner_same_as_execution: true  # M1 16GB — one model at a time",
        "- versor_condition(F) < 1e-6 everywhere",
        "- REFUSE: cosine similarity, ANN, HNSW in vault/",
        "- SPECULATIVE label required until `builder verify` PASS",
    ]

    cache.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cache


# ---------------------------------------------------------------------------
# Goose config.yaml generation
# ---------------------------------------------------------------------------

def build_goose_config(settings: Settings) -> dict:
    """Build the full Goose config.yaml-compatible structure.

    Locks down: recipes, slash commands, and the three strictly bundled
    extensions (developer, skills, summon). Emits provider stubs so the
    config is self-contained and requires no manual env wrangling.
    """
    recipes = settings.project_root / "recipes"
    return {
        # Runtime parameters
        "GOOSE_TEMPERATURE": settings.temperature,
        "GOOSE_MODE": "auto",
        "GOOSE_MAX_TURNS": 1000,
        "GOOSE_AUTO_COMPACT_THRESHOLD": 0.8,
        "GOOSE_CLI_SHOW_COST": False,
        "GOOSE_RECIPE_PATH": str(recipes),
        # Slash commands
        "slash_commands": [
            {"command": "explore",  "recipe_path": str(recipes / "subrecipes" / "explore.yaml")},
            {"command": "implement", "recipe_path": str(recipes / "subrecipes" / "implement.yaml")},
            {"command": "review",   "recipe_path": str(recipes / "subrecipes" / "review.yaml")},
            {"command": "verify",   "recipe_path": str(recipes / "subrecipes" / "verify.yaml")},
            {"command": "handoff",  "recipe_path": str(recipes / "subrecipes" / "handoff.yaml")},
            {"command": "plan",     "recipe_path": str(recipes / "subrecipes" / "plan.yaml")},
            {"command": "platform", "recipe_path": str(recipes / "core-platform.yaml")},
            {"command": "coding",   "recipe_path": str(recipes / "core-coding.yaml")},
        ],
        # Extensions — only bundled; no external network calls
        "extensions": {
            "developer": {
                "bundled": True,
                "enabled": True,
                "name": "developer",
                "timeout": 600,
                "type": "builtin",
                "description": "Filesystem and shell tools for edit-test-fix loops",
            },
            "skills": {
                "bundled": True,
                "enabled": True,
                "name": "skills",
                "timeout": 300,
                "type": "platform",
                "description": "builder-II governed coding skills",
            },
            "summon": {
                "bundled": True,
                "enabled": True,
                "name": "summon",
                "timeout": 300,
                "type": "platform",
                "description": "Sub-agent spawning for plan/implement/verify pipeline",
            },
        },
    }


def write_goose_config(settings: Settings) -> Path:
    """Merge builder-II config into ~/.config/goose/config.yaml.

    Existing provider credentials (API keys, model names already set by
    the user) are preserved — only builder-II keys are overwritten.
    """
    config_dir = goose_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.yaml"
    existing: dict = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merged = {**existing, **build_goose_config(settings)}
    path.write_text(
        yaml.dump(merged, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Recipe validation
# ---------------------------------------------------------------------------

def validate_recipes(settings: Settings) -> list[tuple[Path, bool, str]]:
    """Run `goose recipe validate` against every *.yaml in recipes/."""
    goose = shutil.which("goose")
    if not goose:
        return []
    results: list[tuple[Path, bool, str]] = []
    for recipe in sorted((settings.project_root / "recipes").rglob("*.yaml")):
        proc = subprocess.run(
            [goose, "recipe", "validate", str(recipe)],
            capture_output=True, text=True,
        )
        ok = proc.returncode == 0
        msg = (proc.stdout or proc.stderr).strip()
        results.append((recipe, ok, msg))
    return results


# ---------------------------------------------------------------------------
# Full setup entrypoint
# ---------------------------------------------------------------------------

def run_full_setup(settings: Settings | None = None) -> dict[str, object]:
    """Run the complete pre-boot sequence and return a JSON-safe report."""
    s = settings or load_settings()
    return {
        "goose_config": str(write_goose_config(s)),
        "goosehints": str(write_goosehints(s)),
        "moim_context": str(write_moim_context(s)),
        "skills_installed": [str(p) for p in install_skills_to_core(s)],
        "recipe_validation": [
            {"path": str(p), "ok": ok, "msg": msg}
            for p, ok, msg in validate_recipes(s)
        ],
    }
