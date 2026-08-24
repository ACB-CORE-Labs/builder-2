"""Canonical persisted custody for governed Goose session lifecycle evidence.

This adapter writes only beneath an already-admitted Builder-II artifact root.
Receipt files are persisted and revalidated before a hash-linked lifecycle event
may refer to them.  Compatibility mirrors elsewhere are projections, not run
truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.goose_receipts import (
    validate_goose_close_receipt,
    validate_goose_launch_receipt,
    validate_no_mutation_postflight,
)
from builder_ii.governance.ledger.event_ledger import load_event_records, validate_event_chain_integrity
from builder_ii.governance.ledger.workflow_records import artifact_ref, file_ref
from builder_ii.lifecycle.candidate.runtime_event_append import (
    append_runtime_event,
    open_directory_nofollow,
)

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("invalid canonical Goose session identity")


def goose_session_dir(artifact_root: Path, session_id: str) -> Path:
    _validate_session_id(session_id)
    normalized_root = Path(os.path.abspath(artifact_root))
    return normalized_root / "sessions" / session_id / "goose"


def canonical_transcript_path(artifact_root: Path, session_id: str) -> Path:
    return goose_session_dir(artifact_root, session_id) / "transcript.json"


def _persist_new_json(path: Path, value: dict[str, Any]) -> None:
    parent_fd = open_directory_nofollow(path.parent)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        output_fd = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        try:
            payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
            with os.fdopen(output_fd, "wb", closefd=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(output_fd)
    finally:
        os.close(parent_fd)


def _require_new(paths: tuple[Path, ...]) -> None:
    existing = [path for path in paths if path.exists() or path.is_symlink()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing canonical Goose evidence: "
            + ", ".join(str(path) for path in existing)
        )


def _validate_identity(value: dict[str, Any], session_id: str, label: str) -> None:
    if value.get("session_id") != session_id:
        raise ValueError(f"{label} session_id does not match governed run")


def prepare_transcript_export(artifact_root: Path, session_id: str) -> Path:
    """Create a protected temporary transcript target inside the admitted session directory."""
    session_dir = goose_session_dir(artifact_root, session_id)
    directory_fd = open_directory_nofollow(session_dir)
    try:
        fd, path = tempfile.mkstemp(prefix=".transcript-export-", suffix=".json", dir=session_dir)
        os.fchmod(fd, 0o600)
        os.close(fd)
        return Path(path)
    finally:
        os.close(directory_fd)


def install_transcript_export(
    *, artifact_root: Path, session_id: str, export_path: Path
) -> Path:
    """Install a regular temporary export at the canonical path without replacement."""
    session_dir = goose_session_dir(artifact_root, session_id)
    if export_path.parent != session_dir or not export_path.name.startswith(".transcript-export-"):
        raise ValueError("Goose transcript export is outside the protected session directory")
    info = export_path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Goose transcript export must be a regular file")
    destination = canonical_transcript_path(artifact_root, session_id)
    directory_fd = open_directory_nofollow(session_dir)
    try:
        os.link(
            export_path.name,
            destination.name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        os.unlink(export_path.name, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    return destination


def discard_transcript_export(export_path: Path) -> None:
    """Remove only the protected temporary export produced by this adapter."""
    if export_path.name.startswith(".transcript-export-"):
        try:
            export_path.unlink()
        except FileNotFoundError:
            pass


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        if path.is_symlink() or not path.is_file():
            return None, [f"{label} is missing or is a symlink"]
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{label} is unreadable: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be a JSON object"]
    return value, []


def validate_goose_session_custody(artifact_root: Path, session_id: str) -> list[str]:
    """Independently reconstruct the exact canonical Goose lifecycle quartet and events."""
    try:
        session_dir = goose_session_dir(artifact_root, session_id)
        directory_fd = open_directory_nofollow(session_dir, create=False)
        os.close(directory_fd)
    except (OSError, ValueError) as exc:
        return [f"canonical Goose session namespace is invalid: {exc}"]

    launch_path = session_dir / "launch.json"
    postflight_path = session_dir / "postflight.json"
    close_path = session_dir / "close.json"
    transcript_path = session_dir / "transcript.json"
    launch, errors = _load_json(launch_path, "canonical Goose launch receipt")
    if launch is not None:
        errors.extend(validate_goose_launch_receipt(launch))
        if launch.get("session_id") != session_id:
            errors.append("canonical Goose launch session_id does not match run")
        target_root = (launch.get("evidence") or {}).get("target_root")
        if not isinstance(target_root, str) or not target_root:
            errors.append("Goose launch receipt does not bind target_root")

    events_dir = session_dir.parent / "events"
    integrity = validate_event_chain_integrity(events_dir)
    if not integrity.get("valid"):
        errors.extend(str(error) for error in integrity.get("errors", []))
    events = [event for event, _ in load_event_records(events_dir)]
    if launch is not None:
        start_matches = [
            (event, ref)
            for event in events
            if event.get("event_type") == "goose_session_started"
            for ref in event.get("subject_refs", [])
            if isinstance(ref, dict)
            and ref.get("role") == "goose_launch_receipt"
            and ref.get("path") == str(launch_path)
        ]
        if len(start_matches) != 1:
            errors.append(f"{launch_path}: expected exactly one goose_session_started binding")
        elif (
            start_matches[0][0].get("session_id") != session_id
            or start_matches[0][0].get("command_surface") != "builder start"
            or start_matches[0][1].get("kind") != launch.get("kind")
            or start_matches[0][1].get("sha256")
            != artifact_ref(launch, path=launch_path, role="goose_launch_receipt")["sha256"]
        ):
            errors.append(f"{launch_path}: goose_session_started binding does not match canonical custody")

    close_material_present = any(
        path.exists() or path.is_symlink() for path in (postflight_path, close_path, transcript_path)
    )
    if not close_material_present:
        return list(dict.fromkeys(errors))

    postflight, post_errors = _load_json(postflight_path, "canonical Goose postflight")
    close, close_errors = _load_json(close_path, "canonical Goose close receipt")
    errors.extend(post_errors)
    errors.extend(close_errors)
    if postflight is not None:
        errors.extend(validate_no_mutation_postflight(postflight))
    if close is not None:
        errors.extend(validate_goose_close_receipt(close))
    if errors or launch is None or postflight is None or close is None:
        return list(dict.fromkeys(errors))
    for label, value in (("launch", launch), ("postflight", postflight), ("close", close)):
        if value.get("session_id") != session_id:
            errors.append(f"canonical Goose {label} session_id does not match run")
    if close.get("launch_receipt_digest") != launch.get("digest"):
        errors.append("Goose close receipt does not bind canonical launch receipt")
    if close.get("postflight_digest") != postflight.get("digest"):
        errors.append("Goose close receipt does not bind canonical postflight")
    target_root = (launch.get("evidence") or {}).get("target_root")
    if not isinstance(target_root, str) or not target_root:
        errors.append("Goose launch receipt does not bind target_root")
    elif postflight.get("target_root") != target_root:
        errors.append("Goose postflight target_root does not match launch custody")
    if close.get("transcript_path") != str(transcript_path):
        errors.append("Goose close receipt does not name the canonical transcript")
    try:
        if transcript_path.is_symlink() or not transcript_path.is_file():
            errors.append("canonical Goose transcript is missing or is a symlink")
        elif hashlib.sha256(transcript_path.read_bytes()).hexdigest() != close.get("transcript_digest"):
            errors.append("canonical Goose transcript digest does not match persisted bytes")
    except OSError as exc:
        errors.append(f"canonical Goose transcript is unreadable: {exc}")

    requirements = (
        (launch_path, launch, "goose_launch_receipt", "goose_session_closed"),
        (postflight_path, postflight, "goose_postflight", "goose_session_closed"),
        (close_path, close, "goose_close_receipt", "goose_session_closed"),
    )
    for path, artifact, role, event_type in requirements:
        matches = [
            (event, ref)
            for event in events
            if event.get("event_type") == event_type
            for ref in event.get("subject_refs", [])
            if isinstance(ref, dict)
            and ref.get("role") == role
            and ref.get("path") == str(path)
        ]
        if len(matches) != 1:
            errors.append(f"{path}: expected exactly one {event_type} {role} binding")
        elif (
            matches[0][0].get("session_id") != session_id
            or matches[0][0].get("command_surface") != "builder start"
            or matches[0][1].get("kind") != artifact.get("kind")
            or matches[0][1].get("sha256") != artifact_ref(artifact, path=path, role=role)["sha256"]
        ):
            errors.append(f"{path}: {event_type} binding does not match canonical custody")
    close_events = [event for event in events if event.get("event_type") == "goose_session_closed"]
    if len(close_events) == 1:
        transcript_refs = [
            ref
            for ref in close_events[0].get("subject_refs", [])
            if isinstance(ref, dict) and ref.get("role") == "goose_transcript"
        ]
        if len(transcript_refs) != 1 or transcript_refs[0].get("path") != str(transcript_path) or transcript_refs[0].get("sha256") != close.get("transcript_digest"):
            errors.append("Goose close event does not bind the exact canonical transcript")
    else:
        errors.append("canonical Goose custody requires exactly one close event")
    return list(dict.fromkeys(errors))


def persist_goose_launch(
    *, artifact_root: Path, session_id: str, launch_receipt: dict[str, Any]
) -> dict[str, Any]:
    """Persist and event-bind one governed Goose process launch."""
    errors = validate_goose_launch_receipt(launch_receipt)
    if errors:
        raise ValueError("invalid Goose launch receipt: " + "; ".join(errors))
    _validate_identity(launch_receipt, session_id, "Goose launch receipt")
    target_root = (launch_receipt.get("evidence") or {}).get("target_root")
    if not isinstance(target_root, str) or not target_root:
        raise ValueError("canonical Goose launch receipt must bind target_root")
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
    if transcript_path != expected_transcript:
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
    event = append_runtime_event(
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
    custody_errors = validate_goose_session_custody(artifact_root, session_id)
    if custody_errors:
        raise ValueError("persisted Goose close custody is invalid: " + "; ".join(custody_errors))
    return event
