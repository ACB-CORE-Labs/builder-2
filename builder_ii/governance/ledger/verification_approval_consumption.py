"""Canonical single-use claims for verification execution approvals."""

from __future__ import annotations

import datetime
import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import digest_jsonable

CONSUMPTION_KIND = "builder_ii.verification_approval_consumption"
CONSUMPTION_SCHEMA_VERSION = 1


class ApprovalConsumptionError(RuntimeError):
    """Approval consumption evidence is corrupt or the approval was already used."""


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _is_aware_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def validate_consumption_record(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["approval consumption record must be an object"]
    errors: list[str] = []
    if record.get("kind") != CONSUMPTION_KIND:
        errors.append("kind is invalid")
    if record.get("schema_version") != CONSUMPTION_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if not isinstance(record.get("ledger_index"), int) or record.get("ledger_index", 0) < 1:
        errors.append("ledger_index must be a positive integer")
    for field in ("approval_id", "approval_digest", "plan_digest"):
        if not _is_sha256(record.get(field)):
            errors.append(f"{field} must be a SHA-256 hex digest")
    previous = record.get("previous_record_digest")
    if previous is not None and not _is_sha256(previous):
        errors.append("previous_record_digest must be null or a SHA-256 hex digest")
    if record.get("state") != "CONSUMED_BEFORE_EXECUTION":
        errors.append("state is invalid")
    if not _is_aware_timestamp(record.get("consumed_at")):
        errors.append("consumed_at must be a valid timezone-aware timestamp")
    digest = record.get("verification_approval_consumption_digest")
    if not _is_sha256(digest):
        errors.append("verification_approval_consumption_digest must be a SHA-256 hex digest")
    elif digest != digest_jsonable(record, digest_key="verification_approval_consumption_digest"):
        errors.append("verification_approval_consumption_digest drift detected")
    return errors


def load_consumption_chain(root: Path) -> list[dict[str, Any]]:
    if root.is_symlink():
        raise ApprovalConsumptionError("approval consumption root must not be a symlink")
    if root.exists() and not root.is_dir():
        raise ApprovalConsumptionError("approval consumption root must be a directory")
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")) if root.exists() else []:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApprovalConsumptionError(f"corrupt approval consumption record {path.name}: {exc}") from exc
        errors = validate_consumption_record(record)
        if errors:
            raise ApprovalConsumptionError(
                f"corrupt approval consumption record {path.name}: {'; '.join(errors)}"
            )
        records.append(record)
    records.sort(key=lambda item: item["ledger_index"])
    previous: str | None = None
    seen_approval_ids: set[str] = set()
    seen_approval_digests: set[str] = set()
    for expected_index, record in enumerate(records, start=1):
        if record["ledger_index"] != expected_index:
            raise ApprovalConsumptionError("approval consumption ledger index is discontinuous")
        if record.get("previous_record_digest") != previous:
            raise ApprovalConsumptionError("approval consumption ledger chain is discontinuous")
        approval_id = record["approval_id"]
        approval_digest = record["approval_digest"]
        if approval_id in seen_approval_ids or approval_digest in seen_approval_digests:
            raise ApprovalConsumptionError("approval consumption ledger contains a duplicate approval claim")
        seen_approval_ids.add(approval_id)
        seen_approval_digests.add(approval_digest)
        previous = record["verification_approval_consumption_digest"]
    return records


def assert_consumption_chain_valid(root: Path) -> None:
    load_consumption_chain(root)


def _open_claim_lock(root: Path) -> int:
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ApprovalConsumptionError(f"approval consumption root could not be created: {exc}") from exc
    if root.is_symlink() or not root.is_dir():
        raise ApprovalConsumptionError("approval consumption root must be a non-symlink directory")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(root / ".claim.lock", flags, 0o600)
    except OSError as exc:
        raise ApprovalConsumptionError(f"approval consumption claim lock could not be opened: {exc}") from exc


def _fsync_directory(root: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(root, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def consume_approval(
    *, root: Path, approval: dict[str, Any], plan: dict[str, Any], now: datetime.datetime
) -> dict[str, Any]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ApprovalConsumptionError("approval consumption time must be timezone-aware")
    lock_fd = _open_claim_lock(root)
    locked = False
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        locked = True
        records = load_consumption_chain(root)
        approval_digest = str(approval.get("verification_execution_approval_digest", ""))
        approval_id = str(approval.get("approval_id", ""))
        if any(
            record.get("approval_digest") == approval_digest or record.get("approval_id") == approval_id
            for record in records
        ):
            raise ApprovalConsumptionError("verification execution approval has already been consumed")
        record: dict[str, Any] = {
            "kind": CONSUMPTION_KIND,
            "schema_version": CONSUMPTION_SCHEMA_VERSION,
            "ledger_index": len(records) + 1,
            "previous_record_digest": (
                records[-1]["verification_approval_consumption_digest"] if records else None
            ),
            "approval_id": approval_id,
            "approval_digest": approval_digest,
            "plan_digest": str(plan.get("verification_execution_plan_digest", "")),
            "consumed_at": now.astimezone(datetime.timezone.utc).isoformat(),
            "state": "CONSUMED_BEFORE_EXECUTION",
        }
        record["verification_approval_consumption_digest"] = digest_jsonable(
            record, digest_key="verification_approval_consumption_digest"
        )
        errors = validate_consumption_record(record)
        if errors:
            raise ApprovalConsumptionError("generated approval consumption record is invalid: " + "; ".join(errors))

        path = root / f"{record['ledger_index']:06d}-{approval_digest}.json"
        temporary = root / f".claim-{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ApprovalConsumptionError("verification execution approval has already been consumed") from exc
            _fsync_directory(root)
        finally:
            temporary.unlink(missing_ok=True)
        return record
    except ApprovalConsumptionError:
        raise
    except OSError as exc:
        raise ApprovalConsumptionError(
            f"approval consumption claim could not be durably recorded: {exc}"
        ) from exc
    finally:
        try:
            if locked:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
