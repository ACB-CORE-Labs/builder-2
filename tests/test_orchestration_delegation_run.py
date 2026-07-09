"""Ladder 4 PR-4 — seal + runner enforcement + honesty fix.

Proves the trunk semantics: the approval seals an obligation envelope (lane policy + budget +
allowed kinds + two-key native ack); run-approved enforces every mint against that envelope
fail-closed (R4 grants-not-loans), passes each subagent its OWN obligation task, and classifies
each discharge by evidence (CONTRACT_SATISFIED / DISCHARGED_UNVERIFIED / CONTRACT_VIOLATED /
BLOCKED). Also pins the R3 honesty fix (no fabricated subagent success).
"""

from __future__ import annotations

import copy
import json as json_lib
from pathlib import Path
from unittest.mock import patch

import pytest
from builder_ii.deepagents_cli import deepagents_app
from test_deepagents_execution import _work_plan_fixture
from test_optional_deepagents_readiness import _install_fake_deepagents
from typer.testing import CliRunner

from builder_ii.config import load_settings
from builder_ii.deepagents_bridge import DeepAgentsAvailability
from builder_ii.deepagents_execution import (
    DISCHARGE_BLOCKED,
    DISCHARGE_CONTRACT_SATISFIED,
    DISCHARGE_CONTRACT_VIOLATED,
    DISCHARGE_UNVERIFIED,
    OPTIONAL_DEEPAGENTS_BACKEND,
    PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
    classify_discharge,
    create_deepagents_backend_readiness_gate,
    create_deepagents_execution_approval,
    create_deepagents_execution_candidate,
    is_ladder4_seal,
    run_deepagents_approved_candidate,
    validate_deepagents_execution_approval,
    validate_deepagents_execution_approval_against_candidate,
    validate_deepagents_execution_candidate,
)
from builder_ii.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.deepagents_runtime import DeepAgentsRuntimeHarness
from builder_ii.deepagents_work_artifacts import create_deepagents_work_plan
from builder_ii.orchestration_lane_policy import create_orchestration_lane_policy_artifact
from builder_ii.orchestration_obligation import create_orchestration_obligation
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture

runner = CliRunner()

ROOT_BUDGET = {"max_subagents": 8, "max_events": 256, "max_output_bytes": 65536, "max_human_gates": 2}
SMALL = {"max_subagents": 1, "max_events": 10, "max_output_bytes": 1024, "max_human_gates": 0}
TOO_BIG = {"max_subagents": 99, "max_events": 10, "max_output_bytes": 1024, "max_human_gates": 0}


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _ladder4_candidate(tmp_path: Path, *, allowed_subagents=None, kinds=None, backend_mode="protocol_fake"):
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    policy = create_orchestration_lane_policy_artifact()
    policy_path = _write(tmp_path / "lane-policy.json", policy)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        backend_mode=backend_mode,
        allowed_subagents=allowed_subagents or ["repo_mapper", "code_reviewer"],
        lane_policy=policy,
        lane_policy_path=policy_path,
        root_budget=ROOT_BUDGET,
        allowed_obligation_kinds=kinds or [{"kind": "planning_step", "max_count": 3}],
        refused_lanes=["goose"],
    )
    return candidate, policy, policy_path, work_plan, work_plan_path


def _seal(tmp_path: Path, candidate, *, native_ack=False):
    candidate_path = _write(tmp_path / "candidate.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="Jane Operator",
        approval_reason="Seal the obligation envelope.",
        native_backend_acknowledged=native_ack,
    )
    approval_path = _write(tmp_path / "approval.json", approval)
    return approval, candidate_path, approval_path


def _obligation(tmp_path, idx, *, seal_digest, lpd, expected_kind, evidence, subagent, budget,
                kind="planning_step", lane="deepagents"):
    obl = create_orchestration_obligation(
        lane=lane,
        obligation_kind=kind,
        task=f"obligation number {idx} unique task",
        output_contract_expected_kind=expected_kind,
        output_contract_required_evidence_kinds=evidence,
        briefing_bytes=64,
        budget_partition=budget,
        parent_ref={"seal_digest": seal_digest},
        lane_policy_digest=lpd,
        subagent_profile=subagent,
    )
    return _write(tmp_path / f"obl-{idx}.json", obl), obl


