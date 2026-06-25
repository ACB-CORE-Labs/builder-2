from builder_ii.config import load_settings
from builder_ii.goose_launcher import goose_env, goose_status, recipe_path


def test_goose_status_is_string():
    assert isinstance(goose_status(), str)


def test_goose_env_openai_provider():
    settings = load_settings()
    env = goose_env(settings)
    if settings.backend == "ollama":
        assert env["GOOSE_PROVIDER"] == "ollama"
    else:
        assert env["GOOSE_PROVIDER"] == "openai"
    assert env["GOOSE_TEMPERATURE"] == "0.0"
    assert env["GOOSE_MODEL"] == settings.active_model_id
    assert env["BUILDER_MODEL_ALIAS"] == settings.model_alias


def test_recipe_exists():
    settings = load_settings()
    assert recipe_path(settings).exists()


def test_platform_recipe_exists():
    from builder_ii.model_router import plan_session

    settings = load_settings()
    assert recipe_path(settings, plan_session("orchestrator")).exists()
