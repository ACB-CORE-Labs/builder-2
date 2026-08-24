"""
No-mutation ACP smoke proof.
"""
import pytest
from pathlib import Path
from builder_ii.adapters.dsh.profile_renderer import render_isolated_profile
from builder_ii.adapters.dsh.compatibility_matrix import assert_authority, ThreatModelError

def test_profile_isolation(tmp_path: Path):
    """
    Test that isolated profiles generate the correct GOOSE_PATH_ROOT and DSH_HOME.
    """
    env = render_isolated_profile("test-session-123", tmp_path)
    
    assert "DSH_HOME" in env
    assert "GOOSE_PATH_ROOT" in env
    assert "test-session-123" in env["DSH_HOME"]
    
    dsh_home = Path(env["DSH_HOME"])
    goose_root = Path(env["GOOSE_PATH_ROOT"])
    
    assert dsh_home.exists()
    assert goose_root.exists()
    
    goose_config = goose_root / "config" / "config.yaml"
    assert goose_config.exists()
    assert "developer:\n    enabled: false" in goose_config.read_text()

def test_authority_ownership_fail_closed():
    """
    Test that authority assertions fail closed when invalid.
    """
    # Valid claim
    assert_authority("builder-II", "approvals")
    assert_authority("goose", "agent_loop")
    
    # Invalid claim
    with pytest.raises(ThreatModelError):
        assert_authority("deepseek-harness", "approvals")
    
    with pytest.raises(ThreatModelError):
        assert_authority("goose", "effectful_tools")

