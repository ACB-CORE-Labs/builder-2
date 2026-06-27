from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Callable

from builder_ii.approval_records import APPROVAL_RECORD_KIND, validate_approval_record
from builder_ii.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
    validate_execution_postflight_record,
    validate_execution_verification_record,
)
from builder_ii.goose_command_proposal import GOOSE_COMMAND_PROPOSAL_KIND, validate_goose_command_proposal
from builder_ii.hitl_evidence_bundle import HITL_EVIDENCE_BUNDLE_KIND, validate_hitl_evidence_bundle
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
    validate_hitl_execution_receipt,
    validate_hitl_execution_request,
)
from builder_ii.preflight_records import PREFLIGHT_RECORD_KIND, validate_preflight_record

HITL_CHAIN_BINDING_KIND = "builder_ii.hitl_chain_binding"
HITL_CHAIN_BINDING_SCHEMA_VERSION = 1

_CHAIN_STATE = "BOUND_ONLY"
_SAFE_GOVERNANCE_KEYS = (
    "runtime_execution",
    "model_execution",
    "shell_execution",
    "source_writes",
    "memory_mutation",
    "goose_runtime_start",
    "command_execution",
    "git_mutation",
    "commit_push",
    "network_access",
    "goose_runtime_activation",
    "deepagents_runtime",
)

HITL_CHAIN_BINDING_SLOT_KIND_MAP: dict[str, str] = {
    "proposal": GOOSE_COMMAND_PROPOSAL_KIND,
    "approval": APPROVAL_RECORD_KIND,
    "preflight": PREFLIGHT_RECORD_KIND,
    "request": HITL_EXECUTION_REQUEST_KIND,
    "receipt": HITL_EXECUTION_RECEIPT_KIND,
    "postflight": EXECUTION_POSTFLIGHT_RECORD_KIND,
    "verification": EXECUTION_VERIFICATION_RECORD_KIND,
    "evidence_bundle": HITL_EVIDENCE_BUNDLE_KIND,
}

HITL_CHAIN_BINDING_SLOT_FIELDS = {
    slot: f"{slot}_ref" for slot in HITL_CHAIN_BINDING_SLOT_KIND_MAP
}

_VALIDATORS: dict[str, Callable[[Any], list[str]]] = {
    GOOSE_COMMAND_PROPOSAL_KIND: validate_goose_command_proposal,
    APPROVAL_RECORD_KIND: validate_approval_record,
    PREFLIGHT_RECORD_KIND: validate_preflight_record,
    HITL_EXECUTION_REQUEST_KIND: validate_hitl_execution_request,
    HITL_EXECUTION_RECEIPT_KIND: validate_hitl_execution_receipt,
    EXECUTION_POSTFLIGHT_RECORD_KIND: validate_execution_postflight_record,
    EXECUTION_VERIFICATION_RECORD_KIND: validate_execution_verification_record,
    HITL_EVIDENCE_BUNDLE_KIND: validate_hitl_evidence_bundle,
}


def create_artifact_ref(*, kind: str, path: str, sha256: str = "") -> dict[str, Any]:
    return {"kind": kind, "path": path, "sha256": sha256}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_safe_relative_path_string(path_str: str) -> bool:
    if not path_str:
        return False
    if path_str.startswith("/") or path_str.startswith("\\"):
        return False
    if ":" in path_str:
        return False
    parts = path_str.replace("\\", "/").split("/")
    return ".." not in parts


def _read_json_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"failed to read file: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"artifact must be a JSON object: {path}")
    return data


def _safe_relative_path(base_dir: Path, path: str | Path) -> str:
    base_resolved = base_dir.resolve()
    raw = Path(path)
    if not raw.is_absolute() and not _is_safe_relative_path_string(str(raw)):
        raise ValueError(f"artifact path is not a safe relative path: {path}")
    if raw.is_absolute():
        candidate = raw
    else:
        candidate = base_resolved / raw
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes base_dir: {path}") from exc
    rel_str = rel.as_posix()
    if not rel_str or rel_str.startswith("/") or rel_str.startswith("\\") or ":" in rel_str:
        raise ValueError(f"artifact path is unsafe: {path}")
    if any(part == ".." for part in rel.parts):
        raise ValueError(f"artifact path is unsafe: {path}")
    return rel_str


