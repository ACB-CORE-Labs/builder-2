from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable
from builder_ii.verification_execution_approval import (
    VERIFICATION_EXECUTION_APPROVAL_KIND,
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_plan import (
    VERIFICATION_EXECUTION_PLAN_KIND,
    validate_verification_execution_plan_artifact,
)
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    VERIFICATION_EXECUTION_RECEIPT_KIND,
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
)

VERIFICATION_EXECUTION_LEDGER_RECORD_KIND = "builder_ii.verification_execution_ledger_record"
VERIFICATION_EXECUTION_LEDGER_RECORD_SCHEMA_VERSION = 1
VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_KIND = "builder_ii.verification_execution_ledger_query_report"
VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_SCHEMA_VERSION = 1
VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND = "builder_ii.verification_execution_ledger_integrity_report"
VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_SCHEMA_VERSION = 1
VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND = (
    "builder_ii.verification_execution_ledger_reconstruction_report"
)
VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_SCHEMA_VERSION = 1
LEDGER_RECORD_STATE = "PASSIVE_INDEX_ONLY"
_REQUIRED_SUBJECT_REF_ROLES = (
    "verification_execution_plan",
    "verification_execution_approval",
    "verification_execution_receipt",
)
_EXPECTED_SUBJECT_REF_KINDS = {
    "verification_execution_plan": VERIFICATION_EXECUTION_PLAN_KIND,
    "verification_execution_approval": VERIFICATION_EXECUTION_APPROVAL_KIND,
    "verification_execution_receipt": VERIFICATION_EXECUTION_RECEIPT_KIND,
}


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.expanduser().resolve().read_bytes()).hexdigest()


