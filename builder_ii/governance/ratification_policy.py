"""Ratification policy: the operator's ability to demand *more* governance than the default.

:mod:`builder_ii.governance.ratification_grants` answers "stop asking me things I already
decided". This module answers the opposite question, which is the one an organisation with real
exposure asks: "for this point, I want more than the default, and I want it enforced rather than
remembered."

THE INVARIANT THIS MODULE EXISTS TO CARRY:

    A policy may only tighten. It can never make an ungrantable point grantable.

This is the exact mirror of the grant invariant, and it is enforced by making the loosening case
*unrepresentable* rather than merely rejected. :func:`effective_level` returns
``max(baseline, declared)`` over an ordered ladder, so a policy file hand-edited to declare
``delegable`` on a HITL confirmation does not get rejected -- it gets **ignored**, because the
baseline is already stricter and ``max`` keeps it. Validation *also* reports the attempt, so the
operator is told rather than silently overridden; but the safety does not depend on validation
having run.

THE LADDER (strictly ordered; every level implies every level below it):

0. ``delegable``                   -- a standing grant may satisfy this confirmation.
1. ``always_prompt``               -- no grant satisfies it; a human types the digest every time.
2. ``require_approval_artifact``   -- typing is not enough; a digest-bound ratification approval
                                      artifact must be supplied on the command line.

The baseline for a point is derived, never declared: ``delegable`` where
:func:`~builder_ii.governance.ratification_points.grant_eligibility` says the registry allows a
grant, and ``always_prompt`` everywhere else. So the ungrantable points start at level 1 and a
policy can push them to level 2 -- which is the useful direction -- but nothing can pull them to 0.

``allow_grants: false`` is the project-wide kill switch: it raises the floor for *every* point to
``always_prompt`` in one line, without needing to enumerate points that may not exist yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.governance.ratification_points import (
    RatificationPoint,
    get_ratification_point,
    grant_eligibility,
)

RATIFICATION_POLICY_KIND = "builder_ii.ratification_policy"
RATIFICATION_POLICY_SCHEMA_VERSION = 1
RATIFICATION_POLICY_FILENAME = "policy.json"

LEVEL_DELEGABLE = "delegable"
LEVEL_ALWAYS_PROMPT = "always_prompt"
LEVEL_REQUIRE_APPROVAL_ARTIFACT = "require_approval_artifact"

#: Ordered weakest-to-strictest. Index *is* the strictness, which is what makes `max()` meaningful;
#: reordering this tuple silently reinterprets every stored policy, so it is append-only in spirit.
POLICY_LEVELS: tuple[str, ...] = (
    LEVEL_DELEGABLE,
    LEVEL_ALWAYS_PROMPT,
    LEVEL_REQUIRE_APPROVAL_ARTIFACT,
)

_LEVEL_ORDER: dict[str, int] = {level: index for index, level in enumerate(POLICY_LEVELS)}

_POLICY_REQUIRED_KEYS = (
    "kind",
    "schema_version",
    "allow_grants",
    "levels",
    "set_by",
    "created_at",
    "governance",
    "policy_digest",
)


def policy_path(root: Path) -> Path:
    return Path(root) / RATIFICATION_POLICY_FILENAME


def level_rank(level: str) -> int:
    """Strictness rank. Unknown levels rank strictest, so a typo fails closed rather than open."""
    return _LEVEL_ORDER.get(level, len(POLICY_LEVELS))


def stricter_of(first: str, second: str) -> str:
    """The stricter of two levels. The whole one-way property of this module reduces to this."""
    return first if level_rank(first) >= level_rank(second) else second


def baseline_level(point: RatificationPoint) -> str:
    """The floor the command-authority registry already imposes on ``point``.

    Derived from :func:`grant_eligibility`, never declared, and recomputed on every call for the
    same reason eligibility is: a command whose authority tightens must raise its own floor without
    anyone editing a policy file.
    """
    return LEVEL_DELEGABLE if grant_eligibility(point).eligible else LEVEL_ALWAYS_PROMPT


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_ratification_policy(
    levels: dict[str, str],
    *,
    set_by: str,
    allow_grants: bool = True,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a digest-bound policy artifact declaring per-point levels."""
    artifact = {
        "kind": RATIFICATION_POLICY_KIND,
        "schema_version": RATIFICATION_POLICY_SCHEMA_VERSION,
        "allow_grants": bool(allow_grants),
        "levels": {str(key): str(value) for key, value in sorted(levels.items())},
        "set_by": set_by,
        "created_at": created_at or _now_iso(),
        "governance": {
            "artifact_is_authority": False,
            "capability_state": "tightening_only",
            "can_loosen": False,
            "note": (
                "A policy may only raise the ratification level a point already carries. The "
                "effective level is max(baseline, declared), so a declared level below the "
                "registry baseline is ignored, not honoured."
            ),
        },
    }
    return attach_digest(artifact, digest_key="policy_digest")


