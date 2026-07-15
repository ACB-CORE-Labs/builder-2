"""V.1 semantic/structural RO doctor|map|preview."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.semantic_cli import semantic_app
from builder_ii.semantic_readonly import (
    doctor_semantic,
    map_semantic,
    preview_semantic,
    validate_semantic_doctor,
    validate_semantic_map,
    validate_semantic_preview,
)

runner = CliRunner()


def test_doctor_ok_on_this_repo() -> None:
    report = doctor_semantic(repo_path=Path.cwd())
    assert report["kind"] == "builder_ii.semantic_doctor_report"
    assert report["grants_authority"] is False
    assert report["mutates_target_repo"] is False
    assert report["ok"] is True
    assert validate_semantic_doctor(report) == []


def test_map_and_preview_readonly(tmp_path: Path) -> None:
    """Use a fixture tree so hit_count is not dependent on repo_map sampling order in CI."""
    repo = tmp_path / "repo"
    (repo / "builder_ii").mkdir(parents=True)
    (repo / "builder_ii" / "sample.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")

    mapped = map_semantic(repo, target_name="generic", max_files=50)
    assert mapped["kind"] == "builder_ii.semantic_map"
    assert mapped["file_count"] >= 1
    assert mapped["mutates_target_repo"] is False
    assert validate_semantic_map(mapped) == []

    prev = preview_semantic(repo, query="builder_ii", target_name="generic", max_files=50)
    assert prev["kind"] == "builder_ii.semantic_preview"
    assert prev["invokes_serena_rewrite"] is False
    assert prev["invokes_ast_grep_apply"] is False
    assert prev["hit_count"] >= 1
    assert validate_semantic_preview(prev) == []


def test_cli_doctor_map_preview(tmp_path: Path) -> None:
    d = tmp_path / "doc.json"
    r = runner.invoke(semantic_app, ["doctor", "--repo", str(Path.cwd()), "-o", str(d)])
    assert r.exit_code == 0, r.output

    m = tmp_path / "map.json"
    r = runner.invoke(
        semantic_app,
        ["map", "--repo", str(Path.cwd()), "--max-files", "30", "-o", str(m)],
    )
    assert r.exit_code == 0, r.output
    assert runner.invoke(semantic_app, ["validate", str(m)]).exit_code == 0

    p = tmp_path / "prev.json"
    r = runner.invoke(
        semantic_app,
        ["preview", "--query", "wrp", "--repo", str(Path.cwd()), "-o", str(p)],
    )
    assert r.exit_code == 0, r.output
