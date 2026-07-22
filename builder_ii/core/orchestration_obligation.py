"""Ladder 4 obligation kind — the minted unit of delegated work under a parent seal.

Constitution, Law 1: nothing runs as a subagent step unless an obligation exists first —
who must produce what artifact kind, under what boundary, citing which file-refs (never
dumps), spending which budget partition, under which parent seal. No ticket, no run.

This module is the artifact algebra only: create/dumps/write/validate for the
`builder_ii.orchestration_obligation` kind, plus the pure budget-conservation helpers
(`remaining`, `fits_within`). Mint-time runtime enforcement, lane-policy registration, and
the CLI surface are out of scope here (Ladder 4 PR-3/PR-4) — these helpers provide the
algebra those later PRs enforce against.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Sequence

from builder_ii.core.config_schema import attach_digest, digest_jsonable
from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance

OBLIGATION_KIND = "builder_ii.orchestration_obligation"
OBLIGATION_SCHEMA_VERSION = 1

# obligation_kind -> lane is a many-to-one mapping owned by orchestration_lane_policy.py
# (Ladder 4 PR-2); this module only needs the closed value sets to validate shape.
OBLIGATION_KINDS = ("planning_step", "interactive_ops", "model_call", "mutation", "verification")
LANES = ("deepagents", "goose", "gateway", "hitl_patch", "verify")

BUDGET_FIELDS = ("max_subagents", "max_events", "max_output_bytes", "max_human_gates")

TASK_MAX_CHARS = 2000
REF_FIELD_MAX_CHARS = 512
_FORBIDDEN_REF_KEYS = frozenset({"content", "body", "text"})
_SHA256_HEX = frozenset("0123456789abcdef")

# R4: root seal default for the mint-time human-gates ceiling (operator attention as
# conserved physics). Not enforced here — recorded for callers building a root grant.
DEFAULT_ROOT_MAX_HUMAN_GATES = 2


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in _SHA256_HEX for char in value.lower())


def _clean_str_list(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def create_orchestration_obligation(
    *,
    lane: str,
    obligation_kind: str,
    task: str,
    output_contract_expected_kind: str,
    output_contract_required_evidence_kinds: Sequence[str] | None = None,
    denied_actions: Sequence[str] | None = None,
    refused_lanes: Sequence[str] | None = None,
    file_refs: Sequence[dict[str, Any]] | None = None,
    briefing_bytes: int,
    budget_partition: dict[str, int],
    parent_ref: dict[str, str],
    lane_policy_digest: str,
    subagent_profile: str,
) -> dict[str, Any]:
    """Build a `builder_ii.orchestration_obligation` artifact.

    `obligation_id` is `attach_digest` over the canonical content (every other field);
    because the underlying digest is computed over sort-keyed canonical JSON, the id is
    stable under field reordering of the input.
    """
    content: dict[str, Any] = {
        "kind": OBLIGATION_KIND,
        "schema_version": OBLIGATION_SCHEMA_VERSION,
        "lane": lane,
        "obligation_kind": obligation_kind,
        "task": task,
        "boundary": {
            "denied_actions": _clean_str_list(denied_actions),
            "refused_lanes": _clean_str_list(refused_lanes),
        },
        "output_contract": {
            "expected_kind": output_contract_expected_kind,
            "required_evidence_kinds": _clean_str_list(output_contract_required_evidence_kinds),
        },
        "file_refs": [dict(ref) for ref in (file_refs or [])],
        "briefing_bytes": briefing_bytes,
        "budget_partition": dict(budget_partition),
        "parent_ref": dict(parent_ref),
        "lane_policy_digest": lane_policy_digest,
        "subagent_profile": subagent_profile,
        "governance": build_standard_governance("orchestration_obligation"),
    }
    return attach_digest(content, digest_key="obligation_id")


def dumps_orchestration_obligation(obligation: dict[str, Any]) -> str:
    return json_lib.dumps(obligation, indent=2, sort_keys=True) + "\n"


def write_orchestration_obligation(obligation: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_obligation(obligation), encoding="utf-8")


def _walk_ref_for_dump(value: Any, *, index: int, path: str, errors: list[str]) -> None:
    """Recursively reject smuggled dump content anywhere inside one file_refs entry."""
    if isinstance(value, dict):
        for key, sub_value in value.items():
            key_str = str(key)
            sub_path = f"{path}.{key_str}" if path else key_str
            if key_str.strip().lower() in _FORBIDDEN_REF_KEYS:
                errors.append(
                    f"file_refs[{index}].{sub_path} uses forbidden key {key_str!r} "
                    "(file_refs must cite, never carry dump content)"
                )
            _walk_ref_for_dump(sub_value, index=index, path=sub_path, errors=errors)
    elif isinstance(value, list):
        for position, item in enumerate(value):
            _walk_ref_for_dump(item, index=index, path=f"{path}[{position}]", errors=errors)
    elif isinstance(value, str):
        if len(value) > REF_FIELD_MAX_CHARS:
            label = f"file_refs[{index}].{path}" if path else f"file_refs[{index}]"
            errors.append(f"{label} exceeds {REF_FIELD_MAX_CHARS} chars (anti-dump bound)")


def validate_orchestration_obligation(obligation: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(obligation, dict):
        return ["orchestration obligation must be a JSON object"]

    if obligation.get("kind") != OBLIGATION_KIND:
        errors.append(f"kind must be {OBLIGATION_KIND}")
    if obligation.get("schema_version") != OBLIGATION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {OBLIGATION_SCHEMA_VERSION}")

    if obligation.get("lane") not in LANES:
        errors.append(f"lane must be one of: {', '.join(LANES)}")

    if obligation.get("obligation_kind") not in OBLIGATION_KINDS:
        errors.append(f"obligation_kind must be one of: {', '.join(OBLIGATION_KINDS)}")

    task = obligation.get("task")
    if not isinstance(task, str) or not task.strip():
        errors.append("task must be a non-empty string")
    elif len(task) > TASK_MAX_CHARS:
        errors.append(f"task must be at most {TASK_MAX_CHARS} chars")

    boundary = obligation.get("boundary")
    if not isinstance(boundary, dict):
        errors.append("boundary must be an object")
    else:
        for field in ("denied_actions", "refused_lanes"):
            value = boundary.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"boundary.{field} must be a list of strings")

    output_contract = obligation.get("output_contract")
    if not isinstance(output_contract, dict):
        errors.append("output_contract must be an object")
    else:
        expected_kind = output_contract.get("expected_kind")
        if not isinstance(expected_kind, str) or not expected_kind.strip():
            errors.append("output_contract.expected_kind must be a non-empty string")
        required_evidence_kinds = output_contract.get("required_evidence_kinds")
        if not isinstance(required_evidence_kinds, list) or not all(
            isinstance(item, str) for item in required_evidence_kinds
        ):
            errors.append("output_contract.required_evidence_kinds must be a list of strings")

    file_refs = obligation.get("file_refs")
    if not isinstance(file_refs, list):
        errors.append("file_refs must be a list")
    else:
        for index, ref in enumerate(file_refs):
            if not isinstance(ref, dict):
                errors.append(f"file_refs[{index}] must be an object")
                continue
            path_value = ref.get("path")
            if not isinstance(path_value, str) or not path_value.strip():
                errors.append(f"file_refs[{index}].path must be a non-empty string")
            sha_value = ref.get("sha256")
            if not isinstance(sha_value, str) or not sha_value.strip():
                errors.append(f"file_refs[{index}].sha256 must be a non-empty string")
            _walk_ref_for_dump(ref, index=index, path="", errors=errors)

    briefing_bytes = obligation.get("briefing_bytes")
    briefing_bytes_ok = isinstance(briefing_bytes, int) and not isinstance(briefing_bytes, bool) and briefing_bytes >= 0
    if not briefing_bytes_ok:
        errors.append("briefing_bytes must be a non-negative integer")

    budget_partition = obligation.get("budget_partition")
    if not isinstance(budget_partition, dict):
        errors.append("budget_partition must be an object")
    else:
        for field in BUDGET_FIELDS:
            value = budget_partition.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"budget_partition.{field} must be a non-negative integer")
        max_output_bytes = budget_partition.get("max_output_bytes")
        if (
            briefing_bytes_ok
            and isinstance(briefing_bytes, int)
            and isinstance(max_output_bytes, int)
            and not isinstance(max_output_bytes, bool)
            and briefing_bytes > max_output_bytes
        ):
            errors.append("briefing_bytes must be <= budget_partition.max_output_bytes")

    parent_ref = obligation.get("parent_ref")
    if not isinstance(parent_ref, dict):
        errors.append("parent_ref must be an object")
    else:
        has_seal = "seal_digest" in parent_ref
        has_obligation = "obligation_digest" in parent_ref
        if has_seal == has_obligation:
            errors.append("parent_ref must contain exactly one of seal_digest or obligation_digest")
        else:
            key = "seal_digest" if has_seal else "obligation_digest"
            if not _is_sha256(parent_ref.get(key)):
                errors.append(f"parent_ref.{key} must be a 64-character hex digest")
        extra_keys = sorted(set(parent_ref.keys()) - {"seal_digest", "obligation_digest"})
        if extra_keys:
            errors.append(f"parent_ref must not contain extra keys: {extra_keys}")

    if not _is_sha256(obligation.get("lane_policy_digest")):
        errors.append("lane_policy_digest must be a 64-character hex digest")

    subagent_profile = obligation.get("subagent_profile")
    if not isinstance(subagent_profile, str) or not subagent_profile.strip():
        errors.append("subagent_profile must be a non-empty string")

    errors.extend(validate_standard_governance(obligation.get("governance"), "orchestration_obligation"))

    obligation_id = obligation.get("obligation_id")
    if not _is_sha256(obligation_id):
        errors.append("obligation_id must be a 64-character hex digest")
    elif obligation_id != digest_jsonable(obligation, digest_key="obligation_id"):
        errors.append("obligation_id does not match the canonical digest of its content (tampered or stale)")

    return errors


def validate_orchestration_obligation_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_orchestration_obligation(data)


def remaining(parent_budget: dict[str, int], minted_children: Sequence[dict[str, int]] = ()) -> dict[str, int]:
    """Compute the parent's remaining budget under v1 grants-not-loans semantics.

    remaining(parent) = grant(parent) - sum(grant(child) for child in minted_children)

    v1 tracks only mint-time commitments (no runtime spend accounting here — that lives in
    the existing envelope event/byte counters, wired in PR-4). No refunds in v1: an unspent
    child grant does NOT return to the parent, even after that child obligation closes; that
    reclamation is an explicit phase-2 deferral, not something to "helpfully" add here.
    """
    totals: dict[str, int] = {field: int(parent_budget.get(field, 0)) for field in BUDGET_FIELDS}
    for child in minted_children:
        for field in BUDGET_FIELDS:
            totals[field] -= int(child.get(field, 0))
    return totals


def fits_within(
    child_budget: dict[str, int],
    parent_budget: dict[str, int],
    minted_children: Sequence[dict[str, int]] = (),
) -> bool:
    """True iff `child_budget` fits component-wise inside `remaining(parent_budget, minted_children)`.

    Fail-closed: a missing/negative/non-integer component on either side refuses the fit.
    This is the mint-time ⊆ check (R4); it does not mutate or record anything — the caller
    (PR-4's runtime) is responsible for recording the mint (and its ledger event) only after
    this returns True.
    """
    remaining_budget = remaining(parent_budget, minted_children)
    for field in BUDGET_FIELDS:
        child_value = child_budget.get(field)
        if not isinstance(child_value, int) or isinstance(child_value, bool) or child_value < 0:
            return False
        if child_value > remaining_budget.get(field, -1):
            return False
    return True
