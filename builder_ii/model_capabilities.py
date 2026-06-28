from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import MODEL_ALIASES, Settings, load_settings
from builder_ii.model_policy import runtime_for_alias
from builder_ii.models import model_definitions

MODEL_CAPABILITY_REGISTRY_KIND = "builder_ii.model_capability_registry"
MODEL_CAPABILITY_REGISTRY_SCHEMA_VERSION = 1

_ALLOWED_CAPABILITIES = {
    "code_generation",
    "code_review",
    "repo_mapping",
    "structured_output",
    "reasoning",
    "fast_iteration",
    "long_context",
    "multimodal_input",
}
_ALLOWED_TIERS = {"low", "medium", "high", "very_high"}
_ROLE_GUIDANCE_BY_ALIAS: dict[str, tuple[str, ...]] = {
    "phi-reasoning": (
        "failure_reviewer",
        "invariant_auditor",
        "diff_summarizer",
        "lane_router",
    ),
    "qwen-coder": (
        "patch_planner",
        "handoff_scribe",
    ),
    "gemma-fast": (),
    "gemma-primary": (),
    "llama": (),
    "codegeex": (),
    "qwen-coder-14b": (),
    "qwen3-coder-heavy": (),
    "deepseek": (),
}
_CAPABILITIES_BY_ALIAS: dict[str, tuple[str, ...]] = {
    "phi-reasoning": ("reasoning", "code_review", "fast_iteration"),
    "qwen-coder": ("code_generation", "code_review", "fast_iteration"),
    "gemma-fast": ("multimodal_input",),
    "gemma-primary": ("multimodal_input",),
    "llama": ("reasoning",),
    "codegeex": ("code_generation",),
    "qwen-coder-14b": ("code_generation", "code_review"),
    "qwen3-coder-heavy": ("code_generation", "code_review"),
    "deepseek": ("code_generation", "repo_mapping"),
}
_LIMITATIONS_BY_ALIAS: dict[str, tuple[str, ...]] = {
    "phi-reasoning": (
        "avoid heavy implementation",
        "avoid long Goose tool sessions",
        "review and planning only under Goose tools boundary",
    ),
    "qwen-coder": (
        "avoid whole-repo sweeps",
        "avoid giant-context refactors",
        "avoid unsupervised tool execution",
    ),
    "gemma-fast": (
        "not a normal mlx-lm Goose start target",
        "requires mlx-vlm adapter support for multimodal workflows",
    ),
    "gemma-primary": (
        "explicit opt-in sidecar only",
        "not a normal mlx-lm Goose start target",
        "avoid long coding sessions on M1 16GB",
    ),
    "llama": (
        "manual alternate only",
        "avoid default code implementation when qwen-coder is available",
    ),
    "codegeex": (
        "candidate-verify-first",
        "avoid trusted edits before dedicated validation",
    ),
    "qwen-coder-14b": (
        "heavy explicit opt-in only",
        "avoid default or routine tasks on M1 16GB",
    ),
    "qwen3-coder-heavy": (
        "heavy explicit opt-in only",
        "avoid normal local Goose work on 16GB",
    ),
    "deepseek": (
        "heavy explicit opt-in only",
        "avoid daily operation or default routing",
    ),
}
_MEMORY_TIER_BY_ALIAS: dict[str, str] = {
    "phi-reasoning": "low",
    "qwen-coder": "medium",
    "gemma-fast": "medium",
    "gemma-primary": "medium",
    "llama": "medium",
    "codegeex": "high",
    "qwen-coder-14b": "high",
    "qwen3-coder-heavy": "very_high",
    "deepseek": "high",
}
_LATENCY_TIER_BY_ALIAS: dict[str, str] = {
    "phi-reasoning": "low",
    "qwen-coder": "medium",
    "gemma-fast": "medium",
    "gemma-primary": "high",
    "llama": "medium",
    "codegeex": "high",
    "qwen-coder-14b": "high",
    "qwen3-coder-heavy": "very_high",
    "deepseek": "high",
}
_COST_TIER_BY_ALIAS: dict[str, str] = {
    "phi-reasoning": "low",
    "qwen-coder": "medium",
    "gemma-fast": "medium",
    "gemma-primary": "high",
    "llama": "medium",
    "codegeex": "high",
    "qwen-coder-14b": "high",
    "qwen3-coder-heavy": "very_high",
    "deepseek": "high",
}
_HEAVY_MODEL_ALIASES = {"qwen-coder-14b", "qwen3-coder-heavy", "deepseek"}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _string_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (_clean(value) for value in values) if item]


def _source_evidence() -> dict[str, list[str]]:
    return {
        "modules": [
            "builder_ii/models.py",
            "builder_ii/model_policy.py",
            "builder_ii/model_router.py",
            "builder_ii/config.py",
            "builder_ii/roles.py",
            "builder_ii/lane_guides.py",
        ],
        "docs": [
            "docs/model_operating_policy.md",
            "docs/model_role_matrix.md",
            "docs/personas.md",
            "docs/manual.md",
        ],
        "tests": [
            "tests/test_model_policy.py",
            "tests/test_model_router.py",
            "tests/test_roles.py",
            "tests/test_lane_guides.py",
            "tests/test_config_models.py",
        ],
    }


