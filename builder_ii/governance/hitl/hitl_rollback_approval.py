"""Distinct HITL rollback-approval artifact (plan item 1.4 — B4.3).

Threat model
------------
Before this module the rollback lane (``rollback_hitl_patch``) took a *machine-generated*
``rollback_plan`` — written by ``apply_hitl_patch`` itself — and treated a valid plan as
authorization to reverse a source mutation. That collapsed **planned ≠ approved** for the
rollback direction: the same automation that applied a patch could reverse it with no second
human decision. A rollback is itself a mutation (``git apply -R`` rewrites the working tree
and can discard work done since the apply), so it deserves its own approval boundary — exactly
like ``builder_ii.hitl_patch_approval`` guards the forward apply.

This module makes a rollback approval a **governed artifact** rather than an implicit
consequence of a plan existing. An approval only authorizes a rollback when it is:

1. **Well-formed** — the exact ``builder_ii.hitl_rollback_approval`` kind + schema version
   (strict single-version per the "Ledger Genesis" hard cut; no back-compat parsers), with a
   standard all-disabled governance block and ``artifact_is_authority == False``.
2. **Plan-bound** — its ``rollback_plan_digest`` equals the canonical digest of the exact
   rollback plan being executed. Tampering with the plan (e.g. swapping the reverse-patch ref
   or the recorded ``pre_head``) changes that digest and silently invalidates the approval.
3. **Patch-bound** — its ``patch_digest`` equals the plan's ``patch_digest``.
4. **Live** — ``now <= expires_at``; a stale approval is refused.

What this is NOT (mirrors ``hitl_patch_approval``):

* **Not a cryptographic signature.** The digests are integrity/binding checks, not proof of
  *who* approved. The trust root remains "only the operator invokes ``approve-rollback`` on
  their own machine."
* **Not a substitute for the interactive boundary.** The real approval *event* is the operator
  typing the rollback-plan-digest prefix at ``builder-hitl approve-rollback``. This artifact is
  the durable *evidence* of that event; the binding/expiry checks stop that evidence from being
  reused for a different or mutated plan.

The one-and-only *promoted* mint path is the interactive ``approve-rollback`` prompt. The
underlying ``create_hitl_rollback_approval`` is callable in-process (the demo loop mints one
against a disposable detached worktree); a programmatically-minted approval carries valid
binding but is **not** evidence of human origin — the same 1.7 promotion-gate concern recorded
for the patch-approval lane applies here. The closure audit (plan item 1.7,
``docs/audits/B4_CLOSURE_AUDIT.md``) resolved it, so the operator-invoked lane is now
``OPERATIONALLY_VERIFIED`` while the command stays Tier 3 ``hitl_runtime_candidate``, not enabled.
"""

from __future__ import annotations

import json as json_lib
import time
from pathlib import Path
from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance

# Reuse the patch-approval primitives so the two approval lanes never drift apart: one canonical
# digest algorithm, one confirmation-prefix length, one default TTL, one expiry check.
from builder_ii.governance.hitl.hitl_patch_approval import (
    APPROVAL_CONFIRMATION_PREFIX_LENGTH,
    DEFAULT_APPROVAL_TTL_SECONDS,
    _is_int,
    approval_is_expired,
    canonical_digest,
)
from builder_ii.lifecycle.setup.target_profiles import target_names

HITL_ROLLBACK_APPROVAL_KIND = "builder_ii.hitl_rollback_approval"
HITL_ROLLBACK_APPROVAL_SCHEMA_VERSION = 1

# Re-export so callers can import the shared confirmation constants from this module too.
__all__ = [
    "HITL_ROLLBACK_APPROVAL_KIND",
    "HITL_ROLLBACK_APPROVAL_SCHEMA_VERSION",
    "APPROVAL_CONFIRMATION_PREFIX_LENGTH",
    "DEFAULT_APPROVAL_TTL_SECONDS",
    "create_hitl_rollback_approval",
    "dumps_hitl_rollback_approval",
    "write_hitl_rollback_approval",
    "validate_hitl_rollback_approval",
    "validate_hitl_rollback_approval_file",
    "rollback_approval_binding_errors",
    "approval_is_expired",
    "canonical_digest",
]


