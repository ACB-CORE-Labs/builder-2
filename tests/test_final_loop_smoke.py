"""V.6 final operating loop smoke (validation_only)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from builder_ii.cli.platform_status_cli import platform_app
from builder_ii.core.final_loop_smoke import (
    run_final_loop_smoke,
    validate_final_loop_smoke_report,
)
from builder_ii.lifecycle.candidate.promotion_decision_records import validate_promotion_decision_record


def _settings(tmp_path: Path) -> SimpleNamespace:
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("# core\n", encoding="utf-8")
    (core / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (core / "docs").mkdir()
    (core / "docs" / "x.md").write_text("x\n", encoding="utf-8")
    (builder / "README.md").write_text("# builder\n", encoding="utf-8")
    (builder / "builder_ii").mkdir()
    (builder / "builder_ii" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (builder / "docs").mkdir()
    return SimpleNamespace(target_repo=core, project_root=builder)


def test_final_loop_smoke_builder_and_core(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    out = tmp_path / "smoke-out"
    report = run_final_loop_smoke(
        settings=settings,  # type: ignore[arg-type]
        targets=("builder", "core"),
        output_dir=out,
        max_repo_files=20,
    )
    assert report["kind"] == "builder_ii.final_loop_smoke_report"
    assert report["ok"] is True
    assert report["s3_enabled"] is False
    assert report["s4_promoted"] is False
    assert report["executes_model"] is False
    assert report["executes_shell"] is False
    assert report["mutates_target_repo"] is False
    assert report["workbench_coupling"] == "NONE"
    assert report["smoke_only"] is True
    assert validate_final_loop_smoke_report(report) == []
    assert (out / "final-loop-smoke-report.json").is_file()
    for target in ("builder", "core"):
        assert (out / target / "target-profile.json").is_file()
        assert (out / target / "repo-map.json").is_file()
        assert (out / target / "context-pack.json").is_file()
        assert (out / target / "agent-profile.json").is_file()
        assert (out / target / "quality-gate.json").is_file()
        assert (out / target / "handoff-note.json").is_file()


def test_final_loop_smoke_core_missing_repo_honest(tmp_path: Path) -> None:
    builder = tmp_path / "builder"
    builder.mkdir()
    (builder / "README.md").write_text("b\n", encoding="utf-8")
    (builder / "builder_ii").mkdir()
    settings = SimpleNamespace(target_repo=tmp_path / "missing-core", project_root=builder)
    out = tmp_path / "smoke-missing"
    report = run_final_loop_smoke(
        settings=settings,  # type: ignore[arg-type]
        targets=("core",),
        output_dir=out,
    )
    assert report["ok"] is False
    core_row = report["targets"][0]
    assert core_row["repo_exists"] is False
    assert any(not s["ok"] for s in core_row["steps"])
    assert report["s4_promoted"] is False
    assert report["workbench_coupling"] == "NONE"


def test_cli_final_loop_smoke(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    # The CLI does `from builder_ii.core.final_loop_smoke import run_final_loop_smoke` at call time.
    # Force the smoke runner to use tmp fixtures regardless of ambient load_settings/target_repo.
    real_run = run_final_loop_smoke

    def _run_with_fixture_settings(**kwargs):
        return real_run(
            settings=settings,  # type: ignore[arg-type]
            targets=kwargs["targets"],
            output_dir=kwargs["output_dir"],
            task=kwargs.get("task", "V.6 final loop smoke (validation_only)"),
        )

    monkeypatch.setattr(
        "builder_ii.final_loop_smoke.run_final_loop_smoke",
        _run_with_fixture_settings,
    )
    out = tmp_path / "cli-out"
    r = CliRunner().invoke(
        platform_app,
        ["final-loop-smoke", "--targets", "builder,core", "-o", str(out)],
    )
    assert r.exit_code == 0, r.output
    data = json_lib.loads((out / "final-loop-smoke-report.json").read_text(encoding="utf-8"))
    assert data["ok"] is True


def test_human_s4_decisions_on_disk() -> None:
    """Pins the HUMAN S4 decisions recorded alongside this PR."""
    root = Path("planning/evidence")
    expected = {
        "opa": (True, "approved"),
        "modernbert_embed": (True, "approved"),
        "langgraph": (False, "blocked"),
        "vllm_research": (False, "blocked"),
    }
    for bid, (approved, decision) in expected.items():
        path = root / f"wrp_s4_{bid}_decision.json"
        data = json_lib.loads(path.read_text(encoding="utf-8"))
        assert validate_promotion_decision_record(data) == []
        assert data["decided_by"] == "HUMAN"
        assert data["decision"] == decision
        assert data["approved"] is approved
        assert data.get("s4_promoted") is False
        assert data.get("s3_enabled") is False
