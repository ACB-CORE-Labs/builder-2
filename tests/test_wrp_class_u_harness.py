"""P5 — Class U harness measured utility for S2 v2 gateway path."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.validation.performance_measurements import validate_performance_measurement_record
from builder_ii.wrp.class_u_harness import run_class_u_harness, validate_class_u_report
from builder_ii.wrp.evaluator import validate_proof_record
from builder_ii.wrp.spaces import DEFAULT_PHI

runner = CliRunner()


def test_class_u_harness_produces_measured_report_and_proof_u() -> None:
    phi_snapshot = dict(DEFAULT_PHI)
    result = run_class_u_harness(target="builder", iterations=1)
    report = result["report"]
    proof = result["proof"]
    assert validate_class_u_report(report) == []
    assert validate_proof_record(proof) == []
    assert proof["proof_class"] == "U"
    assert proof["held"] is True
    assert result["utility_ok"] is True
    summary = report["summary"]
    assert summary["scenarios_passed"] == summary["scenarios_total"]
    assert summary["record_wall_ms_median"] >= 0
    assert summary["stub_wall_ms_median"] >= 0
    assert summary["peak_rss_mb"] > 0
    assert summary["phi_intact"] is True
    assert report["cloud_provider_invoke"] is False
    assert report["executes_shell"] is False
    assert report["s3_enabled"] is False
    assert report["grants_authority"] is False
    # Axes present with numbers (adaptivity measured via P4 receipt epochs)
    axes = report["axes"]
    assert axes["latency_ms_record_median"] == summary["record_wall_ms_median"]
    assert axes["safety"] == 1.0
    assert isinstance(axes["adaptivity"], dict)
    assert axes["adaptivity"]["relative_reduction"] >= 0.0
    assert axes["adaptivity"]["applies_phi"] is False
    assert summary["adaptivity_meets_w4"] is True
    # Measurements validate
    assert len(result["measurements"]) >= 4
    for m in result["measurements"]:
        assert validate_performance_measurement_record(m) == []
    # DEFAULT_PHI never mutated
    assert dict(DEFAULT_PHI) == phi_snapshot


def test_class_u_scenarios_include_safety() -> None:
    result = run_class_u_harness(target="builder", iterations=1)
    ids = {s["scenario_id"] for s in result["report"]["scenarios"]}
    assert "s2v2_record_gateways" in ids
    assert "s2v2_stub_tool_echo" in ids
    assert "production_shaped_multi_agent" in ids
    assert "s2v1_refuses_gateway_flags" in ids
    assert "msda_shell_denied" in ids
    for s in result["report"]["scenarios"]:
        assert s["ok"] is True


def test_cli_benchmark_class_u(tmp_path: Path) -> None:
    report = tmp_path / "u.json"
    proof = tmp_path / "proof.json"
    meas = tmp_path / "meas.json"
    r = runner.invoke(
        wrp_app,
        [
            "benchmark",
            "--class",
            "u",
            "--target",
            "builder",
            "-o",
            str(report),
            "--proof-out",
            str(proof),
            "--measurements-out",
            str(meas),
        ],
    )
    assert r.exit_code == 0, r.output
    assert report.is_file() and proof.is_file() and meas.is_file()
    r2 = runner.invoke(wrp_app, ["validate", str(report)])
    assert r2.exit_code == 0, r2.output
