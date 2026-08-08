from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

import builder_ii.governance.ledger.session_ledger as session_ledger
from builder_ii.adapters.mcp.governed_call import build_read_only_policy
from builder_ii.governance.ledger.event_ledger import load_event_records, replay_events
from builder_ii.governance.ledger.session_ledger import append_session_event

SESSION = "atomic-session"


def _append(builder_root: Path, *, prefix: str = "evt") -> Path:
    return append_session_event(
        builder_root=builder_root,
        session_id=SESSION,
        event_type="mcp_call_denied",
        command_surface="builder-mcp serve",
        policy=build_read_only_policy(),
        message="bounded refusal",
        event_id_prefix=prefix,
    )


def test_tail_binds_last_event_and_wal_size(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    first = _append(builder_root, prefix="one")
    second = _append(builder_root, prefix="two")

    tail_path = builder_root / "sessions" / SESSION / ".event-tail.json"
    tail = json.loads(tail_path.read_text(encoding="utf-8"))
    assert tail["sequence"] == 2
    assert tail["event_path"] == str(second)
    assert len(tail["event_sha256"]) == 64
    wal = builder_root / "sessions" / SESSION / "events" / "events.wal"
    assert tail["wal_size"] == wal.stat().st_size
    assert first.exists() and second.exists()

    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert [event["sequence"] for event, _ in records] == [1, 2]
    assert replay_events(records, session_id=SESSION)["valid"]


def test_corrupt_tail_forces_full_replay_before_next_sequence(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    _append(builder_root, prefix="one")
    tail_path = builder_root / "sessions" / SESSION / ".event-tail.json"
    tail = json.loads(tail_path.read_text(encoding="utf-8"))
    tail["wal_size"] = 1
    tail_path.write_text(json.dumps(tail), encoding="utf-8")

    second = _append(builder_root, prefix="two")
    assert second.name.startswith("002_")
    repaired = json.loads(tail_path.read_text(encoding="utf-8"))
    assert repaired["sequence"] == 2

    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert replay_events(records, session_id=SESSION)["valid"]


def test_crash_after_event_commit_before_tail_is_recovered_without_duplicate_sequence(
    tmp_path: Path, monkeypatch: Any
) -> None:
    builder_root = tmp_path / ".builder"
    real_write_tail = session_ledger._write_tail
    calls = 0

    def fail_first_tail(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated crash after event commit")
        real_write_tail(**kwargs)

    monkeypatch.setattr(session_ledger, "_write_tail", fail_first_tail)
    with pytest.raises(OSError, match="simulated crash"):
        _append(builder_root, prefix="interrupted")

    # The event is already committed to the WAL/JSON mirror. The next append must detect that
    # the tail is absent/stale, replay, and choose sequence 2 rather than forking sequence 1.
    second = _append(builder_root, prefix="recovered")
    assert second.name.startswith("002_")
    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert [event["sequence"] for event, _ in records] == [1, 2]
    assert replay_events(records, session_id=SESSION)["valid"]


def test_concurrent_writers_form_one_linear_chain(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"

    def one(index: int) -> str:
        return str(_append(builder_root, prefix=f"worker{index}"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(one, range(32)))

    assert len(set(paths)) == 32
    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert len(records) == 32
    assert [event["sequence"] for event, _ in records] == list(range(1, 33))
    replay = replay_events(records, session_id=SESSION)
    assert replay["valid"], replay["errors"]


def test_sidecar_writes_leave_no_temporary_file_after_success(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    _append(builder_root)
    session_dir = builder_root / "sessions" / SESSION
    leftovers = [path for path in session_dir.rglob("*.tmp") if path.is_file()]
    assert leftovers == []
