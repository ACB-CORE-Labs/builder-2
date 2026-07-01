from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.target_profiles import target_names
from builder_ii.workflow_records import canonical_digest, file_ref


MEMORY_ATOM_KIND = "builder_ii.memory_atom"
MEMORY_INDEX_KIND = "builder_ii.memory_index"
MEMORY_RECONSTRUCTION_KIND = "builder_ii.memory_reconstruction"
MEMORY_SEARCH_RESULT_KIND = "builder_ii.memory_search_result"
MEMORY_SCHEMA_VERSION = 1

CLAIM_BOUNDARIES = (
    "schema_validity_only",
    "operator_declared_intent",
    "metadata_only",
    "verification_result",
    "reviewed_handoff",
    "derived_summary",
    "proposal_only",
)
REVIEW_STATES = (
    "generated",
    "validated",
    "operator_reviewed",
    "superseded",
    "rejected",
)
ATOM_STATES = ("ACTIVE", "STALE", "SUPERSEDED", "REJECTED")
SOURCE_TRUTH_STATES = ("SOURCE_BOUND", "DERIVED_SUMMARY")
SUMMARY_ORIGINS = ("artifact_projection", "operator", "model", "none")
SEARCH_MODE = "deterministic_lexical"
RECONSTRUCTION_MODE = "deterministic_lexical_replay"

_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HANDOFF_SOURCE_KINDS = {
    "builder_ii.handoff_note",
    "builder_ii.handoff_artifact",
    "builder_ii.handoff_bundle_record",
}


