"""Ratification approvals: the artifact level 2 demands, when typing a digest is not enough.

At :data:`~builder_ii.governance.ratification_policy.LEVEL_REQUIRE_APPROVAL_ARTIFACT` a command
will not accept an interactive confirmation at all. The operator must produce a durable,
digest-bound approval artifact first and pass it on the command line, so the decision survives the
terminal it was made in and can be reviewed by someone who was not there.

This is the *opposite* end of the same axis as a standing grant, and the two can never both apply:
a grant satisfies level 0 and nothing above it, an approval satisfies level 2, and level 1 is
satisfied only by a human typing. :func:`~builder_ii.governance.ratification_policy.effective_level`
picks exactly one.

THE INVARIANT THIS MODULE EXISTS TO CARRY:

    An approval binds to the exact subject digest it approved, and to nothing else.

An approval for one overlay plan can never authorise a different overlay plan, because the subject
digest is inside the approval's own digest. It is minted only by a human typing a digest prefix --
the same confirmation grammar as the HITL patch approvals -- so an approval is always evidence a
person decided, never a delegation of that decision. There is deliberately no `--yes` on minting.

KNOWN LIMIT, stated rather than papered over: an approval is **replayable within its TTL** against
the same subject digest. It binds *what* was approved exactly; it does not track *how many times*
that approval was spent. For the setup lane this is benign -- re-applying an identical overlay plan
converges on the same declared paths -- but it is a real property, and a lane where repetition is
not benign must not reuse this artifact without adding consumption tracking.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.governance.ratification_points import RatificationPoint, get_ratification_point

RATIFICATION_APPROVAL_KIND = "builder_ii.ratification_approval"
RATIFICATION_APPROVAL_SCHEMA_VERSION = 1

#: Matches the HITL patch-approval confirmation grammar, deliberately: an operator who has learned
#: one digest-prefix confirmation in this codebase has learned all of them.
APPROVAL_CONFIRMATION_PREFIX_LENGTH = 4

#: 24 hours. An approval is a decision about a specific artifact at a specific moment; letting it
#: authorise indefinitely turns a decision into a standing permission, which is what grants are for
#: and what level 2 exists to refuse.
DEFAULT_APPROVAL_TTL_SECONDS = 24 * 60 * 60

_APPROVAL_REQUIRED_KEYS = (
    "kind",
    "schema_version",
    "point_id",
    "command",
    "subject_digest",
    "approved_by",
    "approved_at",
    "expires_at",
    "confirmation",
    "governance",
    "approval_digest",
)


def build_ratification_approval(
    point: RatificationPoint,
    *,
    subject_digest: str,
    approved_by: str,
    confirmed_digest_prefix: str,
    approved_at: int | None = None,
    ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS,
) -> dict[str, Any]:
    """Build a digest-bound approval for one point and one exact subject digest."""
    if approved_at is None:
        approved_at = int(time.time())
    artifact = {
        "kind": RATIFICATION_APPROVAL_KIND,
        "schema_version": RATIFICATION_APPROVAL_SCHEMA_VERSION,
        "point_id": point.id,
        "command": point.command,
        "subject_digest": subject_digest,
        "approved_by": approved_by,
        "approved_at": int(approved_at),
        "expires_at": int(approved_at) + int(ttl_seconds),
        "confirmation": {
            "method": "digest_prefix",
            "digest_prefix": confirmed_digest_prefix,
            "prefix_length": APPROVAL_CONFIRMATION_PREFIX_LENGTH,
        },
        "governance": {
            "artifact_is_authority": False,
            "capability_state": "human_decision_evidence",
            "originates_approval": True,
            "note": (
                "Evidence that a human approved one exact subject digest. Re-verified against the "
                "subject and the clock at use time; the artifact never substitutes for that check."
            ),
        },
    }
    return attach_digest(artifact, digest_key="approval_digest")


def _is_int(value: Any) -> bool:
    # bool is a subclass of int -- reject it so approved_at/expires_at cannot be True/False.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_ratification_approval_artifact(artifact: Any) -> list[str]:
    """Schema and digest errors in an approval artifact. Empty list means structurally valid.

    Deliberately does **not** check expiry or subject binding: those are properties of a *use*, not
    of the artifact, and are checked by :func:`check_ratification_approval` where the subject and
    the clock are both known. A validator that conflated them would report a perfectly good
    approval as malformed the moment it aged out.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["approval artifact must be a JSON object"]
    for key in _APPROVAL_REQUIRED_KEYS:
        if key not in artifact:
            errors.append(f"missing required key: {key}")
    if artifact.get("kind") != RATIFICATION_APPROVAL_KIND:
        errors.append(f"kind must be {RATIFICATION_APPROVAL_KIND!r}")
    if artifact.get("schema_version") != RATIFICATION_APPROVAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RATIFICATION_APPROVAL_SCHEMA_VERSION}")
    point_id = artifact.get("point_id")
    if isinstance(point_id, str) and get_ratification_point(point_id) is None:
        errors.append(f"no ratification point is registered as {point_id!r}")
    if not isinstance(artifact.get("subject_digest"), str) or not artifact.get("subject_digest"):
        errors.append("subject_digest must be a non-empty string")
    if not _is_int(artifact.get("approved_at")):
        errors.append("approved_at must be an integer unix timestamp")
    if not _is_int(artifact.get("expires_at")):
        errors.append("expires_at must be an integer unix timestamp")
    if (
        _is_int(artifact.get("approved_at"))
        and _is_int(artifact.get("expires_at"))
        and int(artifact["expires_at"]) <= int(artifact["approved_at"])
    ):
        errors.append("expires_at must be after approved_at")
    if not errors:
        expected = digest_jsonable(artifact, digest_key="approval_digest")
        if artifact.get("approval_digest") != expected:
            errors.append("approval_digest does not match artifact content")
    return errors