# ---------------------------------------------------------------------------
# (a) Candidate + approval schema bump (N/N-1)
# ---------------------------------------------------------------------------


def test_ladder4_candidate_and_seal_validate(tmp_path: Path) -> None:
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    assert validate_deepagents_execution_candidate(candidate) == []
    assert candidate["obligation_envelope"]["lane_policy_digest"] == policy["lane_policy_digest"]
    approval, _cp, _ap = _seal(tmp_path, candidate)
    assert is_ladder4_seal(approval)
    assert validate_deepagents_execution_approval(approval) == []
    assert validate_deepagents_execution_approval_against_candidate(approval, candidate) == []


def test_legacy_candidate_and_approval_still_valid(tmp_path: Path) -> None:
    """N/N-1: a candidate/approval without the envelope fields still validates unchanged."""
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan, work_plan_path=work_plan_path, output_root=tmp_path / "runs"
    )
    assert validate_deepagents_execution_candidate(candidate) == []
    assert "obligation_envelope" not in candidate
    approval = create_deepagents_execution_approval(
        candidate=candidate, candidate_path=None, approval_actor="Op", approval_reason="legacy"
    )
    assert not is_ladder4_seal(approval)
    assert validate_deepagents_execution_approval_against_candidate(approval, candidate) == []


def test_half_declared_candidate_envelope_is_invalid(tmp_path: Path) -> None:
    candidate, _p, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    broken = copy.deepcopy(candidate)
    broken.pop("obligation_envelope")  # keep lane_policy_ref, drop envelope
    errors = validate_deepagents_execution_candidate(broken)
    assert any("present together or both absent" in e for e in errors)


def test_seal_lane_policy_digest_tamper_flagged(tmp_path: Path) -> None:
    candidate, _p, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    approval, _cp, _ap = _seal(tmp_path, candidate)
    tampered = copy.deepcopy(approval)
    tampered["lane_policy_digest"] = "0" * 64
    errors = validate_deepagents_execution_approval_against_candidate(tampered, candidate)
    assert any("lane_policy_digest" in e for e in errors)


def test_legacy_approval_for_ladder4_candidate_mismatch(tmp_path: Path) -> None:
    candidate, _p, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    legacy_like = create_deepagents_execution_approval(
        candidate=create_deepagents_execution_candidate(
            work_plan=_wp, work_plan_path=_wpp, output_root=tmp_path / "runs"
        ),
        candidate_path=None,
        approval_actor="Op",
        approval_reason="legacy",
    )
    errors = validate_deepagents_execution_approval_against_candidate(legacy_like, candidate)
    assert any("sealed by a Ladder 4 approval" in e for e in errors)


# ---------------------------------------------------------------------------
# Two-key native acknowledgement
# ---------------------------------------------------------------------------


def _optional_ladder4_candidate(monkeypatch, tmp_path: Path):
    _install_fake_deepagents(monkeypatch)
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    policy = create_orchestration_lane_policy_artifact()
    policy_path = _write(tmp_path / "lane-policy.json", policy)
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)
    gate_path = _write(tmp_path / "gate.json", gate)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        backend_mode=OPTIONAL_DEEPAGENTS_BACKEND,
        backend_readiness_gate=gate,
        backend_readiness_gate_path=gate_path,
        allowed_subagents=["repo_mapper"],
        lane_policy=policy,
        lane_policy_path=policy_path,
        root_budget=ROOT_BUDGET,
        allowed_obligation_kinds=[{"kind": "planning_step", "max_count": 2}],
    )
    return candidate


def test_optional_candidate_requires_native_ack_to_seal(monkeypatch, tmp_path: Path) -> None:
    candidate = _optional_ladder4_candidate(monkeypatch, tmp_path)
    assert validate_deepagents_execution_candidate(candidate) == []
    candidate_path = _write(tmp_path / "candidate.json", candidate)
    with pytest.raises(ValueError, match="native_backend_acknowledged must be true"):
        create_deepagents_execution_approval(
            candidate=candidate, candidate_path=candidate_path, approval_actor="Op", approval_reason="r"
        )
    # With the second key the seal is valid.
    approval = create_deepagents_execution_approval(
        candidate=candidate, candidate_path=candidate_path,
        approval_actor="Op", approval_reason="r", native_backend_acknowledged=True,
    )
    assert approval["native_backend_acknowledged"] is True
    assert validate_deepagents_execution_approval_against_candidate(approval, candidate) == []


