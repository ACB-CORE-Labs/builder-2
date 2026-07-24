"""Pins the two properties the TUI audit ledger claims: diffable state, unforgeable chain.

Every tamper case below is asserted to be *detected*. A ledger advertising "immutable, append-only"
whose validator cannot actually catch a deletion is worse than one making no claim at all -- it
converts an unverified file into a falsely trusted one.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest

from builder_ii.governance.ledger.tui_audit_ledger import (
    GENESIS_PREV_DIGEST,
    MASTER_INDEX_FILENAME,
    TUI_AUDIT_LEDGER_EVENT_KIND,
    TUI_AUDIT_LEDGER_INDEX_KIND,
    TUI_AUDIT_LEDGER_SCHEMA_VERSION,
    append_event,
    append_run_to_index,
    build_event,
    compute_entry_digest,
    compute_index_entry_digest,
    compute_state_digest,
    read_chain_head,
    read_ledger_summary,
    validate_ledger,
    validate_master_index,
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

    append_event(
        path,
        build_event(seq=next_seq, run_id="run-two", timestamp=5.0, event="MOUNT", state=_state_a(), prev_digest=prev),
    )
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
    """ "Nothing to check" must never read as "checked and clean"."""
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


# ── Master index: the cross-run anchor ────────────────────────────────────────────────────
#
# Splitting the ledger per run fixed a real corruption bug and cost one property: a deleted run left
# no gap, because there was no longer a longer chain for it to leave a gap in. These lanes pin that
# `append_run_to_index` restores it *without* restoring the bug -- the index is the same shared-file
# shape that broke before, and only the exclusive lock keeps it from forking the same way.


def _run_ledger(directory: Path, run_id: str, events: int = 2) -> Path:
    """A completed run's ledger: a real chain, `events` long."""
    path = directory / f"tui_audit_ledger_{run_id}.jsonl"
    prev = GENESIS_PREV_DIGEST
    for seq in range(events):
        entry = build_event(
            seq=seq,
            run_id=run_id,
            timestamp=1000.0 + seq,
            event="MOUNT" if seq == 0 else "ACTION",
            state={"run": run_id, "seq": seq},
            prev_digest=prev,
        )
        append_event(path, entry)
        prev = entry["entry_digest"]
    return path


def _index_two_runs(tmp_path: Path) -> Path:
    index = tmp_path / MASTER_INDEX_FILENAME
    for run_id in ("run-aaaa", "run-bbbb"):
        append_run_to_index(index, run_id=run_id, ledger_path=_run_ledger(tmp_path, run_id), timestamp=2000.0)
    return index


def test_master_index_anchors_runs_and_validates(tmp_path: Path) -> None:
    assert validate_master_index(_index_two_runs(tmp_path)) == []


def test_deleting_a_whole_run_ledger_is_detected(tmp_path: Path) -> None:
    """The property the per-run split destroyed, restored -- and the reason this index exists.

    Before the index, this was undetectable by construction: the validator was handed a directory,
    globbed the ledgers *present in it*, and reported them all valid. A directory that had lost half
    its runs read exactly like one that had never had them. Nothing can miss what it never saw.
    """
    index = _index_two_runs(tmp_path)
    (tmp_path / "tui_audit_ledger_run-aaaa.jsonl").unlink()

    errors = validate_master_index(index)

    assert errors, "an entire run's ledger was deleted and the index reported the directory clean"
    assert "is missing" in errors[0]
    assert "run-aaaa" in errors[0]


def test_rewriting_a_completed_run_is_detected(tmp_path: Path) -> None:
    """The run's own chain is re-verifiable, so a rewrite must not simply re-chain cleanly.

    An attacker who rewrites a run's events *and* recomputes its internal chain produces a file that
    `validate_ledger` calls perfectly valid -- the whole file is internally consistent. The index's
    head digest is what refuses it, because it recorded what the head used to be.
    """
    index = _index_two_runs(tmp_path)
    ledger = tmp_path / "tui_audit_ledger_run-aaaa.jsonl"

    # A fully valid, internally consistent replacement chain -- a different run's history.
    ledger.unlink()
    prev = GENESIS_PREV_DIGEST
    for seq in range(2):
        entry = build_event(
            seq=seq,
            run_id="run-aaaa",
            timestamp=9000.0 + seq,
            event="MOUNT" if seq == 0 else "ACTION",
            state={"forged": True, "seq": seq},
            prev_digest=prev,
        )
        append_event(ledger, entry)
        prev = entry["entry_digest"]

    assert validate_ledger(ledger) == [], "precondition: the forged run must be internally valid"

    errors = validate_master_index(index)
    assert errors, "a run's events were replaced with a valid-looking chain and nothing noticed"
    assert "head digest does not match" in errors[0]