def create_hitl_rollback_approval(
    rollback_plan: dict[str, Any],
    *,
    confirmed_digest_prefix: str,
    approved_by: str = "operator",
    approved_at: int | None = None,
    ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS,
) -> dict[str, Any]:
    """Mint a rollback approval bound to a specific rollback plan.

    This ONLY produces a data record. No rollback is executed and no source file is written
    here — the approval is evidence of a human decision, never authority in itself
    (``artifact_is_authority`` is always False).
    """
    if approved_at is None:
        approved_at = int(time.time())
    patch_digest = str(rollback_plan.get("patch_digest", ""))
    return {
        "kind": HITL_ROLLBACK_APPROVAL_KIND,
        "schema_version": HITL_ROLLBACK_APPROVAL_SCHEMA_VERSION,
        "target": dict(rollback_plan.get("target", {})),
        "patch_digest": patch_digest,
        "rollback_plan_digest": canonical_digest(rollback_plan),
        "approved_by": approved_by,
        "approved_at": approved_at,
        "expires_at": approved_at + int(ttl_seconds),
        "confirmation": {
            "method": "digest_prefix",
            "digest_prefix": confirmed_digest_prefix,
            "prefix_length": APPROVAL_CONFIRMATION_PREFIX_LENGTH,
        },
        "artifact_is_authority": False,
        "governance": build_standard_governance("PASSIVE_FOUNDATION"),
    }


def dumps_hitl_rollback_approval(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_rollback_approval(artifact: dict[str, Any], output: Path) -> None:
    """Write the rollback approval record to disk as JSON. No source mutation occurs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_rollback_approval(artifact), encoding="utf-8")


def validate_hitl_rollback_approval(artifact: Any) -> list[str]:
    """Validate a HITL rollback-approval artifact dict.

    Returns a list of error strings; an empty list means the artifact is structurally valid.
    This checks *shape and self-consistency* only — binding to a specific rollback plan and
    liveness are enforced separately by ``rollback_approval_binding_errors`` and
    ``approval_is_expired`` at rollback time, because they require the plan in hand.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl rollback approval artifact must be a JSON object"]

    if artifact.get("kind") != HITL_ROLLBACK_APPROVAL_KIND:
        errors.append(f"kind must be {HITL_ROLLBACK_APPROVAL_KIND}")
    if artifact.get("schema_version") != HITL_ROLLBACK_APPROVAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_ROLLBACK_APPROVAL_SCHEMA_VERSION}")

    patch_digest = artifact.get("patch_digest")
    if not isinstance(patch_digest, str) or not patch_digest:
        errors.append("patch_digest must be a non-empty string")

    plan_digest = artifact.get("rollback_plan_digest")
    if not isinstance(plan_digest, str) or len(plan_digest) != 64:
        errors.append("rollback_plan_digest must be a SHA-256 hex digest")

    if not isinstance(artifact.get("approved_by"), str) or not artifact.get("approved_by"):
        errors.append("approved_by must be a non-empty string")

    approved_at = artifact.get("approved_at")
    expires_at = artifact.get("expires_at")
    if not _is_int(approved_at):
        errors.append("approved_at must be an integer unix timestamp")
    if not _is_int(expires_at):
        errors.append("expires_at must be an integer unix timestamp")
    if (
        isinstance(approved_at, int)
        and not isinstance(approved_at, bool)
        and isinstance(expires_at, int)
        and not isinstance(expires_at, bool)
        and expires_at <= approved_at
    ):
        errors.append("expires_at must be after approved_at")

    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    confirmation = artifact.get("confirmation")
    if not isinstance(confirmation, dict):
        errors.append("confirmation must be an object")
    else:
        if confirmation.get("method") != "digest_prefix":
            errors.append("confirmation.method must be digest_prefix")
        prefix = confirmation.get("digest_prefix")
        if not isinstance(prefix, str) or not prefix:
            errors.append("confirmation.digest_prefix must be a non-empty string")
        elif isinstance(plan_digest, str) and not plan_digest.startswith(prefix):
            errors.append("confirmation.digest_prefix must be a prefix of rollback_plan_digest")

    if artifact.get("artifact_is_authority", False) is not False:
        errors.append(
            "artifact_is_authority must be false — an approval is evidence of a human "
            "decision, not self-authority"
        )

    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "PASSIVE_FOUNDATION"))

    return errors


def validate_hitl_rollback_approval_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:  # noqa: BLE001 - surface any read failure as a validation error
        return [f"failed to read file: {exc}"]
    return validate_hitl_rollback_approval(data)


def rollback_approval_binding_errors(
    approval: dict[str, Any],
    *,
    rollback_plan_digest: str,
    patch_digest: str,
) -> list[str]:
    """Check a rollback approval is bound to exactly this rollback plan.

    Assumes the approval already passed ``validate_hitl_rollback_approval``. Binding is what
    stops a valid-but-unrelated approval (or one minted for a since-tampered plan) from
    authorizing a rollback.
    """
    errors: list[str] = []
    if approval.get("patch_digest") != patch_digest:
        errors.append("approval.patch_digest does not match the rollback plan patch_digest")
    if approval.get("rollback_plan_digest") != rollback_plan_digest:
        errors.append("approval.rollback_plan_digest does not match the rollback plan content digest")
    return errors