def _display_path(path: Path, repo_path: Path | None = None) -> Path:
    resolved_path = path.expanduser().resolve()
    if repo_path is None:
        return resolved_path
    try:
        return resolved_path.relative_to(repo_path.expanduser().resolve())
    except ValueError:
        return resolved_path


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _dedupe_errors(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def _artifact_ref(
    *,
    role: str,
    kind: str,
    path: Path,
    repo_path: Path | None = None,
    digest: str | None = None,
) -> dict[str, Any]:
    resolved_path = path.expanduser().resolve()
    ref: dict[str, Any] = {
        "role": role,
        "kind": kind,
        "path": str(_display_path(resolved_path, repo_path)),
        "sha256": _sha256_file(resolved_path),
        "required": True,
    }
    if digest:
        ref["artifact_digest"] = digest
    return ref


def _default_governance() -> dict[str, Any]:
    return {
        "capability_state": "verification_execution_ledger_record",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT LEDGER ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "replay_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _default_integrity_governance() -> dict[str, Any]:
    return {
        "capability_state": "verification_execution_ledger_integrity_report",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "replay_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _default_reconstruction_governance() -> dict[str, Any]:
    return {
        "capability_state": "verification_execution_ledger_reconstruction_report",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "replay_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _ledger_root_target_repo(resolved_ledger_root: Path) -> Path | None:
    if resolved_ledger_root.name == "ledger" and resolved_ledger_root.parent.name == ".builder":
        return resolved_ledger_root.parent.parent
    return None


def _ledger_json_paths(resolved_ledger_root: Path) -> list[Path]:
    if not resolved_ledger_root.exists() or not resolved_ledger_root.is_dir():
        return []
    return sorted((path for path in resolved_ledger_root.glob("*.json") if path.is_file()), key=lambda path: str(path))


def _record_receipt_digest(record: dict[str, Any]) -> str:
    refs = record.get("subject_refs")
    if not isinstance(refs, list):
        return ""
    for ref in refs:
        if isinstance(ref, dict) and ref.get("role") == "verification_execution_receipt":
            digest = ref.get("artifact_digest")
            return digest if isinstance(digest, str) else ""
    return ""


def _ledger_row_path(path: Path, record: dict[str, Any] | None, display_repo: Path | None) -> str:
    if record is not None and _is_non_empty_string(record.get("target_repo")):
        display_repo = Path(str(record["target_repo"]))
    return str(_display_path(path, display_repo))


def _ledger_record_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    record = row.get("record") if isinstance(row.get("record"), dict) else {}
    return (
        str(record.get("recorded_at", "")),
        str(record.get("chain_digest", "")),
        str(record.get("ledger_record_id", "")),
        str(row.get("path", "")),
    )


def _canonical_sha256(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _record_digest(record: dict[str, Any]) -> str:
    digest = record.get("verification_execution_ledger_record_digest")
    return digest if isinstance(digest, str) else ""


def load_verification_execution_ledger_records(ledger_root: Path) -> dict[str, Any]:
    rejected: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        resolved = ledger_root.expanduser().resolve()
    except OSError as exc:
        errors.append(f"failed to resolve ledger_root: {exc}")
        return {
            "ledger_root": str(ledger_root),
            "records": [],
            "rejected": [],
            "errors": errors,
            "valid": False,
        }

    display_repo = _ledger_root_target_repo(resolved)
    if resolved.exists() and not resolved.is_dir():
        errors.append("ledger_root must be a directory")
        rejected.append({"path": str(resolved), "errors": ["ledger_root must be a directory"]})
    for path in _ledger_json_paths(resolved):
        try:
            record = _load_json_object(path)
        except (OSError, ValueError, json_lib.JSONDecodeError) as exc:
            rejected.append(
                {
                    "path": _ledger_row_path(path, None, display_repo),
                    "errors": [f"failed to load verification execution ledger record: {exc}"],
                }
            )
            continue
        record_errors = validate_verification_execution_ledger_record(record)
        if record_errors:
            rejected.append(
                {
                    "path": _ledger_row_path(path, record, display_repo),
                    "errors": record_errors,
                }
            )
            continue
        rows.append(
            {
                "path": _ledger_row_path(path, record, display_repo),
                "receipt_digest": _record_receipt_digest(record),
                "chain_digest": record.get("chain_digest", ""),
                "receipt_status": record.get("receipt_status", ""),
                "runner_mode": record.get("runner_mode", ""),
                "record": record,
            }
        )
    rows.sort(key=_ledger_record_sort_key)
    rejected.sort(key=lambda item: str(item.get("path", "")))
    return {
        "ledger_root": str(resolved),
        "records": rows,
        "rejected": rejected,
        "errors": errors,
        "valid": not errors,
    }


def _count_by(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        value = row.get(field)
        if isinstance(value, str) and value:
            counts[value] = counts.get(value, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _count_process_result_statuses(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        record = row.get("record") if isinstance(row.get("record"), dict) else {}
        statuses = record.get("process_result_statuses")
        if not isinstance(statuses, list):
            continue
        for status in statuses:
            if isinstance(status, str) and status:
                counts[status] = counts.get(status, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def summarize_verification_execution_ledger_records(
    records: list[dict[str, Any]],
    *,
    available_record_count: int | None = None,
    rejected_count: int = 0,
) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "available_record_count": len(records) if available_record_count is None else available_record_count,
        "rejected_count": rejected_count,
        "by_receipt_status": _count_by(records, "receipt_status"),
        "by_runner_mode": _count_by(records, "runner_mode"),
        "by_process_result_status": _count_process_result_statuses(records),
    }


def _matches_ledger_query(
    row: dict[str, Any],
    *,
    receipt_digest: str | None = None,
    chain_digest: str | None = None,
    receipt_status: str | None = None,
    runner_mode: str | None = None,
) -> bool:
    if receipt_digest is not None and row.get("receipt_digest") != receipt_digest:
        return False
    if chain_digest is not None and row.get("chain_digest") != chain_digest:
        return False
    if receipt_status is not None and row.get("receipt_status") != receipt_status:
        return False
    if runner_mode is not None and row.get("runner_mode") != runner_mode:
        return False
    return True


def query_verification_execution_ledger_records(
    *,
    ledger_root: Path,
    receipt_digest: str | None = None,
    chain_digest: str | None = None,
    receipt_status: str | None = None,
    runner_mode: str | None = None,
) -> dict[str, Any]:
    loaded = load_verification_execution_ledger_records(ledger_root)
    all_records = loaded["records"]
    records = [
        row
        for row in all_records
        if _matches_ledger_query(
            row,
            receipt_digest=receipt_digest,
            chain_digest=chain_digest,
            receipt_status=receipt_status,
            runner_mode=runner_mode,
        )
    ]
    return {
        "kind": VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_KIND,
        "schema_version": VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_SCHEMA_VERSION,
        "ledger_root": loaded["ledger_root"],
        "filters": {
            "receipt_digest": receipt_digest,
            "chain_digest": chain_digest,
            "receipt_status": receipt_status,
            "runner_mode": runner_mode,
        },
        "summary": summarize_verification_execution_ledger_records(
            records,
            available_record_count=len(all_records),
            rejected_count=len(loaded["rejected"]),
        ),
        "records": records,
        "rejected": loaded["rejected"],
        "errors": loaded["errors"],
        "valid": loaded["valid"],
    }


def query_verification_execution_ledger_by_receipt_digest(*, ledger_root: Path, receipt_digest: str) -> dict[str, Any]:
    return query_verification_execution_ledger_records(ledger_root=ledger_root, receipt_digest=receipt_digest)


def query_verification_execution_ledger_by_chain_digest(*, ledger_root: Path, chain_digest: str) -> dict[str, Any]:
    return query_verification_execution_ledger_records(ledger_root=ledger_root, chain_digest=chain_digest)


def query_verification_execution_ledger_by_receipt_status(*, ledger_root: Path, receipt_status: str) -> dict[str, Any]:
    return query_verification_execution_ledger_records(ledger_root=ledger_root, receipt_status=receipt_status)


def query_verification_execution_ledger_by_runner_mode(*, ledger_root: Path, runner_mode: str) -> dict[str, Any]:
    return query_verification_execution_ledger_records(ledger_root=ledger_root, runner_mode=runner_mode)


def _integrity_record_row(row: dict[str, Any]) -> dict[str, Any]:
    record = row.get("record") if isinstance(row.get("record"), dict) else {}
    return {
        "path": row.get("path", ""),
        "ledger_record_id": record.get("ledger_record_id", ""),
        "verification_execution_ledger_record_digest": _record_digest(record),
        "record_sha256": _canonical_sha256(record) if isinstance(record, dict) else "",
        "recorded_at": record.get("recorded_at", ""),
        "chain_digest": record.get("chain_digest", ""),
        "receipt_digest": row.get("receipt_digest", ""),
        "receipt_status": record.get("receipt_status", ""),
        "runner_mode": record.get("runner_mode", ""),
        "ledger_index": record.get("ledger_index"),
        "previous_ledger_record_digest": record.get("previous_ledger_record_digest"),
    }


def _ledger_record_evidence_ref(row: dict[str, Any]) -> dict[str, Any]:
    record = row.get("record") if isinstance(row.get("record"), dict) else {}
    return {
        "role": "verification_execution_ledger_record",
        "kind": VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
        "path": row.get("path", ""),
        "sha256": _canonical_sha256(record) if isinstance(record, dict) else "",
        "artifact_digest": _record_digest(record),
        "required": True,
    }


def _subject_refs_by_role(record: dict[str, Any], role: str) -> list[dict[str, Any]]:
    refs = record.get("subject_refs")
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict) and ref.get("role") == role]


def _subject_artifact_digest(record: dict[str, Any], role: str) -> str:
    refs = _subject_refs_by_role(record, role)
    if len(refs) != 1:
        return ""
    digest = refs[0].get("artifact_digest")
    return digest if isinstance(digest, str) else ""


def _validate_subject_ref_integrity(row: dict[str, Any]) -> list[str]:
    record = row.get("record") if isinstance(row.get("record"), dict) else {}
    path = str(row.get("path", ""))
    errors: list[str] = []
    for role in _REQUIRED_SUBJECT_REF_ROLES:
        refs = _subject_refs_by_role(record, role)
        if len(refs) != 1:
            errors.append(f"{path}: subject_refs must contain exactly one {role} ref")
            continue
        ref = refs[0]
        expected_kind = _EXPECTED_SUBJECT_REF_KINDS[role]
        if ref.get("kind") != expected_kind:
            errors.append(f"{path}: {role} ref kind must be {expected_kind}")
        if not _is_sha256_hex(ref.get("artifact_digest")):
            errors.append(f"{path}: {role} ref artifact_digest must be a SHA-256 hex digest")

    plan_digest = _subject_artifact_digest(record, "verification_execution_plan")
    approval_digest = _subject_artifact_digest(record, "verification_execution_approval")
    receipt_digest = _subject_artifact_digest(record, "verification_execution_receipt")
    if all(_is_sha256_hex(value) for value in (plan_digest, approval_digest, receipt_digest)):
        expected_chain_digest = digest_jsonable(
            {
                "plan_digest": plan_digest,
                "approval_digest": approval_digest,
                "receipt_digest": receipt_digest,
                "receipt_status": record.get("receipt_status"),
                "runner_mode": record.get("runner_mode"),
            }
        )
        if record.get("chain_digest") != expected_chain_digest:
            errors.append(f"{path}: chain_digest does not match plan/approval/receipt subject digests")
        if row.get("receipt_digest") != receipt_digest:
            errors.append(f"{path}: receipt_digest projection does not match receipt subject digest")
    return errors


def _duplicate_reports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        ("ledger_record_id", lambda row: row.get("record", {}).get("ledger_record_id", "")),
        ("verification_execution_ledger_record_digest", lambda row: _record_digest(row.get("record", {}))),
        ("chain_digest", lambda row: row.get("record", {}).get("chain_digest", "")),
        ("receipt_digest", lambda row: row.get("receipt_digest", "")),
    )
    duplicates: list[dict[str, Any]] = []
    for field, getter in fields:
        paths_by_value: dict[str, list[str]] = {}
        for row in rows:
            value = getter(row)
            if isinstance(value, str) and value:
                paths_by_value.setdefault(value, []).append(str(row.get("path", "")))
        for value in sorted(paths_by_value):
            paths = sorted(paths_by_value[value])
            if len(paths) > 1:
                duplicates.append(
                    {
                        "field": field,
                        "value": value,
                        "paths": paths,
                        "errors": [f"duplicate {field} {value} in {', '.join(paths)}"],
                    }
                )
    return duplicates


def _validate_optional_index_chain(rows: list[dict[str, Any]]) -> tuple[str, bool, list[dict[str, Any]]]:
    applies = any(
        isinstance(row.get("record"), dict)
        and ("ledger_index" in row["record"] or "previous_ledger_record_digest" in row["record"])
        for row in rows
    )
    if not applies:
        return "not_applicable_no_sequence_rule", False, []

    errors: list[dict[str, Any]] = []
    indexed_rows: list[tuple[int, dict[str, Any]]] = []
    paths_by_index: dict[int, list[str]] = {}
    rows_by_index: dict[int, list[dict[str, Any]]] = {}

    for row in rows:
        record = row.get("record") if isinstance(row.get("record"), dict) else {}
        path = str(row.get("path", ""))
        index = record.get("ledger_index")
        if not isinstance(index, int) or index < 1:
            errors.append(
                {
                    "path": path,
                    "errors": ["ledger_index must be a positive integer when index-chain fields are present"],
                }
            )
            continue
        indexed_rows.append((index, row))
        paths_by_index.setdefault(index, []).append(path)
        rows_by_index.setdefault(index, []).append(row)

    for index in sorted(paths_by_index):
        paths = sorted(paths_by_index[index])
        if len(paths) > 1:
            errors.append({"path": ", ".join(paths), "errors": [f"duplicate ledger_index {index}"]})

    digests_by_unique_index: dict[int, str] = {}
    for index, index_rows in rows_by_index.items():
        if len(index_rows) == 1:
            record = index_rows[0].get("record") if isinstance(index_rows[0].get("record"), dict) else {}
            digests_by_unique_index[index] = _record_digest(record)

    for expected_index, (actual_index, row) in enumerate(
        sorted(indexed_rows, key=lambda item: (item[0], str(item[1].get("path", "")))), start=1
    ):
        record = row.get("record") if isinstance(row.get("record"), dict) else {}
        path = str(row.get("path", ""))
        row_errors: list[str] = []

        if actual_index != expected_index:
            row_errors.append(f"ledger_index must be {expected_index}")

        previous = record.get("previous_ledger_record_digest")
        if actual_index == 1:
            if previous is not None:
                row_errors.append("previous_ledger_record_digest must be null or absent for first indexed record")
        else:
            expected_prior_digest = digests_by_unique_index.get(actual_index - 1)
            if expected_prior_digest is None:
                row_errors.append(
                    "previous_ledger_record_digest cannot be validated because prior ledger_index is missing or duplicated"
                )
            elif previous != expected_prior_digest:
                row_errors.append("previous_ledger_record_digest does not match prior indexed record digest")

        if row_errors:
            errors.append({"path": path, "errors": row_errors})

    return ("invalid" if errors else "continuous"), True, errors


def validate_verification_execution_ledger_integrity(
    *,
    ledger_root: Path,
    loaded_records: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loaded = loaded_records if loaded_records is not None else load_verification_execution_ledger_records(ledger_root)
    rows = loaded["records"]
    rejected = loaded["rejected"]
    chain_errors: list[dict[str, Any]] = []
    for row in rows:
        row_errors = _validate_subject_ref_integrity(row)
        if row_errors:
            chain_errors.append(
                {
                    "path": row.get("path", ""),
                    "ledger_record_id": row.get("record", {}).get("ledger_record_id", ""),
                    "errors": row_errors,
                }
            )

    duplicates = _duplicate_reports(rows)
    continuity_status, chain_rule_applies, continuity_errors = _validate_optional_index_chain(rows)
    chain_errors.extend(continuity_errors)

    errors: list[str] = list(loaded["errors"])
    for item in rejected:
        errors.extend(f"{item.get('path', '')}: {error}" for error in item.get("errors", []) if isinstance(error, str))
    for item in duplicates:
        errors.extend(error for error in item.get("errors", []) if isinstance(error, str))
    for item in chain_errors:
        errors.extend(f"{item.get('path', '')}: {error}" for error in item.get("errors", []) if isinstance(error, str))

    valid = bool(loaded["valid"]) and not errors
    return {
        "kind": VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND,
        "schema_version": VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_SCHEMA_VERSION,
        "integrity_state": "VALIDATED_ONLY",
        "ledger_root": loaded["ledger_root"],
        "deterministic_order": ["recorded_at", "chain_digest", "ledger_record_id", "path"],
        "summary": {
            "record_count": len(rows),
            "available_record_count": len(rows) + len(rejected),
            "rejected_count": len(rejected),
            "duplicate_count": len(duplicates),
            "chain_error_count": len(chain_errors),
            "chain_rule_applies": chain_rule_applies,
            "chain_continuity_status": continuity_status,
        },
        "records": [_integrity_record_row(row) for row in rows],
        "rejected": rejected,
        "duplicates": duplicates,
        "chain_errors": chain_errors,
        "evidence_refs": [_ledger_record_evidence_ref(row) for row in rows],
        "errors": _dedupe_errors(errors),
        "valid": valid,
        "status": "valid" if valid else "invalid",
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "replays_execution": False,
        "governance": _default_integrity_governance(),
    }


def _reconstructed_chain_row(row: dict[str, Any]) -> dict[str, Any]:
    record = row.get("record") if isinstance(row.get("record"), dict) else {}
    subject_refs = record.get("subject_refs") if isinstance(record.get("subject_refs"), list) else []
    return {
        "chain_digest": record.get("chain_digest", ""),
        "ledger_record_id": record.get("ledger_record_id", ""),
        "verification_execution_ledger_record_digest": _record_digest(record),
        "recorded_at": record.get("recorded_at", ""),
        "target_profile": record.get("target_profile", ""),
        "verification_profile": record.get("verification_profile", ""),
        "target_repo": record.get("target_repo", ""),
        "artifact_root": record.get("artifact_root", ""),
        "receipt_status": record.get("receipt_status", ""),
        "runner_mode": record.get("runner_mode", ""),
        "process_result_count": record.get("process_result_count", 0),
        "process_result_statuses": list(record.get("process_result_statuses", []))
        if isinstance(record.get("process_result_statuses"), list)
        else [],
        "workspace_mutation_detected": record.get("workspace_mutation_detected"),
        "ledger_path": row.get("path", ""),
        "subject_refs": subject_refs,
        "evidence_ref": _ledger_record_evidence_ref(row),
        "valid": record.get("valid", True),
    }


def _invalid_reconstruction_records(integrity_report: dict[str, Any]) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for item in integrity_report.get("rejected", []):
        if isinstance(item, dict):
            invalid.append({"source": "rejected", "path": item.get("path", ""), "errors": item.get("errors", [])})
    for item in integrity_report.get("duplicates", []):
        if isinstance(item, dict):
            invalid.append(
                {
                    "source": "duplicate",
                    "field": item.get("field", ""),
                    "value": item.get("value", ""),
                    "paths": item.get("paths", []),
                    "errors": item.get("errors", []),
                }
            )
    for item in integrity_report.get("chain_errors", []):
        if isinstance(item, dict):
            invalid.append(
                {
                    "source": "chain_error",
                    "path": item.get("path", ""),
                    "ledger_record_id": item.get("ledger_record_id", ""),
                    "errors": item.get("errors", []),
                }
            )
    return invalid


def reconstruct_verification_execution_ledger(*, ledger_root: Path) -> dict[str, Any]:
    loaded = load_verification_execution_ledger_records(ledger_root)
    records = loaded["records"]
    integrity_report = validate_verification_execution_ledger_integrity(ledger_root=ledger_root, loaded_records=loaded)
    invalid_records = _invalid_reconstruction_records(integrity_report)
    reconstructed_chains = [_reconstructed_chain_row(row) for row in records]
    summary = summarize_verification_execution_ledger_records(
        records,
        available_record_count=len(records) + len(loaded["rejected"]),
        rejected_count=len(loaded["rejected"]),
    )
    summary.update(
        {
            "reconstructed_chain_count": len(reconstructed_chains),
            "invalid_record_count": len(invalid_records),
            "duplicate_count": integrity_report.get("summary", {}).get("duplicate_count", 0),
            "chain_error_count": integrity_report.get("summary", {}).get("chain_error_count", 0),
            "chain_rule_applies": integrity_report.get("summary", {}).get("chain_rule_applies", False),
            "chain_continuity_status": integrity_report.get("summary", {}).get(
                "chain_continuity_status",
                "not_applicable_no_sequence_rule",
            ),
        }
    )
    valid = bool(integrity_report.get("valid"))
    return {
        "kind": VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND,
        "schema_version": VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_SCHEMA_VERSION,
        "reconstruction_state": "RECONSTRUCTED_ONLY",
        "ledger_root": loaded["ledger_root"],
        "deterministic_order": ["recorded_at", "chain_digest", "ledger_record_id", "path"],
        "summary": summary,
        "chain_continuity_status": summary["chain_continuity_status"],
        "integrity_summary": integrity_report.get("summary", {}),
        "reconstructed_chains": reconstructed_chains,
        "invalid_records": invalid_records,
        "rejected": loaded["rejected"],
        "evidence_refs": [_ledger_record_evidence_ref(row) for row in records],
        "errors": list(integrity_report.get("errors", [])),
        "valid": valid,
        "status": "valid" if valid else "invalid",
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "replays_execution": False,
        "governance": _default_reconstruction_governance(),
    }


def validate_receipt_chain_for_ledger(*, receipt: Any, plan: Any, approval: Any) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_verification_execution_plan_artifact(plan))
    errors.extend(validate_verification_execution_approval_artifact(approval))
    errors.extend(validate_verification_execution_receipt_artifact(receipt))
    if isinstance(plan, dict) and plan.get("valid") is not True:
        errors.append("referenced verification execution plan must be valid (valid=true)")
    if isinstance(approval, dict) and approval.get("valid") is not True:
        errors.append("referenced verification execution approval must be valid (valid=true)")
    if isinstance(receipt, dict) and receipt.get("valid") is not True:
        errors.append("referenced verification execution receipt must be valid (valid=true)")
    if not errors:
        errors.extend(validate_verification_execution_approval_against_plan(approval, plan))
        errors.extend(validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval))
    return _dedupe_errors(errors)


def create_verification_execution_ledger_record(
    *,
    receipt: dict[str, Any],
    receipt_path: Path,
    plan: dict[str, Any],
    plan_path: Path,
    approval: dict[str, Any],
    approval_path: Path,
) -> dict[str, Any]:
    receipt_digest = str(receipt.get("verification_execution_receipt_digest", ""))
    plan_digest = str(plan.get("verification_execution_plan_digest", ""))
    approval_digest = str(approval.get("verification_execution_approval_digest", ""))
    chain_digest = digest_jsonable(
        {
            "plan_digest": plan_digest,
            "approval_digest": approval_digest,
            "receipt_digest": receipt_digest,
            "receipt_status": receipt.get("receipt_status"),
            "runner_mode": receipt.get("runner_mode"),
        }
    )
    process_results = receipt.get("process_results") if isinstance(receipt.get("process_results"), list) else []
    repo_path = Path(str(receipt.get("target_repo", "."))).expanduser().resolve()
    rel_receipt_path = _display_path(receipt_path, repo_path)
    record: dict[str, Any] = {
        "kind": VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
        "schema_version": VERIFICATION_EXECUTION_LEDGER_RECORD_SCHEMA_VERSION,
        "ledger_record_state": LEDGER_RECORD_STATE,
        "ledger_record_id": digest_jsonable(
            {
                "kind": VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
                "chain_digest": chain_digest,
                "receipt_path": str(rel_receipt_path),
            }
        ),
        "recorded_at_source": "receipt.generated_at",
        "recorded_at": str(receipt.get("generated_at", "")),
        "target_profile": receipt.get("target_profile"),
        "verification_profile": receipt.get("verification_profile"),
        "target_repo": receipt.get("target_repo"),
        "artifact_root": receipt.get("artifact_root"),
        "receipt_status": receipt.get("receipt_status"),
        "runner_mode": receipt.get("runner_mode"),
        "execution_enabled": receipt.get("execution_enabled"),
        "shell_enabled": receipt.get("shell_enabled"),
        "subprocess_mode": receipt.get("subprocess_mode"),
        "workspace_mutation_detected": receipt.get("workspace_mutation_detected"),
        "chain_digest": chain_digest,
        "subject_refs": [
            _artifact_ref(
                role="verification_execution_plan",
                kind=str(plan.get("kind", "")),
                path=plan_path,
                repo_path=repo_path,
                digest=plan_digest,
            ),
            _artifact_ref(
                role="verification_execution_approval",
                kind=str(approval.get("kind", "")),
                path=approval_path,
                repo_path=repo_path,
                digest=approval_digest,
            ),
            _artifact_ref(
                role="verification_execution_receipt",
                kind=VERIFICATION_EXECUTION_RECEIPT_KIND,
                path=receipt_path,
                repo_path=repo_path,
                digest=receipt_digest,
            ),
        ],
        "process_result_count": len(process_results),
        "process_result_statuses": [item.get("status") for item in process_results if isinstance(item, dict)],
        "disabled_authority": dict(receipt.get("disabled_authority", {})),
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "replays_execution": False,
        "governance": _default_governance(),
        "errors": [],
        "valid": True,
    }
    record = attach_digest(record, digest_key="verification_execution_ledger_record_digest")
    errors = validate_verification_execution_ledger_record(record)
    if errors:
        record["errors"] = errors
        record["valid"] = False
        record = attach_digest(record, digest_key="verification_execution_ledger_record_digest")
    return record


def index_verification_execution_receipt(
    *,
    receipt_path: Path,
    plan_path: Path,
    approval_path: Path,
) -> dict[str, Any]:
    receipt = _load_json_object(receipt_path)
    plan = _load_json_object(plan_path)
    approval = _load_json_object(approval_path)
    errors = validate_receipt_chain_for_ledger(receipt=receipt, plan=plan, approval=approval)
    repo_path_for_display = Path(str(receipt.get("target_repo", "."))).expanduser().resolve()
    if errors:
        record = {
            "kind": VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
            "schema_version": VERIFICATION_EXECUTION_LEDGER_RECORD_SCHEMA_VERSION,
            "ledger_record_state": LEDGER_RECORD_STATE,
            "ledger_record_id": digest_jsonable(
                {
                    "receipt_path": str(_display_path(receipt_path, repo_path_for_display)),
                    "plan_path": str(_display_path(plan_path, repo_path_for_display)),
                    "approval_path": str(_display_path(approval_path, repo_path_for_display)),
                    "errors": errors,
                }
            ),
            "recorded_at_source": "blocked_before_index",
            "recorded_at": "",
            "target_profile": receipt.get("target_profile") if isinstance(receipt, dict) else None,
            "verification_profile": receipt.get("verification_profile") if isinstance(receipt, dict) else None,
            "target_repo": receipt.get("target_repo") if isinstance(receipt, dict) else None,
            "artifact_root": receipt.get("artifact_root") if isinstance(receipt, dict) else None,
            "receipt_status": receipt.get("receipt_status") if isinstance(receipt, dict) else None,
            "runner_mode": receipt.get("runner_mode") if isinstance(receipt, dict) else None,
            "execution_enabled": receipt.get("execution_enabled") if isinstance(receipt, dict) else None,
            "shell_enabled": receipt.get("shell_enabled") if isinstance(receipt, dict) else None,
            "subprocess_mode": receipt.get("subprocess_mode") if isinstance(receipt, dict) else None,
            "workspace_mutation_detected": receipt.get("workspace_mutation_detected")
            if isinstance(receipt, dict)
            else None,
            "chain_digest": "",
            "subject_refs": [],
            "process_result_count": 0,
            "process_result_statuses": [],
            "disabled_authority": {},
            "executes_model": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "invokes_mcp": False,
            "mutates_target_repo": False,
            "replays_execution": False,
            "governance": _default_governance(),
            "errors": errors,
            "valid": False,
        }
        return attach_digest(record, digest_key="verification_execution_ledger_record_digest")
    return create_verification_execution_ledger_record(
        receipt=receipt,
        receipt_path=receipt_path,
        plan=plan,
        plan_path=plan_path,
        approval=approval,
        approval_path=approval_path,
    )


def default_verification_execution_ledger_output(record: dict[str, Any]) -> Path:
    target_repo = Path(str(record.get("target_repo", "."))).expanduser().resolve()
    digest = str(record.get("verification_execution_ledger_record_digest", "invalid"))
    return target_repo / ".builder" / "ledger" / f"verification-execution-{digest}.json"


def dumps_verification_execution_ledger_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_verification_execution_ledger_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_verification_execution_ledger_record(record), encoding="utf-8")


def validate_verification_execution_ledger_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["verification execution ledger record must be a JSON object"]
    if record.get("kind") != VERIFICATION_EXECUTION_LEDGER_RECORD_KIND:
        errors.append(f"kind must be {VERIFICATION_EXECUTION_LEDGER_RECORD_KIND}")
    if record.get("schema_version") != VERIFICATION_EXECUTION_LEDGER_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_EXECUTION_LEDGER_RECORD_SCHEMA_VERSION}")
    if record.get("ledger_record_state") != LEDGER_RECORD_STATE:
        errors.append(f"ledger_record_state must be {LEDGER_RECORD_STATE}")
    for field in ("ledger_record_id", "recorded_at_source"):
        if not _is_non_empty_string(record.get(field)):
            errors.append(f"{field} must be a non-empty string")
    for field in (
        "target_profile",
        "verification_profile",
        "target_repo",
        "artifact_root",
        "receipt_status",
        "runner_mode",
        "subprocess_mode",
    ):
        if record.get("valid") is True and not _is_non_empty_string(record.get(field)):
            errors.append(f"{field} must be a non-empty string when valid is true")
    if record.get("valid") is True and record.get("runner_mode") != RUNNER_MODE_BOUNDED_APPROVED:
        errors.append(f"runner_mode must be {RUNNER_MODE_BOUNDED_APPROVED} when valid is true")
    if not _is_sha256_hex(record.get("chain_digest")) and record.get("valid") is True:
        errors.append("chain_digest must be a SHA-256 hex digest when valid is true")
    refs = record.get("subject_refs")
    if not isinstance(refs, list):
        errors.append("subject_refs must be a list")
    elif record.get("valid") is True and len(refs) != 3:
        errors.append("subject_refs must contain plan, approval, and receipt refs when valid is true")
    elif isinstance(refs, list):
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"subject_refs[{index}] must be an object")
                continue
            for key in ("role", "kind", "path", "sha256"):
                if not _is_non_empty_string(ref.get(key)):
                    errors.append(f"subject_refs[{index}].{key} must be a non-empty string")
            if not _is_sha256_hex(ref.get("sha256")):
                errors.append(f"subject_refs[{index}].sha256 must be a SHA-256 hex digest")
            if ref.get("required") is not True:
                errors.append(f"subject_refs[{index}].required must be true")
    if not isinstance(record.get("process_result_count"), int) or record.get("process_result_count", -1) < 0:
        errors.append("process_result_count must be a non-negative integer")
    if not isinstance(record.get("process_result_statuses"), list):
        errors.append("process_result_statuses must be a list")
    if not isinstance(record.get("disabled_authority"), dict):
        errors.append("disabled_authority must be an object")
    for key in (
        "executes_model",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "invokes_mcp",
        "mutates_target_repo",
        "replays_execution",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "target_repo_writes",
            "memory_mutation",
            "goose_runtime_start",
            "deepagents_runtime",
            "mcp_execution",
            "replay_execution",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT LEDGER ARTIFACT OUTPUT PATH":
            errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT LEDGER ARTIFACT OUTPUT PATH")
        for key in ("artifact_is_authority", "grants_runtime_authority", "grants_action_authority"):
            if governance.get(key) is not False:
                errors.append(f"governance.{key} must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    artifact_errors = record.get("errors")
    if not isinstance(artifact_errors, list) or not all(isinstance(item, str) for item in artifact_errors):
        errors.append("errors must be a list of strings")
    valid = record.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif valid is True and artifact_errors:
        errors.append("errors must be empty when valid is true")
    elif valid is False and not artifact_errors:
        errors.append("errors must be non-empty when valid is false")
    digest = record.get("verification_execution_ledger_record_digest")
    if not _is_sha256_hex(digest):
        errors.append("verification_execution_ledger_record_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(record, digest_key="verification_execution_ledger_record_digest"):
        errors.append("verification_execution_ledger_record_digest drift detected")
    return _dedupe_errors(errors)


def validate_verification_execution_ledger_integrity_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["verification execution ledger integrity report must be a JSON object"]
    if record.get("kind") != VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND:
        errors.append(f"kind must be {VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND}")
    if record.get("schema_version") != VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_SCHEMA_VERSION}")
    if record.get("integrity_state") != "VALIDATED_ONLY":
        errors.append("integrity_state must be VALIDATED_ONLY")
    if record.get("status") not in ("valid", "invalid"):
        errors.append("status must be valid or invalid")
    if not isinstance(record.get("ledger_root"), str) or not record["ledger_root"]:
        errors.append("ledger_root must be a non-empty string")
    if not isinstance(record.get("deterministic_order"), list):
        errors.append("deterministic_order must be a list")
    summary = record.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        for key in ("record_count", "available_record_count", "rejected_count", "duplicate_count", "chain_error_count"):
            if not isinstance(summary.get(key), int) or summary[key] < 0:
                errors.append(f"summary.{key} must be a non-negative integer")
        if not isinstance(summary.get("chain_rule_applies"), bool):
            errors.append("summary.chain_rule_applies must be a boolean")
        if summary.get("chain_continuity_status") not in ("continuous", "invalid", "not_applicable_no_sequence_rule"):
            errors.append(
                "summary.chain_continuity_status must be continuous, invalid, or not_applicable_no_sequence_rule"
            )
    for field in ("records", "rejected", "duplicates", "chain_errors", "evidence_refs", "errors"):
        if not isinstance(record.get(field), list):
            errors.append(f"{field} must be a list")
    for index, ref in enumerate(record.get("evidence_refs") if isinstance(record.get("evidence_refs"), list) else []):
        if not isinstance(ref, dict):
            errors.append(f"evidence_refs[{index}] must be an object")
            continue
        for key in ("role", "kind", "path", "sha256", "artifact_digest"):
            if not _is_non_empty_string(ref.get(key)):
                errors.append(f"evidence_refs[{index}].{key} must be a non-empty string")
        if ref.get("role") != "verification_execution_ledger_record":
            errors.append(f"evidence_refs[{index}].role must be verification_execution_ledger_record")
        if ref.get("kind") != VERIFICATION_EXECUTION_LEDGER_RECORD_KIND:
            errors.append(f"evidence_refs[{index}].kind must be {VERIFICATION_EXECUTION_LEDGER_RECORD_KIND}")
        if not _is_sha256_hex(ref.get("sha256")):
            errors.append(f"evidence_refs[{index}].sha256 must be a SHA-256 hex digest")
        if not _is_sha256_hex(ref.get("artifact_digest")):
            errors.append(f"evidence_refs[{index}].artifact_digest must be a SHA-256 hex digest")
        if ref.get("required") is not True:
            errors.append(f"evidence_refs[{index}].required must be true")
    valid = record.get("valid")
    report_errors = record.get("errors")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif isinstance(report_errors, list):
        if valid is True and report_errors:
            errors.append("errors must be empty when valid is true")
        if valid is False and not report_errors:
            errors.append("errors must be non-empty when valid is false")
    for key in (
        "executes_model",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "invokes_mcp",
        "mutates_target_repo",
        "replays_execution",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        expected = _default_integrity_governance()
        for key, value in expected.items():
            if governance.get(key) != value:
                errors.append(f"governance.{key} must be {value}")
    return _dedupe_errors(errors)


def validate_verification_execution_ledger_reconstruction_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["verification execution ledger reconstruction report must be a JSON object"]
    if record.get("kind") != VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND:
        errors.append(f"kind must be {VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND}")
    if record.get("schema_version") != VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_SCHEMA_VERSION}")
    if record.get("reconstruction_state") != "RECONSTRUCTED_ONLY":
        errors.append("reconstruction_state must be RECONSTRUCTED_ONLY")
    if record.get("status") not in ("valid", "invalid"):
        errors.append("status must be valid or invalid")
    if not isinstance(record.get("ledger_root"), str) or not record["ledger_root"]:
        errors.append("ledger_root must be a non-empty string")
    if not isinstance(record.get("deterministic_order"), list):
        errors.append("deterministic_order must be a list")
    summary = record.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        for key in (
            "record_count",
            "available_record_count",
            "rejected_count",
            "reconstructed_chain_count",
            "invalid_record_count",
            "duplicate_count",
            "chain_error_count",
        ):
            if not isinstance(summary.get(key), int) or summary[key] < 0:
                errors.append(f"summary.{key} must be a non-negative integer")
        if not isinstance(summary.get("chain_rule_applies"), bool):
            errors.append("summary.chain_rule_applies must be a boolean")
        if summary.get("chain_continuity_status") not in ("continuous", "invalid", "not_applicable_no_sequence_rule"):
            errors.append(
                "summary.chain_continuity_status must be continuous, invalid, or not_applicable_no_sequence_rule"
            )
    if record.get("chain_continuity_status") not in ("continuous", "invalid", "not_applicable_no_sequence_rule"):
        errors.append("chain_continuity_status must be continuous, invalid, or not_applicable_no_sequence_rule")
    for field in ("reconstructed_chains", "invalid_records", "rejected", "evidence_refs", "errors"):
        if not isinstance(record.get(field), list):
            errors.append(f"{field} must be a list")
    if not isinstance(record.get("integrity_summary"), dict):
        errors.append("integrity_summary must be an object")
    for index, chain in enumerate(
        record.get("reconstructed_chains") if isinstance(record.get("reconstructed_chains"), list) else []
    ):
        if not isinstance(chain, dict):
            errors.append(f"reconstructed_chains[{index}] must be an object")
            continue
        is_chain_valid = chain.get("valid", True)
        if not isinstance(is_chain_valid, bool):
            errors.append(f"reconstructed_chains[{index}].valid must be a boolean")
            is_chain_valid = True
        for key in ("ledger_record_id", "verification_execution_ledger_record_digest", "ledger_path"):
            if not _is_non_empty_string(chain.get(key)):
                errors.append(f"reconstructed_chains[{index}].{key} must be a non-empty string")
        if is_chain_valid:
            if not _is_non_empty_string(chain.get("chain_digest")):
                errors.append(f"reconstructed_chains[{index}].chain_digest must be a non-empty string")
            if not _is_sha256_hex(chain.get("chain_digest")):
                errors.append(f"reconstructed_chains[{index}].chain_digest must be a SHA-256 hex digest")
        if not _is_sha256_hex(chain.get("verification_execution_ledger_record_digest")):
            errors.append(
                f"reconstructed_chains[{index}].verification_execution_ledger_record_digest must be a SHA-256 hex digest"
            )
        if not isinstance(chain.get("subject_refs"), list):
            errors.append(f"reconstructed_chains[{index}].subject_refs must be a list")
        evidence_ref = chain.get("evidence_ref")
        if not isinstance(evidence_ref, dict):
            errors.append(f"reconstructed_chains[{index}].evidence_ref must be an object")
    for index, ref in enumerate(record.get("evidence_refs") if isinstance(record.get("evidence_refs"), list) else []):
        if not isinstance(ref, dict):
            errors.append(f"evidence_refs[{index}] must be an object")
            continue
        for key in ("role", "kind", "path", "sha256", "artifact_digest"):
            if not _is_non_empty_string(ref.get(key)):
                errors.append(f"evidence_refs[{index}].{key} must be a non-empty string")
        if ref.get("role") != "verification_execution_ledger_record":
            errors.append(f"evidence_refs[{index}].role must be verification_execution_ledger_record")
        if ref.get("kind") != VERIFICATION_EXECUTION_LEDGER_RECORD_KIND:
            errors.append(f"evidence_refs[{index}].kind must be {VERIFICATION_EXECUTION_LEDGER_RECORD_KIND}")
        if not _is_sha256_hex(ref.get("sha256")):
            errors.append(f"evidence_refs[{index}].sha256 must be a SHA-256 hex digest")
        if not _is_sha256_hex(ref.get("artifact_digest")):
            errors.append(f"evidence_refs[{index}].artifact_digest must be a SHA-256 hex digest")
        if ref.get("required") is not True:
            errors.append(f"evidence_refs[{index}].required must be true")
    valid = record.get("valid")
    report_errors = record.get("errors")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif isinstance(report_errors, list):
        if valid is True and report_errors:
            errors.append("errors must be empty when valid is true")
        if valid is False and not report_errors:
            errors.append("errors must be non-empty when valid is false")
    for key in (
        "executes_model",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "invokes_mcp",
        "mutates_target_repo",
        "replays_execution",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        expected = _default_reconstruction_governance()
        for key, value in expected.items():
            if governance.get(key) != value:
                errors.append(f"governance.{key} must be {value}")
    return _dedupe_errors(errors)
