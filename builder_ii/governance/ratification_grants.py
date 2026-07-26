"""Standing ratification grants: an operator's recorded, revocable delegation of one confirmation.

A grant is the answer to "don't make me re-type a digest I already reviewed, forty times a day"
that is *not* an ``auto: true`` config flag. A config flag deletes the authority decision. A
grant relocates it: the operator makes one explicit, digest-bound, attributable decision, and
every confirmation it later satisfies names the grant that satisfied it, in the receipt and in
the ledger. Friction moves; responsibility does not.

THE INVARIANT THIS MODULE EXISTS TO CARRY:

    A grant is evidence that an operator delegated a confirmation. It is never the authority
    to skip one.

That is why :func:`consult_ratification_grant` recomputes
:func:`~builder_ii.governance.ratification_points.grant_eligibility` from the live
command-authority registry on **every** consultation and never reads the ``eligibility_at_grant``
block recorded inside the artifact. The recorded block is a receipt of what was true when the
operator decided; it is deliberately not load-bearing, so a command whose authority later
tightens invalidates its outstanding grants with no one remembering to revoke them. A grant
artifact that has been edited to claim eligibility it never had therefore buys nothing: the
claim is not the thing that is read.

Absence is never an implicit grant. Every path out of :func:`consult_ratification_grant` that
is not an affirmatively matched, validated, unrevoked grant against a currently-eligible point
returns ``satisfied=False`` with a reason naming the fact that decided it.
"""

from __future__ import annotations

import json
import os
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

RATIFICATION_GRANT_KIND = "builder_ii.ratification_grant"
RATIFICATION_GRANT_SCHEMA_VERSION = 1
RATIFICATION_REVOCATION_KIND = "builder_ii.ratification_grant_revocation"
RATIFICATION_REVOCATION_SCHEMA_VERSION = 1

#: The `approval_mode` a consuming receipt records when a grant satisfied its confirmation.
#: Deliberately distinct from `interactive_digest_prefix_confirmation`: a receipt must never
#: claim a human typed something a grant satisfied.
APPROVAL_MODE_STANDING_GRANT = "standing_ratification_grant"

#: Default store root, relative to the working directory, matching the `.builder/artifacts`
#: convention the onboarding lane already uses. Overridable per call (tests, alternate roots)
#: and by `BUILDER_RATIFICATION_ROOT` for operators whose artifact root is elsewhere.
DEFAULT_RATIFICATION_DIRNAME = "ratification"
RATIFICATION_ROOT_ENV = "BUILDER_RATIFICATION_ROOT"

_GRANT_REQUIRED_KEYS = (
    "kind",
    "schema_version",
    "point_id",
    "command",
    "granted_by",
    "created_at",
    "eligibility_at_grant",
    "governance",
    "grant_digest",
)

_REVOCATION_REQUIRED_KEYS = (
    "kind",
    "schema_version",
    "grant_digest",
    "point_id",
    "revoked_by",
    "revoked_at",
    "reason",
    "revocation_digest",
)


def resolve_ratification_root(root: Path | None = None) -> Path:
    """The grant store root: explicit argument, then env override, then `.builder/artifacts`."""
    if root is not None:
        return Path(root)
    override = os.environ.get(RATIFICATION_ROOT_ENV, "").strip()
    if override:
        return Path(override)
    return Path(".builder") / "artifacts" / DEFAULT_RATIFICATION_DIRNAME


def grants_dir(root: Path | None = None) -> Path:
    return resolve_ratification_root(root) / "grants"


def revocations_dir(root: Path | None = None) -> Path:
    return resolve_ratification_root(root) / "revocations"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _governance_block() -> dict[str, Any]:
    return {
        "artifact_is_authority": False,
        "capability_state": "operator_delegated_confirmation_only",
        "originates_approval": False,
        "note": (
            "Evidence that an operator delegated one named confirmation. Eligibility is recomputed "
            "from the live command-authority registry at consult time and is never read from this file."
        ),
    }


