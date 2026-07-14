"""V.3 verification runner entrypoints for validation_only WRP/semantic profiles."""

from __future__ import annotations

import json
from pathlib import Path

from builder_ii.verification_execution_plan import (
    B1_1_SUPPORTED_VERIFICATION_PROFILE,
    _default_allowed_command_profiles,
)
from builder_ii.verification_runner_entrypoints import main as entry_main
from builder_ii.wrp.allocation_optimizer import allocate_fleet
from builder_ii.wrp.live_lane import build_live_run_plan


def test_entrypoints_wrp_doctor_and_patterns(capsys) -> None:
    assert entry_main(["wrp-doctor-backends"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data.get("ok") is True
    assert data.get("s4_promoted") is False

    assert entry_main(["wrp-patterns-prove"]) == 0
    out2 = capsys.readouterr().out
    proof = json.loads(out2)
    assert proof.get("ok") is True
    assert proof.get("s2_live") is False


def test_entrypoints_semantic(capsys) -> None:
    assert entry_main(["semantic-doctor"]) == 0
    assert json.loads(capsys.readouterr().out).get("ok") is True
    assert entry_main(["semantic-map"]) == 0
    mapped = json.loads(capsys.readouterr().out)
    assert mapped.get("kind") == "builder_ii.semantic_map"
    assert mapped.get("mutates_target_repo") is False


def test_entrypoints_fleet_fidelity_pinned(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    fleet = allocate_fleet(task_tier="primary", token_budget=40.0)
    plan = build_live_run_plan(
        task="v3-fid",
        s2_version="v2",
        fleet_binding=fleet["fleet_binding"],
    )
    base = tmp_path / ".builder" / "verification" / "fleet-fidelity"
    base.mkdir(parents=True)
    (base / "allocation.json").write_text(json.dumps(fleet), encoding="utf-8")
    (base / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    assert entry_main(["wrp-fleet-fidelity"]) == 0
    assert json.loads(capsys.readouterr().out).get("ok") is True


def test_builder_full_plan_lists_v3_profiles() -> None:
    profiles = {p["profile"] for p in _default_allowed_command_profiles(B1_1_SUPPORTED_VERIFICATION_PROFILE)}
    for name in (
        "wrp_doctor_backends",
        "wrp_patterns_prove",
        "wrp_fleet_fidelity",
        "semantic_doctor",
        "semantic_map",
    ):
        assert name in profiles


def test_unknown_entrypoint() -> None:
    assert entry_main(["not-a-real-profile"]) == 2
