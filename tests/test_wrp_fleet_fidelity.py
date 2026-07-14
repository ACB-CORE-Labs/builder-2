"""W.3 fleet allocation → live plan fidelity checks."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.wrp.allocation_optimizer import (
    allocate_fleet,
    check_fleet_plan_fidelity,
    fleet_fidelity_report,
)
from builder_ii.wrp.live_lane import build_live_run_plan

runner = CliRunner()


def test_fleet_plan_fidelity_happy_v2() -> None:
    fleet = allocate_fleet(task_tier="primary", token_budget=50.0)
    plan = build_live_run_plan(
        task="fidelity-check",
        s2_version="v2",
        gateway_mode="record",
        fleet_binding=fleet["fleet_binding"],
    )
    errors = check_fleet_plan_fidelity(fleet, plan)
    assert errors == [], errors
    report = fleet_fidelity_report(fleet, plan)
    assert report["ok"] is True
    assert report["grants_authority"] is False
    assert report["s3_enabled"] is False


def test_fleet_plan_fidelity_alias_mismatch() -> None:
    fleet = allocate_fleet(task_tier="primary", token_budget=50.0)
    plan = build_live_run_plan(
        task="fidelity-bad",
        s2_version="v2",
        fleet_binding=dict(fleet["fleet_binding"]),
    )
    # Mutate plan binding
    plan = dict(plan)
    plan["fleet_binding"] = {**plan["fleet_binding"], "selected_alias": "not-a-real-alias"}
    plan.pop("digest", None)
    errors = check_fleet_plan_fidelity(fleet, plan)
    assert any("selected_alias" in e for e in errors)


def test_fleet_plan_fidelity_binds_session_routing() -> None:
    fleet = allocate_fleet(task_tier="primary", token_budget=50.0)
    plan = build_live_run_plan(
        task="fidelity-bind",
        s2_version="v1",
        fleet_binding={**fleet["fleet_binding"], "binds_session_routing": False},
    )
    errors = check_fleet_plan_fidelity(fleet, plan)
    assert any("binds_session_routing" in e for e in errors)


def test_cli_fleet_fidelity(tmp_path: Path) -> None:
    fleet = allocate_fleet(task_tier="primary", token_budget=40.0)
    plan = build_live_run_plan(
        task="cli-fid",
        s2_version="v2",
        fleet_binding=fleet["fleet_binding"],
    )
    import json

    ap = tmp_path / "alloc.json"
    pp = tmp_path / "plan.json"
    ap.write_text(json.dumps(fleet, indent=2), encoding="utf-8")
    pp.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    out = tmp_path / "fid.json"
    r = runner.invoke(
        wrp_app,
        ["fleet-fidelity", "--allocation", str(ap), "--plan", str(pp), "-o", str(out)],
    )
    assert r.exit_code == 0, r.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is True