def build_ratification_grant(
    point: RatificationPoint,
    *,
    granted_by: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a digest-bound grant artifact for ``point``.

    The caller is responsible for having checked eligibility and refused an ineligible point:
    this function records the eligibility it observes but does not enforce it, because enforcement
    lives at consult time where it cannot go stale.
    """
    eligibility = grant_eligibility(point)
    artifact = {
        "kind": RATIFICATION_GRANT_KIND,
        "schema_version": RATIFICATION_GRANT_SCHEMA_VERSION,
        "point_id": point.id,
        "command": point.command,
        "ratification_kind": point.kind,
        "granted_by": granted_by,
        "created_at": created_at or _now_iso(),
        "what_is_ratified": point.what_is_ratified,
        "consequence_of_auto": point.consequence_of_auto,
        # Recorded, never read back as authority. See the module docstring.
        "eligibility_at_grant": {
            "eligible": eligibility.eligible,
            "because": eligibility.because,
        },
        "governance": _governance_block(),
    }
    return attach_digest(artifact, digest_key="grant_digest")


def build_ratification_revocation(
    grant: dict[str, Any],
    *,
    revoked_by: str,
    reason: str,
    revoked_at: str | None = None,
) -> dict[str, Any]:
    """Build a digest-bound revocation of ``grant``."""
    artifact = {
        "kind": RATIFICATION_REVOCATION_KIND,
        "schema_version": RATIFICATION_REVOCATION_SCHEMA_VERSION,
        "grant_digest": str(grant.get("grant_digest", "")),
        "point_id": str(grant.get("point_id", "")),
        "revoked_by": revoked_by,
        "revoked_at": revoked_at or _now_iso(),
        "reason": reason,
        "governance": _governance_block(),
    }
    return attach_digest(artifact, digest_key="revocation_digest")


def validate_ratification_grant_artifact(artifact: Any) -> list[str]:
    """Schema and digest errors in a grant artifact. Empty list means valid."""
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["grant artifact must be a JSON object"]
    for key in _GRANT_REQUIRED_KEYS:
        if key not in artifact:
            errors.append(f"missing required key: {key}")
    if artifact.get("kind") != RATIFICATION_GRANT_KIND:
        errors.append(f"kind must be {RATIFICATION_GRANT_KIND!r}")
    if artifact.get("schema_version") != RATIFICATION_GRANT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RATIFICATION_GRANT_SCHEMA_VERSION}")
    point_id = artifact.get("point_id")
    if isinstance(point_id, str) and get_ratification_point(point_id) is None:
        errors.append(f"no ratification point registered as {point_id!r}")
    if not errors:
        expected = digest_jsonable(artifact, digest_key="grant_digest")
        if artifact.get("grant_digest") != expected:
            errors.append("grant_digest does not match artifact content")
    return errors


def validate_ratification_revocation_artifact(artifact: Any) -> list[str]:
    """Schema and digest errors in a revocation artifact. Empty list means valid."""
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["revocation artifact must be a JSON object"]
    for key in _REVOCATION_REQUIRED_KEYS:
        if key not in artifact:
            errors.append(f"missing required key: {key}")
    if artifact.get("kind") != RATIFICATION_REVOCATION_KIND:
        errors.append(f"kind must be {RATIFICATION_REVOCATION_KIND!r}")
    if artifact.get("schema_version") != RATIFICATION_REVOCATION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RATIFICATION_REVOCATION_SCHEMA_VERSION}")
    if not errors:
        expected = digest_jsonable(artifact, digest_key="revocation_digest")
        if artifact.get("revocation_digest") != expected:
            errors.append("revocation_digest does not match artifact content")
    return errors


def validate_ratification_grant_file(path: Path) -> list[str]:
    try:
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"unreadable grant artifact: {exc}"]
    return validate_ratification_grant_artifact(artifact)


def grant_filename(grant: dict[str, Any]) -> str:
    slug = str(grant.get("point_id", "unknown")).replace(".", "-")
    return f"grant-{slug}-{str(grant.get('grant_digest', ''))[:12]}.json"


def revocation_filename(revocation: dict[str, Any]) -> str:
    return f"revocation-{str(revocation.get('revocation_digest', ''))[:12]}.json"


def write_grant(grant: dict[str, Any], *, root: Path | None = None) -> Path:
    directory = grants_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / grant_filename(grant)
    path.write_text(json.dumps(grant, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_revocation(revocation: dict[str, Any], *, root: Path | None = None) -> Path:
    directory = revocations_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / revocation_filename(revocation)
    path.write_text(json.dumps(revocation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _load_json_files(directory: Path) -> list[tuple[dict[str, Any], Path]]:
    if not directory.is_dir():
        return []
    loaded: list[tuple[dict[str, Any], Path]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            loaded.append((payload, path))
    return loaded


def load_grants(*, root: Path | None = None) -> list[tuple[dict[str, Any], Path]]:
    """Every syntactically loadable grant file in the store, valid or not.

    Validation is the caller's business: :func:`consult_ratification_grant` drops invalid grants,
    while ``builder-govern list-grants`` shows them *and* says why they are being ignored. Silently
    filtering here would hide a corrupted grant instead of reporting it.
    """
    return _load_json_files(grants_dir(root))


def load_revocations(*, root: Path | None = None) -> list[tuple[dict[str, Any], Path]]:
    return _load_json_files(revocations_dir(root))


def revoked_grant_digests(*, root: Path | None = None) -> set[str]:
    """Digests of grants with at least one valid revocation on file."""
    digests: set[str] = set()
    for revocation, _path in load_revocations(root=root):
        if validate_ratification_revocation_artifact(revocation):
            continue
        digest = revocation.get("grant_digest")
        if isinstance(digest, str) and digest:
            digests.add(digest)
    return digests


@dataclass(frozen=True)
class GrantConsultation:
    """The result of asking whether a standing grant satisfies one confirmation.

    ``because`` always names the fact that decided it, in both directions, because this string is
    printed to the operator at the moment a prompt is or is not skipped.
    """

    point_id: str
    satisfied: bool
    because: str
    grant_digest: str | None = None
    granted_by: str | None = None


def consult_ratification_grant(point_id: str, *, root: Path | None = None) -> GrantConsultation:
    """Ask whether a standing grant satisfies ``point_id`` right now.

    Recomputes eligibility from the live command-authority registry every time. Never reads
    ``eligibility_at_grant`` from the artifact -- see the module docstring for why that
    distinction is the whole design.
    """
    point = get_ratification_point(point_id)
    if point is None:
        return GrantConsultation(
            point_id=point_id,
            satisfied=False,
            because=f"no ratification point is registered as `{point_id}`",
        )

    eligibility = grant_eligibility(point)
    if not eligibility.eligible:
        return GrantConsultation(
            point_id=point_id,
            satisfied=False,
            because=f"point is not grant-eligible: {eligibility.because}",
        )

    revoked = revoked_grant_digests(root=root)
    candidates: list[dict[str, Any]] = []
    for grant, _path in load_grants(root=root):
        if grant.get("point_id") != point_id:
            continue
        if validate_ratification_grant_artifact(grant):
            continue
        digest = grant.get("grant_digest")
        if isinstance(digest, str) and digest in revoked:
            continue
        candidates.append(grant)

    if not candidates:
        return GrantConsultation(
            point_id=point_id,
            satisfied=False,
            because=f"no valid unrevoked standing grant for `{point_id}`",
        )

    newest = max(candidates, key=lambda grant: str(grant.get("created_at", "")))
    digest = str(newest.get("grant_digest", ""))
    granted_by = str(newest.get("granted_by", ""))
    return GrantConsultation(
        point_id=point_id,
        satisfied=True,
        because=f"standing grant {digest[:12]}, granted by {granted_by} on {newest.get('created_at')}",
        grant_digest=digest,
        granted_by=granted_by,
    )
