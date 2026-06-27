from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.target_profiles import target_names
from builder_ii.session_workflow import SESSION_WORKFLOW_PLAN_KIND, validate_session_workflow_plan
from builder_ii.goose_readonly_session import GOOSE_READONLY_SESSION_PLAN_KIND, validate_goose_readonly_session_plan
from builder_ii.verification_profile_reports import VERIFICATION_PROFILE_REPORT_KIND, validate_verification_profile_report

HANDOFF_NOTE_KIND = "builder_ii.handoff_note"
HANDOFF_NOTE_SCHEMA_VERSION = 1

HandoffStatus = Literal["DRAFT", "READY_FOR_REVIEW", "BLOCKED"]

_ALLOWED_STATUSES = {"DRAFT", "READY_FOR_REVIEW", "BLOCKED"}
_ALLOWED_REF_KINDS = {
    SESSION_WORKFLOW_PLAN_KIND,
    GOOSE_READONLY_SESSION_PLAN_KIND,
    VERIFICATION_PROFILE_REPORT_KIND,
}


def _artifact_ref(*, kind: str, path: str, sha256: str = "", name: str = "") -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path,
        "sha256": sha256,
        "name": name,
    }


def create_handoff_note(
    *,
    target_name: str,
    summary: str,
    next_recommended_action: str,
    session_ref: dict[str, Any] | None = None,
    goose_readonly_session_ref: dict[str, Any] | None = None,
    verification_report_ref: dict[str, Any] | None = None,
    changed_files_summary: list[str] | None = None,
    verification_summary: str = "Verification not yet completed by this artifact.",
    verification_evidence_refs: list[dict[str, Any]] | None = None,
    open_risks: list[str] | None = None,
    human_review_required: bool = True,
    status: HandoffStatus = "DRAFT",
) -> dict[str, Any]:
    """Create a governed handoff note artifact.

    The note is a durable summary and next-action artifact. It never claims
    verification passed unless explicit evidence references are supplied.
    """

    evidence_refs = list(verification_evidence_refs or [])
    return {
        "kind": HANDOFF_NOTE_KIND,
        "schema_version": HANDOFF_NOTE_SCHEMA_VERSION,
        "target_name": target_name,
        "status": status,
        "summary": summary,
        "changed_files_summary": list(changed_files_summary or []),
        "verification_summary": verification_summary,
        "verification_evidence_refs": evidence_refs,
        "verification_claim": "EVIDENCE_REFERENCED" if evidence_refs else "NOT_CLAIMED",
        "session_ref": session_ref,
        "goose_readonly_session_ref": goose_readonly_session_ref,
        "verification_report_ref": verification_report_ref,
        "open_risks": list(open_risks or []),
        "next_recommended_action": next_recommended_action,
        "human_review_required": human_review_required,
        "governance": {
            "capability_state": "handoff_note",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
            "memory_mutation": "DISABLED",
            "executes_commands": False,
            "claims_verification_passed": bool(evidence_refs),
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_artifact_ref(*, kind: str, path: str, sha256: str = "", name: str = "") -> dict[str, Any]:
    return _artifact_ref(kind=kind, path=path, sha256=sha256, name=name)


def _validate_artifact_ref(value: Any, *, field: str, allowed_kinds: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if value is None:
        return errors
    if not isinstance(value, dict):
        return [f"{field} must be an object when present"]
    kind = value.get("kind")
    if not isinstance(kind, str) or not kind:
        errors.append(f"{field}.kind must be a non-empty string")
    elif allowed_kinds is not None and kind not in allowed_kinds:
        errors.append(f"{field}.kind must be an allowed handoff reference kind")
    path = value.get("path")
    if not isinstance(path, str) or not path:
        errors.append(f"{field}.path must be a non-empty string")
    sha256 = value.get("sha256", "")
    if not isinstance(sha256, str):
        errors.append(f"{field}.sha256 must be a string when present")
    name = value.get("name", "")
    if not isinstance(name, str):
        errors.append(f"{field}.name must be a string when present")
    return errors


def _validate_string_list(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_handoff_note(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["handoff note must be a JSON object"]

    if data.get("kind") != HANDOFF_NOTE_KIND:
        errors.append(f"kind must be {HANDOFF_NOTE_KIND}")
    if data.get("schema_version") != HANDOFF_NOTE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HANDOFF_NOTE_SCHEMA_VERSION}")

    if data.get("target_name") not in target_names():
        errors.append("target_name must be one of: generic, builder, core")
    if data.get("status") not in _ALLOWED_STATUSES:
        errors.append("status must be one of: BLOCKED, DRAFT, READY_FOR_REVIEW")
    for field in ("summary", "verification_summary", "next_recommended_action"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    errors.extend(_validate_string_list(data.get("changed_files_summary"), field="changed_files_summary"))
    errors.extend(_validate_string_list(data.get("open_risks"), field="open_risks"))

    evidence_refs = data.get("verification_evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append("verification_evidence_refs must be a list")
        evidence_refs = []
    else:
        for index, ref in enumerate(evidence_refs):
            errors.extend(_validate_artifact_ref(ref, field=f"verification_evidence_refs[{index}]"))

    verification_claim = data.get("verification_claim")
    if evidence_refs:
        if verification_claim != "EVIDENCE_REFERENCED":
            errors.append("verification_claim must be EVIDENCE_REFERENCED when evidence refs are supplied")
    elif verification_claim != "NOT_CLAIMED":
        errors.append("verification_claim must be NOT_CLAIMED when evidence refs are absent")

    errors.extend(_validate_artifact_ref(data.get("session_ref"), field="session_ref", allowed_kinds={SESSION_WORKFLOW_PLAN_KIND}))
    errors.extend(_validate_artifact_ref(data.get("goose_readonly_session_ref"), field="goose_readonly_session_ref", allowed_kinds={GOOSE_READONLY_SESSION_PLAN_KIND}))
    errors.extend(_validate_artifact_ref(data.get("verification_report_ref"), field="verification_report_ref", allowed_kinds={VERIFICATION_PROFILE_REPORT_KIND}))

    if data.get("human_review_required") is not True:
        errors.append("human_review_required must be true")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "handoff_note":
            errors.append("governance.capability_state must be handoff_note")
        for key in ("runtime_execution", "model_execution", "shell_execution", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
            errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
        if governance.get("executes_commands") is not False:
            errors.append("governance.executes_commands must be false")
        expected_claim = bool(evidence_refs)
        if governance.get("claims_verification_passed") is not expected_claim:
            errors.append("governance.claims_verification_passed must match evidence ref presence")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    return errors


def validate_handoff_note_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_handoff_note(data)


def dumps_handoff_note(note: dict[str, Any]) -> str:
    return json_lib.dumps(note, indent=2, sort_keys=True) + "\n"


def write_handoff_note(note: dict[str, Any], output: Path) -> None:
    errors = validate_handoff_note(note)
    if errors:
        raise ValueError("invalid handoff note: " + "; ".join(errors))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_handoff_note(note), encoding="utf-8")
