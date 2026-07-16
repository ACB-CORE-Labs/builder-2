from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

VOICE_IO_POLICY_KIND = "builder_ii.voice_io_policy"
VOICE_IO_POLICY_SCHEMA_VERSION = 1
_DENIED_CURRENT_BEHAVIOR = (
    "microphone_capture",
    "speaker_playback",
    "subprocess_invocation",
    "swift_compilation",
    "model_execution",
    "shell_execution",
    "network_access",
    "target_repo_mutation",
    "hidden_audio_persistence",
    "builder_ask_integration",
)
_PROMOTION_REQUIREMENTS = (
    "docs",
    "tests",
    "command_surface",
    "failure_mode",
    "human_approval_boundary",
    "output_artifact",
    "rollback_path",
    "verification_path",
)


def create_voice_io_policy_artifact() -> dict[str, Any]:
    return {
        "kind": VOICE_IO_POLICY_KIND,
        "schema_version": VOICE_IO_POLICY_SCHEMA_VERSION,
        "capability_state": "voice_io_policy",
        "record_state": "RECORDED_ONLY",
        "current_state": "DESIGN_ONLY",
        "runtime_status": "DISABLED",
        "capabilities": {
            "stt": "FUTURE_CANDIDATE_ONLY",
            "tts": "FUTURE_CANDIDATE_ONLY",
        },
        "backend_declarations": {
            "native_macos": "DECLARATION_ONLY",
            "mlx_whisper": "DECLARATION_ONLY",
            "chatterbox": "DECLARATION_ONLY",
        },
        "denied_current_behavior": list(_DENIED_CURRENT_BEHAVIOR),
        "future_promotion_requirements": list(_PROMOTION_REQUIREMENTS),
        "performed_actions": [],
        "governance": {
            "capability_state": "voice_io_policy",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "network_access": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_voice_io_policy_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_voice_io_policy_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_voice_io_policy_artifact(artifact), encoding="utf-8")


def _require_list_contains(artifact: dict[str, Any], field: str, expected: tuple[str, ...]) -> list[str]:
    value = artifact.get(field)
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    errors: list[str] = []
    for item in expected:
        if item not in value:
            errors.append(f"{field} must include {item}")
    return errors


def validate_voice_io_policy_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["voice io policy artifact must be a JSON object"]
    if artifact.get("kind") != VOICE_IO_POLICY_KIND:
        errors.append(f"kind must be {VOICE_IO_POLICY_KIND}")
    if artifact.get("schema_version") != VOICE_IO_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VOICE_IO_POLICY_SCHEMA_VERSION}")
    if artifact.get("capability_state") != "voice_io_policy":
        errors.append("capability_state must be voice_io_policy")
    if artifact.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if artifact.get("current_state") != "DESIGN_ONLY":
        errors.append("current_state must be DESIGN_ONLY")
    if artifact.get("runtime_status") != "DISABLED":
        errors.append("runtime_status must be DISABLED or NOT_AUTHORIZED")
    if artifact.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    errors.extend(_require_list_contains(artifact, "denied_current_behavior", _DENIED_CURRENT_BEHAVIOR))
    errors.extend(_require_list_contains(artifact, "future_promotion_requirements", _PROMOTION_REQUIREMENTS))

    capabilities = artifact.get("capabilities")
    if not isinstance(capabilities, dict):
        errors.append("capabilities must be an object")
    else:
        if capabilities.get("stt") != "FUTURE_CANDIDATE_ONLY":
            errors.append("capabilities.stt must be FUTURE_CANDIDATE_ONLY")
        if capabilities.get("tts") != "FUTURE_CANDIDATE_ONLY":
            errors.append("capabilities.tts must be FUTURE_CANDIDATE_ONLY")

    backends = artifact.get("backend_declarations")
    if not isinstance(backends, dict):
        errors.append("backend_declarations must be an object")
    else:
        for backend in ("native_macos", "mlx_whisper", "chatterbox"):
            if backends.get(backend) != "DECLARATION_ONLY":
                errors.append(f"backend_declarations.{backend} must be DECLARATION_ONLY")

    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "network_access",
            "source_writes",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_voice_io_policy_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_voice_io_policy_artifact(data)
