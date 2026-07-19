"""The HITL decision envelope carries the evidence a human weighs -- and can never be the decision.

Answers the enterprise question: when the system reaches an exception/uncertainty threshold, what is
surfaced to the human? These pins hold both halves: it carries every element (criteria + acceptable
range + observed value, assumptions, constraints, alternatives, consequences of approve/reject/
escalate, accountable ownership), and it is structurally incapable of being an approval.
"""

from __future__ import annotations

from pathlib import Path

from builder_ii.config_schema import attach_digest
from builder_ii.hitl_decision_envelope import (
    HITL_DECISION_ENVELOPE_KIND,
    decision_envelope_flags_a_violation,
    finalize_hitl_decision_envelope,
    validate_hitl_decision_envelope_artifact,
    validate_hitl_decision_envelope_file,
    write_hitl_decision_envelope,
)

_DIGEST_KEY = "hitl_decision_envelope_digest"


def _envelope(**overrides: object) -> dict:
    kwargs: dict = dict(
        action="apply patch to append a marker line to README.md",
        decision_ref={
            "kind": "builder_ii.hitl_patch_proposal",
            "digest": "a1b2c3d4e5",
            "path": "/tmp/proposal.json",
        },
        criteria=[
            {"name": "files changed outside marker", "acceptable_range": "exactly 0", "observed": "0", "within_range": True},
            {"name": "patch digest matches approval", "acceptable_range": "exact match", "observed": "match", "within_range": True},
        ],
        options={
            "approve": "the marker line is applied in the throwaway worktree; receipt + reverse patch written",
            "reject": "no change is applied; a refusal artifact records the non-approval",
            "escalate": "the decision routes to a second operator; nothing is applied meanwhile",
        },
        assumptions=["the target worktree is disposable"],
        constraints=["source repo is read-only", "no network"],
        alternatives=[
            {"option": "apply directly with git apply", "why_not": "bypasses the digest-bound approval and receipt"}
        ],
        decision_owner_role="operator",
        evidence_prepared_by="builder-agent",
    )
    kwargs.update(overrides)
    return finalize_hitl_decision_envelope(**kwargs)  # type: ignore[arg-type]


def test_a_complete_envelope_validates_and_round_trips(tmp_path: Path) -> None:
    env = _envelope()
    assert env["kind"] == HITL_DECISION_ENVELOPE_KIND
    assert validate_hitl_decision_envelope_artifact(env) == []

    out = tmp_path / "envelope.json"
    write_hitl_decision_envelope(env, out)
    assert validate_hitl_decision_envelope_file(out) == []


def test_it_carries_every_element_of_the_enterprise_spec() -> None:
    env = _envelope()
    # criteria: name + acceptable range + observed value, per criterion
    for criterion in env["criteria"]:
        assert criterion["name"] and criterion["acceptable_range"] and criterion["observed"]
        assert isinstance(criterion["within_range"], bool)
    # assumptions, constraints, alternatives
    assert env["assumptions"] and env["constraints"]
    assert env["alternatives"][0]["option"] and env["alternatives"][0]["why_not"]
    # consequences of approve / reject / escalate
    assert env["options"]["approve"] and env["options"]["reject"] and env["options"]["escalate"]
    # accountable operating ownership
    assert env["accountable"]["decision_owner_role"]


def test_an_envelope_can_never_be_an_approval() -> None:
    env = _envelope()
    assert env["is_approval"] is False
    assert env["grants_authority"] is False
    assert env["artifact_is_authority"] is False
    assert env["governance"]["is_approval"] is False

    # Even re-digested so the digest is valid, a True approval flag must fail validation.
    tampered = {k: v for k, v in env.items() if k != _DIGEST_KEY}
    tampered["is_approval"] = True
    tampered = attach_digest(tampered, digest_key=_DIGEST_KEY)
    errors = validate_hitl_decision_envelope_artifact(tampered)
    assert any("is_approval must be false" in e for e in errors), errors


def test_every_consequence_is_required_no_silent_paths() -> None:
    """You cannot present a decision without stating what reject and escalate do."""
    env = _envelope()
    env["options"] = {"approve": env["options"]["approve"], "reject": "", "escalate": env["options"]["escalate"]}
    env = attach_digest({k: v for k, v in env.items() if k != _DIGEST_KEY}, digest_key=_DIGEST_KEY)
    errors = validate_hitl_decision_envelope_artifact(env)
    assert any("options.'reject'" in e or "'reject'" in e for e in errors), errors


def test_criteria_must_be_present() -> None:
    env = _envelope(criteria=[])
    assert any("criteria must be a non-empty list" in e for e in validate_hitl_decision_envelope_artifact(env))


def test_decision_ref_binds_to_the_subject_digest() -> None:
    env = _envelope(decision_ref={"kind": "builder_ii.hitl_patch_proposal", "path": "/tmp/p.json"})
    errors = validate_hitl_decision_envelope_artifact(env)
    assert any("decision_ref.digest" in e for e in errors), errors


def test_the_digest_is_tamper_evident() -> None:
    env = _envelope()
    assert validate_hitl_decision_envelope_artifact(env) == []
    env["criteria"][0]["observed"] = "1"  # quietly rewrite the observed value
    errors = validate_hitl_decision_envelope_artifact(env)
    assert any("digest is invalid" in e for e in errors), errors


def test_flags_a_violation_when_a_criterion_is_out_of_range() -> None:
    clear = _envelope()
    assert decision_envelope_flags_a_violation(clear) is False

    breach = _envelope(
        criteria=[
            {"name": "files changed outside marker", "acceptable_range": "exactly 0", "observed": "3", "within_range": False},
        ]
    )
    assert decision_envelope_flags_a_violation(breach) is True


def test_the_violation_helper_fails_closed() -> None:
    """No criteria, or a malformed status, is a violation -- never a silent 'all clear'."""
    assert decision_envelope_flags_a_violation({"criteria": []}) is True
    assert decision_envelope_flags_a_violation({"criteria": [{"within_range": "yes"}]}) is True
    assert decision_envelope_flags_a_violation({}) is True
