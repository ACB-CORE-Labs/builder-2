from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

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
    discard_transcript_export,
    install_transcript_export,
    persist_goose_close,
    persist_goose_launch,
    prepare_transcript_export,
    validate_goose_session_custody,
)
from builder_ii.core.run_view import project_run_view
from builder_ii.governance.ledger.event_ledger import (
    load_event_records,
    validate_event_chain_integrity,
    validate_event_record,
)
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event


def _evidence(tmp_path: Path, session_id: str):
    artifact_root = tmp_path / "artifacts"
    launch = create_goose_launch_receipt(
        session_id,
        "builder",
        "patch_planner",
        42,
        "2026-08-24T00:00:00+00:00",
        {"runtime": "goose_governed", "target_root": str(tmp_path / "target")},
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


def test_active_goose_launch_is_valid_before_close_material_exists(tmp_path: Path) -> None:
    session_id = "goose-run-active"
    artifact_root, launch, _, _, transcript = _evidence(tmp_path, session_id)
    transcript.unlink()
    persist_goose_launch(artifact_root=artifact_root, session_id=session_id, launch_receipt=launch)

    assert validate_goose_session_custody(artifact_root, session_id) == []
    assert project_run_view(artifact_root, session_id=session_id).evidence_health == "VERIFIED"


def test_failed_transcript_export_cleanup_allows_retry_without_overwrite(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    session_id = "goose-export-retry"
    first = prepare_transcript_export(artifact_root, session_id)
    first.write_text("partial", encoding="utf-8")
    discard_transcript_export(first)
    assert not first.exists()
    assert not canonical_transcript_path(artifact_root, session_id).exists()

    retry = prepare_transcript_export(artifact_root, session_id)
    retry.write_text('{"messages": []}\n', encoding="utf-8")
    installed = install_transcript_export(
        artifact_root=artifact_root,
        session_id=session_id,
        export_path=retry,
    )

    assert installed == canonical_transcript_path(artifact_root, session_id)
    assert installed.read_text(encoding="utf-8") == '{"messages": []}\n'
    assert not retry.exists()


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
    assert any("canonical Goose launch receipt" in error for error in view.errors)


def test_goose_custody_refuses_symlinked_namespace_and_escaping_session_id(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (artifact_root / "sessions").symlink_to(outside, target_is_directory=True)
    launch = create_goose_launch_receipt(
        "safe-session",
        "builder",
        "patch_planner",
        42,
        "2026-08-24T00:00:00+00:00",
        {"runtime": "goose_governed", "target_root": str(tmp_path / "target")},
    )

    with pytest.raises(OSError):
        persist_goose_launch(
            artifact_root=artifact_root,
            session_id="safe-session",
            launch_receipt=launch,
        )
    assert list(outside.rglob("*")) == []

    escaping_launch = create_goose_launch_receipt(
        "../escape",
        "builder",
        "patch_planner",
        42,
        "2026-08-24T00:00:00+00:00",
        {"runtime": "goose_governed", "target_root": str(tmp_path / "target")},
    )
    with pytest.raises(ValueError, match="session identity"):
        persist_goose_launch(
            artifact_root=tmp_path / "fresh-artifacts",
            session_id="../escape",
            launch_receipt=escaping_launch,
        )


def test_run_view_reconstructs_cross_artifact_goose_bindings(tmp_path: Path) -> None:
    session_id = "goose-run-reconstruct"
    artifact_root, launch, close, postflight, _ = _evidence(tmp_path, session_id)
    persist_goose_launch(artifact_root=artifact_root, session_id=session_id, launch_receipt=launch)
    persist_goose_close(
        artifact_root=artifact_root,
        session_id=session_id,
        launch_receipt=launch,
        close_receipt=close,
        postflight=postflight,
    )
    close_path = artifact_root / "sessions" / session_id / "goose" / "close.json"
    foreign_close = create_goose_close_receipt(
        session_id,
        "f" * 64,
        postflight["digest"],
        close["transcript_path"],
        close["transcript_digest"],
        close["end_time"],
        0,
    )
    close_path.write_text(json.dumps(foreign_close, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert any(
        "does not bind canonical launch receipt" in error
        for error in validate_goose_session_custody(artifact_root, session_id)
    )
    view = project_run_view(artifact_root, session_id=session_id)
    assert view.evidence_health == "CORRUPT"
    assert any("does not bind canonical launch receipt" in error for error in view.errors)


def test_postflight_validator_rejects_unaccounted_mutation(tmp_path: Path) -> None:
    postflight = create_no_mutation_postflight(
        "partition-test",
        str(tmp_path / "target"),
        "2026-08-24T00:00:00+00:00",
        "2026-08-24T00:01:00+00:00",
        1,
        ["changed.txt"],
        unexplained_mutations=[],
    )

    assert (
        "detected mutations must be exactly partitioned into approved and unexplained mutations"
        in validate_no_mutation_postflight(postflight)
    )


@pytest.mark.parametrize(
    "event_types",
    [
        ("goose_session_started", "goose_session_started"),
        ("goose_session_started", "goose_session_closed"),
    ],
)
def test_runtime_event_append_is_lossless_under_concurrency(
    tmp_path: Path, event_types: tuple[str, str]
) -> None:
    events_dir = tmp_path / "events"
    barrier = Barrier(2)

    def append(event_type: str):
        barrier.wait(timeout=5)
        return append_runtime_event(
            events_dir=events_dir,
            session_id="concurrent-run",
            event_type=event_type,
            message="concurrent lesion",
            command_surface="builder start",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(append, event_types))

    assert {record["sequence"] for record in records} == {1, 2}
    assert len({record["event_id"] for record in records}) == 2
    loaded = load_event_records(events_dir)
    assert len(loaded) == 2
    assert validate_event_chain_integrity(events_dir)["valid"] is True
