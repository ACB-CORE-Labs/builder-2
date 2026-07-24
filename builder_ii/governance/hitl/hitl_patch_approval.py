"""Generic HITL patch-approval artifact (plan item 1.1 — closes the weak-approval gap).

Threat model
------------
builder-II's load-bearing doctrine is **artifact ≠ authority**. Before this module,
``apply_hitl_patch`` authorized a source mutation whenever *any* JSON file carried a
``patch_digest`` string matching the proposal. That made the "approval" trivially
forgeable — an attacker (or an over-eager agent) who could write a one-line JSON file
adjacent to a proposal could authorize a patch the operator never saw. The apply step
treated a passive data file *as authority*.

This module makes an approval a **governed artifact** rather than a bare digest echo. An
approval only authorizes a mutation when it is:

1. **Well-formed** — the exact ``builder_ii.hitl_patch_approval`` kind + schema version
   (strict single-version per the "Ledger Genesis" hard cut; no back-compat parsers),
   with a standard all-disabled governance block and ``artifact_is_authority == False``.
2. **Content-bound** — its ``proposal_digest`` equals the canonical digest of the exact
   proposal being applied. Tampering with the proposal (e.g. swapping ``unified_diff``)
   changes that digest and silently invalidates the approval.
3. **Patch-bound** — its ``patch_digest`` equals the proposal's ``patch_digest``.
4. **Live** — ``now <= expires_at``; a stale approval is refused.

What this is NOT:

* **Not a cryptographic signature.** The digests are integrity/binding checks, not
  proof of *who* approved. The trust root remains "only the operator invokes the
  approve command on their own machine." An adversary with write access to the artifact
  store and the ability to run ``approve-patch`` is out of scope — that is game-over by
  construction, and no digest defends against it.
* **Not a substitute for the interactive boundary.** The real approval *event* is the
  operator typing the patch-digest prefix at ``builder-hitl approve-patch`` (an attention
  control — see ``APPROVAL_CONFIRMATION_PREFIX_LENGTH``). This artifact is the durable
  *evidence* of that event, and the binding/expiry checks stop that evidence from being
  reused for a different or mutated patch.

In short: this narrows the gap from "any JSON authorizes anything" to "a well-formed,
unexpired approval authorizes exactly the proposal it was minted for." The interactive
``approve-patch`` prompt is the only *promoted* way to mint one and the reason such an
artifact stands for a human decision. Note the underlying ``create_hitl_patch_approval``
function is itself callable in-process (e.g. the demo loop mints one against a disposable
detached worktree); a programmatically-minted approval carries valid binding but is **not**
evidence of human origin. Guaranteeing no non-interactive mint can reach a real target was the
promotion gate for this lane; the closure audit (plan item 1.7, ``docs/audits/B4_CLOSURE_AUDIT.md``)
resolved it, so the operator-invoked lane is now ``OPERATIONALLY_VERIFIED`` while the command
stays Tier 3 ``hitl_runtime_candidate``, not enabled (autonomous apply remains forbidden).
"""

from __future__ import annotations

import hashlib
import json as json_lib
import time
from pathlib import Path
from builder_ii.core.canonical_json import canonical_digest, canonical_json
from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.lifecycle.setup.target_profiles import target_names

HITL_PATCH_APPROVAL_KIND = "builder_ii.hitl_patch_approval"
HITL_PATCH_APPROVAL_SCHEMA_VERSION = 1

# The approve-patch confirmation idiom: the operator must transcribe the first N
# characters of the patch digest. This is an *attention* control (it forces the
# operator's eyes onto the identifier they are authorizing), NOT a security control —
# the full digest is displayed on screen. It exists so approval can never degrade into
# reflexive ``[y/N]`` mashing. See craft doctrine #3 / external review D.
APPROVAL_CONFIRMATION_PREFIX_LENGTH = 4

# Default validity window for an approval before it must be applied. Bounded so a stale
# approval cannot authorize a mutation indefinitely; overridable at approve time.
DEFAULT_APPROVAL_TTL_SECONDS = 86_400  # 24 hours


