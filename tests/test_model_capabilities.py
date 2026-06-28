from __future__ import annotations

from pathlib import Path

from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.config import MODEL_ALIASES, Settings
from builder_ii.model_capabilities import (
    MODEL_CAPABILITY_REGISTRY_KIND,
    create_model_capability_registry,
    dumps_model_capability_registry,
    validate_model_capability_registry,
)


def settings_stub(alias: str = "qwen-coder") -> Settings:
    return Settings(
        core_repo=Path("/tmp/core"),
        backend="mlx-lm",
        model_tier="primary",
        model_alias=alias,
        model_primary="gemma-4-12b-4bit",
        model_fast="gemma-4-e4b-4bit",
        mlx_model_primary="mlx-community/gemma-4-12B-it-4bit",
        mlx_model_fast="mlx-community/gemma-4-e4b-it-4bit",
        mlx_model_phi="mlx-community/Phi-4-mini-reasoning-4bit",
        mlx_model_qwen="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        mlx_model_deepseek="mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        mlx_model_llama="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        mlx_model_codegeex="mlx-community/codegeex4-all-9b-4bit",
        mlx_model_qwen14="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        mlx_model_qwen3_coder="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.0,
        project_root=Path("/tmp/builder-II"),
    )


def _repo_evidenced_aliases() -> set[str]:
    root = Path(__file__).resolve().parent.parent
    sources = [
        root / "builder_ii" / "config.py",
        root / "builder_ii" / "models.py",
        root / "builder_ii" / "model_policy.py",
        root / "builder_ii" / "model_router.py",
        root / "docs" / "model_operating_policy.md",
        root / "docs" / "model_role_matrix.md",
        root / "tests" / "test_model_policy.py",
        root / "tests" / "test_model_router.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    return {alias for alias in MODEL_ALIASES if alias in combined}


def test_default_registry_validates() -> None:
    registry = create_model_capability_registry(settings_stub())

    assert registry["kind"] == MODEL_CAPABILITY_REGISTRY_KIND
    assert registry["current_state"] == "DISABLED"
    assert registry["artifact_is_authority"] is False
    assert validate_model_capability_registry(registry) == []


def test_all_repo_evidenced_aliases_are_represented() -> None:
    registry = create_model_capability_registry(settings_stub())

    assert {record["alias"] for record in registry["models"]} == _repo_evidenced_aliases()


def test_governance_fields_remain_disabled() -> None:
    registry = create_model_capability_registry(settings_stub())
    governance = registry["governance"]

    assert governance == {
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "model_routing_authority": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "artifact_is_authority": False,
        "core_workbench_coupling": "NONE",
    }


def test_enabling_model_execution_fails() -> None:
    registry = create_model_capability_registry(settings_stub())
    registry["governance"]["model_execution"] = "ENABLED"

    errors = validate_model_capability_registry(registry)

    assert "governance.model_execution must be DISABLED" in errors


def test_enabling_model_routing_authority_fails() -> None:
    registry = create_model_capability_registry(settings_stub())
    registry["governance"]["model_routing_authority"] = "ENABLED"

    errors = validate_model_capability_registry(registry)

    assert "governance.model_routing_authority must be DISABLED" in errors


def test_malformed_model_record_fails() -> None:
    registry = create_model_capability_registry(settings_stub())
    registry["models"][0]["capabilities"] = ["made_up_capability"]
    registry["models"][0]["local_execution_candidate"] = "yes"

    errors = validate_model_capability_registry(registry)

    assert any("unsupported values" in error for error in errors)
    assert "models[0].local_execution_candidate must be a boolean" in errors


def test_registry_kind_is_registered_in_validators() -> None:
    registry = create_model_capability_registry(settings_stub())

    assert MODEL_CAPABILITY_REGISTRY_KIND in INDEX_VALIDATORS
    assert MODEL_CAPABILITY_REGISTRY_KIND in CHAIN_VALIDATORS
    assert INDEX_VALIDATORS[MODEL_CAPABILITY_REGISTRY_KIND](registry) == []
    assert CHAIN_VALIDATORS[MODEL_CAPABILITY_REGISTRY_KIND](registry) == []


def test_registry_json_round_trip() -> None:
    registry = create_model_capability_registry(settings_stub())

    rendered = dumps_model_capability_registry(registry)

    assert MODEL_CAPABILITY_REGISTRY_KIND in rendered
    assert validate_model_capability_registry(registry) == []
