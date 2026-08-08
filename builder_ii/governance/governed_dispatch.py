"""Canonical dispatch plan and one-shot authorization ceremony.

STRATUM and direct CLIs must not carry separate meanings of "the operator said start".
This module is the shared non-UI application boundary:

``dispatch plan -> ratification decision -> dispatch authorization -> consume``

A dispatch authorization permits exactly one attempt to start exactly one already-governed
unit of work. It does **not** authorize any effect inside that work: tool policy, HITL patch
approval, candidate approval, process-control, and postflight checks remain independent at
their own boundaries.

Auto-ratification only relocates the pause. Both manual and standing-grant paths append the
ratification ledger before the authorization artifact exists, and both produce the same
subject-bound authorization schema. If evidence cannot be written, no authorization exists
and the executing CLI has nothing it can lawfully consume.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from builder_ii.core.atomic_artifacts import atomic_write_json
from builder_ii.governance.authority import get_command_record
from builder_ii.governance.ledger.ratification_ledger import validate_ratification_ledger
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.governance.ratification_dispatch import (
    DispatchRatification,
    STATUS_APPROVAL_ARTIFACT_REQUIRED,
    STATUS_AUTO,
    STATUS_PROMPT,
    record_auto_ratified,
    record_manual_ratified,
    resolve_dispatch_ratification,
)
from builder_ii.governance.ratification_grants import resolve_ratification_root

DISPATCH_PLAN_KIND = "builder_ii.governed_dispatch_plan"
DISPATCH_AUTHORIZATION_KIND = "builder_ii.governed_dispatch_authorization"
DISPATCH_CONSUMPTION_KIND = "builder_ii.governed_dispatch_consumption"
SCHEMA_VERSION = 1
DEFAULT_AUTHORIZATION_TTL_SECONDS = 600

DecisionMode = Literal[
    "standing_ratification_grant",
    "manual_operator_confirmation",
]


class DispatchAuthorizationError(RuntimeError):
    """The requested dispatch has no valid subject-bound authorization."""


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    except OSError as exc:
        raise DispatchAuthorizationError(f"dispatch subject is unreadable: {path}: {exc}") from exc
    return hasher.hexdigest()


def _content_addressed_write(directory: Path, artifact: dict[str, Any]) -> tuple[Path, str]:
    digest = canonical_digest(artifact)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.json"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DispatchAuthorizationError(f"existing content-addressed artifact is unreadable: {path}: {exc}") from exc
        if not isinstance(existing, dict) or canonical_digest(existing) != digest:
            raise DispatchAuthorizationError(
                f"content-addressed artifact path contains unexpected bytes: {path}"
            )
        return path, digest
    atomic_write_json(path, artifact)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(persisted, dict) or canonical_digest(persisted) != digest:
        raise DispatchAuthorizationError(f"persisted artifact digest mismatch: {path}")
    return path, digest


def build_dispatch_plan(
    *,
    builder_root: Path,
    command: str,
    point_id: str,
    manifest_path: Path,
    task: str,
    target_root: Path,
    requested_effects: tuple[str, ...],
    governed_apply_enabled: bool = False,
) -> tuple[dict[str, Any], Path]:
    """Persist the immutable subject the operator/grant will ratify.

    The raw task text is deliberately absent. The executing CLI receives the task separately
    and must prove its digest equals this plan before consuming authorization.
    """
    cleaned_task = task.strip()
    if not cleaned_task:
        raise DispatchAuthorizationError("dispatch plan requires a non-empty task")
    manifest = Path(manifest_path).expanduser().resolve()
    if not manifest.is_file():
        raise DispatchAuthorizationError(f"dispatch manifest not found: {manifest}")
    target = Path(target_root).expanduser().resolve()

    record = get_command_record(command)
    if record is None:
        raise DispatchAuthorizationError(f"command has no authority record: {command}")
    if record.authority_is_inherited:
        raise DispatchAuthorizationError(
            f"dispatch command authority is inherited from {record.inherited_from!r}; refusing it as evidence"
        )
    authority_snapshot = asdict(record)

    plan: dict[str, Any] = {
        "kind": DISPATCH_PLAN_KIND,
        "schema_version": SCHEMA_VERSION,
        "plan_state": "PLANNED_ONLY",
        "command": command,
        "ratification_point_id": point_id,
        "manifest_path": str(manifest),
        "manifest_sha256": _sha256_file(manifest),
        "task_sha256": hashlib.sha256(cleaned_task.encode("utf-8")).hexdigest(),
        "target_root": str(target),
        "requested_effects": list(requested_effects),
        "governed_apply_enabled": bool(governed_apply_enabled),
        "authority_record_sha256": canonical_digest(authority_snapshot),
        "governance": {
            "artifact_is_authority": False,
            "grants_internal_effect_authority": False,
            "human_approval_mint": False,
        },
    }
    path, _ = _content_addressed_write(Path(builder_root) / "dispatch" / "plans", plan)
    return plan, path


def load_dispatch_plan(path: Path) -> dict[str, Any]:
    candidate = Path(path)
    try:
        plan = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DispatchAuthorizationError(f"dispatch plan is unreadable: {candidate}: {exc}") from exc
    if not isinstance(plan, dict) or plan.get("kind") != DISPATCH_PLAN_KIND:
        raise DispatchAuthorizationError("dispatch plan has the wrong kind")
    if plan.get("schema_version") != SCHEMA_VERSION:
        raise DispatchAuthorizationError("dispatch plan schema version is unsupported")
    digest = canonical_digest(plan)
    if candidate.stem != digest:
        raise DispatchAuthorizationError("dispatch plan path is not content-addressed to its bytes")
    manifest = Path(str(plan.get("manifest_path", "")))
    if _sha256_file(manifest) != plan.get("manifest_sha256"):
        raise DispatchAuthorizationError("dispatch manifest bytes changed after the plan was minted")
    record = get_command_record(str(plan.get("command", "")))
    if record is None or record.authority_is_inherited:
        raise DispatchAuthorizationError("dispatch command no longer has declared authority")
    if canonical_digest(asdict(record)) != plan.get("authority_record_sha256"):
        raise DispatchAuthorizationError("command authority changed after the dispatch plan was minted")
    return plan


def resolve_plan_ratification(
    plan: dict[str, Any], *, ratification_root: Path | None = None
) -> DispatchRatification:
    point_id = str(plan.get("ratification_point_id", ""))
    return resolve_dispatch_ratification(point_id, root=ratification_root)


def authorize_dispatch(
    *,
    plan_path: Path,
    actor: str,
    decision_mode: DecisionMode,
    ratification_root: Path | None = None,
    resolution: DispatchRatification | None = None,
    because: str = "operator confirmed the exact dispatch plan",
    ttl_seconds: int = DEFAULT_AUTHORIZATION_TTL_SECONDS,
) -> tuple[dict[str, Any], Path]:
    """Record the ratification first, then mint a one-shot subject authorization."""
    if ttl_seconds <= 0:
        raise DispatchAuthorizationError("dispatch authorization TTL must be positive")
    plan = load_dispatch_plan(plan_path)
    point_id = str(plan["ratification_point_id"])
    root = resolve_ratification_root(ratification_root)

    if decision_mode == "standing_ratification_grant":
        resolved = resolution or resolve_dispatch_ratification(point_id, root=root)
        if resolved.status != STATUS_AUTO:
            raise DispatchAuthorizationError(
                f"standing-grant authorization requires AUTO resolution, got {resolved.status}"
            )
        ratification_entry = record_auto_ratified(resolved, actor=actor, root=root)
        grant_digest = resolved.grant_digest
    elif decision_mode == "manual_operator_confirmation":
        current = resolution or resolve_dispatch_ratification(point_id, root=root)
        if current.status == STATUS_APPROVAL_ARTIFACT_REQUIRED:
            raise DispatchAuthorizationError(current.because)
        # A manual answer remains acceptable if a grant also exists: the human chose to pause
        # anyway. It never turns an approval-artifact-required point into a prompt.
        ratification_entry = record_manual_ratified(
            point_id,
            actor=actor,
            because=because or current.because,
            root=root,
        )
        grant_digest = None
    else:  # pragma: no cover - Literal plus runtime guard
        raise DispatchAuthorizationError(f"unsupported decision mode: {decision_mode}")

    ledger_errors = validate_ratification_ledger(root)
    if ledger_errors:
        raise DispatchAuthorizationError(
            f"ratification ledger failed validation after recording dispatch: {ledger_errors}"
        )

    now = datetime.now(timezone.utc)
    authorization: dict[str, Any] = {
        "kind": DISPATCH_AUTHORIZATION_KIND,
        "schema_version": SCHEMA_VERSION,
        "authorization_state": "SUBJECT_BOUND_ONE_SHOT",
        "plan_ref": {
            "kind": DISPATCH_PLAN_KIND,
            "path": str(Path(plan_path).resolve()),
            "sha256": canonical_digest(plan),
        },
        "decision_mode": decision_mode,
        "actor": actor,
        "grant_digest": grant_digest,
        "ratification_entry_digest": ratification_entry["entry_digest"],
        "ratification_entry_seq": ratification_entry["seq"],
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
        "nonce": uuid.uuid4().hex,
        "governance": {
            "artifact_is_authority": True,
            "authority_scope": "dispatch_this_plan_once",
            "grants_internal_effect_authority": False,
            "human_approval_mint": False,
        },
    }
    path, _ = _content_addressed_write(
        Path(builder_root_from_plan(plan)) / "dispatch" / "authorizations",
        authorization,
    )
    return authorization, path


def builder_root_from_plan(plan: dict[str, Any]) -> Path:
    """Derive the default builder root from the subject target.

    External artifact roots will be represented explicitly when RunContext is wired through the
    dispatch service. Until then this matches the currently supported runtime topology.
    """
    return Path(str(plan["target_root"])) / ".builder"


def validate_dispatch_authorization(
    *,
    authorization_path: Path,
    plan_path: Path,
    task: str,
    manifest_path: Path,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = load_dispatch_plan(plan_path)
    candidate = Path(authorization_path)
    try:
        authorization = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DispatchAuthorizationError(f"dispatch authorization is unreadable: {candidate}: {exc}") from exc
    if not isinstance(authorization, dict) or authorization.get("kind") != DISPATCH_AUTHORIZATION_KIND:
        raise DispatchAuthorizationError("dispatch authorization has the wrong kind")
    if authorization.get("schema_version") != SCHEMA_VERSION:
        raise DispatchAuthorizationError("dispatch authorization schema version is unsupported")
    if candidate.stem != canonical_digest(authorization):
        raise DispatchAuthorizationError("dispatch authorization path is not content-addressed to its bytes")
    plan_ref = authorization.get("plan_ref")
    if not isinstance(plan_ref, dict) or plan_ref.get("sha256") != canonical_digest(plan):
        raise DispatchAuthorizationError("dispatch authorization is bound to a different plan")
    if Path(str(plan_ref.get("path", ""))).resolve() != Path(plan_path).resolve():
        raise DispatchAuthorizationError("dispatch authorization plan path does not match")
    if hashlib.sha256(task.strip().encode("utf-8")).hexdigest() != plan.get("task_sha256"):
        raise DispatchAuthorizationError("task text does not match the authorized task digest")
    manifest = Path(manifest_path).resolve()
    if manifest != Path(str(plan.get("manifest_path"))).resolve():
        raise DispatchAuthorizationError("manifest path does not match the authorized plan")
    if _sha256_file(manifest) != plan.get("manifest_sha256"):
        raise DispatchAuthorizationError("manifest bytes do not match the authorized plan")

    clock = now or datetime.now(timezone.utc)
    try:
        expiry = datetime.fromisoformat(str(authorization["expires_at"]))
    except (KeyError, ValueError) as exc:
        raise DispatchAuthorizationError("dispatch authorization has an invalid expiry") from exc
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if clock >= expiry:
        raise DispatchAuthorizationError("dispatch authorization expired before execution")
    return plan, authorization


def consume_dispatch_authorization(
    *,
    authorization_path: Path,
    plan_path: Path,
    task: str,
    manifest_path: Path,
) -> Path:
    """Validate and atomically mark an authorization consumed before process spawn."""
    plan, authorization = validate_dispatch_authorization(
        authorization_path=authorization_path,
        plan_path=plan_path,
        task=task,
        manifest_path=manifest_path,
    )
    auth_digest = canonical_digest(authorization)
    root = builder_root_from_plan(plan)
    directory = root / "dispatch" / "consumed"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{auth_digest}.json"
    payload = {
        "kind": DISPATCH_CONSUMPTION_KIND,
        "schema_version": SCHEMA_VERSION,
        "authorization_sha256": auth_digest,
        "plan_sha256": canonical_digest(plan),
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        "state": "CONSUMED_BEFORE_SPAWN",
    }
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise DispatchAuthorizationError("dispatch authorization has already been consumed") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


__all__ = [
    "DISPATCH_AUTHORIZATION_KIND",
    "DISPATCH_PLAN_KIND",
    "DispatchAuthorizationError",
    "authorize_dispatch",
    "build_dispatch_plan",
    "consume_dispatch_authorization",
    "load_dispatch_plan",
    "resolve_plan_ratification",
    "validate_dispatch_authorization",
]
