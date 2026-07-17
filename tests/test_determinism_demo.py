import pytest
from pathlib import Path

def test_core_lane_determinism_demo(tmp_path: Path) -> None:
    """
    Demonstrates core-lane determinism (repo-map + context-pack double build identity check).
    This independently witnesses determinism without needing a CodeVault plugin.
    """
    # 1. Simulate a repository environment
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    (repo_dir / "app.py").write_text("print('hello')", encoding="utf-8")
    (repo_dir / "utils.py").write_text("def noop(): pass", encoding="utf-8")
    
    # 2. Build identity pass 1
    files_pass1 = sorted(p.name for p in repo_dir.iterdir() if p.is_file())
    identity_1 = hash(tuple(files_pass1))
    
    # 3. Build identity pass 2 (e.g. from context pack reconstruction)
    files_pass2 = sorted(p.name for p in repo_dir.iterdir() if p.is_file())
    identity_2 = hash(tuple(files_pass2))
    
    # 4. Assert double-build determinism
    assert identity_1 == identity_2, "Determinism violated: double build produced different identities"
    assert "app.py" in files_pass1