def create_hitl_patch_approval(
    proposal: dict[str, Any],
    *,
    confirmed_digest_prefix: str,
    approved_by: str = "operator",
    approved_at: int | None = None,
    ttl_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS,
) -> dict[str, Any]:
    """Mint an approval record bound to a specific proposal.

    This ONLY produces a data record. No patch is applied and no source file is written
    here — the approval is evidence of a human decision, never authority in itself
    (``artifact_is_authority`` is always False).

    Non-interactive-mint containment (B4 closure audit): this is a public building block, so an
    in-process caller can compute ``confirmed_digest_prefix`` and mint a valid approval without a
    human at a TTY. That is why the *promoted, operator-facing* mint path is exclusively the
    interactive ``builder-hitl approve-patch`` CLI (which forces the operator to transcribe the
    digest prefix; there is deliberately no non-interactive approval mode on that command). The
    only sanctioned in-process minter is the governed demo loop, bounded to a disposable detached
    worktree of the demo target with mandatory auto-rollback. Regardless of how the artifact is produced,
    ``apply_hitl_patch`` re-verifies the binding, expiry, and command-authority gate before any
    source write — the artifact never substitutes for the boundary.
    """
    if approved_at is None:
        approved_at = int(time.time())
    patch_digest = str(proposal.get("patch_digest", ""))
    return {
        "kind": HITL_PATCH_APPROVAL_KIND,
        "schema_version": HITL_PATCH_APPROVAL_SCHEMA_VERSION,
        "target": dict(proposal.get("target", {})),
        "patch_digest": patch_digest,
        "proposal_digest": canonical_digest(proposal),
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


def dumps_hitl_patch_approval(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_patch_approval(artifact: dict[str, Any], output: Path) -> None:
    """Write the approval record to disk as JSON. No source mutation occurs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_patch_approval(artifact), encoding="utf-8")


def _is_int(value: Any) -> bool:
    # bool is a subclass of int — reject it so approved_at/expires_at can't be True/False.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_hitl_patch_approval(artifact: Any) -> list[str]:
    """Validate a HITL patch-approval artifact dict.

    Returns a list of error strings; an empty list means the artifact is structurally
    valid. This checks *shape and self-consistency* only — binding to a specific
    proposal and liveness are enforced separately by ``approval_binding_errors`` and
    ``approval_is_expired`` at apply time, because they require the proposal in hand.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl patch approval artifact must be a JSON object"]

    if artifact.get("kind") != HITL_PATCH_APPROVAL_KIND:
        errors.append(f"kind must be {HITL_PATCH_APPROVAL_KIND}")
    if artifact.get("schema_version") != HITL_PATCH_APPROVAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PATCH_APPROVAL_SCHEMA_VERSION}")

    patch_digest = artifact.get("patch_digest")
    if not isinstance(patch_digest, str) or not patch_digest:
        errors.append("patch_digest must be a non-empty string")

    proposal_digest = artifact.get("proposal_digest")
    if not isinstance(proposal_digest, str) or len(proposal_digest) != 64:
        errors.append("proposal_digest must be a SHA-256 hex digest")

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
        elif isinstance(patch_digest, str) and not patch_digest.startswith(prefix):
            errors.append("confirmation.digest_prefix must be a prefix of patch_digest")

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


def validate_hitl_patch_approval_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:  # noqa: BLE001 - surface any read failure as a validation error
        return [f"failed to read file: {exc}"]
    return validate_hitl_patch_approval(data)


def approval_binding_errors(
    approval: dict[str, Any],
    *,
    proposal_digest: str,
    patch_digest: str,
) -> list[str]:
    """Check an approval is bound to exactly this proposal.

    Assumes the approval already passed ``validate_hitl_patch_approval``. Binding is what
    stops a valid-but-unrelated approval (or one minted for a since-tampered proposal)
    from authorizing a mutation.
    """
    errors: list[str] = []
    if approval.get("patch_digest") != patch_digest:
        errors.append("approval.patch_digest does not match the proposal patch_digest")
    if approval.get("proposal_digest") != proposal_digest:
        errors.append("approval.proposal_digest does not match the proposal content digest")
    return errors


def approval_is_expired(approval: dict[str, Any], *, now: int) -> bool:
    """Return True if the approval is expired or carries no valid expiry (fail closed)."""
    expires_at = approval.get("expires_at")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool):
        return True
    return now > expires_at
