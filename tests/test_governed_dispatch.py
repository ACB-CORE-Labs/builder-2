from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import builder_ii.governance.governed_dispatch as governed_dispatch
from builder_ii.governance.governed_dispatch import (
    DispatchAuthorizationError,
    authorize_dispatch,
    build_dispatch_plan,
    consume_dispatch_authorization,
    resolve_plan_ratification,
    validate_dispatch_authorization,
)
from builder_ii.governance.ratification_grants import build_ratification_grant, write_grant
from builder_ii.governance.ratification_points import get_ratification_point

COMMAND = "builder-goose run-governed"
POINT = "stratum.dispatch.goose_run"
EFFECTS = ("runtime_start", "external_tool", "artifact_write")


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.goose_session_manifest",
                "schema_version": 1,
                "requested_runtime_mode": "read_only",
                "target": {"name": "builder"},
                "agent_profile": {"name": "patch_planner"},
            }
        ),
        encoding="utf-8",
    )
    return path


def _plan(tmp_path: Path, *, task: str = "inspect") -> tuple[dict[str, Any], Path]:
    return build_dispatch_plan(
        builder_root=tmp_path / ".builder",
        command=COMMAND,
        point_id=POINT,
        manifest_path=_manifest(tmp_path),
        task=task,
        target_root=tmp_path,
        requested_effects=EFFECTS,
    )


def test_plan_is_content_addressed_and_contains_no_raw_task(tmp_path: Path) -> None:
    plan, path = _plan(tmp_path, task="inspect secret internal task wording")
    assert path.stem == governed_dispatch.canonical_digest(plan)
    assert "inspect secret internal task wording" not in path.read_text(encoding="utf-8")
    assert len(plan["task_sha256"]) == 64
    assert len(plan["manifest_sha256"]) == 64
    assert len(plan["authority_record_sha256"]) == 64
    assert plan["governance"]["artifact_is_authority"] is False


def test_manual_confirmation_records_ratification_before_authorization_exists(tmp_path: Path) -> None:
    plan, plan_path = _plan(tmp_path)
    ratification_root = tmp_path / "ratification"

    authorization, authorization_path = authorize_dispatch(
        plan_path=plan_path,
        actor="operator",
        decision_mode="manual_operator_confirmation",
        ratification_root=ratification_root,
    )

    assert authorization_path.exists()
    assert authorization["plan_ref"]["sha256"] == governed_dispatch.canonical_digest(plan)
    assert authorization["decision_mode"] == "manual_operator_confirmation"
    assert authorization["grant_digest"] is None
    ledger = ratification_root / "ratification_ledger.jsonl"
    assert ledger.exists()
    assert authorization["ratification_entry_digest"] in ledger.read_text(encoding="utf-8")


def test_standing_grant_uses_the_same_authorization_schema(tmp_path: Path) -> None:
    plan, plan_path = _plan(tmp_path)
    ratification_root = tmp_path / "ratification"
    point = get_ratification_point(POINT)
    assert point is not None
    grant = build_ratification_grant(point, granted_by="operator")
    write_grant(grant, root=ratification_root)
    resolution = resolve_plan_ratification(plan, ratification_root=ratification_root)
    assert resolution.status == "AUTO"

    authorization, authorization_path = authorize_dispatch(
        plan_path=plan_path,
        actor="stratum",
        decision_mode="standing_ratification_grant",
        ratification_root=ratification_root,
        resolution=resolution,
    )

    assert authorization_path.exists()
    assert authorization["decision_mode"] == "standing_ratification_grant"
    assert authorization["grant_digest"] == grant["grant_digest"]
    assert authorization["plan_ref"]["sha256"] == governed_dispatch.canonical_digest(plan)


def test_ratification_persistence_failure_mints_no_authorization(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _plan_data, plan_path = _plan(tmp_path)
    monkeypatch.setattr(
        governed_dispatch,
        "record_manual_ratified",
        lambda *a, **k: (_ for _ in ()).throw(OSError("ratification unavailable")),
    )

    with pytest.raises(OSError, match="ratification unavailable"):
        authorize_dispatch(
            plan_path=plan_path,
            actor="operator",
            decision_mode="manual_operator_confirmation",
            ratification_root=tmp_path / "ratification",
        )

    assert not list((tmp_path / ".builder" / "dispatch" / "authorizations").glob("*.json"))


def test_authorization_is_subject_bound_to_task_and_manifest(tmp_path: Path) -> None:
    _plan_data, plan_path = _plan(tmp_path, task="inspect")
    manifest = tmp_path / "manifest.json"
    _auth, auth_path = authorize_dispatch(
        plan_path=plan_path,
        actor="operator",
        decision_mode="manual_operator_confirmation",
        ratification_root=tmp_path / "ratification",
    )

    validate_dispatch_authorization(
        authorization_path=auth_path,
        plan_path=plan_path,
        task="inspect",
        manifest_path=manifest,
    )
    with pytest.raises(DispatchAuthorizationError, match="task text"):
        validate_dispatch_authorization(
            authorization_path=auth_path,
            plan_path=plan_path,
            task="different task",
            manifest_path=manifest,
        )

    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(DispatchAuthorizationError, match="manifest bytes"):
        validate_dispatch_authorization(
            authorization_path=auth_path,
            plan_path=plan_path,
            task="inspect",
            manifest_path=manifest,
        )


def test_authorization_expires(tmp_path: Path) -> None:
    _plan_data, plan_path = _plan(tmp_path)
    manifest = tmp_path / "manifest.json"
    authorization, auth_path = authorize_dispatch(
        plan_path=plan_path,
        actor="operator",
        decision_mode="manual_operator_confirmation",
        ratification_root=tmp_path / "ratification",
        ttl_seconds=1,
    )
    expiry = datetime.fromisoformat(authorization["expires_at"])

    with pytest.raises(DispatchAuthorizationError, match="expired"):
        validate_dispatch_authorization(
            authorization_path=auth_path,
            plan_path=plan_path,
            task="inspect",
            manifest_path=manifest,
            now=expiry + timedelta(seconds=1),
        )


def test_one_shot_authorization_is_consumed_before_spawn_and_cannot_replay(tmp_path: Path) -> None:
    _plan_data, plan_path = _plan(tmp_path)
    manifest = tmp_path / "manifest.json"
    _auth, auth_path = authorize_dispatch(
        plan_path=plan_path,
        actor="operator",
        decision_mode="manual_operator_confirmation",
        ratification_root=tmp_path / "ratification",
    )

    marker = consume_dispatch_authorization(
        authorization_path=auth_path,
        plan_path=plan_path,
        task="inspect",
        manifest_path=manifest,
    )
    assert marker.exists()
    assert json.loads(marker.read_text(encoding="utf-8"))["state"] == "CONSUMED_BEFORE_SPAWN"

    with pytest.raises(DispatchAuthorizationError, match="already been consumed"):
        consume_dispatch_authorization(
            authorization_path=auth_path,
            plan_path=plan_path,
            task="inspect",
            manifest_path=manifest,
        )


def test_authority_drift_invalidates_the_plan(tmp_path: Path, monkeypatch: Any) -> None:
    _plan_data, plan_path = _plan(tmp_path)
    original = governed_dispatch.get_command_record(COMMAND)
    assert original is not None

    from dataclasses import replace

    changed = replace(original, notes=original.notes + " changed")
    monkeypatch.setattr(governed_dispatch, "get_command_record", lambda _name: changed)

    with pytest.raises(DispatchAuthorizationError, match="authority changed"):
        governed_dispatch.load_dispatch_plan(plan_path)
