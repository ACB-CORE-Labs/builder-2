from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.config import MODEL_ALIASES

MODEL_CLIENT_REGISTRY_KIND = "builder_ii.model_client_registry"
MODEL_CLIENT_REGISTRY_SCHEMA_VERSION = 1

KNOWN_PROVIDER_IDS = {"mlx_provider", "openai_stub_provider", "anthropic_stub_provider"}
KNOWN_CLIENT_IDS = {"mlx_lm_client", "openai_compat_client", "anthropic_stub_client"}
KNOWN_MODEL_IDS = {
    "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    "mlx-community/Phi-3.5-mini-instruct-4bit",
    "mlx-community/gemma-2-2b-it-4bit",
    "mlx-community/gemma-2-9b-it-4bit",
    "mlx-community/Llama-3.1-8B-Instruct-4bit",
    "mlx-community/codegeex4-all-9b-4bit",
    "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
    "mlx-community/Qwen2.5-Coder-32B-Instruct-4bit",
    "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
    "gpt-4o-stub",
    "claude-3-5-sonnet-stub",
}
ALLOWED_ENDPOINT_KINDS = {"local_mlx", "openai_compatible_local", "cloud_stub"}
ALLOWED_RISK_CLASSIFICATIONS = {"local_offline", "local_network", "cloud_external"}
ALLOWED_COST_CLASSES = {"free_local", "low", "medium", "high", "placeholder"}

_REF_NAME_RE = re.compile(r"^[A-Z0-9_]+$")


def _default_client_records() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "mlx_provider",
            "provider_name": "MLX Local Runtime Provider",
            "client_id": "mlx_lm_client",
            "client_name": "MLX LM Python Client",
            "endpoint_kind": "local_mlx",
            "model_id": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            "model_name": "Qwen 2.5 Coder 7B 4bit",
            "model_family": "qwen2.5",
            "model_alias": "qwen-coder",
            "context_window": 32768,
            "max_input_tokens": 32768,
            "max_output_tokens": 8192,
            "structured_output_supported": True,
            "tool_use_supported": True,
            "multimodal_supported": False,
            "risk_classification": "local_network",
            "cost_class": "free_local",
            "price_metadata": {"unit": "placeholder", "input_cost": "free", "output_cost": "free"},
            "secret_ref_names": ["MLX_MODEL_PATH"],
            "enabled": True,
            "executes_model": False,
            "grants_authority": False,
            "requires_human_promotion_for_execution": True,
        },
        {
            "provider_id": "mlx_provider",
            "provider_name": "MLX Local Runtime Provider",
            "client_id": "mlx_lm_client",
            "client_name": "MLX LM Python Client",
            "endpoint_kind": "local_mlx",
            "model_id": "mlx-community/Phi-3.5-mini-instruct-4bit",
            "model_name": "Phi 3.5 Mini Instruct 4bit",
            "model_family": "phi3",
            "model_alias": "phi-reasoning",
            "context_window": 128000,
            "max_input_tokens": 128000,
            "max_output_tokens": 4096,
            "structured_output_supported": True,
            "tool_use_supported": False,
            "multimodal_supported": False,
            "risk_classification": "local_network",
            "cost_class": "free_local",
            "price_metadata": {"unit": "placeholder", "input_cost": "free", "output_cost": "free"},
            "secret_ref_names": ["MLX_MODEL_PATH"],
            "enabled": True,
            "executes_model": False,
            "grants_authority": False,
            "requires_human_promotion_for_execution": True,
        },
        {
            "provider_id": "openai_stub_provider",
            "provider_name": "OpenAI Compatible Cloud Stub Provider",
            "client_id": "openai_compat_client",
            "client_name": "OpenAI Compatible HTTP Client",
            "endpoint_kind": "cloud_stub",
            "model_id": "gpt-4o-stub",
            "model_name": "GPT 4o Stub",
            "model_family": "gpt4",
            "model_alias": None,
            "context_window": 128000,
            "max_input_tokens": 128000,
            "max_output_tokens": 16384,
            "structured_output_supported": True,
            "tool_use_supported": True,
            "multimodal_supported": True,
            "risk_classification": "cloud_external",
            "cost_class": "placeholder",
            "price_metadata": {"unit": "placeholder", "input_cost": "placeholder", "output_cost": "placeholder"},
            "secret_ref_names": ["OPENAI_API_KEY_REF"],
            "enabled": False,
            "executes_model": False,
            "grants_authority": False,
            "requires_human_promotion_for_execution": True,
        },
    ]


