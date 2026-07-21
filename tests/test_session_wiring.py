from pathlib import Path

from builder_ii.adapters.goose.goose_setup import build_goose_config
from builder_ii.core.config import load_settings


def test_configured_recipe_paths_exist() -> None:
    settings = load_settings()
    cfg = build_goose_config(settings)

    for item in cfg["slash_commands"]:
        assert Path(item["recipe_path"]).exists()


def test_plan_recipe_is_wired() -> None:
    settings = load_settings()
    cfg = build_goose_config(settings)
    recipe_paths = {Path(item["recipe_path"]).name for item in cfg["slash_commands"]}

    assert "plan.yaml" in recipe_paths
