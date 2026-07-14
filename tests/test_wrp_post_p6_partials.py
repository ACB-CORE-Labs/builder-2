"""Post-P6 PARTIAL closes: adaptivity, handoff measure, fleet annotation, agent factory, MSDA status."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.wrp.agent_factory import plan_agent_lifecycle, validate_agent_factory_plan
from builder_ii.wrp.allocation_optimizer import allocate_fleet
from builder_ii.wrp.class_u_harness import run_class_u_harness
from builder_ii.wrp.collaboration_planner import (
    REQUIRED_HANDOFF_KEYS,
    complete_handoff_state,
    measure_handoff_overhead,
    validate_handoff_state,
)
from builder_ii.wrp.live_lane import build_live_run_approval, build_live_run_plan, run_approved
from builder_ii.wrp.msda_preflight import msda_preflight_status
from builder_ii.wrp.spaces import DEFAULT_PHI, AgentPoint

runner = CliRunner()


def test_class_u_adaptivity_axis_from_receipt_epochs() -> None:
    phi_snap = dict(DEFAULT_PHI)
    result = run_class_u_harness(target="builder", iterations=1)
    axes = result["report"]["axes"]
    adapt = axes["adaptivity"]
    assert isinstance(adapt, dict)
    assert adapt["relative_reduction"] >= 0.0
    assert adapt["meets_w4_threshold"] is True
    assert adapt["applies_phi"] is False
    assert adapt["source"] == "real_receipts"
    assert result["report"]["summary"]["adaptivity_meets_w4"] is True
    assert result["report"]["s3_enabled"] is False
    assert dict(DEFAULT_PHI) == phi_snap
    # Measurement row present
    names = {m["metric"]["name"] for m in result["measurements"]}
    assert "class_u_adaptivity_relative_reduction" in names


def test_measure_handoff_overhead_under_50ms() -> None:
    report = measure_handoff_overhead(iterations=15, threshold_ms=50.0)
    assert report["ok"] is True
    assert report["zero_loss"] is True
    assert report["meets_threshold"] is True
    assert report["median_ms"] < 50.0
    assert report["grants_authority"] is False
    assert report["scope"] == "local_pure_python"
    assert set(report["required_keys"]) == set(REQUIRED_HANDOFF_KEYS)


def test_complete_handoff_state_zero_loss() -> None:
    state = complete_handoff_state(task="t")
    assert validate_handoff_state(state) == []


def test_fleet_binding_annotates_model_gateway_on_plan() -> None:
    fleet = allocate_fleet(task_tier="primary", token_budget=50.0)
    binding = fleet["fleet_binding"]
    alias = binding["selected_alias"]
    plan = build_live_run_plan(
        task="fleet-annotate",
        s2_version="v2",
        gateway_mode="record",
        fleet_binding=binding,
        wrp_binding={"tier": "primary", "classification_digest": "a" * 64},
    )
    model_specs = [
        s for s in plan["node_specs"].values() if s.get("node_type") == "model_gateway"
    ]
    assert model_specs
    payload = model_specs[0]["payload"]
    assert payload.get("fleet_selected_alias") == alias
    assert payload.get("model_id") == f"record:{alias}"
    assert payload.get("fleet_binding_annotation_only") is True
    # Execute still local / no cloud
    approval = build_live_run_approval(plan=plan, approved_by="test")
    receipt = run_approved(plan=plan, approval=approval)
    assert receipt["status"] == "success"
    assert receipt["cloud_provider_invoke"] is False
    assert receipt["fleet_binding"]["selected_alias"] == alias


def test_agent_factory_plan_only_no_spawn() -> None:
    agents = [
        AgentPoint(
            role="maker_structural",
            reasoning_coverage=0.9,
            tool_coverage=0.8,
            model_family="plan-only",
            platform="maker",
        )
    ]
    plan = plan_agent_lifecycle(agents=agents, action="register_plan")
    assert plan["spawn_permitted"] is False
    assert plan["runtime_binding"] == "UNBOUND"
    assert plan["grants_authority"] is False
    assert validate_agent_factory_plan(plan) == []


def test_msda_preflight_status_default_off(monkeypatch) -> None:
    monkeypatch.delenv("BUILDER_II_WRP_MSDA_PREFLIGHT", raising=False)
    status = msda_preflight_status()
    assert status["global_env_enabled"] is False
    assert status["default_off"] is True
    assert status["live_lane_forced"] is True
    assert status["grants_authority"] is False
    assert status["product_default_on"] is False


def test_cli_handoff_agent_msda(tmp_path: Path) -> None:
    h = tmp_path / "h.json"
    r = runner.invoke(wrp_app, ["handoff-measure", "--iterations", "10", "-o", str(h)])
    assert r.exit_code == 0, r.output
    assert h.is_file()

    a = tmp_path / "agent.json"
    r = runner.invoke(
        wrp_app,
        ["plan-agent-lifecycle", "--roles", "maker_unit,governor_architecture", "-o", str(a)],
    )
    assert r.exit_code == 0, r.output
    assert runner.invoke(wrp_app, ["validate", str(a)]).exit_code == 0

    m = tmp_path / "msda.json"
    r = runner.invoke(wrp_app, ["msda-status", "-o", str(m)])
    assert r.exit_code == 0, r.output
    assert m.is_file()
