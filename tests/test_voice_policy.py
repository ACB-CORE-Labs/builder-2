import json
import sys
from pathlib import Path

from builder_ii.voice_policy import (
    VOICE_IO_POLICY_KIND,
    create_voice_io_policy_artifact,
    dumps_voice_io_policy_artifact,
    validate_voice_io_policy_artifact,
    validate_voice_io_policy_artifact_file,
    write_voice_io_policy_artifact,
)


def test_voice_io_policy_creation_and_round_trip(tmp_path: Path) -> None:
    artifact = create_voice_io_policy_artifact()

    assert artifact["kind"] == VOICE_IO_POLICY_KIND
    assert artifact["record_state"] == "RECORDED_ONLY"
    assert artifact["current_state"] == "DESIGN_ONLY"
    assert artifact["runtime_status"] == "DISABLED"
    assert validate_voice_io_policy_artifact(artifact) == []

    data = json.loads(dumps_voice_io_policy_artifact(artifact))
    assert validate_voice_io_policy_artifact(data) == []

    output = tmp_path / "voice-policy.json"
    write_voice_io_policy_artifact(artifact, output)
    assert validate_voice_io_policy_artifact_file(output) == []


def test_validate_voice_io_policy_artifact_file_edge_cases(tmp_path: Path) -> None:
    assert any("file not found" in e for e in validate_voice_io_policy_artifact_file(tmp_path / "missing.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert any("invalid JSON" in e for e in validate_voice_io_policy_artifact_file(bad))
    d = tmp_path / "dir"
    d.mkdir()
    assert any("failed to read file" in e for e in validate_voice_io_policy_artifact_file(d))


def test_voice_io_policy_disabled_enforcement() -> None:
    artifact = create_voice_io_policy_artifact()

    denied = artifact["denied_current_behavior"]
    for behavior in [
        "microphone_capture",
        "speaker_playback",
        "subprocess_invocation",
        "swift_compilation",
        "shell_execution",
        "model_execution",
        "network_access",
        "target_repo_mutation",
        "hidden_audio_persistence",
        "builder_ask_integration",
    ]:
        assert behavior in denied

    governance = artifact["governance"]
    assert governance["runtime_execution"] == "DISABLED"
    assert governance["shell_execution"] == "DISABLED"
    assert governance["model_execution"] == "DISABLED"
    assert governance["network_access"] == "DISABLED"
    assert governance["source_writes"] == "DISABLED"
    assert governance["memory_mutation"] == "DISABLED"
    assert governance["artifact_is_authority"] is False
    assert governance["core_workbench_coupling"] == "NONE"

    invalid = create_voice_io_policy_artifact()
    invalid["runtime_status"] = "ENABLED"
    invalid["governance"]["shell_execution"] = "ENABLED"
    invalid["governance"]["source_writes"] = "ENABLED"
    invalid["governance"]["core_workbench_coupling"] = "TIGHT"

    errors = validate_voice_io_policy_artifact(invalid)

    assert "runtime_status must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.shell_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_writes must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in errors


def test_voice_io_policy_future_capabilities_are_declarations_only() -> None:
    artifact = create_voice_io_policy_artifact()

    assert artifact["capabilities"] == {
        "stt": "FUTURE_CANDIDATE_ONLY",
        "tts": "FUTURE_CANDIDATE_ONLY",
    }
    assert artifact["backend_declarations"] == {
        "native_macos": "DECLARATION_ONLY",
        "mlx_whisper": "DECLARATION_ONLY",
        "chatterbox": "DECLARATION_ONLY",
    }
    for requirement in [
        "docs",
        "tests",
        "command_surface",
        "failure_mode",
        "human_approval_boundary",
        "output_artifact",
        "rollback_path",
        "verification_path",
    ]:
        assert requirement in artifact["future_promotion_requirements"]


def test_no_runtime_imports() -> None:
    import builder_ii.voice_policy  # noqa: F401

    for module in ("torch", "torchaudio", "mlx", "mlx_whisper", "chatterbox"):
        assert module not in sys.modules