def create_model_client_registry() -> dict[str, Any]:
    return {
        "kind": MODEL_CLIENT_REGISTRY_KIND,
        "schema_version": MODEL_CLIENT_REGISTRY_SCHEMA_VERSION,
        "registry_name": "passive_model_client_registry",
        "registry_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "executes_model": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "clients": _default_client_records(),
        "governance": {
            "model_execution": "DISABLED",
            "runtime_execution": "DISABLED",
            "network_calls": "DISABLED",
            "shell_execution": "DISABLED",
            "provider_calls": "DISABLED",
            "artifact_is_authority": False,
            "enabled_implies_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_model_client_registry(registry: dict[str, Any]) -> str:
    return json_lib.dumps(registry, indent=2, sort_keys=True) + "\n"


def write_model_client_registry(registry: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_model_client_registry(registry), encoding="utf-8")


def _validate_secret_ref_names(names: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(names, list):
        return [f"{field} must be a list of secret ref names"]
    for idx, name in enumerate(names):
        if not isinstance(name, str) or not name:
            errors.append(f"{field}[{idx}] must be a non-empty string")
            continue
        lower = name.lower()
        if any(lower.startswith(prefix) for prefix in ("sk-", "gsk_", "aiza", "bearer ", "key-", "secret-", "token-")):
            errors.append(f"{field}[{idx}] rejected: appears to contain a raw secret value prefix")
        elif " " in name or len(name) > 64:
            errors.append(f"{field}[{idx}] rejected: must be an environment ref name, not a raw value or passphrase")
        elif not _REF_NAME_RE.match(name):
            errors.append(f"{field}[{idx}] rejected: must follow UPPERCASE_REF syntax (e.g. OPENAI_API_KEY_REF)")
    return errors


def _validate_client_record(record: Any, index: int) -> list[str]:
    errors: list[str] = []
    field_prefix = f"clients[{index}]"
    if not isinstance(record, dict):
        return [f"{field_prefix} must be an object"]

    for forbidden_key in ("secrets", "api_key", "credentials", "token", "password"):
        if forbidden_key in record:
            errors.append(f"{field_prefix} must not contain forbidden secret or credential field '{forbidden_key}'")

    provider_id = record.get("provider_id")
    if provider_id not in KNOWN_PROVIDER_IDS:
        errors.append(f"{field_prefix}.provider_id '{provider_id}' is unknown")

    client_id = record.get("client_id")
    if client_id not in KNOWN_CLIENT_IDS:
        errors.append(f"{field_prefix}.client_id '{client_id}' is unknown")

    model_id = record.get("model_id")
    if model_id not in KNOWN_MODEL_IDS:
        errors.append(f"{field_prefix}.model_id '{model_id}' is unknown")

    endpoint_kind = record.get("endpoint_kind")
    if endpoint_kind not in ALLOWED_ENDPOINT_KINDS:
        errors.append(f"{field_prefix}.endpoint_kind '{endpoint_kind}' must be one of {sorted(ALLOWED_ENDPOINT_KINDS)}")

    risk = record.get("risk_classification")
    if not risk or risk not in ALLOWED_RISK_CLASSIFICATIONS:
        errors.append(f"{field_prefix}.risk_classification is missing or invalid; must be one of {sorted(ALLOWED_RISK_CLASSIFICATIONS)}")

    cost = record.get("cost_class")
    if not cost or cost not in ALLOWED_COST_CLASSES:
        errors.append(f"{field_prefix}.cost_class is missing or invalid; must be one of {sorted(ALLOWED_COST_CLASSES)}")

    model_alias = record.get("model_alias")
    if model_alias is not None and model_alias not in MODEL_ALIASES:
        errors.append(f"{field_prefix}.model_alias '{model_alias}' is not a known model alias")

    for str_field in ("provider_name", "client_name", "model_name", "model_family"):
        if not isinstance(record.get(str_field), str) or not record[str_field]:
            errors.append(f"{field_prefix}.{str_field} must be a non-empty string")

    for bool_field in ("structured_output_supported", "tool_use_supported", "multimodal_supported", "enabled"):
        if not isinstance(record.get(bool_field), bool):
            errors.append(f"{field_prefix}.{bool_field} must be a boolean")

    if record.get("executes_model") is not False:
        errors.append(f"{field_prefix}.executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append(f"{field_prefix}.grants_authority must be false")
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append(f"{field_prefix}.requires_human_promotion_for_execution must be true")

    errors.extend(_validate_secret_ref_names(record.get("secret_ref_names"), f"{field_prefix}.secret_ref_names"))

    if not isinstance(record.get("price_metadata"), dict):
        errors.append(f"{field_prefix}.price_metadata must be an object")

    return errors


def validate_model_client_registry(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["model client registry must be a JSON object"]
    if record.get("kind") != MODEL_CLIENT_REGISTRY_KIND:
        errors.append(f"kind must be {MODEL_CLIENT_REGISTRY_KIND}")
    if record.get("schema_version") != MODEL_CLIENT_REGISTRY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_CLIENT_REGISTRY_SCHEMA_VERSION}")
    if record.get("registry_state") != "RECORDED_ONLY":
        errors.append("registry_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    for forbidden_key in ("secrets", "api_key", "credentials", "token", "password"):
        if forbidden_key in record:
            errors.append(f"registry must not contain forbidden secret or credential field '{forbidden_key}'")

    clients = record.get("clients")
    if not isinstance(clients, list) or not clients:
        errors.append("clients must be a non-empty list")
    else:
        for idx, client in enumerate(clients):
            errors.extend(_validate_client_record(client, idx))

    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in ("model_execution", "runtime_execution", "network_calls", "shell_execution", "provider_calls"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("enabled_implies_authority") is not False:
            errors.append("governance.enabled_implies_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    def _check_no_active_states(obj: Any, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in {"registry_state", "current_state", "enabled"}:
                    continue
                _check_no_active_states(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _check_no_active_states(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            if obj in {"EXECUTED", "AUTHORIZED", "PROMOTED", "ENABLED"}:
                errors.append(f"field '{path}' claims active authority state '{obj}'")

    _check_no_active_states(record, "registry")

    return errors


def validate_model_client_registry_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_model_client_registry(data)
