"""Canonical persisted custody for governed Goose session lifecycle evidence.

This adapter writes only beneath an already-admitted Builder-II artifact root.
Receipt files are persisted and revalidated before a hash-linked lifecycle event
may refer to them.  Compatibility mirrors elsewhere are projections, not run
truth.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.goose_receipts import (
    validate_goose_close_receipt,
    validate_goose_launch_receipt,
    validate_no_mutation_postflight,
)
from builder_ii.governance.ledger.workflow_records import artifact_ref, file_ref
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event


def goose_session_dir(artifact_root: Path, session_id: str) -> Path:
    return artifact_root.resolve() / "sessions" / session_id / "goose"


def canonical_transcript_path(artifact_root: Path, session_id: str) -> Path:
    return goose_session_dir(artifact_root, session_id) / "transcript.json"


def _persist_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing canonical Goose evidence: {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require_new(paths: tuple[Path, ...]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing canonical Goose evidence: "
            + ", ".join(str(path) for path in existing)
        )


def _validate_identity(value: dict[str, Any], session_id: str, label: str) -> None:
    if value.get("session_id") != session_id:
        raise ValueError(f"{label} session_id does not match governed run")


def persist_goose_launch(
    *, artifact_root: Path, session_id: str, launch_receipt: dict[str, Any]
) -> dict[str, Any]:
    """Persist and event-bind one governed Goose process launch."""
    errors = validate_goose_launch_receipt(launch_receipt)
    if errors:
        raise ValueError("invalid Goose launch receipt: " + "; ".join(errors))
    _validate_identity(launch_receipt, session_id, "Goose launch receipt")
    session_dir = goose_session_dir(artifact_root, session_id)
    launch_path = session_dir / "launch.json"
    _require_new((launch_path,))
    _persist_new_json(launch_path, launch_receipt)
    return append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type="goose_session_started",
        message="Governed Goose process launch recorded",
        command_surface="builder start",
        subject_refs=[
            artifact_ref(
                launch_receipt,
                path=launch_path,
                role="goose_launch_receipt",
                name="governed Goose launch",
            )
        ],
        decision_result="executed",
    )


def persist_goose_close(
    *,
    artifact_root: Path,
    session_id: str,
    launch_receipt: dict[str, Any],
    close_receipt: dict[str, Any],
    postflight: dict[str, Any],
) -> dict[str, Any]:
    """Persist exact close evidence, then append its canonical lifecycle event."""
    launch_errors = validate_goose_launch_receipt(launch_receipt)
    close_errors = validate_goose_close_receipt(close_receipt)
    postflight_errors = validate_no_mutation_postflight(postflight)
    errors = [*launch_errors, *close_errors, *postflight_errors]
    if errors:
        raise ValueError("invalid Goose close custody: " + "; ".join(errors))
    for label, value in (
        ("Goose launch receipt", launch_receipt),
        ("Goose close receipt", close_receipt),
        ("Goose postflight", postflight),
    ):
        _validate_identity(value, session_id, label)
    if close_receipt.get("launch_receipt_digest") != launch_receipt.get("digest"):
        raise ValueError("Goose close receipt does not bind the canonical launch receipt")
    if close_receipt.get("postflight_digest") != postflight.get("digest"):
        raise ValueError("Goose close receipt does not bind the canonical postflight")

    transcript_path = Path(str(close_receipt["transcript_path"]))
    expected_transcript = canonical_transcript_path(artifact_root, session_id)
    if transcript_path.resolve() != expected_transcript.resolve():
        raise ValueError("Goose close receipt transcript is outside the canonical session namespace")
    if transcript_path.is_symlink() or not transcript_path.is_file():
        raise ValueError("canonical Goose transcript is missing or is a symlink")
    transcript_digest = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
    if transcript_digest != close_receipt.get("transcript_digest"):
        raise ValueError("canonical Goose transcript digest does not match persisted bytes")

    session_dir = goose_session_dir(artifact_root, session_id)
    launch_path = session_dir / "launch.json"
    if launch_path.is_symlink() or not launch_path.is_file():
        raise ValueError("canonical Goose launch receipt is missing or is a symlink")
    try:
        persisted_launch = json.loads(launch_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"canonical Goose launch receipt is unreadable: {exc}") from exc
    if persisted_launch != launch_receipt:
        raise ValueError("canonical Goose launch receipt bytes do not match close custody")

    postflight_path = session_dir / "postflight.json"
    close_path = session_dir / "close.json"
    _require_new((postflight_path, close_path))
    _persist_new_json(postflight_path, postflight)
    _persist_new_json(close_path, close_receipt)
    return append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type="goose_session_closed",
        message="Governed Goose process close recorded",
        command_surface="builder start",
        subject_refs=[
            artifact_ref(
                launch_receipt,
                path=launch_path,
                role="goose_launch_receipt",
                name="governed Goose launch",
            ),
            artifact_ref(
                postflight,
                path=postflight_path,
                role="goose_postflight",
                name="governed Goose target postflight",
            ),
            artifact_ref(
                close_receipt,
                path=close_path,
                role="goose_close_receipt",
                name="governed Goose close",
            ),
            file_ref(
                kind="builder_ii.goose_transcript",
                path=transcript_path,
                sha256=transcript_digest,
                role="goose_transcript",
                name="canonical Goose JSON transcript",
            ),
        ],
        decision_result="executed" if close_receipt["exit_code"] == 0 and postflight["valid"] else "failed",
    )
