"""Unmocked end-to-end proof of the Ladder 4 governed obligation delegation lane (PR-6).

Drives the real trunk — lane policy -> candidate -> seal -> run-approved --obligation — over the
protocol_fake backend with no monkeypatched validators and no stubbed backend: every artifact is
built by the real create/validate functions in ``orchestration_lane_policy.py``,
``orchestration_obligation.py``, and ``deepagents_execution.py``, and the seal + run steps are
driven through the actual Typer CLI (``builder-deepagents approve-candidate`` /
``run-approved``) via ``CliRunner``, exactly as an operator would type them.

Per the Wave-4 decoupling rule (planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md), this scenario
asserts on ARTIFACTS and LEDGER EVENTS ONLY: discharge states, refused-mint records
(violated_rule/fixing_edit), and tamper detection via replay + chain verification. It never
asserts on ``builder-orchestration status``/``why`` CLI output — PR-5 owns those assertions in
its own test file, keeping the two PRs fully independent.

Ceremony note (documented finding, not a bug in this test): the plan's R1 nuance map describes
the seal as sealed by "one typed 4-char prefix" ceremony, mirroring ``builder-hitl approve-patch``.
Reading ``builder_ii/cli/deepagents_cli.py`` shows ``approve-candidate`` has no interactive
``typer.prompt`` — it mints the approval directly from ``--approval-actor``/``--approval-reason``/
``--native-backend-acknowledged`` flags (confirmed against the merged PR-4 test
``tests/test_orchestration_delegation_run.py::test_cli_ladder4_seal_and_obligation_run``, which
drives it the same non-interactive way). This test drives the REAL command as it actually behaves;
no ``input=`` is passed because there is nothing to confirm interactively. See the PR body for the
note to the PR-8 closure auditor.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path

from builder_ii.deepagents_cli import deepagents_app
from test_deepagents_execution import _work_plan_fixture
from typer.testing import CliRunner

from builder_ii.adapters.deepagents.deepagents_execution import (
    DISCHARGE_BLOCKED,
    DISCHARGE_CONTRACT_SATISFIED,
    DISCHARGE_CONTRACT_VIOLATED,
    DISCHARGE_UNVERIFIED,
    PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
    create_deepagents_execution_candidate,
    is_ladder4_seal,
    replay_deepagents_run,
    validate_deepagents_execution_approval_against_candidate,
    validate_deepagents_replay_report,
)
from builder_ii.core.artifact_chain_verification import verify_artifact_chain
from builder_ii.core.orchestration_lane_policy import create_orchestration_lane_policy_artifact
from builder_ii.core.orchestration_obligation import create_orchestration_obligation

runner = CliRunner()

ROOT_BUDGET = {"max_subagents": 8, "max_events": 256, "max_output_bytes": 65536, "max_human_gates": 2}
SMALL_BUDGET = {"max_subagents": 1, "max_events": 10, "max_output_bytes": 1024, "max_human_gates": 0}
# Deliberately widens past the root's max_subagents=8: a refused mint, not a policy violation
# narrative — the constitution's "widening is an invalid mint" corollary (R4).
WIDENING_BUDGET = {"max_subagents": 99, "max_events": 10, "max_output_bytes": 1024, "max_human_gates": 0}


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _events(events_dir: Path) -> list[dict]:
    return [json_lib.loads(p.read_text(encoding="utf-8")) for p in sorted(events_dir.glob("event-*.json"))]


def _build_sealed_envelope(tmp_path: Path) -> tuple[dict, Path, dict, Path, dict]:
    """Steps 1-2: lane policy -> candidate -> REAL seal via the actual CLI ceremony."""
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    policy = create_orchestration_lane_policy_artifact()
    policy_path = _write(tmp_path / "lane-policy.json", policy)

    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        allowed_subagents=["repo_mapper", "code_reviewer"],
        lane_policy=policy,
        lane_policy_path=policy_path,
        root_budget=ROOT_BUDGET,
        # 4 authorized planning_step mints: 3 accepted (satisfied/unverified/violated) + 1
        # rejected-on-budget mint that must still pass the kind/count gate to reach the budget
        # check (R4 conservation arithmetic, not a count exhaustion).
        allowed_obligation_kinds=[{"kind": "planning_step", "max_count": 4}],
        refused_lanes=["goose"],
    )
    candidate_path = _write(tmp_path / "candidate.json", candidate)

    # REAL seal: drive the actual CLI ceremony via CliRunner, unmocked. protocol_fake backend
    # never requires --native-backend-acknowledged (that two-key rule only gates
    # optional_deepagents); this candidate's backend_mode is protocol_fake, so it is omitted.
    approval_path = tmp_path / "approval.json"
    result = runner.invoke(
        deepagents_app,
        [
            "approve-candidate",
            "--candidate",
            str(candidate_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Seal the Ladder 4 obligation envelope for the delegation lane E2E.",
            "--output",
            str(approval_path),
        ],
    )
    assert result.exit_code == 0, result.output
    approval = json_lib.loads(approval_path.read_text(encoding="utf-8"))
    assert is_ladder4_seal(approval)
    assert validate_deepagents_execution_approval_against_candidate(approval, candidate) == []

    return candidate, candidate_path, approval, approval_path, policy


def _build_four_obligations(tmp_path: Path, *, approval: dict, policy: dict) -> list[Path]:
    """Mint the four obligations that exercise every discharge outcome (Law 1: no ticket, no run)."""
    seal_digest = approval["approval_digest"]
    lpd = policy["lane_policy_digest"]

    satisfied = create_orchestration_obligation(
        lane="deepagents",
        obligation_kind="planning_step",
        task="Map the repo layout for module X and propose a plan (satisfied path).",
        output_contract_expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        output_contract_required_evidence_kinds=[],
        briefing_bytes=64,
        budget_partition=SMALL_BUDGET,
        parent_ref={"seal_digest": seal_digest},
        lane_policy_digest=lpd,
        subagent_profile="repo_mapper",
    )
    unverified = create_orchestration_obligation(
        lane="deepagents",
        obligation_kind="planning_step",
        task="Draft a review plan that the operator must independently verify (unverified path).",
        output_contract_expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        # protocol_fake attaches no downstream evidence at all (Law 2) — requiring any evidence
        # kind here forces DISCHARGED_UNVERIFIED: right shape, missing belief.
        output_contract_required_evidence_kinds=["verification_execution_receipt"],
        briefing_bytes=64,
        budget_partition=SMALL_BUDGET,
        parent_ref={"seal_digest": seal_digest},
        lane_policy_digest=lpd,
        subagent_profile="code_reviewer",
    )
    violated = create_orchestration_obligation(
        lane="deepagents",
        obligation_kind="planning_step",
        task="Produce an artifact of the wrong kind on purpose (violated path).",
        # protocol_fake always produces PROPOSAL_ONLY_RESULT_CONTRACT_KIND; declaring a
        # different expected_kind here can never be satisfied -> CONTRACT_VIOLATED.
        output_contract_expected_kind="builder_ii.some_other_result_kind",
        output_contract_required_evidence_kinds=[],
        briefing_bytes=64,
        budget_partition=SMALL_BUDGET,
        parent_ref={"seal_digest": seal_digest},
        lane_policy_digest=lpd,
        subagent_profile="repo_mapper",
    )
    widened = create_orchestration_obligation(
        lane="deepagents",
        obligation_kind="planning_step",
        task="Ask for a budget the seal never granted (blocked path).",
        output_contract_expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        output_contract_required_evidence_kinds=[],
        briefing_bytes=64,
        budget_partition=WIDENING_BUDGET,
        parent_ref={"seal_digest": seal_digest},
        lane_policy_digest=lpd,
        subagent_profile="code_reviewer",
    )

    return [
        _write(tmp_path / "obl-0-satisfied.json", satisfied),
        _write(tmp_path / "obl-1-unverified.json", unverified),
        _write(tmp_path / "obl-2-violated.json", violated),
        _write(tmp_path / "obl-3-widened-blocked.json", widened),
    ]


def _run_approved(candidate_path: Path, approval_path: Path, output_dir: Path, obligation_paths: list[Path]) -> dict:
    args = [
        "run-approved",
        "--candidate",
        str(candidate_path),
        "--approval",
        str(approval_path),
        "--output-dir",
        str(output_dir),
    ]
    for obligation_path in obligation_paths:
        args.extend(["--obligation", str(obligation_path)])
    result = runner.invoke(deepagents_app, args)
    assert result.exit_code == 0, result.output
    return json_lib.loads(result.output)


def test_full_obligation_delegation_lane_unmocked_with_tamper_beat(tmp_path: Path) -> None:
    candidate, candidate_path, approval, approval_path, policy = _build_sealed_envelope(tmp_path)
    assert candidate["backend_mode"] == "protocol_fake"  # the CI-truth backend, per the object model
    obligation_paths = _build_four_obligations(tmp_path, approval=approval, policy=policy)

    # ---------------------------------------------------------------------------------------
    # Step 3: run-approved --obligation x4, over protocol_fake, driven through the real CLI.
    # This output_dir is the CLEAN, untampered evidence bundle — it is never touched after this
    # point and is exactly what PR-7's B2.0 tree-profile evaluator consumes (see PR body).
    # ---------------------------------------------------------------------------------------
    clean_output_dir = tmp_path / "runs" / "clean"
    summary = _run_approved(candidate_path, approval_path, clean_output_dir, obligation_paths)

    assert summary["status"] == "COMPLETED"
    assert summary["discharge_tally"] == {
        DISCHARGE_CONTRACT_SATISFIED: 1,
        DISCHARGE_UNVERIFIED: 1,
        DISCHARGE_CONTRACT_VIOLATED: 1,
        DISCHARGE_BLOCKED: 1,
    }

    clean_events_dir = Path(summary["events_dir"])
    events = _events(clean_events_dir)

    # The refused widening mint carries the exact violated rule and a fixing edit (zero dead ends).
    refusals = [event for event in events if event["event_type"] == "obligation_mint_refused"]
    assert len(refusals) == 1
    assert refusals[0]["payload"]["violated_rule"] == "budget_partition_exceeds_remaining"
    assert refusals[0]["payload"]["fixing_edit"]
    assert refusals[0]["payload"]["discharge_state"] == DISCHARGE_BLOCKED

    # Every obligation-delegation event is stamped with the obligation and briefing digests
    # (Law 1/Law 2 traceability): who was briefed, under which ticket.
    stamped_types = {"obligation_minted", "obligation_mint_refused", "subagent_scheduled", "obligation_consumed"}
    for event in events:
        if event["event_type"] in stamped_types:
            assert event["payload"]["obligation_digest"]
            assert event["payload"]["briefing_digest"]

    # The clean bundle's own replay report and event ledger validate natively before any tamper.
    replay_path = Path(summary["replay_report_path"])
    ledger_path = Path(summary["event_ledger_path"])
    envelope_path = Path(summary["envelope_path"])
    receipt_path = Path(summary["receipt_path"])
    clean_replay = json_lib.loads(replay_path.read_text(encoding="utf-8"))
    assert clean_replay["valid"] is True and clean_replay["status"] == "COMPLETED"

    # verify_artifact_chain's extract_references() has no registered branch for the deepagents
    # kinds (candidate/approval/envelope/receipt/ledger/replay) — it proves native schema
    # validity for each standalone artifact here, not cross-file link resolution (that is the
    # replay report's job, exercised below by the tamper beat). counts["links"] is 0 for exactly
    # that reason.
    clean_chain_report = verify_artifact_chain(
        [candidate_path, approval_path, envelope_path, receipt_path, ledger_path, replay_path]
    )
    assert clean_chain_report["valid"] is True, clean_chain_report.get("errors")
    assert clean_chain_report["counts"]["native_invalid"] == 0
    assert clean_chain_report["counts"]["links"] == 0

    # ---------------------------------------------------------------------------------------
    # Step 4: THE TAMPER BEAT.
    #
    # A second, independent run of the SAME sealed candidate/approval/obligations into a fresh
    # output_dir (never the clean one above) so the clean evidence bundle stays intact for PR-7.
    # ---------------------------------------------------------------------------------------
    tamper_output_dir = tmp_path / "runs" / "tamper"
    tamper_summary = _run_approved(candidate_path, approval_path, tamper_output_dir, obligation_paths)
    assert tamper_summary["discharge_tally"] == summary["discharge_tally"]
    tamper_events_dir = Path(tamper_summary["events_dir"])

    # Find the CONTRACT_SATISFIED obligation_consumed event and its immediate successor.
    tamper_events = sorted(tamper_events_dir.glob("event-*-obligation_consumed.json"), key=lambda p: p.name)
    satisfied_event_paths = [
        path
        for path in tamper_events
        if json_lib.loads(path.read_text(encoding="utf-8"))["payload"]["discharge_state"]
        == DISCHARGE_CONTRACT_SATISFIED
    ]
    assert len(satisfied_event_paths) == 1
    forged_path = satisfied_event_paths[0]
    forged = json_lib.loads(forged_path.read_text(encoding="utf-8"))
    forged_sequence = int(forged["sequence"])

    successor_candidates = [
        path
        for path in tamper_events_dir.glob("event-*.json")
        if json_lib.loads(path.read_text(encoding="utf-8"))["sequence"] == forged_sequence + 1
    ]
    assert len(successor_candidates) == 1
    successor_path = successor_candidates[0]

    # The frozen replay report on disk is a snapshot from finalize time; it does not
    # retroactively invalidate itself when the underlying events are later edited on disk.
    frozen_replay_before_tamper = json_lib.loads(Path(tamper_summary["replay_report_path"]).read_text(encoding="utf-8"))
    assert frozen_replay_before_tamper["valid"] is True

    # Forge the node: lie about the discharge classification, leaving its own event_digest and
    # payload_sha256 stale — exactly what an operator hand-editing a JSON file on disk would do.
    forged["payload"]["discharge_state"] = DISCHARGE_CONTRACT_VIOLATED
    forged_path.write_text(json_lib.dumps(forged, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Re-running replay from the (now tampered) events on disk is what catches it — reading the
    # stale, frozen report on disk would not have.
    retamper_replay_path = tamper_output_dir / "deepagents-replay-report-post-tamper.json"
    retamper_replay = replay_deepagents_run(events_dir=tamper_events_dir, output=retamper_replay_path)

    assert retamper_replay["valid"] is False
    assert retamper_replay["status"] == "INVALID"
    # The replay report artifact itself stays schema-conformant even while honestly reporting
    # its own invalidity (never a fabricated pass).
    assert validate_deepagents_replay_report(retamper_replay) == []

    errors = retamper_replay["errors"]
    # The forged node is NAMED: its own path appears against a self-digest mismatch.
    assert any(str(forged_path) in error and "digest" in error.lower() for error in errors), errors
    # The chain breaks precisely on the previous_event_sha256 link, named at its successor.
    assert any(
        str(successor_path) in error and "previous_event_sha256 does not match prior event" in error for error in errors
    ), errors

    # The clean bundle, built before any of this, remains completely untouched.
    assert json_lib.loads(replay_path.read_text(encoding="utf-8"))["valid"] is True
    assert clean_events_dir != tamper_events_dir