def model_capability_records(settings: Settings) -> tuple[dict[str, Any], ...]:
    tiers = {definition.alias: definition.tier for definition in model_definitions(settings)}
    return tuple(
        {
            "alias": alias,
            "provider_or_backend": runtime_for_alias(alias),
            "role_tier": tiers[alias],
            "recommended_roles": list(_ROLE_GUIDANCE_BY_ALIAS[alias]),
            "capabilities": list(_CAPABILITIES_BY_ALIAS[alias]),
            "limitations": list(_LIMITATIONS_BY_ALIAS[alias]),
            "memory_tier": _MEMORY_TIER_BY_ALIAS[alias],
            "latency_tier": _LATENCY_TIER_BY_ALIAS[alias],
            "cost_tier": _COST_TIER_BY_ALIAS[alias],
            "local_execution_candidate": True,
            "heavy_model": alias in _HEAVY_MODEL_ALIASES,
        }
        for alias in tiers
    )


def create_model_capability_registry(settings: Settings | None = None) -> dict[str, Any]:
    effective_settings = settings or load_settings()
    records = list(model_capability_records(effective_settings))
    return {
        "kind": MODEL_CAPABILITY_REGISTRY_KIND,
        "schema_version": MODEL_CAPABILITY_REGISTRY_SCHEMA_VERSION,
        "registry_name": "source_backed_model_capability_registry",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "scope": "MODEL_METADATA_ONLY",
        "artifact_is_authority": False,
        "models": records,
        "evidence": _source_evidence(),
        "performed_actions": [],
        "governance": {
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "model_routing_authority": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_model_capability_registry(registry: dict[str, Any]) -> str:
    return json_lib.dumps(registry, indent=2, sort_keys=True) + "\n"


def write_model_capability_registry(registry: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_model_capability_registry(registry), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _validate_model_record(record: Any, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"models[{index}] must be an object"]
    alias = record.get("alias")
    if alias not in MODEL_ALIASES:
        errors.append(f"models[{index}].alias must be a known model alias")
    for field in ("provider_or_backend", "role_tier", "memory_tier", "latency_tier", "cost_tier"):
        if not isinstance(record.get(field), str) or not record[field]:
            errors.append(f"models[{index}].{field} must be a non-empty string")
    if isinstance(record.get("capabilities"), list):
        unknown = sorted(set(record["capabilities"]) - _ALLOWED_CAPABILITIES)
        if unknown:
            errors.append(f"models[{index}].capabilities contains unsupported values: {', '.join(unknown)}")
    errors.extend(_string_list_errors(record.get("recommended_roles"), field=f"models[{index}].recommended_roles", allow_empty=True))
    errors.extend(_string_list_errors(record.get("capabilities"), field=f"models[{index}].capabilities", allow_empty=True))
    errors.extend(_string_list_errors(record.get("limitations"), field=f"models[{index}].limitations"))
    for field in ("memory_tier", "latency_tier", "cost_tier"):
        value = record.get(field)
        if isinstance(value, str) and value not in _ALLOWED_TIERS:
            errors.append(f"models[{index}].{field} must be one of: low, medium, high, very_high")
    for field in ("local_execution_candidate", "heavy_model"):
        if not isinstance(record.get(field), bool):
            errors.append(f"models[{index}].{field} must be a boolean")
    return errors


def validate_model_capability_registry(registry: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(registry, dict):
        return ["model capability registry must be a JSON object"]
    if registry.get("kind") != MODEL_CAPABILITY_REGISTRY_KIND:
        errors.append(f"kind must be {MODEL_CAPABILITY_REGISTRY_KIND}")
    if registry.get("schema_version") != MODEL_CAPABILITY_REGISTRY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_CAPABILITY_REGISTRY_SCHEMA_VERSION}")
    if registry.get("registry_name") != "source_backed_model_capability_registry":
        errors.append("registry_name must be source_backed_model_capability_registry")
    if registry.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if registry.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if registry.get("scope") != "MODEL_METADATA_ONLY":
        errors.append("scope must be MODEL_METADATA_ONLY")
    if registry.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    models = registry.get("models")
    if not isinstance(models, list) or not models:
        errors.append("models must be a non-empty list")
    else:
        aliases = [record.get("alias") for record in models if isinstance(record, dict)]
        if len(set(aliases)) != len(aliases):
            errors.append("models aliases must be unique")
        if set(aliases) != set(MODEL_ALIASES):
            errors.append("models must represent every known model alias exactly once")
        for index, record in enumerate(models):
            errors.extend(_validate_model_record(record, index))
    evidence = registry.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be an object")
    else:
        for field in ("modules", "docs", "tests"):
            errors.extend(_string_list_errors(evidence.get(field), field=f"evidence.{field}"))
    if registry.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = registry.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
            "model_routing_authority",
            "shell_execution",
            "source_writes",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_model_capability_registry_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_model_capability_registry(data)