def _validate_ref_shape(value: Any, *, field: str, allowed_kind: str, base_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    kind = value.get("kind")
    if kind != allowed_kind:
        errors.append(f"{field}.kind must be {allowed_kind}")
    path = value.get("path")
    if not isinstance(path, str) or not path:
        errors.append(f"{field}.path must be a non-empty string")
    elif not _is_safe_relative_path_string(path):
        errors.append(f"{field}.path must be a safe relative path")
    elif base_dir is not None:
        try:
            _safe_relative_path(base_dir, path)
        except ValueError as exc:
            errors.append(f"{field}.path must be safe relative path: {exc}")
    sha256 = value.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256.lower()):
        errors.append(f"{field}.sha256 must be a 64-character hex digest")
    return errors


def _validate_governance(governance: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    for key in _SAFE_GOVERNANCE_KEYS:
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")
    if governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def _load_and_ref(
    *,
    base_dir: Path,
    slot: str,
    artifact_path: str | Path,
) -> dict[str, Any]:
    allowed_kind = HITL_CHAIN_BINDING_SLOT_KIND_MAP[slot]
    rel_path = _safe_relative_path(base_dir, artifact_path)
    resolved = (base_dir.resolve() / rel_path).resolve()
    data = _read_json_artifact(resolved)
    validator = _VALIDATORS.get(data.get("kind", ""))
    if validator is None:
        raise ValueError(f"{slot} artifact has unknown kind: {data.get('kind', '')}")
    errors = validator(data)
    if errors:
        raise ValueError(f"{slot} artifact is invalid: {errors}")
    if data.get("kind") != allowed_kind:
        raise ValueError(f"{slot} artifact kind must be {allowed_kind}")
    return create_artifact_ref(kind=allowed_kind, path=rel_path, sha256=_digest(data))


def bind_hitl_chain_artifacts(
    *,
    base_dir: Path,
    proposal_path: str | Path,
    approval_path: str | Path,
    preflight_path: str | Path,
    request_path: str | Path,
    receipt_path: str | Path,
    postflight_path: str | Path,
    verification_path: str | Path,
    evidence_bundle_path: str | Path | None = None,
) -> dict[str, Any]:
    base_resolved = base_dir.resolve()
    artifact: dict[str, Any] = {
        "kind": HITL_CHAIN_BINDING_KIND,
        "schema_version": HITL_CHAIN_BINDING_SCHEMA_VERSION,
        "chain_state": _CHAIN_STATE,
        "proposal_ref": _load_and_ref(base_dir=base_resolved, slot="proposal", artifact_path=proposal_path),
        "approval_ref": _load_and_ref(base_dir=base_resolved, slot="approval", artifact_path=approval_path),
        "preflight_ref": _load_and_ref(base_dir=base_resolved, slot="preflight", artifact_path=preflight_path),
        "request_ref": _load_and_ref(base_dir=base_resolved, slot="request", artifact_path=request_path),
        "receipt_ref": _load_and_ref(base_dir=base_resolved, slot="receipt", artifact_path=receipt_path),
        "postflight_ref": _load_and_ref(base_dir=base_resolved, slot="postflight", artifact_path=postflight_path),
        "verification_ref": _load_and_ref(base_dir=base_resolved, slot="verification", artifact_path=verification_path),
        "governance": {
            "capability_state": "hitl_chain_binding",
            **{key: "DISABLED" for key in _SAFE_GOVERNANCE_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    if evidence_bundle_path is not None:
        artifact["evidence_bundle_ref"] = _load_and_ref(
            base_dir=base_resolved,
            slot="evidence_bundle",
            artifact_path=evidence_bundle_path,
        )
    errors = validate_hitl_chain_binding(artifact)
    if errors:
        raise ValueError(f"Invalid HITL chain binding artifact constructed: {errors}")
    return artifact


def dumps_hitl_chain_binding(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_chain_binding(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_chain_binding(artifact), encoding="utf-8")


def validate_hitl_chain_binding(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl chain binding artifact must be a JSON object"]
    if artifact.get("kind") != HITL_CHAIN_BINDING_KIND:
        errors.append(f"kind must be {HITL_CHAIN_BINDING_KIND}")
    if artifact.get("schema_version") != HITL_CHAIN_BINDING_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_CHAIN_BINDING_SCHEMA_VERSION}")
    if artifact.get("chain_state") != _CHAIN_STATE:
        errors.append(f"chain_state must be {_CHAIN_STATE}")

    allowed_keys = {
        "kind",
        "schema_version",
        "chain_state",
        "proposal_ref",
        "approval_ref",
        "preflight_ref",
        "request_ref",
        "receipt_ref",
        "postflight_ref",
        "verification_ref",
        "evidence_bundle_ref",
        "artifact_is_authority",
        "governance",
    }
    for key in artifact:
        if key not in allowed_keys:
            errors.append(f"unknown slot or field: {key}")

    for slot, field in HITL_CHAIN_BINDING_SLOT_FIELDS.items():
        if slot == "evidence_bundle":
            continue
        if field not in artifact:
            errors.append(f"{field} is required")
            continue
        errors.extend(
            _validate_ref_shape(
                artifact.get(field),
                field=field,
                allowed_kind=HITL_CHAIN_BINDING_SLOT_KIND_MAP[slot],
            )
        )

    if "evidence_bundle_ref" in artifact and artifact.get("evidence_bundle_ref") is not None:
        errors.extend(
            _validate_ref_shape(
                artifact.get("evidence_bundle_ref"),
                field="evidence_bundle_ref",
                allowed_kind=HITL_EVIDENCE_BUNDLE_KIND,
            )
        )

    if "artifact_is_authority" in artifact and artifact["artifact_is_authority"] is not False:
        errors.append("artifact_is_authority must be false when present")

    errors.extend(_validate_governance(artifact.get("governance")))
    return errors


def validate_hitl_chain_binding_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_chain_binding(data)


def verify_hitl_chain_binding_files(artifact: dict[str, Any], *, base_dir: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl chain binding artifact must be a JSON object"]
    base_resolved = base_dir.resolve()
    for slot, field in HITL_CHAIN_BINDING_SLOT_FIELDS.items():
        if slot == "evidence_bundle" and artifact.get(field) is None:
            continue
        ref = artifact.get(field)
        if not isinstance(ref, dict):
            errors.append(f"{field} must be an object")
            continue
        rel_path = ref.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            errors.append(f"{field}.path must be a non-empty string")
            continue
        try:
            safe_rel = _safe_relative_path(base_resolved, rel_path)
        except ValueError as exc:
            errors.append(f"{field}.path unsafe: {exc}")
            continue
        target_path = (base_resolved / safe_rel).resolve()
        try:
            target_path.relative_to(base_resolved)
        except ValueError:
            errors.append(f"{field}.path escapes base_dir: {rel_path}")
            continue
        if not target_path.exists():
            errors.append(f"{field} target file not found: {target_path}")
            continue
        data = _read_json_artifact(target_path)
        validator = _VALIDATORS.get(data.get("kind", ""))
        if validator is None:
            errors.append(f"{field} target artifact has unknown kind: {data.get('kind', '')}")
            continue
        native_errors = validator(data)
        if native_errors:
            errors.append(f"{field} target artifact failed validation: {native_errors}")
        expected_kind = HITL_CHAIN_BINDING_SLOT_KIND_MAP[slot]
        if data.get("kind") != expected_kind:
            errors.append(f"{field} target artifact kind must be {expected_kind}")
        expected_sha = ref.get("sha256")
        if isinstance(expected_sha, str) and expected_sha and _digest(data) != expected_sha:
            errors.append(f"{field} target digest mismatch")

    evidence_ref = artifact.get("evidence_bundle_ref")
    if evidence_ref is not None:
        if not isinstance(evidence_ref, dict):
            errors.append("evidence_bundle_ref must be an object")
        else:
            rel_path = evidence_ref.get("path")
            if not isinstance(rel_path, str) or not rel_path:
                errors.append("evidence_bundle_ref.path must be a non-empty string")
            else:
                try:
                    safe_rel = _safe_relative_path(base_resolved, rel_path)
                except ValueError as exc:
                    errors.append(f"evidence_bundle_ref.path unsafe: {exc}")
                else:
                    target_path = (base_resolved / safe_rel).resolve()
                    try:
                        target_path.relative_to(base_resolved)
                    except ValueError:
                        errors.append(f"evidence_bundle_ref.path escapes base_dir: {rel_path}")
                    else:
                        if not target_path.exists():
                            errors.append(f"evidence_bundle_ref target file not found: {target_path}")
                        else:
                            data = _read_json_artifact(target_path)
                            validator = _VALIDATORS.get(data.get("kind", ""))
                            if validator is None:
                                errors.append(f"evidence_bundle_ref target artifact has unknown kind: {data.get('kind', '')}")
                            else:
                                native_errors = validator(data)
                                if native_errors:
                                    errors.append(f"evidence_bundle_ref target artifact failed validation: {native_errors}")
                            if data.get("kind") != HITL_EVIDENCE_BUNDLE_KIND:
                                errors.append("evidence_bundle_ref target artifact kind must be builder_ii.hitl_evidence_bundle")
                            expected_sha = evidence_ref.get("sha256")
                            if isinstance(expected_sha, str) and expected_sha and _digest(data) != expected_sha:
                                errors.append("evidence_bundle_ref target digest mismatch")
    return errors