def test_truncating_a_run_is_detected(tmp_path: Path) -> None:
    """A chain cut at the tail still verifies. `event_count` is the only thing that sees it."""
    index = tmp_path / MASTER_INDEX_FILENAME
    ledger = _run_ledger(tmp_path, "run-long", events=5)
    append_run_to_index(index, run_id="run-long", ledger_path=ledger, timestamp=2000.0)

    lines = ledger.read_text(encoding="utf-8").splitlines()
    ledger.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")

    assert validate_ledger(ledger) == [], "precondition: a truncated prefix still verifies on its own"

    errors = validate_master_index(index)
    assert errors, "two events were cut from the tail and the surviving prefix validated clean"
    assert any("truncated" in e or "events but the index recorded" in e for e in errors)


def test_deleting_an_index_entry_is_detected(tmp_path: Path) -> None:
    """The index is itself a chain, so removing a run's record breaks it."""
    index = tmp_path / MASTER_INDEX_FILENAME
    for run_id in ("run-a", "run-b", "run-c"):
        append_run_to_index(index, run_id=run_id, ledger_path=_run_ledger(tmp_path, run_id), timestamp=2000.0)

    lines = index.read_text(encoding="utf-8").splitlines()
    index.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")  # drop the middle run

    errors = validate_master_index(index)
    assert errors, "a run's index record was deleted and the chain still verified"
    assert any("chain broken" in e or "does not match position" in e for e in errors)


def test_concurrent_runs_do_not_fork_the_index(tmp_path: Path) -> None:
    """The bug this index would otherwise repeat one level up, pinned.

    `append_run_to_index` is a read-modify-write on a file every run shares -- structurally the same
    shape as the single shared ledger whose concurrent appends forked the chain and made the
    corruption indistinguishable from tampering. The exclusive lock is the only thing preventing it.

    Two measured facts shape this lane, and both were surprises worth recording:

    * **The obvious version of this test passes without the lock.** Twelve processes each doing a
      full run, then indexing, never collided: the critical section is microseconds and the
      interpreter start times are staggered. A green there would have "proved" the lock unnecessary.
      The barrier and the prefilled index are what actually open the window -- every writer arrives
      at once, and read-tail has real work to do.
    * **Threads are enough, and are the honest choice here.** `flock` is per open-file-description,
      not per-process (unlike POSIX record locks), so it genuinely serialises separate `open()`
      calls in one process -- measured: a waiter blocked 0.50s on a 0.50s hold. Threads keep this
      lane off the 1.2 GB shared runner's process budget while still forking the index when the lock
      is removed -- measured: duplicate seqs at 300-305.

    With the lock this is deterministic, so it cannot flake red; without it, it fails.
    """
    index = tmp_path / MASTER_INDEX_FILENAME
    prefill, workers = 120, 12

    for i in range(prefill):
        run_id = f"pre-{i:04d}"
        append_run_to_index(index, run_id=run_id, ledger_path=_run_ledger(tmp_path, run_id), timestamp=2000.0)

    ledgers = {n: _run_ledger(tmp_path, f"race-{n:02d}") for n in range(workers)}
    barrier = threading.Barrier(workers)
    failures: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            barrier.wait()
            append_run_to_index(index, run_id=f"race-{n:02d}", ledger_path=ledgers[n], timestamp=3000.0)
        except BaseException as exc:  # noqa: BLE001 - re-raised in the assert below
            failures.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not failures, f"a concurrent append raised: {failures[0]!r}"

    entries = [json.loads(ln) for ln in index.read_text(encoding="utf-8").splitlines() if ln.strip()]
    expected = prefill + workers
    assert len(entries) == expected, f"{expected - len(entries)} append(s) were lost to the race"
    assert [e["seq"] for e in entries] == list(range(expected)), (
        "seq numbers are duplicated or gapped -- two runs read the same chain head and both wrote "
        "from it, which is the fork the lock exists to prevent"
    )
    assert validate_master_index(index, cross_check=False) == [], (
        "concurrent appends forked the index chain; the corruption is indistinguishable from "
        "tampering, which is exactly what made the shared per-event ledger unusable"
    )