def test_cross_validator_flags_optional_without_ack(tmp_path: Path) -> None:
    candidate, _p, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    approval, _cp, _ap = _seal(tmp_path, candidate)  # protocol_fake, ack False
    optional_candidate = copy.deepcopy(candidate)
    optional_candidate["backend_mode"] = OPTIONAL_DEEPAGENTS_BACKEND
    errors = validate_deepagents_execution_approval_against_candidate(approval, optional_candidate)
    assert any("native_backend_acknowledged must be true" in e for e in errors)


# ---------------------------------------------------------------------------
# (c) Runner enforcement + discharge classification
# ---------------------------------------------------------------------------


def _events(output_dir: Path) -> list[dict]:
    return [json_lib.loads(p.read_text()) for p in sorted((output_dir / "events").glob("*.json"))]


def test_obligation_run_classifies_all_four_states(tmp_path: Path) -> None:
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    lpd = policy["lane_policy_digest"]
    seal = approval["approval_digest"]
    obligations = [
        _obligation(tmp_path, 0, seal_digest=seal, lpd=lpd,
                    expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[],
                    subagent="repo_mapper", budget=SMALL)[0],
        _obligation(tmp_path, 1, seal_digest=seal, lpd=lpd,
                    expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
                    evidence=["verification_execution_receipt"], subagent="code_reviewer", budget=SMALL)[0],
        _obligation(tmp_path, 2, seal_digest=seal, lpd=lpd,
                    expected_kind="builder_ii.some_other_kind", evidence=[],
                    subagent="repo_mapper", budget=SMALL)[0],
        _obligation(tmp_path, 3, seal_digest=seal, lpd=lpd,
                    expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[],
                    subagent="repo_mapper", budget=TOO_BIG)[0],
    ]
    output_dir = tmp_path / "runs" / "obl"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=output_dir, obligation_paths=obligations,
    )
    assert summary["status"] == "COMPLETED"
    assert summary["discharge_tally"] == {
        DISCHARGE_CONTRACT_SATISFIED: 1,
        DISCHARGE_UNVERIFIED: 1,
        DISCHARGE_CONTRACT_VIOLATED: 1,
        DISCHARGE_BLOCKED: 1,
    }
    replay = json_lib.loads(Path(summary["replay_report_path"]).read_text())
    assert replay["valid"] is True and replay["status"] == "COMPLETED"


def test_every_obligation_event_is_stamped(tmp_path: Path) -> None:
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    obl_path, obl = _obligation(
        tmp_path, 0, seal_digest=approval["approval_digest"], lpd=policy["lane_policy_digest"],
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[], subagent="repo_mapper", budget=SMALL,
    )
    output_dir = tmp_path / "runs" / "obl"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=output_dir, obligation_paths=[obl_path],
    )
    stamped = {"obligation_minted", "subagent_scheduled", "subagent_result_recorded", "obligation_consumed"}
    seen = set()
    for event in _events(output_dir):
        if event["event_type"] in stamped:
            seen.add(event["event_type"])
            assert event["payload"]["obligation_digest"] == obl["obligation_id"]
            assert event["payload"]["briefing_digest"]
    assert seen == stamped


def test_subagent_runs_obligation_task_not_root_task(tmp_path: Path) -> None:
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    obl_path, obl = _obligation(
        tmp_path, 7, seal_digest=approval["approval_digest"], lpd=policy["lane_policy_digest"],
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[], subagent="repo_mapper", budget=SMALL,
    )
    output_dir = tmp_path / "runs" / "obl"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=output_dir, obligation_paths=[obl_path],
    )
    results = [e for e in _events(output_dir) if e["event_type"] == "subagent_result_recorded"]
    assert results and "obligation number 7 unique task" in results[0]["payload"]["summary"]
    assert candidate["task"] not in results[0]["payload"]["summary"]


