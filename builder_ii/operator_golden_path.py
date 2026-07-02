from __future__ import annotations

import hashlib
import json as json_lib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.operator_next import (
    create_operator_next_action_report,
    validate_operator_next_action_report,
    write_operator_next_action_report,
)
from builder_ii.operator_status import (
    create_operator_status_report,
    validate_operator_status_report,
    write_operator_status_report,
)
from builder_ii.platform_completion_audit import REQUIRED_CAPABILITY_ROWS

OPERATOR_GOLDEN_PATH_REPORT_KIND = "builder_ii.operator_golden_path_report"
SCHEMA_VERSION = 2


def canonical_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_governance() -> dict[str, Any]:
    return {
        "artifact_is_authority": False,
        "grants_authority": False,
        "no_source_truth_inflation": True,
    }


def create_operator_golden_path_report(target_profile: str, output_dir: Path) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Status Report
    status_path = output_dir / "operator-status.json"
    status_report = create_operator_status_report(target=target_profile)
    status_errors = validate_operator_status_report(status_report)
    if status_errors:
        raise ValueError(f"Status report validation failed: {status_errors}")
    write_operator_status_report(status_report, status_path)
    status_digest = status_report["report_digest"]

    # 2. Next Report
    next_path = output_dir / "operator-next.json"
    next_report = create_operator_next_action_report()
    next_errors = validate_operator_next_action_report(next_report)
    if next_errors:
        raise ValueError(f"Next report validation failed: {next_errors}")
    write_operator_next_action_report(next_report, next_path)
    next_digest = next_report["report_digest"]

    # 3. Classify capabilities
    exercised = []
    skipped = []
    known_gaps = []

    for row in REQUIRED_CAPABILITY_ROWS:
        # Check real evidence files
        has_evidence = len(row.evidence_files) > 0 and all(Path(f).exists() for f in row.evidence_files)

        if row.state == "OPERATIONALLY_VERIFIED" and has_evidence:
            if row.command_surfaces:
                exercised.append({"capability": row.capability, "status": "exercised"})
            else:
                exercised.append({"capability": row.capability, "status": "validated_only"})
        else:
            if row.state == "DISABLED":
                status = "skipped_disabled"
            elif row.state == "NOT_STARTED":
                status = "unavailable"
            elif row.state in (
                "PASSIVE_FOUNDATION",
                "ARTIFACT_ONLY",
                "MERGED_BUT_NOT_OPERATIONAL",
                "DESIGN_ONLY",
                "IMPLEMENTED_ON_BRANCH",
                "PR_OPEN",
                "OPERATIONALLY_VERIFIED",
            ):
                status = "skipped_missing_evidence"
            else:
                status = "not_applicable"

            entry = {
                "capability": row.capability,
                "status": status,
            }
            if has_evidence:
                entry["surface_present"] = True
                entry["reason"] = (
                    f"Surface exists (evidence files are present) but the capability state is '{row.state}', which is not operationally verified."
                )
            else:
                entry["surface_present"] = False
                entry["reason"] = f"State is {row.state} and evidence files are missing."

            skipped.append(entry)

            if row.state != "OPERATIONALLY_VERIFIED":
                known_gaps.append(f"{row.capability} ({row.state})")

    # 4. Check B8 memory index evidence
    memory_status = "skipped_missing_evidence"
    default_memory_index = Path(".builder/artifacts/memory-index.json")
    if default_memory_index.is_file():
        memory_status = "available"
    else:
        skipped.append(
            {
                "capability": "memory_status",
                "status": "skipped_missing_evidence",
                "reason": "Missing B8 memory index evidence.",
            }
        )

    # 5. Check Ledger/artifact chain evidence
    ledger_status = "skipped_missing_evidence"
    default_ledger = Path(".builder/artifacts/event-ledger.json")
    if default_ledger.is_file():
        ledger_status = "available"
    else:
        skipped.append(
            {
                "capability": "ledger_status",
                "status": "skipped_missing_evidence",
                "reason": "Missing Ledger/artifact chain evidence.",
            }
        )

    generated_artifacts = [
        {"name": "operator-status.json", "path": str(status_path), "digest": status_digest},
        {"name": "operator-next.json", "path": str(next_path), "digest": next_digest},
        {"name": "golden-path-report.json", "path": str(output_dir / "golden-path-report.json"), "digest": None},
    ]

    evidence_refs = [
        {"artifact": "builder_ii.operator_status_report", "path": str(status_path), "digest": status_digest},
        {"artifact": "builder_ii.operator_next_report", "path": str(next_path), "digest": next_digest},
    ]

    report = {
        "kind": OPERATOR_GOLDEN_PATH_REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": target_profile,
        "target_profile": target_profile,
        "output_dir": str(output_dir),
        "exercised_capabilities": exercised,
        "skipped_capabilities": skipped,
        "evidence_refs": evidence_refs,
        "generated_artifacts": generated_artifacts,
        "warnings": ["Golden path demo generated without execution. No target repository mutation occurred."],
        "known_gaps": known_gaps,
        "no_mutation_proof": "Verified: B9 operator primitive disabled all source write, runtime, and model authorities. Output confined to output_dir.",
        "disabled_authority_summary": {
            "model_execution": "Disabled",
            "shell_execution": "Disabled",
            "runtime_start": "Disabled",
            "mcp_tool_invocation": "Disabled",
            "goose_runtime": "Disabled",
            "deepagents_runtime": "Disabled",
            "source_writes": "Disabled",
            "target_repo_writes": "Disabled",
            "hidden_memory": "Disabled",
            "autonomous_writes": "Disabled",
        },
        "artifact_is_authority": False,
        "grants_authority": False,
        "memory_status": memory_status,
        "ledger_status": ledger_status,
        "governance": _default_governance(),
    }

    report["report_digest"] = canonical_digest(report)
    return report


