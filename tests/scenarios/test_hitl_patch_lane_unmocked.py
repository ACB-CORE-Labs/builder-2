"""Unmocked end-to-end proof of the HITL patch apply/rollback lane (plan item 1.6).

The pre-existing apply/rollback tests monkeypatch the chain ``VALIDATORS`` dict and mock
``validate_verification_execution_receipt_file`` so a *stub* receipt is accepted. That
proves the mechanics but not the governance: a mocked validator cannot demonstrate that the
lane accepts a genuinely schema-valid verification receipt.

This scenario uses **real** governed artifacts throughout — a real ``verification_execution``
plan -> approval -> receipt chain that passes its own standalone validator with no mock —
drives a full propose -> approve -> apply -> approve-rollback -> rollback loop on a real git
tree, and asserts the passive ledger records emitted at each mutation validate through both
registries and chain-verify natively. No ``@patch``, no ``VALIDATORS`` monkeypatch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hitl_patch_lane_helpers import PATCH_DIFF, init_target_repo, real_verification_receipt

from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.hitl_patch_apply import apply_hitl_patch, rollback_hitl_patch
from builder_ii.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.hitl_patch_ledger import (
    EVENT_PATCH_APPLIED,
    EVENT_PATCH_ROLLED_BACK,
    HITL_PATCH_LEDGER_RECORD_KIND,
    validate_hitl_patch_ledger_record_file,
)
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.hitl_rollback_approval import (
    canonical_json_digest,
    create_hitl_rollback_approval,
    write_hitl_rollback_approval,
)
from builder_ii.verification_execution_receipt import validate_verification_execution_receipt_file


def test_unmocked_apply_rollback_emits_and_chain_verifies_ledger(tmp_path: Path) -> None:
    repo = init_target_repo(tmp_path)
    target_file = repo / "file.txt"

    # Real proposal bound to a real diff digest.
    patch_digest = hashlib.sha256(PATCH_DIFF.encode("utf-8")).hexdigest()
    proposal = create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=PATCH_DIFF)
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(proposal, prop_path)

    # Real patch approval (bound to this proposal).
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )

    # Real, unmocked verification receipt — proves the gate on a genuine artifact.
    vr_path = real_verification_receipt(tmp_path)
    assert validate_verification_execution_receipt_file(vr_path) == []

    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    assert target_file.read_text() == "Line 1\nLine 2 modified\n"

    # Apply emitted a passive ledger record binding the whole governing chain.
    apply_ledger_path = out_dir / "patch_ledger_record.json"
    assert validate_hitl_patch_ledger_record_file(apply_ledger_path) == []
    apply_ledger = json.loads(apply_ledger_path.read_text())
    assert apply_ledger["kind"] == HITL_PATCH_LEDGER_RECORD_KIND
    assert apply_ledger["event_type"] == EVENT_PATCH_APPLIED
    assert apply_ledger["valid"] is True
    assert apply_ledger["patch_digest"] == patch_digest
    roles = {ref["role"] for ref in apply_ledger["subject_refs"]}
    assert roles == {
        "patch_proposal",
        "patch_approval",
        "pre_apply_verification_receipt",
        "patch_apply_receipt",
        "rollback_plan",
    }
    # Validates through both registries (registry closure for the new kind).
    assert INDEX_VALIDATORS[HITL_PATCH_LEDGER_RECORD_KIND](apply_ledger) == []
    assert CHAIN_VALIDATORS[HITL_PATCH_LEDGER_RECORD_KIND](apply_ledger) == []

    # Real rollback approval bound to the machine-generated rollback plan.
    plan_data = json.loads((out_dir / "rollback_plan.json").read_text())
    rollback_approval_path = tmp_path / "rollback_approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(plan_data, confirmed_digest_prefix=canonical_json_digest(plan_data)[:4]),
        rollback_approval_path,
    )

    rollback_out = out_dir / "rollback_out"
    rollback_hitl_patch(
        out_dir / "rollback_plan.json",
        out_dir / "rollback.patch",
        rollback_out,
        approval_path=rollback_approval_path,
    )
    assert target_file.read_text() == "Line 1\nLine 2\n"

    # Rollback emitted its own passive ledger record.
    rollback_ledger_path = rollback_out / "rollback_ledger_record.json"
    assert validate_hitl_patch_ledger_record_file(rollback_ledger_path) == []
    rollback_ledger = json.loads(rollback_ledger_path.read_text())
    assert rollback_ledger["event_type"] == EVENT_PATCH_ROLLED_BACK
    assert rollback_ledger["valid"] is True
    assert {ref["role"] for ref in rollback_ledger["subject_refs"]} == {
        "rollback_plan",
        "rollback_approval",
        "rollback_reverse_patch",
        "rollback_receipt",
    }

    # The full patch-lane evidence set chain-verifies natively and unmocked: standalone
    # records, zero links, zero errors.
    report = verify_artifact_chain(
        [
            out_dir / "patch_apply_receipt.json",
            apply_ledger_path,
            rollback_out / "rollback_receipt.json",
            rollback_ledger_path,
        ]
    )
    assert report["valid"] is True, report.get("errors")
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0