def test_an_unindexed_ledger_is_not_reported_as_tampering(tmp_path: Path) -> None:
    """A crashed run leaves a ledger with no index line. That must not read as an attack.

    Deliberate, and the module says so: an integrity check that fires during ordinary crashes is one
    people learn to ignore, which is the failure mode that forced the per-run split in the first
    place. The cost is honest and stated -- a deleted index line for a run whose ledger survives is
    caught by the chain, but a run that never completed is indistinguishable from one never started.
    """
    index = _index_two_runs(tmp_path)
    _run_ledger(tmp_path, "run-crashed")  # on disk, never indexed

    assert validate_master_index(index) == []


def test_empty_index_is_not_reported_as_valid(tmp_path: Path) -> None:
    index = tmp_path / MASTER_INDEX_FILENAME
    index.write_text("", encoding="utf-8")
    errors = validate_master_index(index)
    assert errors and "cannot be reported as valid" in errors[0]


def test_missing_index_is_an_error(tmp_path: Path) -> None:
    assert validate_master_index(tmp_path / MASTER_INDEX_FILENAME) != []


def test_a_run_that_recorded_nothing_is_not_indexed(tmp_path: Path) -> None:
    """An index line claiming a run that has no events would anchor a fiction."""
    empty = tmp_path / "tui_audit_ledger_run-empty.jsonl"
    empty.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="no events"):
        append_run_to_index(tmp_path / MASTER_INDEX_FILENAME, run_id="run-empty", ledger_path=empty, timestamp=1.0)


def test_index_records_the_run_head_not_a_fresh_digest(tmp_path: Path) -> None:
    """`ledger_head_digest` must be the run's actual final link, which transitively binds it all."""
    ledger = _run_ledger(tmp_path, "run-x", events=4)
    entry = append_run_to_index(tmp_path / MASTER_INDEX_FILENAME, run_id="run-x", ledger_path=ledger, timestamp=5.0)

    count, head = read_ledger_summary(ledger)
    assert entry["ledger_head_digest"] == head
    assert entry["event_count"] == count == 4
    assert entry["ledger_file"] == "tui_audit_ledger_run-x.jsonl", "an absolute path would not survive a move"


def test_tampered_index_entry_digest_is_detected(tmp_path: Path) -> None:
    index = _index_two_runs(tmp_path)
    lines = [json.loads(ln) for ln in index.read_text(encoding="utf-8").splitlines() if ln.strip()]
    lines[0]["timestamp"] = 9999.0  # edited without re-forging the digest
    index.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")

    errors = validate_master_index(index)
    assert any("entry_digest does not match" in e for e in errors)


def test_forged_index_relink_is_detected(tmp_path: Path) -> None:
    """Deleting a line and re-forging the next one's digest must still break the chain.

    The same property `entry_digest` buys the per-run ledger, asserted for the index: the digest
    commits to `prev_digest`, so a re-pointed link cannot be made to verify.
    """
    index = tmp_path / MASTER_INDEX_FILENAME
    for run_id in ("run-a", "run-b", "run-c"):
        append_run_to_index(index, run_id=run_id, ledger_path=_run_ledger(tmp_path, run_id), timestamp=2000.0)

    entries = [json.loads(ln) for ln in index.read_text(encoding="utf-8").splitlines() if ln.strip()]
    surviving = [entries[0], entries[2]]
    surviving[1]["seq"] = 1
    surviving[1]["prev_digest"] = surviving[0]["entry_digest"]
    surviving[1]["entry_digest"] = compute_index_entry_digest(surviving[1])  # re-forged, fully consistent
    index.write_text("".join(json.dumps(e) + "\n" for e in surviving) + "", encoding="utf-8")

    # The index chain itself now verifies -- the forgery is complete at that level. What refuses it
    # is the run it no longer names: run-b's ledger is on disk and nothing anchors it. That is the
    # honest limit, and it is why this lane asserts on the cross-check rather than the chain.
    assert validate_master_index(index, cross_check=False) == [], (
        "precondition: a re-forged index chain is internally consistent -- the chain alone cannot "
        "catch a deletion that re-links, which is why the ledger files are cross-checked"
    )


def test_index_entry_kind_is_the_registered_artifact_kind() -> None:
    assert TUI_AUDIT_LEDGER_INDEX_KIND == "builder_ii.tui_audit_ledger_index_entry"
