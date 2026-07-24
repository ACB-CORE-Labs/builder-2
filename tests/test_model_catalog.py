import pytest
from builder_ii.routing.model_catalog import MODEL_ALIASES, ALIAS_NORMALIZATION, normalize_model_alias
from builder_ii.routing.model_client_registry import _default_client_records

def test_registry_integrity():
    """Strict registry integrity tests."""
    roster = _default_client_records()
    registry_aliases = {model["model_alias"] for model in roster}
    
    # All aliases in MODEL_ALIASES should exist in the registry
    for alias in MODEL_ALIASES:
        assert alias in registry_aliases, f"Alias {alias} in MODEL_ALIASES not found in registry roster."
    
    # All aliases in registry should exist in MODEL_ALIASES
    for alias in registry_aliases:
        assert alias in MODEL_ALIASES, f"Registry alias {alias} not found in MODEL_ALIASES."

def test_normalize_fallback():
    assert normalize_model_alias(None, tier_fallback="fast") == "phi-reasoning"
    assert normalize_model_alias(None, tier_fallback="primary") == "qwen-coder"

def test_normalize_normalization():
    for raw, expected in ALIAS_NORMALIZATION.items():
        assert normalize_model_alias(raw) == expected
