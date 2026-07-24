"""Unit tests for the HITL patch apply/rollback passive ledger record (plan item 1.6)."""

from __future__ import annotations

import json
from pathlib import Path

from builder_ii.core.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.core.artifact_chain_verification import extract_references
from builder_ii.governance.hitl.hitl_patch_ledger import (
    EVENT_PATCH_APPLIED,
    EVENT_PATCH_ROLLED_BACK,
    HITL_PATCH_LEDGER_RECORD_KIND,
    create_hitl_patch_ledger_record,
    hitl_patch_ledger_subject_ref,
    validate_hitl_patch_ledger_record,
    validate_hitl_patch_ledger_record_file,
    write_hitl_patch_ledger_record,
)
from builder_ii.governance.ledger.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS


def _ref(tmp_path: Path, name: str = "proposal.json", *, role: str = "patch_proposal") -> dict:
    path = tmp_path / name
    path.write_text(json.dumps({"kind": "builder_ii.hitl_patch_proposal", "name": name}))
    return hitl_patch_ledger_subject_ref(role=role, kind="builder_ii.hitl_patch_proposal", path=path)


def _record(tmp_path: Path, *, event_type: str = EVENT_PATCH_APPLIED) -> dict:
    return create_hitl_patch_ledger_record(
        event_type=event_type,
        target={"name": "generic", "repo": str(tmp_path)},
        patch_digest="a" * 64,
        pre_head="b" * 40,
        subject_refs=[
            _ref(tmp_path, "proposal.json", role="patch_proposal"),
            _ref(tmp_path, "receipt.json", role="patch_apply_receipt"),
        ],
    )


def test_valid_record_self_validates(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert record["kind"] == HITL_PATCH_LEDGER_RECORD_KIND
    assert record["ledger_record_state"] == "PASSIVE_INDEX_ONLY"
    assert record["event_type"] == EVENT_PATCH_APPLIED
    assert record["valid"] is True
    assert record["errors"] == []
    assert validate_hitl_patch_ledger_record(record) == []


def test_rollback_event_type_is_valid(tmp_path: Path) -> None:
    record = _record(tmp_path, event_type=EVENT_PATCH_ROLLED_BACK)
    assert record["event_type"] == EVENT_PATCH_ROLLED_BACK
    assert validate_hitl_patch_ledger_record(record) == []


def test_record_is_standalone_evidence_no_chain_links(tmp_path: Path) -> None:
    """The ledger record indexes a governed event; it must not emit outbound chain
    references (which chain verification would try to resolve). subject_refs are evidence
    fingerprints, not links."""
    record = _record(tmp_path)
    assert extract_references(record) == []


def test_registered_in_both_registries_and_validates(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert HITL_PATCH_LEDGER_RECORD_KIND in INDEX_VALIDATORS
    assert HITL_PATCH_LEDGER_RECORD_KIND in CHAIN_VALIDATORS
    assert INDEX_VALIDATORS[HITL_PATCH_LEDGER_RECORD_KIND](record) == []
    assert CHAIN_VALIDATORS[HITL_PATCH_LEDGER_RECORD_KIND](record) == []


def test_digest_tamper_is_detected(tmp_path: Path) -> None:
    record = _record(tmp_path)
    tampered = dict(record)
    tampered["patch_digest"] = "c" * 64  # digest field left stale
    errors = validate_hitl_patch_ledger_record(tampered)
    assert any("drift detected" in e for e in errors)


def test_subject_ref_tamper_breaks_chain_digest(tmp_path: Path) -> None:
    """Editing a bound artifact's fingerprint without recomputing chain_digest is caught:
    the record cannot silently claim a chain it no longer binds."""
    record = _record(tmp_path)
    tampered = dict(record)
    tampered["subject_refs"] = [dict(record["subject_refs"][0], sha256="d" * 64)] + record["subject_refs"][1:]
    errors = validate_hitl_patch_ledger_record(tampered)
    assert any("chain_digest does not match" in e for e in errors)


def test_duplicate_subject_ref_roles_rejected(tmp_path: Path) -> None:
    """A duplicate role would collapse in the chain_digest's {role: sha256} map, dropping one
    ref's fingerprint from the binding while the record still self-validated. The validator
    must reject it so chain_digest genuinely binds every ref (adversarial review, 1.6)."""
    real = _ref(tmp_path, "real.json", role="patch_proposal")
    fake = _ref(tmp_path, "fake.json", role="patch_proposal")  # same role, different file/sha
    record = create_hitl_patch_ledger_record(
        event_type=EVENT_PATCH_APPLIED,
        target={"name": "generic", "repo": str(tmp_path)},
        patch_digest="a" * 64,
        pre_head="b" * 40,
        subject_refs=[real, fake],
    )
    assert record["valid"] is False
    assert any("roles must be unique" in e for e in record["errors"])


def test_unknown_event_type_rejected(tmp_path: Path) -> None:
    record = _record(tmp_path)
    tampered = dict(record)
    tampered["event_type"] = "patch_teleported"
    assert any("event_type must be one of" in e for e in validate_hitl_patch_ledger_record(tampered))


def test_empty_subject_refs_rejected(tmp_path: Path) -> None:
    record = create_hitl_patch_ledger_record(
        event_type=EVENT_PATCH_APPLIED,
        target={"name": "generic", "repo": str(tmp_path)},
        patch_digest="a" * 64,
        pre_head="b" * 40,
        subject_refs=[],
    )
    # create embeds the failure rather than raising, so the record is never silently valid.
    assert record["valid"] is False
    assert any("subject_refs must be a non-empty list" in e for e in record["errors"])


def test_governance_must_be_disabled(tmp_path: Path) -> None:
    record = _record(tmp_path)
    tampered = dict(record)
    tampered["governance"] = dict(record["governance"], runtime_execution="ENABLED")
    assert any("governance.runtime_execution" in e for e in validate_hitl_patch_ledger_record(tampered))


def test_artifact_is_authority_must_be_false(tmp_path: Path) -> None:
    record = _record(tmp_path)
    tampered = dict(record)
    tampered["governance"] = dict(record["governance"], artifact_is_authority=True)
    assert any("artifact_is_authority" in e for e in validate_hitl_patch_ledger_record(tampered))


def test_file_roundtrip(tmp_path: Path) -> None:
    record = _record(tmp_path)
    out = tmp_path / "ledger" / "patch_ledger_record.json"
    write_hitl_patch_ledger_record(record, out)
    assert out.exists()
    assert validate_hitl_patch_ledger_record_file(out) == []


def test_validate_missing_file() -> None:
    assert validate_hitl_patch_ledger_record_file(Path("/nonexistent/x.json")) == [
        "file not found: /nonexistent/x.json"
    ]