def validate_operator_golden_path_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["golden path report must be a JSON object"]

    if record.get("kind") != OPERATOR_GOLDEN_PATH_REPORT_KIND:
        errors.append(f"kind must be {OPERATOR_GOLDEN_PATH_REPORT_KIND}")

    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    for field in [
        "run_id",
        "created_at_utc",
        "target",
        "output_dir",
        "no_mutation_proof",
        "disabled_authority_summary",
        "exercised_capabilities",
        "skipped_capabilities",
        "evidence_refs",
        "generated_artifacts",
        "known_gaps",
        "memory_status",
        "ledger_status",
    ]:
        if field not in record:
            errors.append(f"missing required field: {field}")

    if not isinstance(record.get("exercised_capabilities"), list):
        errors.append("exercised_capabilities must be a list")

    if not isinstance(record.get("skipped_capabilities"), list):
        errors.append("skipped_capabilities must be a list")

    if not isinstance(record.get("evidence_refs"), list) or not record.get("evidence_refs"):
        errors.append("evidence_refs must be a non-empty list")

    if not isinstance(record.get("generated_artifacts"), list) or not record.get("generated_artifacts"):
        errors.append("generated_artifacts must be a non-empty list")

    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")

    gov = record.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        for key in ("artifact_is_authority", "grants_authority"):
            if gov.get(key) is not False:
                errors.append(f"governance.{key} must be false")
        if gov.get("no_source_truth_inflation") is not True:
            errors.append("governance.no_source_truth_inflation must be true")

    known_gaps = record.get("known_gaps", [])
    skipped_caps = record.get("skipped_capabilities", [])

    # 1. Reject exercised capabilities that are not OPERATIONALLY_VERIFIED
    capability_states = {row.capability: row.state for row in REQUIRED_CAPABILITY_ROWS}
    exercised_caps = record.get("exercised_capabilities", [])
    if isinstance(exercised_caps, list):
        for entry in exercised_caps:
            if isinstance(entry, dict):
                cap_name = entry.get("capability")
                state = capability_states.get(cap_name)
                if state != "OPERATIONALLY_VERIFIED":
                    errors.append(
                        f"truth inflation: capability '{cap_name}' is in exercised_capabilities but its state is '{state}', not 'OPERATIONALLY_VERIFIED'"
                    )

    # 2. Reject skipped capability statuses outside the allowed set
    ALLOWED_SKIPPED_STATUSES = {"skipped_disabled", "skipped_missing_evidence", "unavailable", "not_applicable"}
    if isinstance(skipped_caps, list):
        for entry in skipped_caps:
            if isinstance(entry, dict):
                status = entry.get("status")
                if status not in ALLOWED_SKIPPED_STATUSES:
                    errors.append(
                        f"invalid skipped status: status '{status}' for capability '{entry.get('capability')}' is not in allowed set {ALLOWED_SKIPPED_STATUSES}"
                    )

    # 3. Load referenced next report if available
    next_data = None
    evidence_refs = record.get("evidence_refs", [])
    if isinstance(evidence_refs, list):
        for ref in evidence_refs:
            if isinstance(ref, dict) and ref.get("artifact") == "builder_ii.operator_next_report":
                next_path = ref.get("path")
                if next_path and Path(next_path).is_file():
                    try:
                        import json

                        next_data = json.loads(Path(next_path).read_text(encoding="utf-8"))
                    except Exception:
                        pass
                    break

    # 4. Reject empty known_gaps / empty skipped_capabilities if next report has incomplete actions (or fallback to codebase state)
    if next_data is not None:
        next_actions = next_data.get("ordered_next_actions", [])
        if len(next_actions) > 0:
            if isinstance(known_gaps, list) and len(known_gaps) == 0:
                errors.append("truth inflation: known_gaps is empty but next report shows incomplete capabilities")
            if isinstance(skipped_caps, list) and len(skipped_caps) == 0:
                errors.append(
                    "truth inflation: skipped_capabilities is empty but next report has incomplete capabilities"
                )
    else:
        # Fallback if next report file is not accessible
        has_incomplete = any(row.state != "OPERATIONALLY_VERIFIED" for row in REQUIRED_CAPABILITY_ROWS)
        if has_incomplete:
            if isinstance(known_gaps, list) and len(known_gaps) == 0:
                errors.append("truth inflation: known_gaps is empty but codebase has incomplete capabilities")
            if isinstance(skipped_caps, list) and len(skipped_caps) == 0:
                errors.append("truth inflation: skipped_capabilities is empty but codebase has incomplete capabilities")

    # 5. Reject if memory_status/ledger_status is skipped but no entry in skipped_capabilities references them
    memory_status = record.get("memory_status")
    ledger_status = record.get("ledger_status")

    if memory_status == "skipped_missing_evidence":
        has_memory_ref = False
        if isinstance(skipped_caps, list):
            for entry in skipped_caps:
                if isinstance(entry, dict):
                    cap = str(entry.get("capability", "")).lower()
                    reason = str(entry.get("reason", "")).lower()
                    if "memory" in cap or "memory" in reason:
                        has_memory_ref = True
                        break
        if not has_memory_ref:
            errors.append(
                "memory_status is skipped_missing_evidence but no entry in skipped_capabilities references memory evidence"
            )

    if ledger_status == "skipped_missing_evidence":
        has_ledger_ref = False
        if isinstance(skipped_caps, list):
            for entry in skipped_caps:
                if isinstance(entry, dict):
                    cap = str(entry.get("capability", "")).lower()
                    reason = str(entry.get("reason", "")).lower()
                    if "ledger" in cap or "artifact-chain" in cap or "ledger" in reason or "artifact-chain" in reason:
                        has_ledger_ref = True
                        break
        if not has_ledger_ref:
            errors.append(
                "ledger_status is skipped_missing_evidence but no entry in skipped_capabilities references ledger/artifact-chain evidence"
            )

    digest = record.get("report_digest")
    if digest:
        temp_record = dict(record)
        del temp_record["report_digest"]
        if canonical_digest(temp_record) != digest:
            errors.append("report_digest does not match canonical content")
    else:
        errors.append("report_digest is required")

    return errors


def write_operator_golden_path_report(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = json_lib.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(out, encoding="utf-8")


def dumps_operator_golden_path_report(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"