def test_legacy_approval_refuses_obligations(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan, work_plan_path=work_plan_path, output_root=tmp_path / "runs",
        allowed_subagents=["repo_mapper"],
    )
    candidate_path = _write(tmp_path / "c.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate, candidate_path=candidate_path, approval_actor="Op", approval_reason="legacy"
    )
    approval_path = _write(tmp_path / "a.json", approval)
    policy = create_orchestration_lane_policy_artifact()
    obl_path, _obl = _obligation(
        tmp_path, 0, seal_digest=approval["approval_digest"], lpd=policy["lane_policy_digest"],
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[], subagent="repo_mapper", budget=SMALL,
    )
    with pytest.raises(ValueError, match="requires a Ladder 4 approval"):
        run_deepagents_approved_candidate(
            candidate_path=candidate_path, approval_path=approval_path,
            output_dir=tmp_path / "runs" / "obl", obligation_paths=[obl_path],
        )


@pytest.mark.parametrize(
    "mutate,violated",
    [
        (lambda o: o.update(subagent_profile="not_approved"), "subagent_not_approved"),
        (lambda o: o.__setitem__("lane_policy_digest", "0" * 64), "lane_policy_drift"),
    ],
)
def test_mint_refusals_carry_fixing_edit(tmp_path: Path, mutate, violated) -> None:
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(tmp_path)
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    obl = create_orchestration_obligation(
        lane="deepagents", obligation_kind="planning_step", task="t",
        output_contract_expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        briefing_bytes=8, budget_partition=SMALL,
        parent_ref={"seal_digest": approval["approval_digest"]},
        lane_policy_digest=policy["lane_policy_digest"], subagent_profile="repo_mapper",
    )
    mutate(obl)
    # Re-mint through the factory so the digest stays valid after the mutation.
    obl2 = create_orchestration_obligation(
        lane=obl["lane"], obligation_kind=obl["obligation_kind"], task=obl["task"],
        output_contract_expected_kind=obl["output_contract"]["expected_kind"],
        briefing_bytes=obl["briefing_bytes"], budget_partition=obl["budget_partition"],
        parent_ref=obl["parent_ref"], lane_policy_digest=obl["lane_policy_digest"],
        subagent_profile=obl["subagent_profile"],
    )
    obl_path = _write(tmp_path / "bad-obl.json", obl2)
    output_dir = tmp_path / "runs" / "obl"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=output_dir, obligation_paths=[obl_path],
    )
    assert summary["discharge_tally"][DISCHARGE_BLOCKED] == 1
    refusals = [e for e in _events(output_dir) if e["event_type"] == "obligation_mint_refused"]
    assert refusals and refusals[0]["payload"]["violated_rule"] == violated
    assert refusals[0]["payload"]["fixing_edit"]


def test_budget_conservation_refuses_second_child_over_root(tmp_path: Path) -> None:
    # Root grants max_subagents=8; two children of 5 each -> second exceeds remaining (grants-not-loans).
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(
        tmp_path, kinds=[{"kind": "planning_step", "max_count": 3}]
    )
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    lpd = policy["lane_policy_digest"]
    seal = approval["approval_digest"]
    big = {"max_subagents": 5, "max_events": 10, "max_output_bytes": 1024, "max_human_gates": 0}
    o0 = _obligation(tmp_path, 0, seal_digest=seal, lpd=lpd,
                     expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[],
                     subagent="repo_mapper", budget=big)[0]
    o1 = _obligation(tmp_path, 1, seal_digest=seal, lpd=lpd,
                     expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[],
                     subagent="code_reviewer", budget=big)[0]
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=tmp_path / "runs" / "obl", obligation_paths=[o0, o1],
    )
    assert summary["discharge_tally"][DISCHARGE_BLOCKED] == 1
    refusals = [e for e in _events(tmp_path / "runs" / "obl") if e["event_type"] == "obligation_mint_refused"]
    assert refusals[0]["payload"]["violated_rule"] == "budget_partition_exceeds_remaining"


