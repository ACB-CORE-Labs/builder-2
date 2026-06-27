from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

VOICE_IO_POLICY_KIND = "builder_ii.voice_io_policy"
VOICE_IO_POLICY_SCHEMA_VERSION = 1

def create_voice_io_policy_artifact() -> dict[str, Any]:
    return {
        "kind": VOICE_IO_POLICY_KIND,
        "schema_version": VOICE_IO_POLICY_SCHEMA_VERSION,
        "state": {
            "current_state": "DESIGN_ONLY",
            "runtime_status": "DISABLED",
        },
        "capabilities": {
            "stt_status": "future_candidate",
            "tts_status": "future_candidate",
        },
        "backends": {
            "native_macos": "future_declaration_only",
            "mlx_whisper": "future_declaration_only",
            "chatterbox": "future_declaration_only",
        },
        "denied_current_behavior": [
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
        ],
        "future_promotion_requirements": [
            "docs",
            "tests",
            "command_surface",
            "failure_mode",
            "human_approval_boundary",
            "output_artifact",
            "rollback_path",
            "verification_path",
        ],
        "governance": {
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }

def dumps_voice_io_policy_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"

def write_voice_io_policy_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_voice_io_policy_artifact(artifact), encoding="utf-8")

def validate_voice_io_policy_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["voice io policy artifact must be a JSON object"]
    if artifact.get("kind") != VOICE_IO_POLICY_KIND:
        errors.append(f"kind must be {VOICE_IO_POLICY_KIND}")
    if artifact.get("schema_version") != VOICE_IO_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VOICE_IO_POLICY_SCHEMA_VERSION}")
    
    state = artifact.get("state")
    if not isinstance(state, dict):
        errors.append("state must be an object")
    else:
        if state.get("current_state") != "DESIGN_ONLY":
            errors.append("state.current_state must be DESIGN_ONLY")
        if state.get("runtime_status") != "DISABLED":
            errors.append("state.runtime_status must be DISABLED")

    denied = artifact.get("denied_current_behavior")
    if isinstance(denied, list):
        for behavior in [
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
        ]:
            if behavior not in denied:
                errors.append(f"denied_current_behavior must include {behavior}")
    else:
        errors.append("denied_current_behavior must be a list")

    gov = artifact.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        if gov.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if gov.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
            
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
