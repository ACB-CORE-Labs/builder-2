from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from builder_ii.adapters.goose.goose_runtime_context import write_moim_context
from builder_ii.core.config import Settings
from builder_ii.core.context import load_session_context
from builder_ii.routing.model_router import SessionPlan, plan_session


def find_goose_binary() -> str | None:
    return shutil.which("goose")


def _server_root_url(base_url: str) -> str:
    """Return provider host root without a trailing OpenAI /v1 path.

    Goose's OpenAI provider appends `/v1/chat/completions` itself. Passing a
    host that already ends in `/v1` produces `/v1/v1/chat/completions`.
    """
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[: -len("/v1")]
    return base


def _get_google_project_id() -> str:
    if os.getenv("GOOGLE_PROJECT_ID"):
        return os.environ["GOOGLE_PROJECT_ID"]
    res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, check=False)
    return res.stdout.strip()


def _get_google_access_token() -> str:
    if os.getenv("GOOGLE_ACCESS_TOKEN"):
        return os.environ["GOOGLE_ACCESS_TOKEN"]
    if os.getenv("GOOGLE_OAUTH_TOKEN"):
        return os.environ["GOOGLE_OAUTH_TOKEN"]
    res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=False)
    return res.stdout.strip()


def resolve_model_id(settings: Settings, alias: str) -> str:
    backend = settings.backend
    if backend == "groq":
        return {
            "groq-llama": "llama-3.3-70b-versatile",
            "groq-mixtral": "mixtral-8x7b-32768",
            "groq-llama-instant": "llama-3.1-8b-instant",
            "groq-gpt-oss-20b": "openai/gpt-oss-20b",
            "groq-llama-scout": "meta-llama/llama-4-scout-17b-16e-instruct",
            "groq-gpt-oss-120b": "openai/gpt-oss-120b",
            "groq-qwen3-32b": "qwen/qwen3-32b",
            "groq-kimi-k2": "moonshotai/kimi-k2-instruct-0905",
        }.get(alias, "llama-3.3-70b-versatile")
    if backend == "xai":
        return {
            "grok-reasoning": "grok-2-1212",
            "grok-beta": "grok-beta",
            "grok-4.3": "grok-4.3",
            "grok-build-0.1": "grok-build-0.1",
            "grok-4.1-fast": "grok-4.1-fast",
        }.get(alias, "grok-4.3")
    if backend == "openai":
        return {
            "gpt-5.5": "gpt-5.5",
            "gpt-5.5-pro": "gpt-5.5-pro",
            "gpt-5.4": "gpt-5.4",
            "gpt-5.4-mini": "gpt-5.4-mini",
            "gpt-5.4-nano": "gpt-5.4-nano",
            "gpt-5.3-codex": "gpt-5.3-codex",
            "gpt-4o": "gpt-4o",
            "o3": "o3",
        }.get(alias, "gpt-5.5")
    if backend == "anthropic":
        return {
            "claude-fable-5": "claude-fable-5",
            "claude-opus-4.8": "claude-opus-4-8",
            "claude-opus-4.7": "claude-opus-4-7",
            "claude-opus-4.6": "claude-opus-4-6",
            "claude-sonnet-5": "claude-sonnet-5",
            "claude-sonnet-4.6": "claude-sonnet-4-6",
            "claude-sonnet-4.5": "claude-sonnet-4-5",
            "claude-haiku-4.5": "claude-haiku-4-5-20251001",
        }.get(alias, "claude-opus-4-8")
    if backend == "google":
        return {
            "gemini-pro": "gemini-1.5-pro",
            "gemini-flash": "gemini-1.5-flash",
            "gemini-ultra": "gemini-1.0-ultra",
            "gemini-3.5-flash": "gemini-3.5-flash",
            "gemini-3.1-pro": "gemini-3.1-pro-preview",
            "gemini-3.1-flash": "gemini-3.1-flash-lite",
            "gemini-3-flash": "gemini-3-flash-preview",
        }.get(alias, "gemini-1.5-pro")
    if backend == "ollama":
        return alias
    if backend == "mlx-lm":
        return {
            "phi-reasoning": settings.mlx_model_phi,
            "qwen-coder": settings.mlx_model_qwen,
            "gemma-fast": settings.mlx_model_fast,
            "gemma-primary": settings.mlx_model_primary,
            "llama": settings.mlx_model_llama,
            "codegeex": settings.mlx_model_codegeex,
            "qwen-coder-14b": settings.mlx_model_qwen14,
            "qwen3-coder-heavy": settings.mlx_model_qwen3_coder,
            "deepseek": settings.mlx_model_deepseek,
        }.get(alias, settings.mlx_model_phi)
    # rapid-mlx
    if alias == "gemma-primary":
        return settings.model_primary
    if alias == "gemma-fast":
        return settings.model_fast
    return alias