def test_unauthorized_obligation_kind_blocked(tmp_path: Path) -> None:
    # Seal authorizes only planning_step; a well-formed verification obligation is outside the envelope.
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(
        tmp_path, kinds=[{"kind": "planning_step", "max_count": 2}]
    )
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    obl_path, _obl = _obligation(
        tmp_path, 0, seal_digest=approval["approval_digest"], lpd=policy["lane_policy_digest"],
        expected_kind="builder_ii.verification_execution_receipt", evidence=[],
        subagent="repo_mapper", budget=SMALL, kind="verification", lane="verify",
    )
    output_dir = tmp_path / "runs" / "obl"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=output_dir, obligation_paths=[obl_path],
    )
    assert summary["discharge_tally"][DISCHARGE_BLOCKED] == 1
    refusals = [e for e in _events(output_dir) if e["event_type"] == "obligation_mint_refused"]
    assert refusals[0]["payload"]["violated_rule"] == "obligation_kind_not_authorized"
    assert refusals[0]["payload"]["fixing_edit"]


def test_obligation_kind_count_exhausted(tmp_path: Path) -> None:
    # Seal authorizes planning_step exactly once; the second mint of that kind is refused.
    candidate, policy, _pp, _wp, _wpp = _ladder4_candidate(
        tmp_path, kinds=[{"kind": "planning_step", "max_count": 1}]
    )
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    lpd = policy["lane_policy_digest"]
    seal = approval["approval_digest"]
    o0 = _obligation(tmp_path, 0, seal_digest=seal, lpd=lpd,
                     expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[],
                     subagent="repo_mapper", budget=SMALL)[0]
    o1 = _obligation(tmp_path, 1, seal_digest=seal, lpd=lpd,
                     expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[],
                     subagent="code_reviewer", budget=SMALL)[0]
    output_dir = tmp_path / "runs" / "obl"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path, approval_path=approval_path,
        output_dir=output_dir, obligation_paths=[o0, o1],
    )
    assert summary["discharge_tally"][DISCHARGE_CONTRACT_SATISFIED] == 1
    assert summary["discharge_tally"][DISCHARGE_BLOCKED] == 1
    refusals = [e for e in _events(output_dir) if e["event_type"] == "obligation_mint_refused"]
    assert refusals[0]["payload"]["violated_rule"] == "obligation_kind_count_exhausted"


def test_status_why_records_promoted_to_validation_only_with_live_cli(tmp_path: Path) -> None:
    """PR-5 landed the status/why CLI, so their command-authority records are promoted out of the
    spec_only placeholder to validation_only and the commands are registered on the app. The
    registry must match code: no residual NOT-YET-IMPLEMENTED text, and the live command must
    exist for each record (no docs-ahead-of-code, and no code-ahead-of-registry)."""
    from builder_ii.orchestration_cli import orchestration_app

    from builder_ii.command_authority import STATE_VALIDATION_ONLY, get_command_record

    live = set()
    import typer

    for cmd in typer.main.get_command(orchestration_app).commands:  # type: ignore[attr-defined]
        live.add(f"builder-orchestration {cmd}")
    for name in ("builder-orchestration status", "builder-orchestration why"):
        record = get_command_record(name)
        assert record is not None
        assert record.promotion_state == STATE_VALIDATION_ONLY, f"{name} must be validation_only now its CLI landed"
        assert "NOT YET IMPLEMENTED" not in record.runtime_boundary
        assert name in live, f"{name} CLI must be registered on orchestration_app"


# ---------------------------------------------------------------------------
# classify_discharge unit
# ---------------------------------------------------------------------------


def test_classify_discharge_unit() -> None:
    ok = {"output_contract": {"expected_kind": PROPOSAL_ONLY_RESULT_CONTRACT_KIND, "required_evidence_kinds": []}}
    assert classify_discharge(ok, {}, produced_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND)["discharge_state"] == (
        DISCHARGE_CONTRACT_SATISFIED
    )
    unv = {"output_contract": {"expected_kind": PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
                               "required_evidence_kinds": ["x"]}}
    assert classify_discharge(unv, {}, produced_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND)["discharge_state"] == (
        DISCHARGE_UNVERIFIED
    )
    vio = {"output_contract": {"expected_kind": "other", "required_evidence_kinds": []}}
    assert classify_discharge(vio, {}, produced_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND)["discharge_state"] == (
        DISCHARGE_CONTRACT_VIOLATED
    )