def validate_ratification_policy_artifact(artifact: Any) -> list[str]:
    """Schema, digest, and one-way errors in a policy artifact. Empty list means valid.

    A declared level below the baseline is reported here so the operator learns their policy is a
    no-op, rather than believing they loosened something. It is reported as an error and not merely
    ignored, because a policy that does not do what it says is a governance defect even when the
    failure mode is safe.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["policy artifact must be a JSON object"]
    for key in _POLICY_REQUIRED_KEYS:
        if key not in artifact:
            errors.append(f"missing required key: {key}")
    if artifact.get("kind") != RATIFICATION_POLICY_KIND:
        errors.append(f"kind must be {RATIFICATION_POLICY_KIND!r}")
    if artifact.get("schema_version") != RATIFICATION_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RATIFICATION_POLICY_SCHEMA_VERSION}")
    if not isinstance(artifact.get("allow_grants"), bool):
        errors.append("allow_grants must be a boolean")

    levels = artifact.get("levels")
    if not isinstance(levels, dict):
        errors.append("levels must be an object mapping point ids to levels")
    else:
        for point_id, level in sorted(levels.items()):
            point = get_ratification_point(str(point_id))
            if point is None:
                errors.append(f"levels: no ratification point is registered as {point_id!r}")
                continue
            if level not in POLICY_LEVELS:
                errors.append(f"levels[{point_id}]: unknown level {level!r}")
                continue
            baseline = baseline_level(point)
            if level_rank(str(level)) < level_rank(baseline):
                errors.append(
                    f"levels[{point_id}]: declares {level!r}, which is weaker than the registry "
                    f"baseline {baseline!r}; a policy may only tighten (the declared level is ignored)"
                )

    if not errors:
        expected = digest_jsonable(artifact, digest_key="policy_digest")
        if artifact.get("policy_digest") != expected:
            errors.append("policy_digest does not match artifact content")
    return errors


def validate_ratification_policy_file(path: Path) -> list[str]:
    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"unreadable policy artifact: {exc}"]
    return validate_ratification_policy_artifact(artifact)


def write_policy(policy: dict[str, Any], *, root: Path) -> Path:
    path = policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_policy(*, root: Path) -> dict[str, Any] | None:
    """The policy on file, or None. An invalid policy is treated as absent by the readers below.

    Absent-and-invalid collapse to the same *effective* answer only because absence already means
    "baseline applies", and baseline is the safe direction. A policy that fails validation because
    it tried to loosen something therefore cannot loosen it by being malformed either.
    """
    path = policy_path(root)
    if not path.is_file():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return artifact if isinstance(artifact, dict) else None


@dataclass(frozen=True)
class PolicyDecision:
    """The level actually in force for one point, and what put it there."""

    point_id: str
    level: str
    because: str


def effective_level(point_id: str, *, root: Path | None = None) -> PolicyDecision:
    """The ratification level in force for ``point_id`` right now.

    ``max(baseline, declared)`` over the ordered ladder. A declared level weaker than the baseline
    cannot take effect -- not because it is rejected here, but because ``max`` keeps the baseline.
    """
    point = get_ratification_point(point_id)
    if point is None:
        return PolicyDecision(
            point_id=point_id,
            level=LEVEL_REQUIRE_APPROVAL_ARTIFACT,
            because=f"no ratification point is registered as `{point_id}`; failing closed",
        )

    baseline = baseline_level(point)
    level = baseline
    because = f"registry baseline is `{baseline}`"

    policy = load_policy(root=root) if root is not None else None
    if policy is None:
        return PolicyDecision(point_id=point_id, level=level, because=because)

    if policy.get("allow_grants") is False:
        raised = stricter_of(level, LEVEL_ALWAYS_PROMPT)
        if raised != level:
            level, because = raised, "project policy sets `allow_grants: false`"

    declared = policy.get("levels", {})
    if isinstance(declared, dict):
        candidate = declared.get(point_id)
        if isinstance(candidate, str) and candidate in POLICY_LEVELS:
            raised = stricter_of(level, candidate)
            if raised != level:
                level = raised
                because = f"project policy sets `{candidate}` for this point"

    return PolicyDecision(point_id=point_id, level=level, because=because)


def requires_approval_artifact(point_id: str, *, root: Path | None = None) -> bool:
    return effective_level(point_id, root=root).level == LEVEL_REQUIRE_APPROVAL_ARTIFACT
