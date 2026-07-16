"""Ladder 4 lane policy — the derived view binding each obligation_kind to exactly one lane.

This module is the single source of truth for obligation_kind -> lane -> discharge-mechanism
mapping (Object model: "Lane policy — NEW kind builder_ii.orchestration_lane_policy (derived
view)"). The in-code table below is authoritative; the rendered artifact is a projection of it,
never a hand-maintained parallel registry.

Collisions resolve by policy lookup only (require_lane_match / lane_for_obligation_kind), never
by "whichever adapter got invoked first". Discharge-mechanism existence for command-form
mechanisms is checked lazily against the live builder_ii.command_authority registry (import
only — this module never edits that registry).
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable
from builder_ii.governance_standard import build_standard_governance, validate_standard_governance

LANE_POLICY_KIND = "builder_ii.orchestration_lane_policy"
LANE_POLICY_SCHEMA_VERSION = 1

DISCHARGE_MECHANISM_KINDS = ("command", "artifact")

# The plan's table (Object model -> Lane policy), verbatim. Never hand-duplicate this mapping
# elsewhere; import from here.
LANE_POLICY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "obligation_kind": "planning_step",
        "lane": "deepagents",
        "discharge_mechanisms": (
            {
                "mechanism": "builder-deepagents run-approved",
                "mechanism_kind": "command",
                "description": "protocol backend execution lane (candidate -> seal -> run-approved)",
            },
        ),
    },
    {
        "obligation_kind": "interactive_ops",
        "lane": "goose",
        "discharge_mechanisms": (
            {
                "mechanism": "goose readonly session / proposal artifacts",
                "mechanism_kind": "artifact",
                "description": "Goose readonly session manifest or proposal artifact evidence",
            },
        ),
    },
    {
        "obligation_kind": "model_call",
        "lane": "gateway",
        "discharge_mechanisms": (
            {
                "mechanism": "model execution receipt",
                "mechanism_kind": "artifact",
                "description": "model_execution_gateway receipt evidence",
            },
        ),
    },
    {
        "obligation_kind": "mutation",
        "lane": "hitl_patch",
        "discharge_mechanisms": (
            {
                "mechanism": "builder-hitl apply-patch",
                "mechanism_kind": "command",
                "description": "only mutation discharge path; no other lane may discharge mutation",
            },
        ),
    },
    {
        "obligation_kind": "verification",
        "lane": "verify",
        "discharge_mechanisms": (
            {
                "mechanism": "verification execution receipt",
                "mechanism_kind": "artifact",
                "description": "verification_execution_receipt evidence",
            },
        ),
    },
)

OBLIGATION_KINDS: tuple[str, ...] = tuple(row["obligation_kind"] for row in LANE_POLICY_ROWS)
LANES: tuple[str, ...] = tuple(row["lane"] for row in LANE_POLICY_ROWS)


class LanePolicyViolation(ValueError):
    """Raised when an obligation_kind is resolved/minted under a lane the policy refuses."""


def lane_for_obligation_kind(obligation_kind: str) -> str:
    """Return the single lane the policy assigns to obligation_kind.

    Raises LanePolicyViolation (a named error, never a bare KeyError) for unknown kinds.
    """
    for row in LANE_POLICY_ROWS:
        if row["obligation_kind"] == obligation_kind:
            return str(row["lane"])
    raise LanePolicyViolation(
        f"lane_policy_unknown_obligation_kind: {obligation_kind!r} is not a known obligation_kind; "
        f"known kinds: {OBLIGATION_KINDS}"
    )


def require_lane_match(obligation_kind: str, lane: str) -> None:
    """Fail closed if lane is not the policy-assigned lane for obligation_kind.

    This is the collision-refusal check: an attempt to mint/resolve, e.g., interactive_ops under
    lane "deepagents" is refused with a named error citing the expected lane — never silently
    resolved to "whichever adapter got invoked first".
    """
    expected = lane_for_obligation_kind(obligation_kind)
    if lane != expected:
        raise LanePolicyViolation(
            f"lane_policy_collision: obligation_kind={obligation_kind!r} must mint under "
            f"lane={expected!r}, got lane={lane!r}; resolve by policy lookup only"
        )


def discharge_mechanisms_for_obligation_kind(obligation_kind: str) -> tuple[dict[str, Any], ...]:
    for row in LANE_POLICY_ROWS:
        if row["obligation_kind"] == obligation_kind:
            return tuple(dict(mechanism) for mechanism in row["discharge_mechanisms"])
    raise LanePolicyViolation(
        f"lane_policy_unknown_obligation_kind: {obligation_kind!r} is not a known obligation_kind; "
        f"known kinds: {OBLIGATION_KINDS}"
    )


def _command_form_discharge_mechanisms() -> tuple[tuple[str, str], ...]:
    """Return (obligation_kind, command_name) pairs whose mechanism_kind is 'command'."""
    return tuple(
        (row["obligation_kind"], mechanism["mechanism"])
        for row in LANE_POLICY_ROWS
        for mechanism in row["discharge_mechanisms"]
        if mechanism["mechanism_kind"] == "command"
    )


def check_command_discharge_mechanism_registered(command_name: str) -> str | None:
    """Return None if command_name resolves in COMMAND_AUTHORITY_REGISTRY, else a named error.

    Import-only, lazy: this module never edits builder_ii.command_authority.
    """
    from builder_ii.command_authority import get_command_record

    record = get_command_record(command_name)
    if record is None:
        return f"discharge_mechanism_unregistered: {command_name!r} has no COMMAND_AUTHORITY_REGISTRY record"
    return None


def validate_discharge_mechanisms_against_registry() -> list[str]:
    """Validate every command-form discharge mechanism in the lane policy against the live
    COMMAND_AUTHORITY_REGISTRY. Receipt/artifact-form mechanisms are named strings, not registry
    lookups, and are not checked here.
    """
    errors: list[str] = []
    for obligation_kind, command_name in _command_form_discharge_mechanisms():
        error = check_command_discharge_mechanism_registered(command_name)
        if error:
            errors.append(f"{error} (obligation_kind={obligation_kind!r})")
    return errors


def create_orchestration_lane_policy_artifact() -> dict[str, Any]:
    lanes = [
        {
            "obligation_kind": row["obligation_kind"],
            "lane": row["lane"],
            "discharge_mechanisms": [dict(mechanism) for mechanism in row["discharge_mechanisms"]],
        }
        for row in LANE_POLICY_ROWS
    ]
    artifact = {
        "kind": LANE_POLICY_KIND,
        "schema_version": LANE_POLICY_SCHEMA_VERSION,
        "obligation_kinds": list(OBLIGATION_KINDS),
        "lanes": lanes,
        "governance": build_standard_governance("orchestration_lane_policy"),
    }
    return attach_digest(artifact, digest_key="lane_policy_digest")


def dumps_orchestration_lane_policy_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_orchestration_lane_policy_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_lane_policy_artifact(artifact), encoding="utf-8")


def validate_orchestration_lane_policy_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["orchestration lane policy artifact must be a JSON object"]
    if artifact.get("kind") != LANE_POLICY_KIND:
        errors.append(f"kind must be {LANE_POLICY_KIND}")
    if artifact.get("schema_version") != LANE_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {LANE_POLICY_SCHEMA_VERSION}")

    obligation_kinds = artifact.get("obligation_kinds")
    if not isinstance(obligation_kinds, list) or tuple(obligation_kinds) != OBLIGATION_KINDS:
        errors.append(f"obligation_kinds must equal {list(OBLIGATION_KINDS)} in order")

    lanes = artifact.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        errors.append("lanes must be a non-empty list")
    else:
        seen_kinds: set[str] = set()
        for index, row in enumerate(lanes):
            prefix = f"lanes[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix} must be an object")
                continue
            kind = row.get("obligation_kind")
            if kind not in OBLIGATION_KINDS:
                errors.append(f"{prefix}.obligation_kind must be one of {OBLIGATION_KINDS}")
            elif kind in seen_kinds:
                errors.append(f"{prefix}.obligation_kind {kind!r} is duplicated (totality violation)")
            else:
                seen_kinds.add(kind)
            if not isinstance(row.get("lane"), str) or not row.get("lane"):
                errors.append(f"{prefix}.lane must be a non-empty string")
            mechanisms = row.get("discharge_mechanisms")
            if not isinstance(mechanisms, list) or not mechanisms:
                errors.append(f"{prefix}.discharge_mechanisms must be a non-empty list")
            else:
                for m_index, mechanism in enumerate(mechanisms):
                    m_prefix = f"{prefix}.discharge_mechanisms[{m_index}]"
                    if not isinstance(mechanism, dict):
                        errors.append(f"{m_prefix} must be an object")
                        continue
                    if not isinstance(mechanism.get("mechanism"), str) or not mechanism.get("mechanism"):
                        errors.append(f"{m_prefix}.mechanism must be a non-empty string")
                    if mechanism.get("mechanism_kind") not in DISCHARGE_MECHANISM_KINDS:
                        errors.append(f"{m_prefix}.mechanism_kind must be one of {DISCHARGE_MECHANISM_KINDS}")
        missing = [kind for kind in OBLIGATION_KINDS if kind not in seen_kinds]
        if missing:
            errors.append(f"lanes missing obligation_kind entries (totality violation): {missing}")

    errors.extend(validate_standard_governance(artifact.get("governance"), "orchestration_lane_policy"))

    digest = artifact.get("lane_policy_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("lane_policy_digest must be a 64-character hex string")
    elif digest != digest_jsonable(artifact, digest_key="lane_policy_digest"):
        errors.append("lane_policy_digest does not match canonical artifact payload")

    return errors


def validate_orchestration_lane_policy_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_orchestration_lane_policy_artifact(data)
