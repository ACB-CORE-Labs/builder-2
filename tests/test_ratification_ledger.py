"""Pins for the ratification audit ledger: chain integrity, and what tampering it can actually see.

The tamper tests are deliberately specific about the *limit* of the guarantee. This ledger is
tamper-evident, not tamper-proof: an attacker who rewrites every following line rebuilds a valid
chain. What it closes is the quiet single-line edit and the silent deletion, which is what a
receipt written by the acting process can honestly claim.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.governance.ledger.ratification_ledger import (
    EVENT_AUTO_ACCEPTED,
    EVENT_GRANT_CREATED,
    GENESIS_PREV_DIGEST,
    RATIFICATION_LEDGER_KIND,
    append_ratification_event,
    compute_entry_digest,
    ledger_path,
    read_ratification_events,
    validate_ratification_ledger,
)


def _append(root: Path, event: str = EVENT_GRANT_CREATED, **overrides: object) -> dict:
    payload = {
        "event": event,
        "point_id": "setup.apply.overlay_digest",
        "command": "builder-setup apply",
        "actor": "op",
        "because": "test",
    }
    payload.update(overrides)  # type: ignore[arg-type]
    return append_ratification_event(root, **payload)  # type: ignore[arg-type]


def test_an_absent_ledger_is_an_empty_history_not_an_error(tmp_path: Path) -> None:
    assert read_ratification_events(tmp_path) == []
    assert validate_ratification_ledger(tmp_path) == []


def test_the_first_entry_starts_the_chain_at_genesis(tmp_path: Path) -> None:
    entry = _append(tmp_path)
    assert entry["seq"] == 0
    assert entry["prev_digest"] == GENESIS_PREV_DIGEST
    assert entry["kind"] == RATIFICATION_LEDGER_KIND
    assert entry["governance"]["independent_observer"] is False


def test_entries_chain_and_the_chain_verifies(tmp_path: Path) -> None:
    first = _append(tmp_path)
    second = _append(tmp_path, EVENT_AUTO_ACCEPTED, grant_digest="a" * 64)
    assert second["seq"] == 1
    assert second["prev_digest"] == first["entry_digest"]
    assert validate_ratification_ledger(tmp_path) == []


def test_the_entry_digest_commits_to_prev_digest(tmp_path: Path) -> None:
    """Digesting the payload alone would leave a re-pointed chain verifying. It must not."""
    entry = _append(tmp_path)
    relinked = dict(entry)
    relinked["prev_digest"] = "b" * 64
    assert compute_entry_digest(relinked) != entry["entry_digest"]


def test_editing_one_field_breaks_that_line(tmp_path: Path) -> None:
    _append(tmp_path)
    _append(tmp_path, EVENT_AUTO_ACCEPTED)
    path = ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["actor"] = "someone-else"
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    errors = validate_ratification_ledger(tmp_path)
    assert errors == ["line 1: entry_digest does not match recomputed digest"]


def test_deleting_a_line_breaks_sequence_and_link(tmp_path: Path) -> None:
    _append(tmp_path)
    _append(tmp_path, EVENT_AUTO_ACCEPTED)
    _append(tmp_path, EVENT_AUTO_ACCEPTED)
    path = ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    errors = validate_ratification_ledger(tmp_path)
    assert any("seq is 2, expected 1" in error for error in errors)
    assert any("prev_digest" in error for error in errors)


def test_an_unknown_event_name_is_refused_rather_than_recorded(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown ratification ledger event"):
        _append(tmp_path, "quietly_did_something")
    assert read_ratification_events(tmp_path) == []


def test_appends_after_a_forked_tail_are_refused(tmp_path: Path) -> None:
    """A file whose last line is unreadable must not silently start a second, unlinked chain."""
    _append(tmp_path)
    path = ledger_path(tmp_path)
    path.write_text(path.read_text(encoding="utf-8") + "{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing to fork the chain"):
        _append(tmp_path)
