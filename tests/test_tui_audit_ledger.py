"""Pins the two properties the TUI audit ledger claims: diffable state, unforgeable chain.

Every tamper case below is asserted to be *detected*. A ledger advertising "immutable, append-only"
whose validator cannot actually catch a deletion is worse than one making no claim at all -- it
converts an unverified file into a falsely trusted one.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from builder_ii.tui_audit_ledger import (
    GENESIS_PREV_DIGEST,
    TUI_AUDIT_LEDGER_EVENT_KIND,
    TUI_AUDIT_LEDGER_SCHEMA_VERSION,
    append_event,
    build_event,
    compute_entry_digest,
    compute_state_digest,
    read_chain_head,
    validate_ledger,
)


# Factories, not module-level dicts. `build_event` stores the state by reference, so a shared
# fixture is mutated in place by any tamper case that edits a payload -- which silently defeated
# `test_edited_state_with_recomputed_state_digest_is_detected`: it re-forged an already-forged
# value, changed nothing, and so detected nothing. A tamper suite undone by its own state leak is
# the exact failure mode these lanes exist to catch.
def _state_a() -> dict:
    return {"active_screen": "Screen", "focused_id": "spine-container", "widgets": [{"id": "x"}]}


def _state_b() -> dict:
    return {"active_screen": "CommandPaletteScreen", "focused_id": "palette-input", "widgets": []}


def _chain(*states: dict) -> list[dict]:
    """Build a valid chain over `states`, one MOUNT then ACTIONs."""
    events: list[dict] = []
    prev = GENESIS_PREV_DIGEST
    for seq, state in enumerate(states):
        entry = build_event(
            seq=seq,
            run_id="11111111-1111-1111-1111-111111111111",
            timestamp=1000.0 + seq,
            event="MOUNT" if seq == 0 else "ACTION",
            state=state,
            prev_digest=prev,
            action=None if seq == 0 else "press",
            target=None if seq == 0 else "tab",
            status=None if seq == 0 else "success",
        )
        events.append(entry)
        prev = entry["entry_digest"]
    return events


def _write(path: Path, events: list[dict]) -> Path:
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    return path


def test_valid_chain_validates(tmp_path: Path) -> None:
    assert validate_ledger(_write(tmp_path / "l.jsonl", _chain(_state_a(), _state_b()))) == []


def test_state_digest_is_identical_for_identical_state_across_runs() -> None:
    """The whole point: two runs of the same UI state must produce the same state_digest.

    The previous implementation folded `uuid4` run_id and `time.time()` into the digest, so this
    was false by construction and the ledger could never be diffed run-over-run to catch a
    regression.
    """
    a = build_event(seq=0, run_id="run-one", timestamp=1.0, event="MOUNT", state=_state_a(), prev_digest=None)
    b = build_event(seq=7, run_id="run-two", timestamp=99999.0, event="MOUNT", state=_state_a(), prev_digest="deadbeef")

    assert a["state_digest"] == b["state_digest"]
    # ...while the chain links, which must bind position and run metadata, still differ.
    assert a["entry_digest"] != b["entry_digest"]


def test_state_digest_changes_when_the_ui_changes() -> None:
    assert compute_state_digest(_state_a()) != compute_state_digest(_state_b())


def test_chain_spans_the_file_not_the_run(tmp_path: Path) -> None:
    """A second run continues the chain, so deleting a whole run's block is detectable."""
    path = tmp_path / "l.jsonl"
    for event in _chain(_state_a(), _state_b()):
        append_event(path, event)

    next_seq, prev = read_chain_head(path)
    assert next_seq == 2
    assert prev == json.loads(path.read_text().splitlines()[-1])["entry_digest"]

    append_event(path, build_event(seq=next_seq, run_id="run-two", timestamp=5.0, event="MOUNT",
                                   state=_state_a(), prev_digest=prev))
    assert validate_ledger(path) == []


def test_fresh_file_starts_at_genesis(tmp_path: Path) -> None:
    assert read_chain_head(tmp_path / "absent.jsonl") == (0, GENESIS_PREV_DIGEST)


def test_unreadable_tail_refuses_to_fork_the_chain(tmp_path: Path) -> None:
    """Starting a second genesis inside one file would hide the gap between the two chains."""
    path = tmp_path / "l.jsonl"
    path.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing to fork the chain"):
        read_chain_head(path)


def test_missing_file_is_an_error(tmp_path: Path) -> None:
    assert validate_ledger(tmp_path / "nope.jsonl")


