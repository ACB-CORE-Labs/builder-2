"""Ladder 4 PR-5 — `builder-orchestration status` / `builder-orchestration why`.

This file owns ALL status/why OUTPUT assertions (Wave-4 decoupling rule; PR-6 must not assert on
them). It reuses the PR-4 fixtures in test_orchestration_delegation_run.py to build one real
obligation-delegation run that produces all four discharge states (CONTRACT_SATISFIED,
DISCHARGED_UNVERIFIED, CONTRACT_VIOLATED, BLOCKED), then asserts the status board rows + budget
columns and the why belief trace for each state.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path

from test_orchestration_delegation_run import SMALL, TOO_BIG, _ladder4_candidate, _obligation, _seal
from typer.testing import CliRunner

from builder_ii.adapters.deepagents.deepagents_execution import (
    DISCHARGE_BLOCKED,
    DISCHARGE_CONTRACT_SATISFIED,
    DISCHARGE_CONTRACT_VIOLATED,
    DISCHARGE_UNVERIFIED,
    PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
    create_deepagents_event_record,
    run_deepagents_approved_candidate,
)
from builder_ii.cli.orchestration_cli import orchestration_app
from builder_ii.core.orchestration_status import (
    BOARD_STATE_BLOCKED,
    BOARD_STATE_OPEN,
    BOARD_STATE_SATISFIED,
    BOARD_STATE_UNVERIFIED,
    BOARD_STATE_VIOLATED,
    build_obligation_rows,
)

runner = CliRunner()


def _build_four_state_run(tmp_path: Path) -> tuple[Path, dict[str, dict]]:
    """Real run producing one obligation in each of the four discharge states.

    Returns (output_dir, {board_state: obligation_dict}) so tests can look up each obligation's
    obligation_id / evidence contract by the outcome it produced.
    """
    # max_count=4: three obligations mint normally, leaving exactly one slot so the fourth's
    # oversized budget is what gets refused (budget_partition_exceeds_remaining), not the count.
    candidate, policy, *_rest = _ladder4_candidate(tmp_path, kinds=[{"kind": "planning_step", "max_count": 4}])
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    lpd = policy["lane_policy_digest"]
    seal = approval["approval_digest"]

    satisfied_path, satisfied_obl = _obligation(
        tmp_path,
        0,
        seal_digest=seal,
        lpd=lpd,
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        evidence=[],
        subagent="repo_mapper",
        budget=SMALL,
    )
    unverified_path, unverified_obl = _obligation(
        tmp_path,
        1,
        seal_digest=seal,
        lpd=lpd,
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        evidence=["builder_ii.verification_execution_receipt"],
        subagent="code_reviewer",
        budget=SMALL,
    )
    violated_path, violated_obl = _obligation(
        tmp_path,
        2,
        seal_digest=seal,
        lpd=lpd,
        expected_kind="builder_ii.some_other_kind",
        evidence=[],
        subagent="repo_mapper",
        budget=SMALL,
    )
    blocked_path, blocked_obl = _obligation(
        tmp_path,
        3,
        seal_digest=seal,
        lpd=lpd,
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        evidence=[],
        subagent="repo_mapper",
        budget=TOO_BIG,
    )

    output_dir = tmp_path / "runs" / "obl"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
        obligation_paths=[satisfied_path, unverified_path, violated_path, blocked_path],
    )
    assert summary["status"] == "COMPLETED"
    assert summary["discharge_tally"] == {
        DISCHARGE_CONTRACT_SATISFIED: 1,
        DISCHARGE_UNVERIFIED: 1,
        DISCHARGE_CONTRACT_VIOLATED: 1,
        DISCHARGE_BLOCKED: 1,
    }
    return output_dir, {
        BOARD_STATE_SATISFIED: satisfied_obl,
        BOARD_STATE_UNVERIFIED: unverified_obl,
        BOARD_STATE_VIOLATED: violated_obl,
        BOARD_STATE_BLOCKED: blocked_obl,
    }


def _event_path_for(output_dir: Path, event_type: str, obligation_digest: str) -> Path:
    for path in sorted((output_dir / "events").glob(f"event-*-{event_type}.json")):
        event = json_lib.loads(path.read_text(encoding="utf-8"))
        if event["payload"].get("obligation_digest") == obligation_digest:
            return path
    raise AssertionError(f"no {event_type} event found for obligation {obligation_digest}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_board_has_one_row_per_obligation_with_all_four_states(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    board_out = tmp_path / "board.json"

    result = runner.invoke(orchestration_app, ["status", str(output_dir), "--output", str(board_out)])
    assert result.exit_code == 0, result.output

    board = json_lib.loads(board_out.read_text(encoding="utf-8"))
    assert board["chain_valid"] is True
    assert board["chain_errors"] == []
    assert board["run_status"] == "COMPLETED"
    assert board["backend_mode"] == "protocol_fake"

    rows_by_digest = {row["obligation_digest"]: row for row in board["rows"]}
    assert len(rows_by_digest) == 4

    satisfied_row = rows_by_digest[obligations[BOARD_STATE_SATISFIED]["obligation_id"]]
    assert satisfied_row["board_state"] == BOARD_STATE_SATISFIED
    assert satisfied_row["discharge_state"] == DISCHARGE_CONTRACT_SATISFIED
    assert satisfied_row["budget_partition"] == SMALL
    assert satisfied_row["subagent_profile"] == "repo_mapper"

    unverified_row = rows_by_digest[obligations[BOARD_STATE_UNVERIFIED]["obligation_id"]]
    assert unverified_row["board_state"] == BOARD_STATE_UNVERIFIED
    assert unverified_row["discharge_state"] == DISCHARGE_UNVERIFIED
    assert unverified_row["required_evidence_kinds"] == ["builder_ii.verification_execution_receipt"]
    assert unverified_row["attached_evidence_kinds"] == []
    assert unverified_row["budget_partition"] == SMALL

    violated_row = rows_by_digest[obligations[BOARD_STATE_VIOLATED]["obligation_id"]]
    assert violated_row["board_state"] == BOARD_STATE_VIOLATED
    assert violated_row["discharge_state"] == DISCHARGE_CONTRACT_VIOLATED
    assert violated_row["expected_kind"] == "builder_ii.some_other_kind"
    assert violated_row["produced_kind"] == PROPOSAL_ONLY_RESULT_CONTRACT_KIND

    blocked_row = rows_by_digest[obligations[BOARD_STATE_BLOCKED]["obligation_id"]]
    assert blocked_row["board_state"] == BOARD_STATE_BLOCKED
    assert blocked_row["discharge_state"] == DISCHARGE_BLOCKED
    assert blocked_row["violated_rule"] == "budget_partition_exceeds_remaining"
    assert blocked_row["fixing_edit"]
    # The runner never stamps a refused mint's attempted budget onto the ledger (see
    # deepagents_execution._run_obligation_delegation's obligation_mint_refused payload) so the
    # board honestly reports "unknown", not a fabricated value.
    assert blocked_row["budget_partition"] is None
    assert blocked_row["consumed"] is False


def test_status_board_prints_table_when_no_output_flag(tmp_path: Path) -> None:
    output_dir, _obligations = _build_four_state_run(tmp_path)
    result = runner.invoke(orchestration_app, ["status", str(output_dir)])
    assert result.exit_code == 0, result.output
    assert "Obligation status" in result.output
    for state in (BOARD_STATE_SATISFIED, BOARD_STATE_UNVERIFIED, BOARD_STATE_VIOLATED, BOARD_STATE_BLOCKED):
        assert state in result.output


def test_render_status_table_state_column_survives_narrow_width() -> None:
    """Host-independent guard: the board-state enum column renders in full even when the table is
    squeezed by long kinds / a long output_dir and a narrow render width. Regression test for Rich
    proportional-shrink ellipsizing 'SATISFIED' -> 'SATISF...' (was host-fragile: passed on wide
    terminals, failed on narrow ones under CliRunner)."""
    from io import StringIO

    from rich.console import Console

    from builder_ii.core.orchestration_status import BOARD_STATES, render_status_table

    board = {
        "run_status": "COMPLETE",
        "output_dir": "/a/deliberately/long/output/directory/path/that/consumes/render/width/run-0001",
        "rows": [
            {
                "obligation_digest": f"{index:064x}",
                "board_state": state,
                "obligation_kind": "builder_ii.a_deliberately_long_obligation_contract_kind_name",
                "subagent_profile": "a-long-subagent-profile-identifier",
                "budget_partition": {
                    column: 1 for column in ("max_subagents", "max_events", "max_output_bytes", "max_human_gates")
                },
            }
            for index, state in enumerate(BOARD_STATES)
        ],
    }
    buffer = StringIO()
    Console(file=buffer, width=60).print(render_status_table(board))
    output = buffer.getvalue()
    for state in BOARD_STATES:
        assert state in output, f"state {state!r} was truncated in the rendered board:\n{output}"


def test_status_missing_run_output_dir_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(orchestration_app, ["status", str(tmp_path / "does-not-exist")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_status_missing_events_dir_exits_nonzero(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-run"
    empty_dir.mkdir()
    result = runner.invoke(orchestration_app, ["status", str(empty_dir)])
    assert result.exit_code == 1
    assert "events/" in result.output


def test_status_detects_tampered_event_and_exits_nonzero(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    consumed_path = _event_path_for(
        output_dir, "obligation_consumed", obligations[BOARD_STATE_SATISFIED]["obligation_id"]
    )
    tampered = json_lib.loads(consumed_path.read_text(encoding="utf-8"))
    tampered["payload"]["discharge_state"] = DISCHARGE_CONTRACT_VIOLATED  # forge, digest now stale
    consumed_path.write_text(json_lib.dumps(tampered), encoding="utf-8")

    board_out = tmp_path / "board.json"
    result = runner.invoke(orchestration_app, ["status", str(output_dir), "--output", str(board_out)])
    assert result.exit_code == 1

    board = json_lib.loads(board_out.read_text(encoding="utf-8"))
    assert board["chain_valid"] is False
    assert any("event_digest" in error or "payload_sha256" in error for error in board["chain_errors"])


# ---------------------------------------------------------------------------
# why
# ---------------------------------------------------------------------------


def test_why_satisfied_is_believed_and_exits_zero(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    digest = obligations[BOARD_STATE_SATISFIED]["obligation_id"]
    event_path = _event_path_for(output_dir, "obligation_consumed", digest)
    trace_out = tmp_path / "trace.json"

    result = runner.invoke(orchestration_app, ["why", str(event_path), "--output", str(trace_out)])
    assert result.exit_code == 0, result.output
    assert "believed? YES" in result.output

    trace = json_lib.loads(trace_out.read_text(encoding="utf-8"))
    assert trace["believed"] is True
    assert trace["discharge_state"] == DISCHARGE_CONTRACT_SATISFIED
    assert trace["obligation_digest"] == digest
    assert trace["required_evidence_kinds"] == []
    assert trace["attached_evidence_kinds"] == []
    assert trace["consumed"] is True
    assert trace["chain_valid"] is True


def test_why_unverified_is_not_believed_and_exits_nonzero(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    digest = obligations[BOARD_STATE_UNVERIFIED]["obligation_id"]
    event_path = _event_path_for(output_dir, "obligation_consumed", digest)

    result = runner.invoke(orchestration_app, ["why", str(event_path)])
    assert result.exit_code == 1
    assert "believed? NO — DISCHARGED_UNVERIFIED" in result.output
    assert "required: builder_ii.verification_execution_receipt" in result.output
    assert "attached: none" in result.output
    assert "consumed: yes" in result.output


def test_why_violated_is_not_believed_and_exits_nonzero(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    digest = obligations[BOARD_STATE_VIOLATED]["obligation_id"]
    event_path = _event_path_for(output_dir, "obligation_consumed", digest)

    result = runner.invoke(orchestration_app, ["why", str(event_path)])
    assert result.exit_code == 1
    assert "believed? NO — CONTRACT_VIOLATED" in result.output
    assert "expected: builder_ii.some_other_kind" in result.output
    assert f"produced: {PROPOSAL_ONLY_RESULT_CONTRACT_KIND}" in result.output


def test_why_blocked_is_not_believed_and_exits_nonzero(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    digest = obligations[BOARD_STATE_BLOCKED]["obligation_id"]
    event_path = _event_path_for(output_dir, "obligation_mint_refused", digest)

    result = runner.invoke(orchestration_app, ["why", str(event_path)])
    assert result.exit_code == 1
    assert "believed? NO — BLOCKED" in result.output
    assert "violated_rule: budget_partition_exceeds_remaining" in result.output
    assert "consumed: no" in result.output


def test_why_rejects_non_event_artifact(tmp_path: Path) -> None:
    _output_dir, obligations = _build_four_state_run(tmp_path)
    not_an_event = tmp_path / "not-an-event.json"
    not_an_event.write_text(json_lib.dumps(obligations[BOARD_STATE_SATISFIED]), encoding="utf-8")

    result = runner.invoke(orchestration_app, ["why", str(not_an_event)])
    assert result.exit_code == 1
    assert "deepagents_event_record" in result.output


def test_why_missing_artifact_path_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(orchestration_app, ["why", str(tmp_path / "missing.json")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_why_tampered_chain_exits_nonzero_even_though_state_would_be_satisfied(tmp_path: Path) -> None:
    output_dir, obligations = _build_four_state_run(tmp_path)
    digest = obligations[BOARD_STATE_SATISFIED]["obligation_id"]
    minted_path = _event_path_for(output_dir, "obligation_minted", digest)
    forged = json_lib.loads(minted_path.read_text(encoding="utf-8"))
    forged["message"] = "forged after the fact"  # digest now stale
    minted_path.write_text(json_lib.dumps(forged), encoding="utf-8")

    consumed_path = _event_path_for(output_dir, "obligation_consumed", digest)
    result = runner.invoke(orchestration_app, ["why", str(consumed_path)])
    assert result.exit_code == 1
    assert "believed? YES" in result.output  # still reports the row honestly...
    assert any(line.strip() for line in result.output.splitlines()[1:])  # ...plus chain error lines


# ---------------------------------------------------------------------------
# board-building unit coverage: OPEN state (minted, never discharged — e.g. an interrupted run)
# ---------------------------------------------------------------------------


def test_open_state_for_obligation_minted_without_consumption() -> None:
    minted = create_deepagents_event_record(
        session_id="deepagents-test-session",
        sequence=1,
        event_type="obligation_minted",
        subject_refs=[],
        payload={
            "obligation_digest": "a" * 64,
            "briefing_digest": "b" * 64,
            "obligation_kind": "planning_step",
            "lane": "deepagents",
            "subagent_profile": "repo_mapper",
            "budget_partition": SMALL,
        },
        message="minted, run interrupted before consumption",
    )
    rows = build_obligation_rows([(minted, Path("event-0001-obligation_minted.json"))])
    assert len(rows) == 1
    assert rows[0]["board_state"] == BOARD_STATE_OPEN
    assert rows[0]["discharge_state"] is None
    assert rows[0]["consumed"] is False
    assert rows[0]["budget_partition"] == SMALL
