from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from builder_ii.adapters.goose.goose_receipts import (
    create_goose_close_receipt,
    create_goose_launch_receipt,
    create_no_mutation_postflight,
    validate_goose_close_receipt,
    validate_no_mutation_postflight,
)
from builder_ii.adapters.goose.goose_session_custody import (
    canonical_transcript_path,
    persist_goose_close,
    persist_goose_launch,
)
from builder_ii.core.run_view import project_run_view
from builder_ii.governance.ledger.event_ledger import (
    load_event_records,
    validate_event_chain_integrity,
    validate_event_record,
)


def _evidence(tmp_path: Path, session_id: str):
    artifact_root = tmp_path / "artifacts"
    launch = create_goose_launch_receipt(
        session_id,
        "builder",
        "patch_planner",
        42,
        "2026-08-24T00:00:00+00:00",
        {"runtime": "goose_governed"},
    )
    transcript = canonical_transcript_path(artifact_root, session_id)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text('{"messages": []}\n', encoding="utf-8")
    transcript_digest = hashlib.sha256(transcript.read_bytes()).hexdigest()
    postflight = create_no_mutation_postflight(
        session_id,
        str(tmp_path / "target"),
        "2026-08-24T00:00:00+00:00",
        "2026-08-24T00:01:00+00:00",
        1,
        [],
    )
    close = create_goose_close_receipt(
        session_id,
        launch["digest"],
        postflight["digest"],
        str(transcript),
        transcript_digest,
        "2026-08-24T00:01:00+00:00",
        0,
    )
    return artifact_root, launch, close, postflight, transcript


def test_goose_start_and_close_share_one_valid_run_event_chain(tmp_path: Path) -> None:
    session_id = "goose-run-1"
    artifact_root, launch, close, postflight, _ = _evidence(tmp_path, session_id)

    started = persist_goose_launch(
        artifact_root=artifact_root,
        session_id=session_id,
        launch_receipt=launch,
    )
    closed = persist_goose_close(
        artifact_root=artifact_root,
        session_id=session_id,
        launch_receipt=launch,
        close_receipt=close,
        postflight=postflight,
    )

    events_dir = artifact_root / "sessions" / session_id / "events"
    records = load_event_records(events_dir)
    assert [record[0]["event_type"] for record in records] == [
        "goose_session_started",
        "goose_session_closed",
    ]
    assert started["sequence"] == 1
    assert closed["sequence"] == 2
    assert validate_event_record(started) == []
    assert validate_event_record(closed) == []
    assert validate_event_chain_integrity(events_dir)["valid"] is True
    assert {ref["role"] for ref in closed["subject_refs"]} == {
        "goose_launch_receipt",
        "goose_postflight",
        "goose_close_receipt",
        "goose_transcript",
    }
    goose_dir = artifact_root / "sessions" / session_id / "goose"
    assert (goose_dir / "launch.json").is_file()
    assert (goose_dir / "postflight.json").is_file()
    assert (goose_dir / "close.json").is_file()
    view = project_run_view(artifact_root, session_id=session_id)
    assert view.evidence_health == "VERIFIED"
    assert not any("Goose evidence must have" in error for error in view.errors)


def test_goose_close_refuses_transcript_drift_before_persisting_close_event(tmp_path: Path) -> None:
    session_id = "goose-run-drift"
    artifact_root, launch, close, postflight, transcript = _evidence(tmp_path, session_id)
    persist_goose_launch(artifact_root=artifact_root, session_id=session_id, launch_receipt=launch)
    transcript.write_text('{"messages": ["changed"]}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="transcript digest"):
        persist_goose_close(
            artifact_root=artifact_root,
            session_id=session_id,
            launch_receipt=launch,
            close_receipt=close,
            postflight=postflight,
        )

    goose_dir = artifact_root / "sessions" / session_id / "goose"
    assert not (goose_dir / "postflight.json").exists()
    assert not (goose_dir / "close.json").exists()
    records = load_event_records(artifact_root / "sessions" / session_id / "events")
    assert [record[0]["event_type"] for record in records] == ["goose_session_started"]


def test_goose_close_and_postflight_validators_reject_digest_tampering(tmp_path: Path) -> None:
    _, _, close, postflight, _ = _evidence(tmp_path, "goose-run-validators")
    close["exit_code"] = 9
    postflight["files_checked"] = 99

    assert "digest does not match receipt content" in validate_goose_close_receipt(close)
    assert "digest does not match postflight content" in validate_no_mutation_postflight(postflight)


def test_run_view_rejects_unbound_goose_close_receipt(tmp_path: Path) -> None:
    session_id = "goose-run-unbound"
    artifact_root, _, close, _, _ = _evidence(tmp_path, session_id)
    goose_dir = artifact_root / "sessions" / session_id / "goose"
    (goose_dir / "close.json").write_text(
        json.dumps(close, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    view = project_run_view(artifact_root, session_id=session_id)

    assert view.evidence_health == "CORRUPT"
    assert any("Goose evidence must have exactly one canonical goose_session_closed binding" in error for error in view.errors)
