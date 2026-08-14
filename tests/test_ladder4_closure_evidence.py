"""Gate-8 pin for the Ladder 4 closure audit (PR-8).

The committed B2.0 delegation-tree PASS evidence
(``planning/evidence/ladder4-b2-delegation-tree-pass.json``) is the artifact the closure audit
(``docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md``) cites by digest as gate 8. This pin keeps
that citation honest in CI: the committed artifact must stay schema-valid, digest-intact
(tamper-evident), a PASS over the ``delegation_tree`` gate profile, and bound to the exact
capability row the flip promotes. RECORDED_ONLY evidence never grants authority or flips the
matrix by itself — the operator's merge of PR-8 is what applied the flip.

Regeneration (fresh bundle, new digest — the artifact embeds run paths and timestamps):
re-run the PR-6 clean-run fixtures (``tests/scenarios/test_full_obligation_delegation_lane.py``)
and evaluate ``evaluate_delegation_tree_promotion_gates_from_run`` over the output directory, as
``tests/scenarios/test_promotion_gate_delegation_tree.py`` does on every CI run.
"""

import json
from pathlib import Path

from builder_ii.core.config_schema import digest_jsonable
from builder_ii.lifecycle.candidate.verification_promotion_gate import validate_promotion_evidence

EVIDENCE_PATH = Path("planning/evidence/ladder4-b2-delegation-tree-pass.json")

_SUBJECT_DIGEST_KEYS = (
    "candidate_digest",
    "seal_digest",
    "lane_policy_digest",
    "replay_report_digest",
    "event_ledger_digest",
    "envelope_digest",
    "receipt_digest",
)


def _load_evidence() -> dict:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_committed_ladder4_closure_evidence_is_valid_pass_and_digest_intact() -> None:
    evidence = _load_evidence()
    assert validate_promotion_evidence(evidence) == []
    assert evidence["overall_state"] == "PASS"
    assert evidence["failed_gates"] == []
    assert evidence["gate_profile"] == "delegation_tree"
    assert evidence["capability_name"] == "governed obligation delegation"
    assert evidence["evidence_state"] == "RECORDED_ONLY"
    assert evidence["ready_for_operator_promotion_review"] is True
    # Artifact != authority: the evidence itself grants and flips nothing.
    assert evidence["flips_matrix"] is False
    assert evidence["grants_runtime_authority"] is False
    assert evidence["grants_action_authority"] is False
    # validate_promotion_evidence checks digest shape only; re-derive it for tamper-evidence.
    assert evidence["verification_promotion_evidence_digest"] == digest_jsonable(
        evidence, digest_key="verification_promotion_evidence_digest"
    )


def test_committed_ladder4_closure_evidence_gates_and_subject_bindings() -> None:
    evidence = _load_evidence()
    # The nine machine-checkable gates individually PASS; R2 gates 1/2/3/7 (docs, tests,
    # command surface, rollback) are human closure-audit gates, asserted in the audit doc.
    gates = {gate["gate"]: gate["state"] for gate in evidence["gates"]}
    assert len(gates) == 9
    assert set(gates.values()) == {"PASS"}
    # Subject digests bind real artifacts — the PR-7 review defect (empty guessed-key digests)
    # stays pinned against the committed artifact too.
    refs = evidence["subject_refs"]
    for key in _SUBJECT_DIGEST_KEYS:
        value = refs.get(key)
        assert isinstance(value, str) and len(value) == 64, f"subject_refs.{key} must be 64-hex, got {value!r}"
    obligation_digests = refs.get("obligation_digests", [])
    assert obligation_digests and all(isinstance(d, str) and len(d) == 64 for d in obligation_digests)