# ---------------------------------------------------------------------------
# (a/c) CLI end-to-end
# ---------------------------------------------------------------------------


def test_cli_ladder4_seal_and_obligation_run(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    policy = create_orchestration_lane_policy_artifact()
    policy_path = _write(tmp_path / "lane-policy.json", policy)
    candidate_path = tmp_path / "candidate.json"
    approval_path = tmp_path / "approval.json"

    r1 = runner.invoke(deepagents_app, [
        "execution-candidate", "--work-plan", str(work_plan_path), "--output-root", str(tmp_path / "runs"),
        "--allowed-subagents", "repo_mapper,code_reviewer",
        "--lane-policy", str(policy_path), "--allowed-obligation-kind", "planning_step:3",
        "--refused-lane", "goose", "--output", str(candidate_path),
    ])
    assert r1.exit_code == 0, r1.output
    candidate = json_lib.loads(candidate_path.read_text())
    assert candidate["obligation_envelope"]["lane_policy_digest"] == policy["lane_policy_digest"]

    r2 = runner.invoke(deepagents_app, [
        "approve-candidate", "--candidate", str(candidate_path),
        "--approval-actor", "Op", "--approval-reason", "seal", "--output", str(approval_path),
    ])
    assert r2.exit_code == 0, r2.output
    approval = json_lib.loads(approval_path.read_text())
    assert is_ladder4_seal(approval)

    obl_path, _obl = _obligation(
        tmp_path, 0, seal_digest=approval["approval_digest"], lpd=policy["lane_policy_digest"],
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND, evidence=[], subagent="repo_mapper", budget=SMALL,
    )
    r3 = runner.invoke(deepagents_app, [
        "run-approved", "--candidate", str(candidate_path), "--approval", str(approval_path),
        "--output-dir", str(tmp_path / "runs" / "cli-obl"), "--obligation", str(obl_path),
    ])
    assert r3.exit_code == 0, r3.output
    summary = json_lib.loads(r3.output)
    assert summary["discharge_tally"][DISCHARGE_CONTRACT_SATISFIED] == 1


# ---------------------------------------------------------------------------
# (d) R3 honesty fix
# ---------------------------------------------------------------------------


def _runtime_work_plan(tmp_path: Path) -> Path:
    goal2 = build_goal2_assignment_fixture(tmp_path, task="Deepagents honesty pin")
    policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")
    policy_path = _write(tmp_path / "deepagents-policy.json", policy)
    readiness_path = _write(tmp_path / "deepagents-readiness.json", readiness)
    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Honesty pin work plan",
        orchestration_assignment_plan=goal2["artifacts"]["orchestration"],
        orchestration_assignment_dry_run=goal2["artifacts"]["dry_run"],
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        orchestration_assignment_plan_path=goal2["paths"]["orchestration"],
        orchestration_assignment_dry_run_path=goal2["paths"]["dry_run"],
        deepagents_policy_path=policy_path,
        deepagents_readiness_path=readiness_path,
        proposed_subagents=["repo_mapper", "code_reviewer"],
        expected_outputs=["subagent_assignment"],
        review_gates=["operator_review"],
    )
    return _write(tmp_path / "plan.json", work_plan)


def test_runtime_run_plan_summary_is_not_fabricated_success(tmp_path: Path) -> None:
    work_plan_path = _runtime_work_plan(tmp_path)
    available = DeepAgentsAvailability(available=True, source="/mock", detail="ok", import_status="PASS")
    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=available):
        harness = DeepAgentsRuntimeHarness(load_settings(), work_plan_path)
        harness.run(tmp_path / "envelope.json", tmp_path / "receipts")
    results = list((tmp_path / "receipts").glob("result-*.json"))
    assert results
    for path in results:
        summary = json_lib.loads(path.read_text())["summary"]
        assert "successfully completed" not in summary
        assert "no backend ran" in summary
        assert "proposal-only" in summary
