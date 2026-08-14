"""W0.2 — unified runtime event ledger append + chain integrity."""

from __future__ import annotations

from pathlib import Path

from builder_ii.governance.ledger.event_ledger import (
    validate_event_chain_integrity,
    validate_event_record,
)
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event


def test_append_runtime_event_hash_chain(tmp_path: Path) -> None:
    events_dir = tmp_path / "events"
    e1 = append_runtime_event(
        events_dir=events_dir,
        session_id="sess-1",
        event_type="model_call_executed",
        message="first",
        command_surface="test",
    )
    assert validate_event_record(e1) == []
    e2 = append_runtime_event(
        events_dir=events_dir,
        session_id="sess-1",
        event_type="wrp_gateway_node",
        message="second",
        command_surface="test",
    )
    assert e2["sequence"] == 2
    assert e2["previous_event_sha256"] is not None
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2
    assert report["independent_observer"] is False


def test_chain_integrity_detects_break(tmp_path: Path) -> None:
    events_dir = tmp_path / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id="sess-1",
        event_type="model_call_executed",
        message="first",
        command_surface="test",
    )
    append_runtime_event(
        events_dir=events_dir,
        session_id="sess-1",
        event_type="model_call_failed",
        message="second",
        command_surface="test",
    )
    # Prefer real on-disk JSON files (WAL may synthesize non-existent paths).
    import json

    json_files = sorted(p for p in events_dir.glob("*.json") if p.name != "events.wal")
    assert len(json_files) >= 2
    # Second file by sequence prefix
    bad_path = json_files[1]
    data = json.loads(bad_path.read_text(encoding="utf-8"))
    data["previous_event_sha256"] = "f" * 64
    if isinstance(data.get("previous_event_ref"), dict):
        data["previous_event_ref"]["sha256"] = "f" * 64
    bad_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    # Remove WAL so integrity reads the corrupted JSON files only
    wal = events_dir / "events.wal"
    if wal.exists():
        wal.unlink()
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is False
    assert report["errors"]