def validate_ratification_approval_file(path: Path) -> list[str]:
    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"unreadable approval artifact: {exc}"]
    return validate_ratification_approval_artifact(artifact)


def write_ratification_approval(artifact: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


@dataclass(frozen=True)
class ApprovalCheck:
    """Whether a supplied approval authorises one specific use, and why."""

    accepted: bool
    because: str
    approval_digest: str | None = None
    approved_by: str | None = None


def check_ratification_approval(
    path: Path | None,
    *,
    point_id: str,
    subject_digest: str,
    now: int | None = None,
) -> ApprovalCheck:
    """Re-verify a supplied approval against this exact use: schema, point, subject, and clock.

    Every rejection names the fact that decided it. An absent path is a rejection, not a pass:
    level 2 means the artifact is required, so "none supplied" is the most common refusal and must
    read clearly.
    """
    if path is None:
        return ApprovalCheck(
            accepted=False,
            because=f"policy requires a ratification approval artifact for `{point_id}` and none was supplied",
        )
    errors = validate_ratification_approval_file(path)
    if errors:
        return ApprovalCheck(accepted=False, because=f"approval artifact is invalid: {errors[0]}")

    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if artifact.get("point_id") != point_id:
        return ApprovalCheck(
            accepted=False,
            because=(
                f"approval is for point `{artifact.get('point_id')}`, not `{point_id}`; "
                "an approval never transfers between points"
            ),
        )
    if artifact.get("subject_digest") != subject_digest:
        return ApprovalCheck(
            accepted=False,
            because=(
                f"approval binds subject digest {str(artifact.get('subject_digest'))[:12]}, "
                f"but this operation's subject is {subject_digest[:12]}"
            ),
        )
    moment = int(time.time()) if now is None else int(now)
    if moment > int(artifact["expires_at"]):
        return ApprovalCheck(
            accepted=False,
            because=f"approval expired at {artifact['expires_at']} (now {moment}); mint a fresh one",
        )
    return ApprovalCheck(
        accepted=True,
        because=f"approval {str(artifact['approval_digest'])[:12]} by {artifact['approved_by']}",
        approval_digest=str(artifact["approval_digest"]),
        approved_by=str(artifact["approved_by"]),
    )
