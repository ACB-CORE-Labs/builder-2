from __future__ import annotations

from pathlib import Path

import pytest

from builder_ii.context_packs import (
    CONTEXT_PACK_KIND,
    create_architecture_aware_context_pack,
    create_context_pack,
    dumps_context_pack,
    validate_context_pack,
    validate_context_pack_file,
)
from builder_ii.repo_map import create_repo_map


def test_context_pack_selects_in_stable_order(tmp_path: Path) -> None:
    repo = tmp_path / "ordered_repo"
    repo.mkdir()

    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("x = 1\n", encoding="utf-8")

    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_x(): pass\n", encoding="utf-8")

    (repo / "README.md").write_text("docs\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    repo_map = create_repo_map(repo, target_name="generic")
    pack = create_context_pack(repo_map, target_name="generic", task="test selection")

    assert pack["kind"] == CONTEXT_PACK_KIND
    assert validate_context_pack(pack) == []

    selected_paths = [f["path"] for f in pack["selected_files"]]
    assert selected_paths == [
        "README.md",
        "pyproject.toml",
        "tests/test_app.py",
        "src/app.py",
    ]

    out_file = tmp_path / "context-pack.json"
    out_file.write_text(dumps_context_pack(pack), encoding="utf-8")
    assert validate_context_pack_file(out_file) == []


def test_context_pack_refuses_invalid_repo_map() -> None:
    bad_map = {"kind": "wrong_kind", "schema_version": 1}
    with pytest.raises(ValueError, match="invalid repo map"):
        create_context_pack(bad_map, target_name="generic")  # type: ignore[arg-type]


def test_context_pack_omitted_file_count(tmp_path: Path) -> None:
    repo = tmp_path / "many_repo"
    repo.mkdir()
    for i in range(10):
        (repo / f"file_{i}.py").write_text("# code\n", encoding="utf-8")

    repo_map = create_repo_map(repo, target_name="generic")
    pack = create_context_pack(repo_map, target_name="generic", max_entries=4)

    assert len(pack["selected_files"]) == 4
    assert pack["omitted_file_count"] == 6


def test_context_pack_boundaries_and_guidance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hi", encoding="utf-8")
    repo_map = create_repo_map(repo, target_name="generic")
    pack = create_context_pack(repo_map, target_name="generic")

    guidance = pack["operator_guidance"]
    assert "inspect" in guidance["inspection"].lower()
    assert "verification" in guidance["manual_verification"].lower()
    assert "proof of correctness" in guidance["caution"].lower()

    boundary = pack["verification_boundary"]
    assert "read-only" in boundary["read_only"].lower()
    assert "prove" in boundary["proof"].lower()
    assert "evidence" in boundary["evidence_conversion"].lower()

    gov = pack["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["subprocess_backed_authority"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["target_repo_writes"] == "DISABLED"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"


def test_architecture_aware_context_pack_merges_code_vault_metadata(tmp_path: Path) -> None:
    pytest.importorskip("builder_ii.code_vault")
    from builder_ii.code_vault.hierarchy import create_hierarchical_frame
    from builder_ii.code_vault.repo_map_adapter import hierarchical_input_from_repo_map
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    (repo / "README.md").write_text("# docs\n", encoding="utf-8")

    repo_map = create_repo_map(repo, target_name="generic")
    frame_input = hierarchical_input_from_repo_map(repo_map, repo_root=repo, enrich_symbols=True)
    frame = create_hierarchical_frame(frame_input, target_name="generic")

    pack = create_architecture_aware_context_pack(
        repo_map,
        target_name="generic",
        hierarchical_frame=frame,
        task="architecture merge",
    )

    assert validate_context_pack(pack) == []
    enrichment = pack["code_vault_enrichment"]
    assert len(enrichment["frame_digest"]) == 64
    assert enrichment["epistemic_status"] == "speculative"
    assert enrichment["architecture_summary"]["node_count"] >= 1
    assert "projection" in enrichment
    assert enrichment["projection"]["kind"] == "builder_ii.code_vault.context_projection"
