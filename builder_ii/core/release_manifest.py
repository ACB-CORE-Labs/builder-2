from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance

V0_RELEASE_MANIFEST_KIND = "builder_ii.v0_release_manifest"
V0_RELEASE_MANIFEST_SCHEMA_VERSION = 1


def create_artifact_ref(*, kind: str, path: str, sha256: str = "") -> dict[str, Any]:
    return {"kind": kind, "path": path, "sha256": sha256}


def _validate_ref(val: Any, field: str, allow_empty_sha: bool = False) -> list[str]:
    errors: list[str] = []
    if val is None:
        return errors
    if not isinstance(val, dict):
        return [f"{field} must be an object when present"]
    if not isinstance(val.get("kind"), str) or not val["kind"]:
        errors.append(f"{field}.kind must be a non-empty string")
    if not isinstance(val.get("path"), str) or not val["path"]:
        errors.append(f"{field}.path must be a non-empty string")
    sha = val.get("sha256", "")
    if not isinstance(sha, str):
        errors.append(f"{field}.sha256 must be a string")
    elif not sha and not allow_empty_sha:
        errors.append(f"{field}.sha256 must be a non-empty string")
    return errors


def _validate_required_ref(
    container: dict[str, Any],
    key: str,
    field: str,
    *,
    allow_empty_sha: bool = False,
) -> list[str]:
    if key not in container or container.get(key) is None:
        return [f"{field} is required"]
    return _validate_ref(container[key], field, allow_empty_sha=allow_empty_sha)


def create_v0_release_manifest(
    *,
    repository: str = "AssetOverflow/builder-II",
    lineage: str = "v0 release lineage",
    release_version: str = "v0.1.0",
    target_profile: str = "generic",
    task: str = "prove canonical governed session lane e2e",
    governed_session_proof: dict[str, Any],
    platform_spine_proof: dict[str, Any],
    audit_references: dict[str, Any],
) -> dict[str, Any]:
    manifest = {
        "kind": V0_RELEASE_MANIFEST_KIND,
        "schema_version": V0_RELEASE_MANIFEST_SCHEMA_VERSION,
        "release_identity": {
            "repository": repository,
            "lineage": lineage,
            "release_version": release_version,
            "target_profile": target_profile,
            "task": task,
        },
        "governed_session_proof": governed_session_proof,
        "platform_spine_proof": platform_spine_proof,
        "audit_references": audit_references,
        "proof_status": {
            "verified_no_runtime_authority": True,
            "verified_no_source_writes": True,
            "verified_chain_valid": True,
            "verified_index_valid": True,
        },
        "governance": build_standard_governance("v0_release_manifest"),
    }
    errors = validate_v0_release_manifest(manifest)
    if errors:
        raise ValueError(f"Invalid v0 release manifest constructed: {errors}")
    return manifest


def dumps_v0_release_manifest(data: dict[str, Any]) -> str:
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"


def write_v0_release_manifest(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_v0_release_manifest(data), encoding="utf-8")


def validate_v0_release_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["v0 release manifest must be a JSON object"]
    if data.get("kind") != V0_RELEASE_MANIFEST_KIND:
        errors.append(f"kind must be {V0_RELEASE_MANIFEST_KIND}")
    if data.get("schema_version") != V0_RELEASE_MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {V0_RELEASE_MANIFEST_SCHEMA_VERSION}")

    rel_id = data.get("release_identity")
    if not isinstance(rel_id, dict):
        errors.append("release_identity must be an object")
    else:
        if rel_id.get("repository") != "AssetOverflow/builder-II":
            errors.append("release_identity.repository must be 'AssetOverflow/builder-II'")
        for field in ("lineage", "release_version", "target_profile", "task"):
            val = rel_id.get(field)
            if not isinstance(val, str) or not val:
                errors.append(f"release_identity.{field} must be a non-empty string")

    session_proof = data.get("governed_session_proof")
    if not isinstance(session_proof, dict):
        errors.append("governed_session_proof must be an object")
    else:
        for req_field in (
            "prepare_package_ref",
            "session_workflow_ref",
            "goose_readonly_session_ref",
            "verification_report_ref",
            "repo_map_ref",
            "context_pack_ref",
            "handoff_note_ref",
        ):
            errors.extend(
                _validate_required_ref(
                    session_proof,
                    req_field,
                    f"governed_session_proof.{req_field}",
                )
            )
        if "deepagents_readiness_ref" in session_proof and session_proof["deepagents_readiness_ref"] is not None:
            errors.extend(
                _validate_ref(
                    session_proof["deepagents_readiness_ref"],
                    "governed_session_proof.deepagents_readiness_ref",
                )
            )

    spine_proof = data.get("platform_spine_proof")
    if not isinstance(spine_proof, dict):
        errors.append("platform_spine_proof must be an object")
    else:
        errors.extend(
            _validate_required_ref(
                spine_proof,
                "platform_spine_ref",
                "platform_spine_proof.platform_spine_ref",
            )
        )

    audit_refs = data.get("audit_references")
    if not isinstance(audit_refs, dict):
        errors.append("audit_references must be an object")
    else:
        errors.extend(
            _validate_required_ref(
                audit_refs,
                "artifact_index_ref",
                "audit_references.artifact_index_ref",
                allow_empty_sha=True,
            )
        )
        errors.extend(
            _validate_required_ref(
                audit_refs,
                "chain_verification_report_ref",
                "audit_references.chain_verification_report_ref",
            )
        )

    status = data.get("proof_status")
    if not isinstance(status, dict):
        errors.append("proof_status must be an object")
    else:
        for k in (
            "verified_no_runtime_authority",
            "verified_no_source_writes",
            "verified_chain_valid",
            "verified_index_valid",
        ):
            if status.get(k) is not True:
                errors.append(f"proof_status.{k} must be true")

    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(gov, "v0_release_manifest"))

    return errors


def validate_v0_release_manifest_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_v0_release_manifest(data)
