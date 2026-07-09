"""Ladder 4 PR-5 — read-only belief/status walks over a `builder-deepagents run-approved
--obligation` output directory (Object model: discharge states; docs/ORCHESTRATION_OBLIGATIONS.md).

Two deterministic reports, both re-derived fresh from the raw per-event JSON files on disk (never
from the cached `deepagents-replay-report.json` snapshot, which would be stale against any
post-run tampering):

- ``build_obligation_board`` — one row per obligation minted/refused in the run, its board state
  (OPEN / SATISFIED / UNVERIFIED / VIOLATED / BLOCKED) and its granted budget partition. Backs
  `builder-orchestration status`.
- ``build_belief_trace`` — the belief trace for exactly one obligation (believed?, required
  evidence, attached evidence, consumed), located from the path to one of its lifecycle event
  files. Backs `builder-orchestration why`.

Board state is a superset of the runner's DISCHARGE_STATES (Law 2): OPEN covers an obligation that
was minted but never reached an `obligation_consumed` event (the run ended before discharge).

This module never runs anything, calls a model, or writes to the run directory it reads.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from rich.table import Table

from builder_ii.deepagents_execution import (
    DEEPAGENTS_EVENT_LEDGER_KIND,
    DEEPAGENTS_EVENT_RECORD_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    DISCHARGE_BLOCKED,
    DISCHARGE_CONTRACT_SATISFIED,
    DISCHARGE_CONTRACT_VIOLATED,
    DISCHARGE_UNVERIFIED,
    create_deepagents_replay_report,
    validate_deepagents_event_ledger,
    validate_deepagents_execution_receipt,
)

BOARD_STATE_OPEN = "OPEN"
BOARD_STATE_SATISFIED = "SATISFIED"
BOARD_STATE_UNVERIFIED = "UNVERIFIED"
BOARD_STATE_VIOLATED = "VIOLATED"
BOARD_STATE_BLOCKED = "BLOCKED"
BOARD_STATES = (
    BOARD_STATE_OPEN,
    BOARD_STATE_SATISFIED,
    BOARD_STATE_UNVERIFIED,
    BOARD_STATE_VIOLATED,
    BOARD_STATE_BLOCKED,
)

_DISCHARGE_TO_BOARD_STATE = {
    DISCHARGE_CONTRACT_SATISFIED: BOARD_STATE_SATISFIED,
    DISCHARGE_UNVERIFIED: BOARD_STATE_UNVERIFIED,
    DISCHARGE_CONTRACT_VIOLATED: BOARD_STATE_VIOLATED,
    DISCHARGE_BLOCKED: BOARD_STATE_BLOCKED,
}

_OBLIGATION_LIFECYCLE_EVENT_TYPES = ("obligation_minted", "obligation_mint_refused", "obligation_consumed")

BUDGET_COLUMNS = ("max_subagents", "max_events", "max_output_bytes", "max_human_gates")


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} not found at {path}")
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {label} at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} at {path} must contain a JSON object")
    return data


def _events_dir_for(output_dir: Path) -> Path:
    events_dir = output_dir / "events"
    if not events_dir.is_dir():
        raise ValueError(f"{output_dir} has no events/ directory; not a builder-deepagents run-approved output")
    return events_dir


def _load_event_records(events_dir: Path) -> list[tuple[dict[str, Any], Path]]:
    paths = sorted(events_dir.glob("event-*.json"))
    if not paths:
        raise ValueError(f"{events_dir} contains no event-*.json records")
    return [(_read_json_object(path, label="deepagents event record"), path) for path in paths]


def _payload_of(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _new_row(obligation_digest: str) -> dict[str, Any]:
    return {
        "obligation_digest": obligation_digest,
        "briefing_digest": "",
        "obligation_kind": None,
        "lane": None,
        "subagent_profile": None,
        "budget_partition": None,
        "board_state": BOARD_STATE_OPEN,
        "discharge_state": None,
        "expected_kind": None,
        "produced_kind": None,
        "required_evidence_kinds": None,
        "attached_evidence_kinds": None,
        "violated_rule": None,
        "fixing_edit": None,
        "provenance": None,
        "consumed": False,
    }


def _apply_event_to_row(row: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
    if payload.get("briefing_digest"):
        row["briefing_digest"] = payload["briefing_digest"]
    if event_type == "obligation_minted":
        row["obligation_kind"] = payload.get("obligation_kind")
        row["lane"] = payload.get("lane")
        row["subagent_profile"] = payload.get("subagent_profile")
        row["budget_partition"] = payload.get("budget_partition")
    elif event_type == "obligation_mint_refused":
        row["obligation_kind"] = payload.get("obligation_kind")
        row["lane"] = payload.get("lane")
        row["violated_rule"] = payload.get("violated_rule")
        row["fixing_edit"] = payload.get("fixing_edit")
        row["discharge_state"] = DISCHARGE_BLOCKED
        row["board_state"] = BOARD_STATE_BLOCKED
    elif event_type == "obligation_consumed":
        discharge_state = payload.get("discharge_state")
        row["discharge_state"] = discharge_state
        row["expected_kind"] = payload.get("expected_kind")
        row["produced_kind"] = payload.get("produced_kind")
        row["required_evidence_kinds"] = list(payload.get("missing_evidence") or [])
        # v1 proposal-only lane invariant (deepagents_execution._result_attached_evidence_kinds):
        # the lane never attaches downstream evidence, so an obligation_consumed event never has any.
        row["attached_evidence_kinds"] = []
        row["provenance"] = payload.get("provenance")
        row["consumed"] = True
        row["board_state"] = (
            _DISCHARGE_TO_BOARD_STATE.get(discharge_state, BOARD_STATE_OPEN)
            if isinstance(discharge_state, str)
            else BOARD_STATE_OPEN
        )


def build_obligation_rows(records: list[tuple[dict[str, Any], Path]]) -> list[dict[str, Any]]:
    """Walk obligation-lifecycle events (already sorted or not) into one row per obligation_digest,
    in order of first appearance. Deterministic: no clocks, no randomness, pure event replay."""
    ordered = sorted(records, key=lambda item: int(item[0].get("sequence", 10**9)))
    rows: dict[str, dict[str, Any]] = {}
    for event, _ in ordered:
        event_type = event.get("event_type")
        if not isinstance(event_type, str) or event_type not in _OBLIGATION_LIFECYCLE_EVENT_TYPES:
            continue
        payload = _payload_of(event)
        digest = payload.get("obligation_digest")
        if not isinstance(digest, str) or not digest:
            continue
        row = rows.setdefault(digest, _new_row(digest))
        _apply_event_to_row(row, event_type, payload)
    return list(rows.values())


def build_obligation_board(output_dir: Path) -> dict[str, Any]:
    """Deterministic read-only board over one `run-approved --obligation` output directory.

    Re-derives the event replay fresh from the raw per-event files (tamper-sensitive: a hand-
    edited event JSON fails its own digest check inside `create_deepagents_replay_report`), and
    cross-checks the run's execution receipt and event ledger artifacts. ``chain_valid`` is False
    on any of: a broken/tampered event chain, a missing run artifact, or a tampered receipt/ledger.
    """
    if not output_dir.is_dir():
        raise ValueError(f"run-output-dir not found: {output_dir}")

    events_dir = _events_dir_for(output_dir)
    records = _load_event_records(events_dir)
    ordered = sorted(records, key=lambda item: int(item[0].get("sequence", 10**9)))
    session_id = str(ordered[0][0].get("session_id", ""))
    replay = create_deepagents_replay_report(session_id=session_id, event_records=records)
    errors = list(replay.get("errors") or [])

    receipt_path = output_dir / "deepagents-execution-receipt.json"
    receipt = _read_json_object(receipt_path, label="deepagents execution receipt")
    if receipt.get("kind") != DEEPAGENTS_EXECUTION_RECEIPT_KIND:
        errors.append(f"{receipt_path}: not a {DEEPAGENTS_EXECUTION_RECEIPT_KIND}")
    else:
        errors.extend(f"{receipt_path}: {error}" for error in validate_deepagents_execution_receipt(receipt))

    ledger_path = output_dir / "deepagents-event-ledger.json"
    ledger = _read_json_object(ledger_path, label="deepagents event ledger")
    if ledger.get("kind") != DEEPAGENTS_EVENT_LEDGER_KIND:
        errors.append(f"{ledger_path}: not a {DEEPAGENTS_EVENT_LEDGER_KIND}")
    else:
        errors.extend(f"{ledger_path}: {error}" for error in validate_deepagents_event_ledger(ledger))

    return {
        "output_dir": str(output_dir),
        "session_id": session_id,
        "backend_mode": receipt.get("backend_mode"),
        "run_status": receipt.get("receipt_state"),
        "chain_valid": not errors,
        "chain_errors": errors,
        "rows": build_obligation_rows(records),
    }


def render_status_table(board: dict[str, Any]) -> Table:
    table = Table(
        "obligation",
        "state",
        "kind",
        "subagent",
        "max_subagents",
        "max_events",
        "max_output_bytes",
        "max_human_gates",
        title=f"Obligation status — {board.get('run_status') or 'UNKNOWN'} ({board.get('output_dir')})",
    )
    for row in board["rows"]:
        budget = row.get("budget_partition") or {}
        table.add_row(
            str(row["obligation_digest"])[:12],
            str(row["board_state"]),
            str(row.get("obligation_kind") or "-"),
            str(row.get("subagent_profile") or "-"),
            *(str(budget.get(column, "-")) for column in BUDGET_COLUMNS),
        )
    return table


def build_belief_trace(artifact_path: Path) -> dict[str, Any]:
    """Deterministic belief trace for the one obligation named by an obligation-lifecycle event
    file (one of `obligation_minted` / `obligation_mint_refused` / `obligation_consumed` under a
    run-output-dir's `events/` directory). Re-walks the whole run (see `build_obligation_board`)
    so tampering anywhere in the chain is visible in `chain_valid`/`chain_errors`.
    """
    event = _read_json_object(artifact_path, label="orchestration why artifact")
    if event.get("kind") != DEEPAGENTS_EVENT_RECORD_KIND:
        raise ValueError(
            f"{artifact_path} is not a {DEEPAGENTS_EVENT_RECORD_KIND}; pass the path to one of the "
            "obligation_minted / obligation_mint_refused / obligation_consumed event files under a "
            "run-output-dir's events/ directory"
        )
    payload = _payload_of(event)
    obligation_digest = payload.get("obligation_digest")
    if not isinstance(obligation_digest, str) or not obligation_digest:
        raise ValueError(f"{artifact_path} has no payload.obligation_digest; not an obligation-lifecycle event")

    events_dir = artifact_path.resolve().parent
    output_dir = events_dir.parent
    board = build_obligation_board(output_dir)
    row = next((candidate for candidate in board["rows"] if candidate["obligation_digest"] == obligation_digest), None)
    if row is None:
        raise ValueError(f"obligation {obligation_digest} not found among lifecycle events in {events_dir}")

    believed = row["discharge_state"] == DISCHARGE_CONTRACT_SATISFIED
    trace = {
        "output_dir": board["output_dir"],
        "obligation_digest": obligation_digest,
        "board_state": row["board_state"],
        "discharge_state": row["discharge_state"],
        "believed": believed,
        "expected_kind": row["expected_kind"],
        "produced_kind": row["produced_kind"],
        "required_evidence_kinds": row["required_evidence_kinds"],
        "attached_evidence_kinds": row["attached_evidence_kinds"],
        "violated_rule": row["violated_rule"],
        "fixing_edit": row["fixing_edit"],
        "consumed": row["consumed"],
        "chain_valid": board["chain_valid"],
        "chain_errors": board["chain_errors"],
    }
    trace["verdict_line"] = format_belief_trace_line(trace)
    return trace


def format_belief_trace_line(trace: dict[str, Any]) -> str:
    verdict = "YES" if trace["believed"] else "NO"
    state = trace["discharge_state"] or trace["board_state"]
    head = f"believed? {verdict} — {state}"
    consumed = "yes" if trace["consumed"] else "no"
    state_key = trace["discharge_state"]
    if state_key in (DISCHARGE_CONTRACT_SATISFIED, DISCHARGE_UNVERIFIED):
        required = ", ".join(trace["required_evidence_kinds"] or []) or "none"
        attached = ", ".join(trace["attached_evidence_kinds"] or []) or "none"
        return f"{head}; required: {required}; attached: {attached}; consumed: {consumed}"
    if state_key == DISCHARGE_CONTRACT_VIOLATED:
        return f"{head}; expected: {trace['expected_kind']}; produced: {trace['produced_kind']}; consumed: {consumed}"
    if state_key == DISCHARGE_BLOCKED:
        return f"{head}; violated_rule: {trace['violated_rule']}; fixing_edit: {trace['fixing_edit']}; consumed: {consumed}"
    return f"{head}; reason: minted but not yet discharged; consumed: {consumed}"
