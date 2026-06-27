from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.repo_map import (
    REPO_MAP_KIND,
    create_repo_map,
    dumps_repo_map,
    validate_repo_map,
    validate_repo_map_file,
)


def test_repo_map_creates_valid_artifact_for_fake_repo(tmp_path: Path) -> None:
    repo = tmp_path / "fake_repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Fake Repo\n", encoding="utf-8")
    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")

    data = create_repo_map(repo, target_name="generic")
    assert data["kind"] == REPO_MAP_KIND
    assert data["scan_state"] == "READ_ONLY"
    assert data["file_count"] == 2
    assert validate_repo_map(data) == []

    out_file = tmp_path / "repo-map.json"
    out_file.write_text(dumps_repo_map(data), encoding="utf-8")
    assert validate_repo_map_file(out_file) == []


def test_repo_map_ignores_noisy_directories(tmp_path: Path) -> None:
    repo = tmp_path / "noisy_repo"
    repo.mkdir()
    (repo / "README.md").write_text("docs", encoding="utf-8")

    for noisy in [".git", ".builder", "node_modules", "__pycache__", ".venv", "dist"]:
        d = repo / noisy
        d.mkdir()
        (d / "ignored.txt").write_text("noise", encoding="utf-8")

    data = create_repo_map(repo, target_name="generic")
    assert data["file_count"] == 1
    assert data["files"][0]["path"] == "README.md"


def test_repo_map_classifies_roles(tmp_path: Path) -> None:
    repo = tmp_path / "classified_repo"
    repo.mkdir()

    (repo / "README.md").write_text("docs", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("x = 1\n", encoding="utf-8")

    artifacts_dir = repo / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "out.json").write_text("{}", encoding="utf-8")

    (repo / "image.png").write_text("binary", encoding="utf-8")

    data = create_repo_map(repo, target_name="generic")
    roles_by_path = {f["path"]: f["role"] for f in data["files"]}

    assert roles_by_path["README.md"] == "docs"
    assert roles_by_path["pyproject.toml"] == "config"
    assert roles_by_path["tests/test_app.py"] == "test"
    assert roles_by_path["src/app.py"] == "source"
    assert roles_by_path["artifacts/out.json"] == "artifact"
    assert roles_by_path["image.png"] == "unknown"

    counts = data["summary_counts"]
    assert counts["docs_files"] == 1
    assert counts["config_files"] == 1
    assert counts["test_files"] == 1
    assert counts["source_files"] == 1
    assert counts["artifact_files"] == 1
    assert counts["unknown_files"] == 1


def test_repo_map_hash_changes_if_file_contents_change(tmp_path: Path) -> None:
    repo = tmp_path / "hash_repo"
    repo.mkdir()
    file_path = repo / "code.py"

    file_path.write_text("v1\n", encoding="utf-8")
    map1 = create_repo_map(repo, target_name="generic")
    sha1 = map1["files"][0]["sha256"]

    file_path.write_text("v2\n", encoding="utf-8")
    map2 = create_repo_map(repo, target_name="generic")
    sha2 = map2["files"][0]["sha256"]

    assert sha1 != sha2


def test_repo_map_governance_and_invalid_inputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "f.txt").write_text("ok", encoding="utf-8")

    with pytest.raises(ValueError, match="target_name must be one of"):
        create_repo_map(repo, target_name="invalid_target")

    data = create_repo_map(repo, target_name="generic")
    gov = data["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["subprocess_backed_authority"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["target_repo_writes"] == "DISABLED"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"


def test_repo_map_ignores_symlinks(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("secret outside data", encoding="utf-8")

    link = repo / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlinks not supported on this platform/volume")

    data = create_repo_map(repo, target_name="generic")
    paths = [f["path"] for f in data["files"]]
    assert "link.txt" not in paths
