from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from builder_ii.config import Settings
from builder_ii.context import load_session_context
from builder_ii.goose_setup import write_moim_context
from builder_ii.model_router import SessionPlan, plan_session


def find_goose_binary() -> str | None:
    return shutil.which("goose")


def goose_env(settings: Settings, *, session: SessionPlan | None = None) -> dict[str, str]:
    env = os.environ.copy()
    base = settings.base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

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
    env["GOOSE_MAX_TURNS"] = "1000"

    # M1 16GB: planner shares execution endpoint (one model loaded).
    env["GOOSE_PLANNER_PROVIDER"] = env["GOOSE_PROVIDER"]
    env["GOOSE_PLANNER_MODEL"] = env["GOOSE_MODEL"]

    recipe_dir = settings.project_root / "recipes"
    env["GOOSE_RECIPE_PATH"] = str(recipe_dir)

    # Top-of-mind context injection every turn.
    moim = write_moim_context(settings)
    env["GOOSE_MOIM_MESSAGE_FILE"] = str(moim)

    tier = session.model_tier if session else settings.model_tier
    env["BUILDER_MODEL_TIER"] = tier
    env["BUILDER_SESSION_MODE"] = session.mode if session else "orchestrator"

    return env


def recipe_path(settings: Settings, session: SessionPlan | None = None) -> Path:
    name = session.recipe_name if session else "core-platform.yaml"
    return settings.project_root / "recipes" / name


def launch_goose_session(
    settings: Settings,
    *,
    cwd: Path | None = None,
    resume: bool = False,
    session: SessionPlan | None = None,
    name: str | None = None,
) -> subprocess.Popen[str]:
    goose = find_goose_binary()
    if not goose:
        raise FileNotFoundError(
            "Codename Goose CLI not found. Install: brew install block-goose-cli "
            "or scripts/install-goose.sh"
        )

    plan = session or plan_session("orchestrator")
    recipe = recipe_path(settings, plan)
    if not recipe.exists():
        raise FileNotFoundError(f"Missing recipe: {recipe}")

    workdir = cwd or settings.core_repo
    ctx = load_session_context(settings)
    env = goose_env(settings, session=plan)

    argv = [goose, "session", "--recipe", str(recipe)]
    if name:
        argv.extend(["--name", name])
    if resume:
        argv.append("--resume")

    argv.extend(
        [
            "--with-builtin",
            "developer,skills,summon",
        ]
    )

    return subprocess.Popen(argv, cwd=workdir, env=env)


def pull_models(settings: Settings) -> list[str]:
    """Pre-download Rapid-MLX model weights."""
    rapid = shutil.which("rapid-mlx")
    if not rapid or settings.backend != "rapid-mlx":
        return []
    commands = []
    for model in (settings.model_primary, settings.model_fast):
        proc = subprocess.run(
            [rapid, "pull", model],
            capture_output=True,
            text=True,
        )
        commands.append(f"rapid-mlx pull {model} -> exit {proc.returncode}")
    return commands


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