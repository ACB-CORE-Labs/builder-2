"""HITL decision envelope — the evidence an operator weighs at a decision point.

kind: builder_ii.hitl_decision_envelope

An enterprise HITL question (paraphrasing a real one): *when the system reaches an exception or
uncertainty threshold, what evidence is surfaced to the human?* This artifact is that evidence,
structured: the criteria evaluated, the acceptable range and observed value for each, the
assumptions and constraints, the alternatives considered, and the consequences of approving,
rejecting, or escalating.

It is **decision support, never the decision.** An envelope does not approve, grant authority, or
act — `grants_authority`, `artifact_is_authority`, and `is_approval` are always False. The operator
still approves through the digest-bound HITL lane (`builder-hitl approve-patch`, etc.); this artifact
only organizes what they are approving *against*. Like a receipt, it is written by the same process
that assembled the evidence, so `independent_observer` is False: it removes ambiguity about what was
weighed, not the need for a human to weigh it.

The envelope binds to the exact subject it informs by that subject's digest (`decision_ref.digest`),
so it cannot be silently re-pointed at a different decision, and it carries its own digest so an edit
announces itself under re-validation.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable

HITL_DECISION_ENVELOPE_KIND = "builder_ii.hitl_decision_envelope"
HITL_DECISION_ENVELOPE_SCHEMA_VERSION = 1
DECISION_SUPPORT_ONLY = "DECISION_SUPPORT_ONLY"
_DIGEST_KEY = "hitl_decision_envelope_digest"

#: The three paths a human decision can take. Every envelope must state the consequence of each --
#: presenting a decision without saying what "reject" or "escalate" does is the compliance theater
#: this artifact exists to prevent.
DECISION_OPTIONS: tuple[str, ...] = ("approve", "reject", "escalate")


def finalize_hitl_decision_envelope(
    *,
    action: str,
    decision_ref: dict[str, Any],
    criteria: list[dict[str, Any]],
    options: dict[str, str],
    assumptions: list[str] | None = None,
    constraints: list[str] | None = None,
    alternatives: list[dict[str, str]] | None = None,
    decision_owner_role: str = "operator",
    evidence_prepared_by: str = "",
) -> dict[str, Any]:
    """Build a digest-bound decision envelope.

    ``decision_ref`` binds to the subject under decision: ``{"kind": ..., "digest": ..., "path": ...}``.
    ``criteria`` is a list of ``{"name", "acceptable_range", "observed", "within_range"}``.
    ``options`` states the consequence of each of ``DECISION_OPTIONS`` (approve/reject/escalate).
    """
    envelope: dict[str, Any] = {
        "kind": HITL_DECISION_ENVELOPE_KIND,
        "schema_version": HITL_DECISION_ENVELOPE_SCHEMA_VERSION,
        "record_state": DECISION_SUPPORT_ONLY,
        "action": action,
        "decision_ref": dict(decision_ref),
        "criteria": [dict(criterion) for criterion in criteria],
        "assumptions": list(assumptions or []),
        "constraints": list(constraints or []),
        "alternatives": [dict(alternative) for alternative in (alternatives or [])],
        "options": {key: options.get(key, "") for key in DECISION_OPTIONS},
        "accountable": {
            "decision_owner_role": decision_owner_role,
            "evidence_prepared_by": evidence_prepared_by,
        },
        # Structural guarantee: an envelope is evidence, not authority and not an approval.
        "grants_authority": False,
        "artifact_is_authority": False,
        "is_approval": False,
        "governance": {
            "capability_state": "hitl_decision_envelope",
            "grants_authority": False,
            "artifact_is_authority": False,
            "is_approval": False,
            "independent_observer": False,
        },
    }
    return attach_digest(envelope, digest_key=_DIGEST_KEY)


def _validate_criterion(criterion: Any, index: int) -> list[str]:
    errors: list[str] = []
    where = f"criteria[{index}]"
    if not isinstance(criterion, dict):
        return [f"{where} must be an object"]
    for field in ("name", "acceptable_range", "observed"):
        value = criterion.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}.{field} must be a non-empty string")
    within = criterion.get("within_range")
    # A criterion's status must be an explicit boolean -- "unknown" is not "in range". A missing or
    # non-bool within_range fails closed here and is surfaced as a violation by the helper below.
    if not isinstance(within, bool):
        errors.append(f"{where}.within_range must be a boolean")
    return errors


def validate_hitl_decision_envelope_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl decision envelope must be a JSON object"]

    if data.get("kind") != HITL_DECISION_ENVELOPE_KIND:
        errors.append(f"kind must be {HITL_DECISION_ENVELOPE_KIND}")
    if data.get("schema_version") != HITL_DECISION_ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_DECISION_ENVELOPE_SCHEMA_VERSION}")
    if data.get("record_state") != DECISION_SUPPORT_ONLY:
        errors.append(f"record_state must be {DECISION_SUPPORT_ONLY}")

    if not isinstance(data.get("action"), str) or not str(data.get("action")).strip():
        errors.append("action must be a non-empty string")

    decision_ref = data.get("decision_ref")
    if not isinstance(decision_ref, dict):
        errors.append("decision_ref must be an object")
    else:
        for field in ("kind", "digest"):
            value = decision_ref.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"decision_ref.{field} must be a non-empty string (binds the envelope to its subject)")

    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
    else:
        for index, criterion in enumerate(criteria):
            errors.extend(_validate_criterion(criterion, index))

    options = data.get("options")
    if not isinstance(options, dict):
        errors.append("options must be an object")
    else:
        for key in DECISION_OPTIONS:
            value = options.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"options.{key} must state the consequence of {key!r} (non-empty string)")

    for list_field in ("assumptions", "constraints"):
        value = data.get(list_field)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            errors.append(f"{list_field} must be a list of strings")

    alternatives = data.get("alternatives")
    if not isinstance(alternatives, list):
        errors.append("alternatives must be a list (may be empty)")
    else:
        for index, alternative in enumerate(alternatives):
            if not isinstance(alternative, dict):
                errors.append(f"alternatives[{index}] must be an object")
                continue
            for field in ("option", "why_not"):
                value = alternative.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"alternatives[{index}].{field} must be a non-empty string")

    accountable = data.get("accountable")
    if not isinstance(accountable, dict):
        errors.append("accountable must be an object")
    elif not isinstance(accountable.get("decision_owner_role"), str) or not str(
        accountable.get("decision_owner_role")
    ).strip():
        errors.append("accountable.decision_owner_role must be a non-empty string")

    # The load-bearing invariant: an envelope can never be authority or an approval.
    for flag in ("grants_authority", "artifact_is_authority", "is_approval"):
        if data.get(flag) is not False:
            errors.append(f"{flag} must be false (an envelope is decision support, never the decision)")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for flag in ("grants_authority", "artifact_is_authority", "is_approval"):
            if governance.get(flag) is not False:
                errors.append(f"governance.{flag} must be false")

    if isinstance(data, dict):
        expected = digest_jsonable(data, digest_key=_DIGEST_KEY)
        if data.get(_DIGEST_KEY) != expected:
            errors.append(f"{_DIGEST_KEY} is invalid or missing")

    return errors


def validate_hitl_decision_envelope_file(path: Path) -> list[str]:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except (OSError, json_lib.JSONDecodeError) as exc:
        return [f"failed to load hitl decision envelope file: {exc}"]
    return validate_hitl_decision_envelope_artifact(data)


def decision_envelope_flags_a_violation(envelope: dict[str, Any]) -> bool:
    """True when any evaluated criterion is not within its acceptable range.

    This is the "exception threshold reached" signal a composer surfaces to the operator before they
    decide. Fail-closed: a criterion whose ``within_range`` is not an explicit ``True`` counts as a
    violation, so a malformed or missing status never reads as "all clear".
    """
    criteria = envelope.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return True
    for criterion in criteria:
        if not isinstance(criterion, dict) or criterion.get("within_range") is not True:
            return True
    return False


def dumps_hitl_decision_envelope(envelope: dict[str, Any]) -> str:
    return json_lib.dumps(envelope, indent=2, sort_keys=True)


def write_hitl_decision_envelope(envelope: dict[str, Any], output: Path) -> None:
    errors = validate_hitl_decision_envelope_artifact(envelope)
    if errors:
        raise ValueError(f"invalid hitl decision envelope: {'; '.join(errors)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_decision_envelope(envelope) + "\n", encoding="utf-8")
