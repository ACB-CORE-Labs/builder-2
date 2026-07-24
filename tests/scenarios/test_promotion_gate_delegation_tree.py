import json
from datetime import datetime, timezone
from pathlib import Path

from test_full_obligation_delegation_lane import (
    _build_four_obligations,
    _build_sealed_envelope,
    _run_approved,
)

from builder_ii.adapters.deepagents.deepagents_execution import DISCHARGE_CONTRACT_SATISFIED
from builder_ii.lifecycle.candidate.verification_promotion_gate import (
    evaluate_delegation_tree_promotion_gates_from_run,
    validate_promotion_evidence,
)


def test_delegation_tree_gate_passes_clean_bundle(tmp_path: Path) -> None:
    candidate, candidate_path, approval, approval_path, policy = _build_sealed_envelope(tmp_path)
    obligation_paths = _build_four_obligations(tmp_path, approval=approval, policy=policy)

    output_dir = tmp_path / "runs" / "output"
    output_dir.mkdir(parents=True)

    summary = _run_approved(candidate_path, approval_path, output_dir, obligation_paths)
    assert summary.get("status") == "COMPLETED"

    now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
    evidence = evaluate_delegation_tree_promotion_gates_from_run(
        run_output_dir=output_dir,
        candidate_path=candidate_path,
        approval_path=approval_path,
        obligation_paths=obligation_paths,
        capability_name="test_capability",
        now=now,
    )

    assert evidence.get("overall_state") == "PASS"
    assert evidence.get("failed_gates") == []
    assert evidence.get("ready_for_operator_promotion_review") is True
    assert evidence.get("evidence_state") == "RECORDED_ONLY"
    assert evidence.get("flips_matrix") is False
    assert evidence.get("grants_runtime_authority") is False
    assert evidence.get("grants_action_authority") is False
    assert evidence.get("gate_profile") == "delegation_tree"

    digest = evidence.get("verification_promotion_evidence_digest")
    assert isinstance(digest, str)
    assert len(digest) == 64

    assert validate_promotion_evidence(evidence) == []

    # Assert every gate individually PASSes
    gates = evidence.get("gates", [])
    assert len(gates) == 9
    for gate in gates:
        assert gate.get("state") == "PASS", f"Gate {gate.get('gate')} failed: {gate.get('detail')}"

    # Provenance must be real, not hollow: every subject digest must bind an actual artifact.
    # (Pins the guessed-key defect where subject_refs digests silently serialized as "".)
    refs = evidence.get("subject_refs", {})
    for key in (
        "candidate_digest",
        "seal_digest",
        "lane_policy_digest",
        "replay_report_digest",
        "event_ledger_digest",
        "envelope_digest",
        "receipt_digest",
    ):
        value = refs.get(key)
        assert isinstance(value, str) and len(value) == 64, f"subject_refs.{key} must be a 64-hex digest, got {value!r}"
    obligation_digests = refs.get("obligation_digests", [])
    assert obligation_digests and all(isinstance(d, str) and len(d) == 64 for d in obligation_digests)


def test_delegation_tree_gate_is_deterministic(tmp_path: Path) -> None:
    candidate, candidate_path, approval, approval_path, policy = _build_sealed_envelope(tmp_path)
    obligation_paths = _build_four_obligations(tmp_path, approval=approval, policy=policy)

    output_dir = tmp_path / "runs" / "output"
    output_dir.mkdir(parents=True)

    _run_approved(candidate_path, approval_path, output_dir, obligation_paths)

    now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

    evidence1 = evaluate_delegation_tree_promotion_gates_from_run(
        run_output_dir=output_dir,
        candidate_path=candidate_path,
        approval_path=approval_path,
        obligation_paths=obligation_paths,
        capability_name="test_capability",
        now=now,
    )

    evidence2 = evaluate_delegation_tree_promotion_gates_from_run(
        run_output_dir=output_dir,
        candidate_path=candidate_path,
        approval_path=approval_path,
        obligation_paths=obligation_paths,
        capability_name="test_capability",
        now=now,
    )

    assert evidence1.get("verification_promotion_evidence_digest") == evidence2.get(
        "verification_promotion_evidence_digest"
    )


def test_delegation_tree_gate_fails_on_tampered_discharge(tmp_path: Path) -> None:
    candidate, candidate_path, approval, approval_path, policy = _build_sealed_envelope(tmp_path)
    obligation_paths = _build_four_obligations(tmp_path, approval=approval, policy=policy)

    output_dir = tmp_path / "runs" / "output"
    output_dir.mkdir(parents=True)

    _run_approved(candidate_path, approval_path, output_dir, obligation_paths)

    # Tamper with the discharge state on disk
    events_dir = output_dir / "events"
    tampered = False
    for p in events_dir.glob("event-*-obligation_consumed.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("payload", {}).get("discharge_state") == DISCHARGE_CONTRACT_SATISFIED:
            data["payload"]["discharge_state"] = "CONTRACT_VIOLATED"
            p.write_text(json.dumps(data), encoding="utf-8")
            tampered = True
            break

    assert tampered, "Could not find a CONTRACT_SATISFIED event to tamper with"

    now = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
    evidence = evaluate_delegation_tree_promotion_gates_from_run(
        run_output_dir=output_dir,
        candidate_path=candidate_path,
        approval_path=approval_path,
        obligation_paths=obligation_paths,
        capability_name="test_capability",
        now=now,
    )

    assert evidence.get("overall_state") == "FAIL"
    assert evidence.get("ready_for_operator_promotion_review") is False
    assert "event_chain_intact" in evidence.get("failed_gates", [])

    # Assert that the artifact still validates natively
    assert validate_promotion_evidence(evidence) == []
