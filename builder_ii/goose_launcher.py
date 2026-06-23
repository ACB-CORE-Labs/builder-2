from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from builder_ii.config import Settings
from builder_ii.context import load_session_context


def find_goose_binary() -> str | None:
    return shutil.which("goose")


def goose_env(settings: Settings) -> dict[str, str]:
    env = os.environ.copy()
    base = settings.base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    # Rapid-MLX / mlx-lm expose OpenAI-compatible APIs. Goose OpenAI provider
    # also accepts Ollama-compat via OLLAMA_HOST when backend=ollama.
    if settings.backend == "ollama":
        host = settings.base_url.rstrip("/v1").rstrip("/")
        env["GOOSE_PROVIDER"] = "ollama"
        env["OLLAMA_HOST"] = host
    else:
        env["GOOSE_PROVIDER"] = "openai"
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "not-needed")
        env["OPENAI_HOST"] = base

    env["GOOSE_MODEL"] = "default"
    env["GOOSE_TEMPERATURE"] = str(settings.temperature)
    env["GOOSE_MODE"] = "auto"
    recipe_dir = settings.project_root / "recipes"
    env["GOOSE_RECIPE_PATH"] = str(recipe_dir)
    return env


def recipe_path(settings: Settings) -> Path:
    return settings.project_root / "recipes" / "core-coding.yaml"


def launch_goose_session(
    settings: Settings,
    *,
    cwd: Path | None = None,
    resume: bool = False,
) -> subprocess.Popen[str]:
    goose = find_goose_binary()
    if not goose:
        raise FileNotFoundError(
            "Codename Goose CLI not found. Install: brew install block-goose-cli "
            "or scripts/install-goose.sh"
        )

    recipe = recipe_path(settings)
    if not recipe.exists():
        raise FileNotFoundError(f"Missing recipe: {recipe}")

    workdir = cwd or settings.core_repo
    ctx = load_session_context(settings)
    env = goose_env(settings)
    env["CORE_AGENT_CONTEXT"] = (
        f"repo={ctx.core_repo}\ngit={ctx.git_status}\ndirs={ctx.top_level_dirs}"
    )

    argv = [goose, "session", "--recipe", str(recipe)]
    if resume:
        argv.append("--resume")
    return subprocess.Popen(argv, cwd=workdir, env=env)


def goose_status() -> str:
    goose = find_goose_binary()
    if not goose:
        return "goose: NOT INSTALLED (brew install block-goose-cli)"
    try:
        proc = subprocess.run(
            [goose, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = (proc.stdout or proc.stderr).strip()
        return f"goose: {version}"
    except subprocess.SubprocessError as exc:
        return f"goose: error ({exc})"