def _normalize_text(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def _normalize_tags(values: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized = {
        str(value).strip().lower()
        for value in (values or [])
        if str(value).strip()
    }
    return sorted(normalized)


def _sorted_refs(values: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    refs = list(values or [])
    return sorted(
        refs,
        key=lambda item: (
            str(item.get("kind", "")),
            str(item.get("path", "")),
            str(item.get("sha256", "")),
            str(item.get("role", "")),
        ),
    )


def _default_governance(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "opaque_vector_store": "DISABLED",
        "autonomous_memory_writes": "DISABLED",
        "hidden_memory": False,
        "model_summary_is_authority": False,
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "grants_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _with_digest(value: dict[str, Any], field: str) -> dict[str, Any]:
    payload = dict(value)
    payload[field] = canonical_digest(payload)
    return payload


def create_memory_ref(
    *,
    kind: str,
    path: str | Path,
    sha256: str,
    role: str,
    name: str = "",
    required: bool = True,
) -> dict[str, Any]:
    resolved_name = name or Path(path).name
    return file_ref(
        kind=kind,
        path=path,
        sha256=sha256,
        role=role,
        name=resolved_name,
        required=required,
    )


def create_memory_atom(
    *,
    artifact_ref: dict[str, Any],
    target_profile: str,
    task: str,
    created_at_utc: str,
    claim_boundary: str,
    review_state: str = "validated",
    atom_state: str = "ACTIVE",
    source_truth_state: str = "SOURCE_BOUND",
    summary_text: str = "",
    summary_origin: str = "artifact_projection",
    tags: list[str] | tuple[str, ...] | None = None,
    source_refs: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    parent_refs: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    superseded_by_ref: dict[str, Any] | None = None,
    stale_reason: str = "",
    atom_id: str = "",
) -> dict[str, Any]:
    resolved_atom_id = _normalize_text(atom_id) or f"atom-{artifact_ref.get('sha256', '')[:12] or 'unknown'}"
    base = {
        "kind": MEMORY_ATOM_KIND,
        "schema_version": MEMORY_SCHEMA_VERSION,
        "atom_state": atom_state,
        "atom_id": resolved_atom_id,
        "target_profile": _normalize_text(target_profile),
        "task": _normalize_text(task),
        "created_at_utc": _normalize_text(created_at_utc),
        "artifact_ref": dict(artifact_ref),
        "source_refs": _sorted_refs(source_refs),
        "parent_refs": _sorted_refs(parent_refs),
        "superseded_by_ref": dict(superseded_by_ref) if isinstance(superseded_by_ref, dict) else None,
        "claim_boundary": _normalize_text(claim_boundary),
        "review_state": _normalize_text(review_state),
        "source_truth_state": _normalize_text(source_truth_state),
        "summary_text": _normalize_text(summary_text),
        "summary_origin": _normalize_text(summary_origin),
        "tags": _normalize_tags(tags),
        "stale_reason": _normalize_text(stale_reason),
        "artifact_is_authority": False,
        "grants_authority": False,
        "model_summary_is_authority": False,
        "target_repo_mutation": False,
        "governance": _default_governance("memory_atom"),
    }
    return _with_digest(base, "atom_digest")


def create_memory_index_entry(atom: dict[str, Any], *, path: str | Path) -> dict[str, Any]:
    return {
        "atom_id": atom.get("atom_id", ""),
        "atom_ref": create_memory_ref(
            kind=MEMORY_ATOM_KIND,
            path=path,
            sha256=canonical_digest(atom),
            role="memory_atom",
            name=str(atom.get("atom_id", "")),
        ),
        "artifact_kind": atom.get("artifact_ref", {}).get("kind", ""),
        "artifact_ref": dict(atom.get("artifact_ref", {})),
        "task": atom.get("task", ""),
        "claim_boundary": atom.get("claim_boundary", ""),
        "review_state": atom.get("review_state", ""),
        "atom_state": atom.get("atom_state", ""),
        "source_truth_state": atom.get("source_truth_state", ""),
        "summary_text": atom.get("summary_text", ""),
        "summary_origin": atom.get("summary_origin", ""),
        "tags": list(atom.get("tags", [])),
        "created_at_utc": atom.get("created_at_utc", ""),
        "source_ref_count": len(atom.get("source_refs", [])),
        "parent_ref_count": len(atom.get("parent_refs", [])),
        "stale_reason": atom.get("stale_reason", ""),
    }


def _state_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    return {
        state: sum(1 for entry in entries if entry.get("atom_state") == state)
        for state in ATOM_STATES
    }


def _review_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    return {
        state: sum(1 for entry in entries if entry.get("review_state") == state)
        for state in REVIEW_STATES
    }


def _tag_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        for tag in entry.get("tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items()))


def create_memory_index(
    *,
    entries: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    target_profile: str,
    created_at_utc: str,
    index_name: str = "",
    task_scope: str = "",
) -> dict[str, Any]:
    ordered_entries = sorted(
        list(entries),
        key=lambda item: (
            str(item.get("atom_id", "")),
            str(item.get("atom_ref", {}).get("sha256", "")),
            str(item.get("atom_ref", {}).get("path", "")),
        ),
    )
    base = {
        "kind": MEMORY_INDEX_KIND,
        "schema_version": MEMORY_SCHEMA_VERSION,
        "index_state": "INDEXED_ONLY",
        "target_profile": _normalize_text(target_profile),
        "task_scope": _normalize_text(task_scope),
        "created_at_utc": _normalize_text(created_at_utc),
        "index_name": _normalize_text(index_name) or f"{target_profile}-memory-index",
        "search_policy": {
            "mode": SEARCH_MODE,
            "opaque_vector_store": "DISABLED",
            "autonomous_memory_writes": "DISABLED",
            "hidden_memory": False,
        },
        "entries": ordered_entries,
        "atom_count": len(ordered_entries),
        "state_counts": _state_counts(ordered_entries),
        "review_counts": _review_counts(ordered_entries),
        "tag_counts": _tag_counts(ordered_entries),
        "atom_refs": [entry["atom_ref"] for entry in ordered_entries],
        "source_artifact_refs": _sorted_refs([entry["artifact_ref"] for entry in ordered_entries if "artifact_ref" in entry]),
        "deterministic_sort_key": "atom_ref.sha256_atom_id",
        "stale_atom_ids": [entry["atom_id"] for entry in ordered_entries if entry.get("atom_state") == "STALE"],
        "superseded_atom_ids": [entry["atom_id"] for entry in ordered_entries if entry.get("atom_state") == "SUPERSEDED"],
        "search_keys": ["tags", "task", "summary_text", "artifact_kind"],
        "artifact_is_authority": False,
        "grants_authority": False,
        "governance": _default_governance("memory_index"),
    }
    return _with_digest(base, "index_digest")


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _match_entry(entry: dict[str, Any], query_tokens: list[str]) -> tuple[int, list[str]]:
    task_tokens = set(_tokenize(str(entry.get("task", ""))))
    summary_tokens = set(_tokenize(str(entry.get("summary_text", ""))))
    artifact_tokens = set(_tokenize(str(entry.get("artifact_kind", ""))))
    tag_tokens = set(str(tag) for tag in entry.get("tags", []))

    if not query_tokens:
        reasons = ["empty_query_replay_order"]
        if entry.get("atom_state") == "STALE":
            reasons.append("state:stale")
        return 1, reasons

    score = 0
    reasons: list[str] = []
    for token in query_tokens:
        if token in tag_tokens:
            score += 3
            reasons.append(f"tag:{token}")
        if token in task_tokens:
            score += 2
            reasons.append(f"task:{token}")
        if token in summary_tokens:
            score += 1
            reasons.append(f"summary:{token}")
        if token in artifact_tokens:
            score += 1
            reasons.append(f"kind:{token}")
    if score > 0 and entry.get("atom_state") == "STALE":
        reasons.append("state:stale")
    return score, _dedupe(reasons)


def create_memory_search_result(
    index: dict[str, Any],
    *,
    index_ref: dict[str, Any],
    query: str,
    created_at_utc: str,
    limit: int = 10,
) -> dict[str, Any]:
    normalized_query = _normalize_text(query)
    query_tokens = _dedupe(_tokenize(normalized_query))
    entries = list(index.get("entries", []))
    ranked: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for entry in entries:
        atom_ref = dict(entry.get("atom_ref", {}))
        atom_state = entry.get("atom_state")
        if atom_state in {"SUPERSEDED", "REJECTED"}:
            excluded.append(
                {
                    "ref": atom_ref,
                    "reason": f"excluded atom_state={atom_state.lower()}",
                }
            )
            continue
        score, reasons = _match_entry(entry, query_tokens)
        if score <= 0:
            continue
        ranked.append(
            {
                "score": score,
                "match_reasons": reasons,
                "entry": entry,
            }
        )

    ranked.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item["entry"].get("atom_id", "")),
            str(item["entry"].get("atom_ref", {}).get("sha256", "")),
            str(item["entry"].get("atom_ref", {}).get("path", "")),
        )
    )

    matches: list[dict[str, Any]] = []
    for rank, item in enumerate(ranked[: max(limit, 1)], start=1):
        entry = item["entry"]
        matches.append(
            {
                "rank": rank,
                "score": item["score"],
                "atom_ref": dict(entry.get("atom_ref", {})),
                "atom_id": entry.get("atom_id", ""),
                "artifact_kind": entry.get("artifact_kind", ""),
                "artifact_ref": dict(entry.get("artifact_ref", {})),
                "task": entry.get("task", ""),
                "claim_boundary": entry.get("claim_boundary", ""),
                "review_state": entry.get("review_state", ""),
                "atom_state": entry.get("atom_state", ""),
                "source_truth_state": entry.get("source_truth_state", ""),
                "summary_text": entry.get("summary_text", ""),
                "tags": list(entry.get("tags", [])),
                "match_reasons": list(item["match_reasons"]),
            }
        )

    base = {
        "kind": MEMORY_SEARCH_RESULT_KIND,
        "schema_version": MEMORY_SCHEMA_VERSION,
        "search_state": "SEARCH_RESULTS_ONLY",
        "created_at_utc": _normalize_text(created_at_utc),
        "index_ref": dict(index_ref),
        "query": normalized_query,
        "normalized_query_tokens": query_tokens,
        "search_policy": {
            "mode": SEARCH_MODE,
            "limit": max(limit, 1),
            "include_states": ["ACTIVE", "STALE"],
            "excluded_states": ["SUPERSEDED", "REJECTED"],
            "opaque_vector_store": "DISABLED",
            "hidden_memory": False,
        },
        "total_indexed_atoms": int(index.get("atom_count", 0)),
        "match_count": len(matches),
        "matches": matches,
        "excluded_atom_refs": excluded,
        "artifact_is_authority": False,
        "grants_authority": False,
        "governance": _default_governance("memory_search_result"),
    }
    return _with_digest(base, "search_result_digest")


def create_memory_reconstruction(
    index: dict[str, Any],
    *,
    index_ref: dict[str, Any],
    query: str,
    created_at_utc: str,
    max_atoms: int = 5,
) -> dict[str, Any]:
    search_result = create_memory_search_result(
        index,
        index_ref=index_ref,
        query=query,
        created_at_utc=created_at_utc,
        limit=max_atoms,
    )
    selected_atom_refs = [dict(match["atom_ref"]) for match in search_result.get("matches", [])]
    warnings: list[str] = []
    known_gaps: list[str] = []
    context: list[dict[str, Any]] = []
    for order, match in enumerate(search_result.get("matches", []), start=1):
        if match.get("atom_state") == "STALE":
            warnings.append(f"{match.get('atom_id', '')} is marked STALE")
        context.append(
            {
                "order": order,
                "atom_ref": dict(match.get("atom_ref", {})),
                "atom_id": match.get("atom_id", ""),
                "artifact_kind": match.get("artifact_kind", ""),
                "artifact_ref": dict(match.get("artifact_ref", {})),
                "task": match.get("task", ""),
                "claim_boundary": match.get("claim_boundary", ""),
                "review_state": match.get("review_state", ""),
                "atom_state": match.get("atom_state", ""),
                "source_truth_state": match.get("source_truth_state", ""),
                "summary_text": match.get("summary_text", ""),
                "tags": list(match.get("tags", [])),
                "match_reasons": list(match.get("match_reasons", [])),
            }
        )

    if not context:
        known_gaps.append("No ACTIVE or STALE atoms matched the reconstruction query.")
    elif int(index.get("atom_count", 0)) > max_atoms:
        known_gaps.append("Reconstruction is truncated to max_atoms for replay-stable review.")

    base = {
        "kind": MEMORY_RECONSTRUCTION_KIND,
        "schema_version": MEMORY_SCHEMA_VERSION,
        "reconstruction_state": "RECONSTRUCTED_ONLY",
        "created_at_utc": _normalize_text(created_at_utc),
        "index_ref": dict(index_ref),
        "query": _normalize_text(query),
        "reconstruction_policy": {
            "mode": RECONSTRUCTION_MODE,
            "max_atoms": max(max_atoms, 1),
            "include_states": ["ACTIVE", "STALE"],
            "excluded_states": ["SUPERSEDED", "REJECTED"],
            "opaque_vector_store": "DISABLED",
            "hidden_memory": False,
            "autonomous_memory_writes": "DISABLED",
        },
        "selected_atom_refs": selected_atom_refs,
        "excluded_atom_refs": list(search_result.get("excluded_atom_refs", [])),
        "source_refs": _sorted_refs([dict(match["artifact_ref"]) for match in search_result.get("matches", []) if "artifact_ref" in match]),
        "stale_warnings": [f"{match.get('atom_id', '')} is marked STALE" for match in search_result.get("matches", []) if match.get("atom_state") == "STALE"],
        "supersession_warnings": [f"{item['ref']['name']} is superseded" for item in search_result.get("excluded_atom_refs", []) if "superseded" in item.get("reason", "")],
        "no_source_truth_inflation": True,
        "deterministic_ordering_declaration": "matches are sorted by score descending, then atom_id ascending",
        "reconstructed_context": context,
        "warnings": _dedupe(warnings),
        "known_gaps": _dedupe(known_gaps),
        "artifact_is_authority": False,
        "grants_authority": False,
        "governance": _default_governance("memory_reconstruction"),
    }
    return _with_digest(base, "reconstruction_digest")


def _validate_ref(value: Any, *, field: str, expected_kind: str | None = None) -> list[str]:
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    errors: list[str] = []
    for key in ("role", "kind", "path", "sha256", "name"):
        if key not in value:
            errors.append(f"{field}.{key} is required")
        elif not isinstance(value.get(key), str) or not value[key]:
            errors.append(f"{field}.{key} must be a non-empty string")
    if "required" not in value:
        errors.append(f"{field}.required is required")
    elif not isinstance(value.get("required"), bool):
        errors.append(f"{field}.required must be a bool")
    if expected_kind is not None and value.get("kind") != expected_kind:
        errors.append(f"{field}.kind must be {expected_kind}")
    return errors


def _validate_string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _validate_governance(value: Any, *, capability_state: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["governance must be an object"]
    if value.get("capability_state") != capability_state:
        errors.append(f"governance.capability_state must be {capability_state}")
    for key in (
        "runtime_execution",
        "model_execution",
        "shell_execution",
        "target_repo_writes",
        "memory_mutation",
        "goose_runtime_start",
        "deepagents_runtime",
        "mcp_execution",
        "opaque_vector_store",
        "autonomous_memory_writes",
    ):
        if value.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")
    if value.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("hidden_memory", "model_summary_is_authority", "artifact_is_authority", "grants_runtime_authority", "grants_action_authority", "grants_authority"):
        if value.get(key) is not False:
            errors.append(f"governance.{key} must be false")
    if value.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_memory_atom(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["memory atom must be a JSON object"]

    if data.get("kind") != MEMORY_ATOM_KIND:
        errors.append(f"kind must be {MEMORY_ATOM_KIND}")
    if data.get("schema_version") != MEMORY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MEMORY_SCHEMA_VERSION}")
    if data.get("atom_state") not in ATOM_STATES:
        errors.append(f"atom_state must be one of: {', '.join(ATOM_STATES)}")
    if not isinstance(data.get("atom_id"), str) or not data["atom_id"]:
        errors.append("atom_id must be a non-empty string")
    if data.get("target_profile") not in target_names():
        errors.append("target_profile must be one of: generic, builder, core")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")
    if not isinstance(data.get("created_at_utc"), str) or not _TIMESTAMP_RE.match(data["created_at_utc"]):
        errors.append("created_at_utc must be an RFC3339 UTC timestamp like 2026-07-01T00:00:00Z")

    errors.extend(_validate_ref(data.get("artifact_ref"), field="artifact_ref"))

    source_refs = data.get("source_refs")
    if not isinstance(source_refs, list):
        errors.append("source_refs must be a list")
        source_refs = []
    else:
        for index, ref in enumerate(source_refs):
            errors.extend(_validate_ref(ref, field=f"source_refs[{index}]"))

    parent_refs = data.get("parent_refs")
    if not isinstance(parent_refs, list):
        errors.append("parent_refs must be a list")
        parent_refs = []
    else:
        for index, ref in enumerate(parent_refs):
            errors.extend(_validate_ref(ref, field=f"parent_refs[{index}]", expected_kind=MEMORY_ATOM_KIND))

    superseded_by_ref = data.get("superseded_by_ref")
    if superseded_by_ref is not None:
        errors.extend(_validate_ref(superseded_by_ref, field="superseded_by_ref", expected_kind=MEMORY_ATOM_KIND))

    if data.get("claim_boundary") not in CLAIM_BOUNDARIES:
        errors.append(f"claim_boundary must be one of: {', '.join(CLAIM_BOUNDARIES)}")
    if data.get("review_state") not in REVIEW_STATES:
        errors.append(f"review_state must be one of: {', '.join(REVIEW_STATES)}")
    if data.get("source_truth_state") not in SOURCE_TRUTH_STATES:
        errors.append(f"source_truth_state must be one of: {', '.join(SOURCE_TRUTH_STATES)}")
    if data.get("summary_origin") not in SUMMARY_ORIGINS:
        errors.append(f"summary_origin must be one of: {', '.join(SUMMARY_ORIGINS)}")
    if not isinstance(data.get("summary_text"), str):
        errors.append("summary_text must be a string")
    errors.extend(_validate_string_list(data.get("tags"), field="tags"))
    if not isinstance(data.get("stale_reason"), str):
        errors.append("stale_reason must be a string")

    if data.get("review_state") == "superseded" and data.get("atom_state") != "SUPERSEDED":
        errors.append("review_state superseded requires atom_state SUPERSEDED")
    if data.get("review_state") == "rejected" and data.get("atom_state") != "REJECTED":
        errors.append("review_state rejected requires atom_state REJECTED")

    if data.get("atom_state") == "STALE" and not data.get("stale_reason"):
        errors.append("stale_reason is required when atom_state is STALE")
    if data.get("atom_state") == "SUPERSEDED":
        if not data.get("stale_reason"):
            errors.append("stale_reason is required when atom_state is SUPERSEDED")
        if not isinstance(superseded_by_ref, dict):
            errors.append("superseded_by_ref is required when atom_state is SUPERSEDED")
    if data.get("atom_state") == "REJECTED" and not data.get("stale_reason"):
        errors.append("stale_reason is required when atom_state is REJECTED")

    if data.get("model_summary_is_authority") is not False:
        errors.append("model_summary_is_authority must be false")
    if data.get("target_repo_mutation") is not False:
        errors.append("target_repo_mutation must be false")

    if data.get("claim_boundary") == "derived_summary":
        if data.get("source_truth_state") != "DERIVED_SUMMARY":
            errors.append("derived_summary claim_boundary requires source_truth_state DERIVED_SUMMARY")
        if not source_refs:
            errors.append("derived_summary claim_boundary requires non-empty source_refs")

    if data.get("summary_origin") == "model":
        if data.get("claim_boundary") != "derived_summary":
            errors.append("summary_origin model requires claim_boundary derived_summary")
        if data.get("source_truth_state") != "DERIVED_SUMMARY":
            errors.append("summary_origin model requires source_truth_state DERIVED_SUMMARY")
        if not source_refs:
            errors.append("summary_origin model requires source_refs")

    artifact_kind = data.get("artifact_ref", {}).get("kind")
    if artifact_kind in _HANDOFF_SOURCE_KINDS:
        if data.get("claim_boundary") not in {"reviewed_handoff", "derived_summary"}:
            errors.append("handoff-derived memory atoms may only claim reviewed_handoff or derived_summary")
        if not source_refs:
            errors.append("handoff-derived memory atoms require source_refs to avoid source-truth inflation")

    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    errors.extend(_validate_governance(data.get("governance"), capability_state="memory_atom"))

    digest = data.get("atom_digest")
    if not isinstance(digest, str) or not digest:
        errors.append("atom_digest must be a non-empty string")
    else:
        candidate = dict(data)
        candidate.pop("atom_digest", None)
        if canonical_digest(candidate) != digest:
            errors.append("atom_digest does not match canonical content digest")

    return errors


def validate_memory_index(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["memory index must be a JSON object"]
    if data.get("kind") != MEMORY_INDEX_KIND:
        errors.append(f"kind must be {MEMORY_INDEX_KIND}")
    if data.get("schema_version") != MEMORY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MEMORY_SCHEMA_VERSION}")
    if data.get("index_state") != "INDEXED_ONLY":
        errors.append("index_state must be INDEXED_ONLY")
    if data.get("target_profile") not in target_names():
        errors.append("target_profile must be one of: generic, builder, core")
    if not isinstance(data.get("task_scope"), str):
        errors.append("task_scope must be a string")
    if not isinstance(data.get("created_at_utc"), str) or not _TIMESTAMP_RE.match(data["created_at_utc"]):
        errors.append("created_at_utc must be an RFC3339 UTC timestamp like 2026-07-01T00:00:00Z")
    if not isinstance(data.get("index_name"), str) or not data["index_name"]:
        errors.append("index_name must be a non-empty string")

    search_policy = data.get("search_policy")
    if not isinstance(search_policy, dict):
        errors.append("search_policy must be an object")
    else:
        if search_policy.get("mode") != SEARCH_MODE:
            errors.append(f"search_policy.mode must be {SEARCH_MODE}")
        if search_policy.get("opaque_vector_store") != "DISABLED":
            errors.append("search_policy.opaque_vector_store must be DISABLED")
        if search_policy.get("autonomous_memory_writes") != "DISABLED":
            errors.append("search_policy.autonomous_memory_writes must be DISABLED")
        if search_policy.get("hidden_memory") is not False:
            errors.append("search_policy.hidden_memory must be false")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        entries = []
    else:
        seen_refs: set[tuple[str, str]] = set()
        for index, entry in enumerate(entries):
            prefix = f"entries[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(entry.get("atom_id"), str) or not entry["atom_id"]:
                errors.append(f"{prefix}.atom_id must be a non-empty string")
            errors.extend(_validate_ref(entry.get("atom_ref"), field=f"{prefix}.atom_ref", expected_kind=MEMORY_ATOM_KIND))
            errors.extend(_validate_ref(entry.get("artifact_ref"), field=f"{prefix}.artifact_ref"))
            ref = entry.get("atom_ref", {})
            ref_key = (str(ref.get("sha256", "")), str(ref.get("path", "")))
            if ref_key in seen_refs:
                errors.append(f"{prefix}.atom_ref duplicates another entry")
            seen_refs.add(ref_key)
            if not isinstance(entry.get("artifact_kind"), str) or not entry["artifact_kind"]:
                errors.append(f"{prefix}.artifact_kind must be a non-empty string")
            if not isinstance(entry.get("task"), str) or not entry["task"]:
                errors.append(f"{prefix}.task must be a non-empty string")
            if entry.get("claim_boundary") not in CLAIM_BOUNDARIES:
                errors.append(f"{prefix}.claim_boundary must be a supported claim boundary")
            if entry.get("review_state") not in REVIEW_STATES:
                errors.append(f"{prefix}.review_state must be a supported review_state")
            if entry.get("atom_state") not in ATOM_STATES:
                errors.append(f"{prefix}.atom_state must be a supported atom_state")
            if entry.get("source_truth_state") not in SOURCE_TRUTH_STATES:
                errors.append(f"{prefix}.source_truth_state must be a supported source_truth_state")
            if entry.get("summary_origin") not in SUMMARY_ORIGINS:
                errors.append(f"{prefix}.summary_origin must be a supported summary_origin")
            if not isinstance(entry.get("summary_text"), str):
                errors.append(f"{prefix}.summary_text must be a string")
            errors.extend(_validate_string_list(entry.get("tags"), field=f"{prefix}.tags"))
            if not isinstance(entry.get("created_at_utc"), str) or not _TIMESTAMP_RE.match(entry["created_at_utc"]):
                errors.append(f"{prefix}.created_at_utc must be an RFC3339 UTC timestamp like 2026-07-01T00:00:00Z")
            for count_field in ("source_ref_count", "parent_ref_count"):
                if not isinstance(entry.get(count_field), int) or entry[count_field] < 0:
                    errors.append(f"{prefix}.{count_field} must be a non-negative integer")
            if not isinstance(entry.get("stale_reason"), str):
                errors.append(f"{prefix}.stale_reason must be a string")

    if data.get("atom_count") != len(entries):
        errors.append("atom_count must equal len(entries)")
    if data.get("state_counts") != _state_counts(entries):
        errors.append("state_counts must match entry atom_state values")
    if data.get("review_counts") != _review_counts(entries):
        errors.append("review_counts must match entry review_state values")
    if data.get("tag_counts") != _tag_counts(entries):
        errors.append("tag_counts must match entry tag values")

    atom_refs = data.get("atom_refs")
    if not isinstance(atom_refs, list):
        errors.append("atom_refs must be a list")
    else:
        for idx, ref in enumerate(atom_refs):
            errors.extend(_validate_ref(ref, field=f"atom_refs[{idx}]", expected_kind=MEMORY_ATOM_KIND))

    source_artifact_refs = data.get("source_artifact_refs")
    if not isinstance(source_artifact_refs, list):
        errors.append("source_artifact_refs must be a list")
    else:
        for idx, ref in enumerate(source_artifact_refs):
            errors.extend(_validate_ref(ref, field=f"source_artifact_refs[{idx}]"))

    if data.get("deterministic_sort_key") != "atom_ref.sha256_atom_id":
        errors.append("deterministic_sort_key must be atom_ref.sha256_atom_id")

    stale_atom_ids = data.get("stale_atom_ids")
    if not isinstance(stale_atom_ids, list) or any(not isinstance(x, str) for x in stale_atom_ids):
        errors.append("stale_atom_ids must be a list of strings")
    else:
        expected_stale = [entry["atom_id"] for entry in entries if entry.get("atom_state") == "STALE"]
        if stale_atom_ids != expected_stale:
            errors.append("stale_atom_ids must match entry atom_state STALE values")

    superseded_atom_ids = data.get("superseded_atom_ids")
    if not isinstance(superseded_atom_ids, list) or any(not isinstance(x, str) for x in superseded_atom_ids):
        errors.append("superseded_atom_ids must be a list of strings")
    else:
        expected_superseded = [entry["atom_id"] for entry in entries if entry.get("atom_state") == "SUPERSEDED"]
        if superseded_atom_ids != expected_superseded:
            errors.append("superseded_atom_ids must match entry atom_state SUPERSEDED values")

    if data.get("search_keys") != ["tags", "task", "summary_text", "artifact_kind"]:
        errors.append("search_keys must be ['tags', 'task', 'summary_text', 'artifact_kind']")

    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    errors.extend(_validate_governance(data.get("governance"), capability_state="memory_index"))

    digest = data.get("index_digest")
    if not isinstance(digest, str) or not digest:
        errors.append("index_digest must be a non-empty string")
    else:
        candidate = dict(data)
        candidate.pop("index_digest", None)
        if canonical_digest(candidate) != digest:
            errors.append("index_digest does not match canonical content digest")
    return errors


def validate_memory_search_result(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["memory search result must be a JSON object"]
    if data.get("kind") != MEMORY_SEARCH_RESULT_KIND:
        errors.append(f"kind must be {MEMORY_SEARCH_RESULT_KIND}")
    if data.get("schema_version") != MEMORY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MEMORY_SCHEMA_VERSION}")
    if data.get("search_state") != "SEARCH_RESULTS_ONLY":
        errors.append("search_state must be SEARCH_RESULTS_ONLY")
    if not isinstance(data.get("created_at_utc"), str) or not _TIMESTAMP_RE.match(data["created_at_utc"]):
        errors.append("created_at_utc must be an RFC3339 UTC timestamp like 2026-07-01T00:00:00Z")
    errors.extend(_validate_ref(data.get("index_ref"), field="index_ref", expected_kind=MEMORY_INDEX_KIND))
    if not isinstance(data.get("query"), str):
        errors.append("query must be a string")
    errors.extend(_validate_string_list(data.get("normalized_query_tokens"), field="normalized_query_tokens"))

    policy = data.get("search_policy")
    if not isinstance(policy, dict):
        errors.append("search_policy must be an object")
    else:
        if policy.get("mode") != SEARCH_MODE:
            errors.append(f"search_policy.mode must be {SEARCH_MODE}")
        if not isinstance(policy.get("limit"), int) or policy["limit"] <= 0:
            errors.append("search_policy.limit must be a positive integer")
        if policy.get("include_states") != ["ACTIVE", "STALE"]:
            errors.append("search_policy.include_states must be ['ACTIVE', 'STALE']")
        if policy.get("excluded_states") != ["SUPERSEDED", "REJECTED"]:
            errors.append("search_policy.excluded_states must be ['SUPERSEDED', 'REJECTED']")
        if policy.get("opaque_vector_store") != "DISABLED":
            errors.append("search_policy.opaque_vector_store must be DISABLED")
        if policy.get("hidden_memory") is not False:
            errors.append("search_policy.hidden_memory must be false")

    if not isinstance(data.get("total_indexed_atoms"), int) or data["total_indexed_atoms"] < 0:
        errors.append("total_indexed_atoms must be a non-negative integer")

    matches = data.get("matches")
    if not isinstance(matches, list):
        errors.append("matches must be a list")
        matches = []
    else:
        for index, match in enumerate(matches, start=1):
            prefix = f"matches[{index - 1}]"
            if not isinstance(match, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if match.get("rank") != index:
                errors.append(f"{prefix}.rank must be contiguous starting at 1")
            if not isinstance(match.get("score"), int) or match["score"] <= 0:
                errors.append(f"{prefix}.score must be a positive integer")
            errors.extend(_validate_ref(match.get("atom_ref"), field=f"{prefix}.atom_ref", expected_kind=MEMORY_ATOM_KIND))
            errors.extend(_validate_ref(match.get("artifact_ref"), field=f"{prefix}.artifact_ref"))
            for field in ("atom_id", "artifact_kind", "task", "claim_boundary", "review_state", "atom_state", "source_truth_state"):
                if not isinstance(match.get(field), str) or not match[field]:
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            if not isinstance(match.get("summary_text"), str):
                errors.append(f"{prefix}.summary_text must be a string")
            errors.extend(_validate_string_list(match.get("tags"), field=f"{prefix}.tags"))
            errors.extend(_validate_string_list(match.get("match_reasons"), field=f"{prefix}.match_reasons"))

    if data.get("match_count") != len(matches):
        errors.append("match_count must equal len(matches)")

    excluded = data.get("excluded_atom_refs")
    if not isinstance(excluded, list):
        errors.append("excluded_atom_refs must be a list")
    else:
        for index, item in enumerate(excluded):
            prefix = f"excluded_atom_refs[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            errors.extend(_validate_ref(item.get("ref"), field=f"{prefix}.ref", expected_kind=MEMORY_ATOM_KIND))
            if not isinstance(item.get("reason"), str) or not item["reason"]:
                errors.append(f"{prefix}.reason must be a non-empty string")

    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    errors.extend(_validate_governance(data.get("governance"), capability_state="memory_search_result"))

    digest = data.get("search_result_digest")
    if not isinstance(digest, str) or not digest:
        errors.append("search_result_digest must be a non-empty string")
    else:
        candidate = dict(data)
        candidate.pop("search_result_digest", None)
        if canonical_digest(candidate) != digest:
            errors.append("search_result_digest does not match canonical content digest")
    return errors


def validate_memory_reconstruction(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["memory reconstruction must be a JSON object"]
    if data.get("kind") != MEMORY_RECONSTRUCTION_KIND:
        errors.append(f"kind must be {MEMORY_RECONSTRUCTION_KIND}")
    if data.get("schema_version") != MEMORY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MEMORY_SCHEMA_VERSION}")
    if data.get("reconstruction_state") != "RECONSTRUCTED_ONLY":
        errors.append("reconstruction_state must be RECONSTRUCTED_ONLY")
    if not isinstance(data.get("created_at_utc"), str) or not _TIMESTAMP_RE.match(data["created_at_utc"]):
        errors.append("created_at_utc must be an RFC3339 UTC timestamp like 2026-07-01T00:00:00Z")
    errors.extend(_validate_ref(data.get("index_ref"), field="index_ref", expected_kind=MEMORY_INDEX_KIND))
    if not isinstance(data.get("query"), str):
        errors.append("query must be a string")

    policy = data.get("reconstruction_policy")
    if not isinstance(policy, dict):
        errors.append("reconstruction_policy must be an object")
    else:
        if policy.get("mode") != RECONSTRUCTION_MODE:
            errors.append(f"reconstruction_policy.mode must be {RECONSTRUCTION_MODE}")
        if not isinstance(policy.get("max_atoms"), int) or policy["max_atoms"] <= 0:
            errors.append("reconstruction_policy.max_atoms must be a positive integer")
        if policy.get("include_states") != ["ACTIVE", "STALE"]:
            errors.append("reconstruction_policy.include_states must be ['ACTIVE', 'STALE']")
        if policy.get("excluded_states") != ["SUPERSEDED", "REJECTED"]:
            errors.append("reconstruction_policy.excluded_states must be ['SUPERSEDED', 'REJECTED']")
        if policy.get("opaque_vector_store") != "DISABLED":
            errors.append("reconstruction_policy.opaque_vector_store must be DISABLED")
        if policy.get("hidden_memory") is not False:
            errors.append("reconstruction_policy.hidden_memory must be false")
        if policy.get("autonomous_memory_writes") != "DISABLED":
            errors.append("reconstruction_policy.autonomous_memory_writes must be DISABLED")

    selected_refs = data.get("selected_atom_refs")
    if not isinstance(selected_refs, list):
        errors.append("selected_atom_refs must be a list")
        selected_refs = []
    else:
        for index, ref in enumerate(selected_refs):
            errors.extend(_validate_ref(ref, field=f"selected_atom_refs[{index}]", expected_kind=MEMORY_ATOM_KIND))

    excluded = data.get("excluded_atom_refs")
    if not isinstance(excluded, list):
        errors.append("excluded_atom_refs must be a list")
    else:
        for index, item in enumerate(excluded):
            prefix = f"excluded_atom_refs[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            errors.extend(_validate_ref(item.get("ref"), field=f"{prefix}.ref", expected_kind=MEMORY_ATOM_KIND))
            if not isinstance(item.get("reason"), str) or not item["reason"]:
                errors.append(f"{prefix}.reason must be a non-empty string")

    context = data.get("reconstructed_context")
    if not isinstance(context, list):
        errors.append("reconstructed_context must be a list")
        context = []
    else:
        for index, item in enumerate(context, start=1):
            prefix = f"reconstructed_context[{index - 1}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if item.get("order") != index:
                errors.append(f"{prefix}.order must be contiguous starting at 1")
            errors.extend(_validate_ref(item.get("atom_ref"), field=f"{prefix}.atom_ref", expected_kind=MEMORY_ATOM_KIND))
            errors.extend(_validate_ref(item.get("artifact_ref"), field=f"{prefix}.artifact_ref"))
            for field in ("atom_id", "artifact_kind", "task", "claim_boundary", "review_state", "atom_state", "source_truth_state"):
                if not isinstance(item.get(field), str) or not item[field]:
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            if not isinstance(item.get("summary_text"), str):
                errors.append(f"{prefix}.summary_text must be a string")
            errors.extend(_validate_string_list(item.get("tags"), field=f"{prefix}.tags"))
            errors.extend(_validate_string_list(item.get("match_reasons"), field=f"{prefix}.match_reasons"))

    source_refs = data.get("source_refs")
    if not isinstance(source_refs, list):
        errors.append("source_refs must be a list")
    else:
        for idx, ref in enumerate(source_refs):
            errors.extend(_validate_ref(ref, field=f"source_refs[{idx}]"))

    stale_warnings = data.get("stale_warnings")
    if not isinstance(stale_warnings, list) or any(not isinstance(x, str) for x in stale_warnings):
        errors.append("stale_warnings must be a list of strings")

    supersession_warnings = data.get("supersession_warnings")
    if not isinstance(supersession_warnings, list) or any(not isinstance(x, str) for x in supersession_warnings):
        errors.append("supersession_warnings must be a list of strings")

    if data.get("no_source_truth_inflation") is not True:
        errors.append("no_source_truth_inflation must be true")

    if data.get("deterministic_ordering_declaration") != "matches are sorted by score descending, then atom_id ascending":
        errors.append("deterministic_ordering_declaration must be 'matches are sorted by score descending, then atom_id ascending'")

    errors.extend(_validate_string_list(data.get("warnings"), field="warnings"))
    errors.extend(_validate_string_list(data.get("known_gaps"), field="known_gaps"))

    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    errors.extend(_validate_governance(data.get("governance"), capability_state="memory_reconstruction"))

    digest = data.get("reconstruction_digest")
    if not isinstance(digest, str) or not digest:
        errors.append("reconstruction_digest must be a non-empty string")
    else:
        candidate = dict(data)
        candidate.pop("reconstruction_digest", None)
        if canonical_digest(candidate) != digest:
            errors.append("reconstruction_digest does not match canonical content digest")
    return errors


def _validate_file(path: Path, validator: Any) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validator(data)


def validate_memory_atom_file(path: Path) -> list[str]:
    return _validate_file(path, validate_memory_atom)


def validate_memory_index_file(path: Path) -> list[str]:
    return _validate_file(path, validate_memory_index)


def validate_memory_reconstruction_file(path: Path) -> list[str]:
    return _validate_file(path, validate_memory_reconstruction)


def validate_memory_search_result_file(path: Path) -> list[str]:
    return _validate_file(path, validate_memory_search_result)


def dumps_memory_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_memory_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_memory_record(record), encoding="utf-8")


def write_memory_atom(atom: dict[str, Any], output: Path) -> None:
    errors = validate_memory_atom(atom)
    if errors:
        raise ValueError("invalid memory atom: " + "; ".join(errors))
    write_memory_record(atom, output)


def write_memory_index(index: dict[str, Any], output: Path) -> None:
    errors = validate_memory_index(index)
    if errors:
        raise ValueError("invalid memory index: " + "; ".join(errors))
    write_memory_record(index, output)


def write_memory_reconstruction(reconstruction: dict[str, Any], output: Path) -> None:
    errors = validate_memory_reconstruction(reconstruction)
    if errors:
        raise ValueError("invalid memory reconstruction: " + "; ".join(errors))
    write_memory_record(reconstruction, output)


def write_memory_search_result(search_result: dict[str, Any], output: Path) -> None:
    errors = validate_memory_search_result(search_result)
    if errors:
        raise ValueError("invalid memory search result: " + "; ".join(errors))
    write_memory_record(search_result, output)
