"""Gate-8 pin for the Ladder 9 assurance promotion.

Three B2.0 promotion-evidence artifacts under ``planning/evidence/`` are what
``docs/audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md`` cites for the flip of
``HITL-approved verification execution`` to ``BOUNDED_EXECUTION_VERIFIED``:

- ``ladder9-b2-platform-status-pass.json``           the first in-scope profile
- ``ladder9-b2-docs-audit-pass.json``                the second in-scope profile
- ``ladder9-b2-platform-status-isolated-pass.json``  the same profile under a docker policy

Each was produced on the promoting host by the real CLI (``builder-verify plan / validate-plan /
approve-plan / validate-approval / run-approved / validate-receipt``, ``builder-ledger
index-receipt``, ``builder-verify evaluate-promotion``) over a fresh chain that reached
``receipt_status: EXECUTED``.

This pin keeps the citation honest in CI: each artifact must stay schema-valid, digest-intact,
a PASS over every machine gate, bound to the exact capability row the flip promotes, free of
host-specific absolute paths, and -- being ``RECORDED_ONLY`` -- must grant no authority and flip
no matrix by itself. The operator's merge is what applies the flip.

Regeneration: re-run the chains against a clean tree; the artifacts embed run paths and receipt
digests, so a fresh bundle carries a new self-digest. Nothing here is a hardcoded hash.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.core.config_schema import digest_jsonable
from builder_ii.lifecycle.candidate.verification_isolation_policy import finalize_verification_isolation_policy
from builder_ii.lifecycle.candidate.verification_promotion_gate import validate_promotion_evidence

PROMOTED_CAPABILITY = "HITL-approved verification execution"
_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "planning" / "evidence"
_DIGEST_KEY = "verification_promotion_evidence_digest"

# The eleven machine gates the B2.0 evaluator emits for a verification chain. Enumerated, not
# counted: a gate silently disappearing would otherwise leave `failed_gates == []` looking green.
EXPECTED_GATES = (
    "plan_valid",
    "approval_valid",
    "approval_bound_to_plan",
    "receipt_valid",
    "receipt_bound_to_plan_and_approval",
    "receipt_executed",
    "workspace_unmutated",
    "commit_identity_recorded",
    "approval_unexpired",
    "ledger_chain_consistent",
    "profile_matches_capability",
)

EVIDENCE = {
    "platform_status": "ladder9-b2-platform-status-pass.json",
    "docs_audit": "ladder9-b2-docs-audit-pass.json",
    "platform_status (docker isolation)": "ladder9-b2-platform-status-isolated-pass.json",
}


def _load(name: str) -> dict:
    return json.loads((_EVIDENCE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("label,name", sorted(EVIDENCE.items()))
def test_committed_ladder9_evidence_is_a_valid_pass_and_digest_intact(label: str, name: str) -> None:
    evidence = _load(name)

    assert validate_promotion_evidence(evidence) == []
    assert evidence["overall_state"] == "PASS", label
    assert evidence["failed_gates"] == []
    assert evidence["capability_name"] == PROMOTED_CAPABILITY
    assert evidence["receipt_status"] == "EXECUTED"

    # Re-derive rather than compare to a literal: a hardcoded hash pins the paste, not the artifact.
    body = {key: value for key, value in evidence.items() if key != _DIGEST_KEY}
    assert digest_jsonable(body) == evidence[_DIGEST_KEY], f"{name} has been edited since it was signed"


@pytest.mark.parametrize("label,name", sorted(EVIDENCE.items()))
def test_every_machine_gate_ran_and_passed(label: str, name: str) -> None:
    gates = {gate["gate"]: gate["state"] for gate in _load(name)["gates"]}

    assert tuple(gate["gate"] for gate in _load(name)["gates"]) == EXPECTED_GATES, (
        f"{name}: the gate set changed -- an absent gate cannot fail, so it must not vanish silently"
    )
    assert set(gates.values()) == {"PASS"}, f"{name}: {[g for g, s in gates.items() if s != 'PASS']}"


@pytest.mark.parametrize("label,name", sorted(EVIDENCE.items()))
def test_evidence_grants_nothing_and_carries_no_host_paths(label: str, name: str) -> None:
    """RECORDED_ONLY: an artifact is never authority, and never a map of the author's disk."""
    evidence = _load(name)

    assert evidence["evidence_state"] == "RECORDED_ONLY"
    assert evidence["flips_matrix"] is False
    assert evidence["grants_action_authority"] is False
    assert evidence["grants_runtime_authority"] is False

    raw = (_EVIDENCE_DIR / name).read_text(encoding="utf-8")
    assert "/Users/" not in raw and "/home/" not in raw, f"{name} embeds an absolute host path"

    refs = evidence["subject_refs"]
    for key, value in refs.items():
        if key.endswith("_digest"):
            assert len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{key}={value!r}"
        if key.endswith("_path"):
            assert value and not value.startswith("/"), f"{key} must be repo-relative, got {value!r}"


def test_the_two_in_scope_profiles_are_the_only_ones_this_evidence_covers() -> None:
    """The flip is scoped to platform_status and docs_audit. pytest_full/builder_full stay outside."""
    covered = {
        gate["evidence"]
        for name in EVIDENCE.values()
        for gate in _load(name)["gates"]
        if gate["gate"] == "profile_matches_capability"
    }

    assert not any(
        "pytest_full" in item or "builder_full" in item.replace("verification_profiles.builder_full", "")
        for item in covered
    ), "target-code-executing profiles must never appear in this promotion's evidence"


def test_the_isolated_chain_is_a_different_run_from_the_unisolated_one() -> None:
    """Otherwise the 'isolation pair' would be one receipt cited twice."""
    plain = _load(EVIDENCE["platform_status"])["subject_refs"]["receipt_digest"]
    isolated = _load(EVIDENCE["platform_status (docker isolation)"])["subject_refs"]["receipt_digest"]

    assert plain != isolated


def test_the_docker_policy_digest_cited_by_the_audit_is_reproducible() -> None:
    """The audit names a policy digest. Recompute it; never trust a pasted hash.

    The isolation policy artifact is pure, so its digest is deterministic. The receipt it produced
    is not committed -- receipts embed absolute host paths -- so this is what binds the audit's
    isolation claim to something CI can recompute.
    """
    policy = finalize_verification_isolation_policy(
        backend="docker", image_ref="python:3.12-slim", network_policy="none"
    )
    digest = policy["verification_isolation_policy_digest"]

    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)

    audit = (
        Path(__file__).resolve().parent.parent / "docs" / "audits" / "LADDER9_ASSURANCE_CLOSURE_AUDIT.md"
    ).read_text(encoding="utf-8")
    assert digest in audit, "the closure audit cites an isolation policy digest this code no longer produces"
