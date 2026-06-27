import json
import sys
from builder_ii.voice_policy import (
    create_voice_io_policy_artifact,
    validate_voice_io_policy_artifact,
    VOICE_IO_POLICY_KIND,
)

def test_voice_io_policy_creation():
    artifact = create_voice_io_policy_artifact()
    assert artifact["kind"] == VOICE_IO_POLICY_KIND
    assert validate_voice_io_policy_artifact(artifact) == []

def test_voice_io_policy_disabled_enforcement():
    artifact = create_voice_io_policy_artifact()
    
    # Assert runtime/shell/model/source writes are disabled
    denied = artifact["denied_current_behavior"]
    assert "shell_execution" in denied
    assert "model_execution" in denied
    assert "target_repo_mutation" in denied
    assert "subprocess_invocation" in denied
    assert "swift_compilation" in denied

    # Assert artifact is not authority
    assert artifact["governance"]["artifact_is_authority"] is False
    
    # Assert CORE Workbench coupling is NONE
    assert artifact["governance"]["core_workbench_coupling"] == "NONE"

    # Ensure validation fails if these invariants are violated
    invalid_artifact = create_voice_io_policy_artifact()
    invalid_artifact["state"]["runtime_status"] = "ENABLED"
    errors = validate_voice_io_policy_artifact(invalid_artifact)
    assert "state.runtime_status must be DISABLED" in errors
    
    invalid_gov = create_voice_io_policy_artifact()
    invalid_gov["governance"]["core_workbench_coupling"] = "TIGHT"
    errors_gov = validate_voice_io_policy_artifact(invalid_gov)
    assert "governance.core_workbench_coupling must be NONE" in errors_gov

def test_no_runtime_imports():
    import builder_ii.voice_policy
    # Ensure no optional MLX/torch deps are imported
    assert "torch" not in sys.modules
    assert "torchaudio" not in sys.modules
    assert "mlx" not in sys.modules
