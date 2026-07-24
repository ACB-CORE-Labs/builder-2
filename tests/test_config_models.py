import pytest

from builder_ii.core.config import load_settings
from builder_ii.routing.model_catalog import MODEL_ALIASES, normalize_model_alias
from builder_ii.core.models import model_definitions


def test_normalize_legacy_tiers():
    assert normalize_model_alias(None, tier_fallback="fast") == "phi-reasoning"
    assert normalize_model_alias(None, tier_fallback="primary") == "qwen-coder"
    assert normalize_model_alias("qwen") == "qwen-coder"
    assert normalize_model_alias("qwen14") == "qwen-coder-14b"


def test_unknown_alias_fails_closed():
    with pytest.raises(ValueError):
        normalize_model_alias("mystery-model")


def test_roster_contains_every_public_alias():
    settings = load_settings()
    aliases = {definition.alias for definition in model_definitions(settings)}
    assert set(MODEL_ALIASES) == aliases
    assert "phi-reasoning" in aliases
    assert "qwen-coder" in aliases