def derive_goose_environment(
    settings: Settings | None = None,
    session: SessionPlan | None = None,
) -> tuple[dict[str, str], dict[str, any]]:
    from builder_ii.core.config import load_settings

    if settings is None:
        settings = load_settings()

    env = os.environ.copy()

    goose_provider = "openai"
    provider_host = ""
    key = None
    key_present = False

    google_project_id = ""
    google_token = ""
    if settings.backend == "google":
        try:
            google_project_id = _get_google_project_id()
        except Exception:
            pass
        try:
            google_token = _get_google_access_token()
        except Exception:
            pass

    if settings.backend == "ollama":
        goose_provider = "ollama"
        provider_host = _server_root_url(settings.base_url)
        key = None
        key_present = True
    elif settings.backend == "groq":
        goose_provider = "openai"
        provider_host = "https://api.groq.com/openai"
        key = env.get("GROQ_API_KEY") or env.get("OPENAI_API_KEY")
        key_present = bool(key)
    elif settings.backend == "xai":
        goose_provider = "openai"
        provider_host = "https://api.x.ai"
        key = env.get("XAI_API_KEY") or env.get("OPENAI_API_KEY")
        key_present = bool(key)
    elif settings.backend == "google":
        goose_provider = "openai"
        if google_project_id:
            provider_host = f"https://aiplatform.googleapis.com/v1beta1/projects/{google_project_id}/locations/global/endpoints/openapi"
        else:
            provider_host = ""
        key = env.get("GEMINI_API_KEY") or google_token
        key_present = bool(key)
    elif settings.backend == "anthropic":
        goose_provider = "anthropic"
        provider_host = ""
        key = env.get("ANTHROPIC_API_KEY")
        key_present = bool(key)
    elif settings.backend in ("mlx-lm", "rapid-mlx"):
        goose_provider = "openai"
        provider_host = _server_root_url(settings.base_url)
        key = env.get("OPENAI_API_KEY") or "not-needed"
        key_present = True
    else:  # openai or other
        goose_provider = "openai"
        provider_host = _server_root_url(settings.base_url)
        key = env.get("OPENAI_API_KEY")
        key_present = bool(key)

    goose_model = settings.active_model_id
    temperature = str(settings.temperature)
    planner_provider = goose_provider
    planner_model = goose_model

    recipe = recipe_path(settings, session)
    moim = write_moim_context(settings)

    fast_model = None
    _BACKEND_FAST_ALIAS = {
        "groq": "groq-llama-instant",
        "xai": "grok-4.1-fast",
        "openai": "gpt-5.4-mini",
        "anthropic": "claude-haiku-4.5",
        "google": "gemini-3.5-flash",
        "ollama": "phi-reasoning",
        "mlx-lm": "phi-reasoning",
        "rapid-mlx": "gemma-fast",
    }
    fast_alias = _BACKEND_FAST_ALIAS.get(settings.backend)
    if fast_alias:
        try:
            fast_model = resolve_model_id(settings, fast_alias)
        except Exception:
            pass

    goose_installed = bool(find_goose_binary())
    launch_ready = goose_installed and key_present

    actual_env = env.copy()
    actual_env["GOOSE_PROVIDER"] = goose_provider
    actual_env["GOOSE_MODEL"] = goose_model
    actual_env["GOOSE_TEMPERATURE"] = temperature
    actual_env["GOOSE_MODE"] = "auto"
    actual_env["GOOSE_MAX_TURNS"] = "1000"
    actual_env["GOOSE_PLANNER_PROVIDER"] = planner_provider
    actual_env["GOOSE_PLANNER_MODEL"] = planner_model
    actual_env["GOOSE_RECIPE_PATH"] = str(recipe.parent)
    actual_env["GOOSE_MOIM_MESSAGE_FILE"] = str(moim)

    if fast_model:
        actual_env["GOOSE_FAST_MODEL"] = fast_model

    # Modern Goose provider variables
    actual_env["GOOSE_PROVIDER__TYPE"] = goose_provider
    if provider_host:
        actual_env["GOOSE_PROVIDER__HOST"] = provider_host
    if key:
        actual_env["GOOSE_PROVIDER__API_KEY"] = key

    # Compatibility variables
    if goose_provider == "ollama":
        if provider_host:
            actual_env["OLLAMA_HOST"] = provider_host
    elif goose_provider == "anthropic":
        if key:
            actual_env["ANTHROPIC_API_KEY"] = key
    else:  # openai compatible
        if provider_host:
            actual_env["OPENAI_HOST"] = provider_host
        if key:
            actual_env["OPENAI_API_KEY"] = key

        # Preserve specific keys if not overridden
        if settings.backend == "groq" and os.getenv("GROQ_API_KEY"):
            actual_env["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
        elif settings.backend == "xai" and os.getenv("XAI_API_KEY"):
            actual_env["XAI_API_KEY"] = os.getenv("XAI_API_KEY")
        elif settings.backend == "google":
            if os.getenv("GEMINI_API_KEY"):
                actual_env["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

    actual_env["BUILDER_MODEL_TIER"] = session.model_tier if session else settings.model_tier
    actual_env["BUILDER_MODEL_ALIAS"] = settings.model_alias
    actual_env["BUILDER_SESSION_MODE"] = session.mode if session else "orchestrator"

    report = {
        "selected_backend": settings.backend,
        "selected_model_alias": settings.model_alias,
        "goose_provider": goose_provider,
        "goose_model": goose_model,
        "provider_host": provider_host,
        "key_present": "yes" if key_present else "no",
        "recipe_path": str(recipe),
        "moim_file": str(moim),
        "launch_ready": launch_ready,
    }

    return actual_env, report


def goose_env(settings: Settings, *, session: SessionPlan | None = None) -> dict[str, str]:
    return derive_goose_environment(settings, session)[0]


def recipe_path(settings: Settings, session: SessionPlan | None = None) -> Path:
    name = session.recipe_name if session else "core-platform.yaml"
    return settings.project_root / "recipes" / name


def _goose_session_help(goose: str) -> str:
    try:
        proc = subprocess.run(
            [goose, "session", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def _supports_flag(help_text: str, flag: str) -> bool:
    return flag in help_text


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
            "Codename Goose CLI not found. Install: brew install block-goose-cli or scripts/install-goose.sh"
        )

    plan = session or plan_session("orchestrator")
    recipe = recipe_path(settings, plan)
    if not recipe.exists():
        raise FileNotFoundError(f"Missing recipe: {recipe}")

    workdir = cwd or settings.target_repo
    load_session_context(settings)

    env, report = derive_goose_environment(settings, session=plan)
    if not report["launch_ready"]:
        raise ValueError(
            "No Goose provider could be derived from builder-II settings/.env. "
            "Set BUILDER_MODEL_BACKEND/BUILDER_MODEL_ALIAS plus the required key, "
            "or run goose configure."
        )

    help_text = _goose_session_help(goose)
    argv = [goose, "session"]

    # Goose 1.38 rejects `goose session --recipe`. Older builds accepted it.
    # Detect support from help text instead of assuming one CLI shape.
    if _supports_flag(help_text, "--recipe"):
        argv.extend(["--recipe", str(recipe)])
    else:
        env["BUILDER_RECIPE_PATH"] = str(recipe)

    if name and _supports_flag(help_text, "--name"):
        argv.extend(["--name", name])
    if resume and _supports_flag(help_text, "--resume"):
        argv.append("--resume")

    if _supports_flag(help_text, "--with-builtin"):
        argv.extend(["--with-builtin", "developer,skills,summon"])

    return subprocess.Popen(argv, cwd=workdir, env=env)


def pull_models(settings: Settings) -> list[str]:
    """Pre-download Rapid-MLX model weights for legacy rapid-mlx mode."""
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