def test_empty_ledger_is_not_reported_as_valid(tmp_path: Path) -> None:
    """"Nothing to check" must never read as "checked and clean"."""
    errors = validate_ledger(_write(tmp_path / "l.jsonl", []))
    assert errors and "empty ledger" in errors[0]


# ── Tamper matrix ───────────────────────────────────────────────────
# Each case asserts DETECTION. See test_forged_relink_is_detected for why this is not paranoia.


def test_deleted_event_is_detected(tmp_path: Path) -> None:
    events = _chain(_state_a(), _state_b(), _state_a())
    assert validate_ledger(_write(tmp_path / "l.jsonl", events[:1] + events[2:]))


def test_reordered_events_are_detected(tmp_path: Path) -> None:
    events = _chain(_state_a(), _state_b(), _state_a())
    events[1], events[2] = events[2], events[1]
    assert validate_ledger(_write(tmp_path / "l.jsonl", events))


def test_edited_state_is_detected(tmp_path: Path) -> None:
    events = _chain(_state_a(), _state_b())
    events[1]["state"]["active_screen"] = "Forged"
    errors = validate_ledger(_write(tmp_path / "l.jsonl", events))
    assert any("state_digest does not match" in e for e in errors)


def test_edited_state_with_recomputed_state_digest_is_detected(tmp_path: Path) -> None:
    """A forger who knows how state_digest is computed still cannot get past entry_digest."""
    events = _chain(_state_a(), _state_b())
    events[1]["state"]["active_screen"] = "Forged"
    events[1]["state_digest"] = compute_state_digest(events[1]["state"])
    errors = validate_ledger(_write(tmp_path / "l.jsonl", events))
    assert any("entry_digest does not match" in e for e in errors)


def test_forged_relink_is_detected(tmp_path: Path) -> None:
    """The case that justifies two digests instead of one.

    Delete an event, re-point the next event's `prev_digest` at the survivor, and renumber `seq`.
    Had `state_digest` doubled as the chain link -- the literal "rebind the digest to the state
    payload" reading -- every remaining line would still verify, because a state-bound digest does
    not commit to `prev_digest`. `entry_digest` binds the link itself, so the forgery breaks.
    """
    events = _chain(_state_a(), _state_b(), _state_a())
    forged = [copy.deepcopy(e) for e in events[:1] + events[2:]]
    forged[1]["prev_digest"] = forged[0]["entry_digest"]
    for index, entry in enumerate(forged):
        entry["seq"] = index

    errors = validate_ledger(_write(tmp_path / "l.jsonl", forged))
    assert any("entry_digest does not match" in e for e in errors)


def test_tampered_entry_digest_alone_is_detected(tmp_path: Path) -> None:
    events = _chain(_state_a(), _state_b())
    events[0]["entry_digest"] = "0" * 64
    assert validate_ledger(_write(tmp_path / "l.jsonl", events))


def test_wrong_kind_and_schema_version_are_detected(tmp_path: Path) -> None:
    events = _chain(_state_a())
    events[0]["kind"] = "builder_ii.something_else"
    errors = validate_ledger(_write(tmp_path / "l.jsonl", events))
    assert any("invalid kind" in e for e in errors)

    events = _chain(_state_a())
    events[0]["schema_version"] = TUI_AUDIT_LEDGER_SCHEMA_VERSION + 1
    errors = validate_ledger(_write(tmp_path / "l.jsonl", events))
    assert any("invalid schema_version" in e for e in errors)


def test_missing_required_field_is_detected(tmp_path: Path) -> None:
    events = _chain(_state_a())
    del events[0]["prev_digest"]
    errors = validate_ledger(_write(tmp_path / "l.jsonl", events))
    assert any("missing required field" in e for e in errors)


def test_non_genesis_first_event_is_detected(tmp_path: Path) -> None:
    events = _chain(_state_a())
    events[0]["prev_digest"] = "a" * 64
    events[0]["entry_digest"] = compute_entry_digest(events[0])
    errors = validate_ledger(_write(tmp_path / "l.jsonl", events))
    assert any("first event must have prev_digest" in e for e in errors)


def test_malformed_line_is_reported_not_skipped(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    path.write_text(json.dumps(_chain(_state_a())[0]) + "\n{ broken\n", encoding="utf-8")
    errors = validate_ledger(path)
    assert any("not valid JSON" in e for e in errors)


def test_event_kind_is_the_registered_artifact_kind() -> None:
    """Pins the string that `docs/ARTIFACT_INDEX.md` and the validator script both name."""
    assert TUI_AUDIT_LEDGER_EVENT_KIND == "builder_ii.tui_audit_ledger_event"
