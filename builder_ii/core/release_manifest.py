from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance

V0_RELEASE_MANIFEST_KIND = "builder_ii.v0_release_manifest"
V0_RELEASE_MANIFEST_SCHEMA_VERSION = 1
RELEASE_PROOF_BUNDLE_KIND = "builder_ii.release_proof_bundle"
RELEASE_PROOF_BUNDLE_SCHEMA_VERSION = 1
RELEASE_EVIDENCE_KIND = "builder_ii.release_evidence"
RELEASE_EVIDENCE_SCHEMA_VERSION = 1
RELEASE_RESULT_STATES = ("PASS", "FAIL", "SKIP", "NOT_RUN")
REQUIRED_RELEASE_LANES = (
    "local_ci",
    "linux_golden_path",
    "macos_apple_silicon_golden_path",
    "release_sabotage",
    "docs_audit",
    "platform_matrix",
    "plan_set_5_benchmark",
    "flagship_demo",
    "rehearsal_pr_custody",
    "artifact_chain",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


def create_release_proof_bundle(
    *,
    source: dict[str, Any],
    distributions: list[dict[str, Any]],
    supported_runtime: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    artifact_index_ref: dict[str, Any],
) -> dict[str, Any]:
    """Create the canonical exact-candidate v1 release evidence artifact.

    This record describes independently obtained evidence.  It never grants
    promotion, tag, release, or publication authority.
    """
    bundle = {
        "kind": RELEASE_PROOF_BUNDLE_KIND,
        "schema_version": RELEASE_PROOF_BUNDLE_SCHEMA_VERSION,
        "release_identity": {
            "repository": "ACB-CORE-Labs/builder-2",
            "lineage": "open-source-v1",
            "package_version": "1.0.0",
            "proposed_tag": "v1.0.0",
        },
        "source": source,
        "distributions": distributions,
        "supported_runtime": supported_runtime,
        "evidence": evidence,
        "artifact_index_ref": artifact_index_ref,
        "authority": {
            "capability_promotion": "NOT_AUTHORIZED",
            "tag_creation": "NOT_AUTHORIZED",
            "release_publication": "NOT_AUTHORIZED",
            "package_publication": "NOT_AUTHORIZED",
        },
        "governance": build_standard_governance("release_proof_bundle"),
    }
    errors = validate_release_proof_bundle(bundle)
    if errors:
        raise ValueError(f"Invalid release proof bundle constructed: {errors}")
    return bundle


def _validate_sha(value: Any, field: str, pattern: re.Pattern[str] = _SHA256_RE) -> list[str]:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        return [f"{field} must be lowercase hexadecimal with length {pattern.pattern[-4:-2] or 'required'}"]
    return []


def validate_release_proof_bundle(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["release proof bundle must be a JSON object"]
    if data.get("kind") != RELEASE_PROOF_BUNDLE_KIND:
        errors.append(f"kind must be {RELEASE_PROOF_BUNDLE_KIND}")
    if data.get("schema_version") != RELEASE_PROOF_BUNDLE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RELEASE_PROOF_BUNDLE_SCHEMA_VERSION}")

    identity = data.get("release_identity")
    expected_identity = {
        "repository": "ACB-CORE-Labs/builder-2",
        "lineage": "open-source-v1",
        "package_version": "1.0.0",
        "proposed_tag": "v1.0.0",
    }
    if not isinstance(identity, dict):
        errors.append("release_identity must be an object")
    else:
        for key, expected in expected_identity.items():
            if identity.get(key) != expected:
                errors.append(f"release_identity.{key} must be {expected!r}")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        for key in ("commit", "tree"):
            errors.extend(_validate_sha(source.get(key), f"source.{key}", _GIT_SHA_RE))
        parents = source.get("parents")
        if not isinstance(parents, list) or not parents:
            errors.append("source.parents must be a non-empty list")
        else:
            for index, parent in enumerate(parents):
                errors.extend(_validate_sha(parent, f"source.parents[{index}]", _GIT_SHA_RE))
        for key in ("uv_lock_sha256", "source_archive_sha256"):
            errors.extend(_validate_sha(source.get(key), f"source.{key}"))
        if source.get("clean") is not True:
            errors.append("source.clean must be true")

    distributions = data.get("distributions")
    required_types = {"sdist", "wheel"}
    seen_types: set[str] = set()
    if not isinstance(distributions, list) or not distributions:
        errors.append("distributions must be a non-empty list")
    else:
        for index, dist in enumerate(distributions):
            field = f"distributions[{index}]"
            if not isinstance(dist, dict):
                errors.append(f"{field} must be an object")
                continue
            dist_type = dist.get("type")
            if dist_type not in required_types:
                errors.append(f"{field}.type must be 'sdist' or 'wheel'")
            else:
                seen_types.add(dist_type)
            if not isinstance(dist.get("filename"), str) or not dist["filename"]:
                errors.append(f"{field}.filename must be a non-empty string")
            if not isinstance(dist.get("size"), int) or dist["size"] <= 0:
                errors.append(f"{field}.size must be a positive integer")
            errors.extend(_validate_sha(dist.get("sha256"), f"{field}.sha256"))
            if dist_type == "wheel":
                inventory = dist.get("record_inventory")
                if not isinstance(inventory, list) or not inventory or not all(isinstance(v, str) for v in inventory):
                    errors.append(f"{field}.record_inventory must be a non-empty string list")
        missing_types = sorted(required_types - seen_types)
        if missing_types:
            errors.append(f"distributions missing required types: {', '.join(missing_types)}")

    runtime = data.get("supported_runtime")
    if not isinstance(runtime, dict):
        errors.append("supported_runtime must be an object")
    else:
        expected_runtime = {
            "python": ">=3.12.13,<3.13",
            "macos_apple_silicon": "SUPPORTED_MLX_PRIMARY",
            "linux": "SUPPORTED_NO_MLX_PARITY",
            "windows": "UNSUPPORTED_V1",
            "wsl2": "UNSUPPORTED_V1",
        }
        for key, expected in expected_runtime.items():
            if runtime.get(key) != expected:
                errors.append(f"supported_runtime.{key} must be {expected!r}")

    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        errors.append("evidence must be an object")
    else:
        for lane in REQUIRED_RELEASE_LANES:
            record = evidence.get(lane)
            if not isinstance(record, dict):
                errors.append(f"evidence.{lane} is required and must be an object")
                continue
            if record.get("result") != "PASS":
                errors.append(f"evidence.{lane}.result must be PASS for a release candidate")
            errors.extend(_validate_ref(record.get("ref"), f"evidence.{lane}.ref"))

    errors.extend(_validate_ref(data.get("artifact_index_ref"), "artifact_index_ref"))
    authority = data.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority must be an object")
    else:
        for key in ("capability_promotion", "tag_creation", "release_publication", "package_publication"):
            if authority.get(key) != "NOT_AUTHORIZED":
                errors.append(f"authority.{key} must be NOT_AUTHORIZED")
    errors.extend(validate_standard_governance(data.get("governance"), "release_proof_bundle"))
    return errors


def dumps_release_proof_bundle(data: dict[str, Any]) -> str:
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"


def write_release_proof_bundle(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_release_proof_bundle(data), encoding="utf-8")


def validate_release_proof_bundle_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except OSError as exc:
        return [f"failed to read file: {exc}"]
    return validate_release_proof_bundle(data)


def create_release_evidence(
    *,
    lane: str,
    result: str,
    platform: dict[str, str],
    candidate: dict[str, str],
    commands: list[dict[str, Any]],
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    data = {
        "kind": RELEASE_EVIDENCE_KIND,
        "schema_version": RELEASE_EVIDENCE_SCHEMA_VERSION,
        "lane": lane,
        "result": result,
        "platform": platform,
        "candidate": candidate,
        "commands": commands,
        "limitations": limitations or [],
        "governance": build_standard_governance("release_evidence"),
    }
    errors = validate_release_evidence(data)
    if errors:
        raise ValueError(f"Invalid release evidence constructed: {errors}")
    return data


def validate_release_evidence(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["release evidence must be a JSON object"]
    if data.get("kind") != RELEASE_EVIDENCE_KIND:
        errors.append(f"kind must be {RELEASE_EVIDENCE_KIND}")
    if data.get("schema_version") != RELEASE_EVIDENCE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RELEASE_EVIDENCE_SCHEMA_VERSION}")
    if not isinstance(data.get("lane"), str) or not data["lane"]:
        errors.append("lane must be a non-empty string")
    if data.get("result") not in RELEASE_RESULT_STATES:
        errors.append(f"result must be one of {', '.join(RELEASE_RESULT_STATES)}")
    for field in ("platform", "candidate"):
        value = data.get(field)
        if not isinstance(value, dict) or not value or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in value.items()
        ):
            errors.append(f"{field} must be a non-empty string map")
    commands = data.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                errors.append(f"commands[{index}] must be an object")
                continue
            if not isinstance(command.get("name"), str) or not command["name"]:
                errors.append(f"commands[{index}].name must be a non-empty string")
            if command.get("result") not in RELEASE_RESULT_STATES:
                errors.append(f"commands[{index}].result must be one of {', '.join(RELEASE_RESULT_STATES)}")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        errors.append("limitations must be a string list")
    errors.extend(validate_standard_governance(data.get("governance"), "release_evidence"))
    return errors
