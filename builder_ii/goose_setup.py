from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from builder_ii.config import Settings, load_settings
from builder_ii.context import load_session_context


def goose_config_dir() -> Path:
    return Path.home() / ".config" / "goose"


def skills_source(settings: Settings) -> Path:
    return settings.project_root / ".agents" / "skills"


def install_skills_to_core(settings: Settings) -> list[Path]:
    """Copy builder-II skills into CORE repo .agents/skills for Goose discovery."""
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
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
        installed.append(target)
    return installed


def write_goosehints(settings: Settings) -> Path:
    """Top-of-mind hints file in CORE repo root."""
    path = settings.core_repo / ".goosehints"
    content = """# CORE + builder-II local agent hints
- temperature 0 everywhere
- Read AGENTS.md, GROK.md, docs/runtime_contracts.md before edits
- Proposals are SPECULATIVE until `builder verify` passes
- Use skills: core-governed-coding, core-verify-loop, core-pre-edit-sweep, core-handoff
- Slash: /explore /implement /review /verify /handoff /plan
- Switch model: builder switch-model fast|primary (one model on M1 16GB)
- versor_condition(F) < 1e-6 — refuse cosine/ANN/HNSW in vault
"""
    path.write_text(content, encoding="utf-8")
    return path


def write_moim_context(settings: Settings) -> Path:
    """Session context file injected via GOOSE_MOIM_MESSAGE_FILE."""
    cache = settings.project_root / ".builder" / "session-context.md"
    cache.parent.mkdir(parents=True, exist_ok=True)
    ctx = load_session_context(settings)
    lines = [
        "# Builder session context (auto-generated)",
        f"CORE repo: {ctx.core_repo}",
        f"Git: {ctx.git_status}",
        f"Top dirs: {', '.join(ctx.top_level_dirs[:25])}",
        "",
        "## Governance loaded",
    ]
    for name in ctx.governance_snippets:
        lines.append(f"- {name}")
    if ctx.recent_handoff:
        lines.append("- recent HANDOFF present")
    cache.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cache


def build_goose_config(settings: Settings) -> dict:
    recipes = settings.project_root / "recipes"
    return {
        "GOOSE_TEMPERATURE": settings.temperature,
        "GOOSE_MODE": "auto",
        "GOOSE_MAX_TURNS": 1000,
        "GOOSE_AUTO_COMPACT_THRESHOLD": 0.8,
        "GOOSE_CLI_SHOW_COST": False,
        "GOOSE_RECIPE_PATH": str(recipes),
        "slash_commands": [
            {"command": "explore", "recipe_path": str(recipes / "subrecipes" / "explore.yaml")},
            {"command": "implement", "recipe_path": str(recipes / "subrecipes" / "implement.yaml")},
            {"command": "review", "recipe_path": str(recipes / "subrecipes" / "review.yaml")},
            {"command": "verify", "recipe_path": str(recipes / "subrecipes" / "verify.yaml")},
            {"command": "handoff", "recipe_path": str(recipes / "subrecipes" / "handoff.yaml")},
            {"command": "platform", "recipe_path": str(recipes / "core-platform.yaml")},
            {"command": "coding", "recipe_path": str(recipes / "core-coding.yaml")},
        ],
        "extensions": {
            "developer": {
                "bundled": True,
                "enabled": True,
                "name": "developer",
                "timeout": 600,
                "type": "builtin",
            },
            "skills": {
                "bundled": True,
                "enabled": True,
                "name": "skills",
                "timeout": 300,
                "type": "platform",
            },
            "summon": {
                "bundled": True,
                "enabled": True,
                "name": "summon",
                "timeout": 300,
                "type": "platform",
            },
        },
    }


def write_goose_config(settings: Settings) -> Path:
    config_dir = goose_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.yaml"
    existing: dict = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text()) or {}
    merged = {**existing, **build_goose_config(settings)}
    path.write_text(yaml.dump(merged, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


def validate_recipes(settings: Settings) -> list[tuple[Path, bool, str]]:
    goose = shutil.which("goose")
    if not goose:
        return []
    results: list[tuple[Path, bool, str]] = []
    for recipe in sorted((settings.project_root / "recipes").rglob("*.yaml")):
        proc = subprocess.run(
            [goose, "recipe", "validate", str(recipe)],
            capture_output=True,
            text=True,
        )
        ok = proc.returncode == 0
        msg = (proc.stdout or proc.stderr).strip()
        results.append((recipe, ok, msg))
    return results


def run_full_setup(settings: Settings | None = None) -> dict[str, object]:
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