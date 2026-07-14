"""W.4 pure graph_runtime pattern mastery proof."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.verification_execution_plan import TARGET_CODE_EXECUTING_PROFILES
from builder_ii.verification_execution_runner import SUPPORTED_COMMAND_PROFILES
from builder_ii.wrp.graph_runtime import SUPPORTED_PATTERNS
from builder_ii.wrp.pattern_proof import prove_all_patterns

runner = CliRunner()


def test_prove_all_patterns_ok() -> None:
    report = prove_all_patterns()
    assert report["ok"] is True
    assert report["grants_authority"] is False
    assert report["s2_live"] is False
    assert report["gateway_handler"] is False
    assert report["s3_enabled"] is False
    assert report["executes_model"] is False
    assert {r["pattern"] for r in report["patterns"]} == set(SUPPORTED_PATTERNS)
    assert all(r["ok"] for r in report["patterns"])
    assert all(isinstance(r["wall_ms"], (int, float)) for r in report["patterns"])
    assert isinstance(report.get("digest"), str) and len(report["digest"]) == 64


def test_cli_patterns_prove(tmp_path: Path) -> None:
    out = tmp_path / "proof.json"
    r = runner.invoke(wrp_app, ["patterns-prove", "-o", str(out)])
    assert r.exit_code == 0, r.output
    assert out.is_file()


def test_v3_profiles_in_supported_not_target_code() -> None:
    for name in (
        "wrp_doctor_backends",
        "wrp_patterns_prove",
        "wrp_fleet_fidelity",
        "semantic_doctor",
        "semantic_map",
    ):
        assert name in SUPPORTED_COMMAND_PROFILES
        assert name not in TARGET_CODE_EXECUTING_PROFILES
        prof = SUPPORTED_COMMAND_PROFILES[name]
        assert prof.builder_self is True
        assert "verification_runner_entrypoints" in " ".join(prof.argv)
