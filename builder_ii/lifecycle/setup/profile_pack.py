from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.lifecycle.setup.profile_pack_dry_run import PROFILE_PACK_DRY_RUN_KIND, validate_profile_pack_dry_run
from builder_ii.lifecycle.setup.profile_pack_manifest import (
    PROFILE_PACK_MANIFEST_KIND,
    canonical_digest,
    validate_profile_pack_manifest,
)
from builder_ii.lifecycle.setup.profile_pack_render_plan import (
    PROFILE_PACK_RENDER_PLAN_KIND,
    validate_profile_pack_render_plan,
)
from builder_ii.lifecycle.setup.profile_pack_validation_report import (
    PROFILE_PACK_VALIDATION_REPORT_KIND,
    validate_profile_pack_validation_report,
)

PROFILE_PACK_KIND = "builder_ii.profile_pack"
PROFILE_PACK_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _artifact_ref(data: dict[str, Any], *, path: Path | None) -> dict[str, Any]:
    return {
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
    }


def _ref_sha(record: dict[str, Any], field: str) -> str | None:
    value = record.get(field)
    if not isinstance(value, dict):
        return None
    sha = value.get("sha256")
    return sha if isinstance(sha, str) else None


def _lifecycle_binding_errors(
    *,
    manifest: dict[str, Any],
    render_plan: dict[str, Any],
    dry_run: dict[str, Any],
    validation_report: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field in ("pack_id", "target_profile", "task"):
        manifest_value = manifest.get(field)
        if render_plan.get(field) != manifest_value:
            errors.append(f"render_plan.{field} must match manifest.{field}")
        if dry_run.get(field) != manifest_value:
            errors.append(f"dry_run.{field} must match manifest.{field}")

    manifest_digest = canonical_digest(manifest)
    render_plan_digest = canonical_digest(render_plan)
    dry_run_digest = canonical_digest(dry_run)

    if _ref_sha(render_plan, "source_manifest_ref") != manifest_digest:
        errors.append("render_plan.source_manifest_ref.sha256 must match manifest digest")
    if _ref_sha(dry_run, "source_manifest_ref") != manifest_digest:
        errors.append("dry_run.source_manifest_ref.sha256 must match manifest digest")
    if _ref_sha(dry_run, "source_render_plan_ref") != render_plan_digest:
        errors.append("dry_run.source_render_plan_ref.sha256 must match render plan digest")

    if validation_report.get("valid") is not True:
        errors.append("validation_report.valid must be true")
    if validation_report.get("status") != "valid":
        errors.append("validation_report.status must be valid")

    subject_ref = validation_report.get("subject_ref")
    subject_sha = subject_ref.get("sha256") if isinstance(subject_ref, dict) else None
    subject_kind = validation_report.get("subject_kind")
    expected_subjects = {
        PROFILE_PACK_MANIFEST_KIND: manifest_digest,
        PROFILE_PACK_RENDER_PLAN_KIND: render_plan_digest,
        PROFILE_PACK_DRY_RUN_KIND: dry_run_digest,
    }
    if subject_kind not in expected_subjects:
        errors.append("validation_report.subject_kind must reference this lifecycle manifest, render plan, or dry-run")
    elif subject_sha != expected_subjects[subject_kind]:
        errors.append("validation_report.subject_ref.sha256 must match the referenced lifecycle artifact")

    return errors


def _lifecycle_bindings(
    *,
    manifest: dict[str, Any],
    render_plan: dict[str, Any],
    dry_run: dict[str, Any],
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    subject_ref = validation_report.get("subject_ref")
    subject_sha = subject_ref.get("sha256") if isinstance(subject_ref, dict) else ""
    return {
        "manifest_sha256": canonical_digest(manifest),
        "render_plan_sha256": canonical_digest(render_plan),
        "dry_run_sha256": canonical_digest(dry_run),
        "validation_report_sha256": canonical_digest(validation_report),
        "render_plan_manifest_sha256": _ref_sha(render_plan, "source_manifest_ref") or "",
        "dry_run_manifest_sha256": _ref_sha(dry_run, "source_manifest_ref") or "",
        "dry_run_render_plan_sha256": _ref_sha(dry_run, "source_render_plan_ref") or "",
        "validation_report_subject_kind": str(validation_report.get("subject_kind", "")),
        "validation_report_subject_sha256": subject_sha if isinstance(subject_sha, str) else "",
    }


def create_profile_pack(
    *,
    manifest: dict[str, Any],
    render_plan: dict[str, Any],
    dry_run: dict[str, Any],
    validation_report: dict[str, Any],
    manifest_path: Path | None = None,
    render_plan_path: Path | None = None,
    dry_run_path: Path | None = None,
    validation_report_path: Path | None = None,
) -> dict[str, Any]:
    manifest_errors = validate_profile_pack_manifest(manifest)
    render_errors = validate_profile_pack_render_plan(render_plan)
    dry_run_errors = validate_profile_pack_dry_run(dry_run)
    report_errors = validate_profile_pack_validation_report(validation_report)
    if manifest_errors or render_errors or dry_run_errors or report_errors:
        raise ValueError(
            "profile pack lifecycle artifacts are invalid: "
            + "; ".join(manifest_errors + render_errors + dry_run_errors + report_errors)
        )
    binding_errors = _lifecycle_binding_errors(
        manifest=manifest,
        render_plan=render_plan,
        dry_run=dry_run,
        validation_report=validation_report,
    )
    if binding_errors:
        raise ValueError("profile pack lifecycle artifacts are not bound: " + "; ".join(binding_errors))

    return {
        "kind": PROFILE_PACK_KIND,
        "schema_version": PROFILE_PACK_SCHEMA_VERSION,
        "pack_state": "PACKED_ONLY",
        "pack_id": manifest["pack_id"],
        "target_profile": manifest["target_profile"],
        "task": manifest["task"],
        "manifest_ref": _artifact_ref(manifest, path=manifest_path),
        "render_plan_ref": _artifact_ref(render_plan, path=render_plan_path),
        "dry_run_ref": _artifact_ref(dry_run, path=dry_run_path),
        "validation_report_ref": _artifact_ref(validation_report, path=validation_report_path),
        "lifecycle_bindings": _lifecycle_bindings(
            manifest=manifest,
            render_plan=render_plan,
            dry_run=dry_run,
            validation_report=validation_report,
        ),
        "lifecycle": {
            "planned": True,
            "rendered": True,
            "dry_run": True,
            "validated": True,
            "executed": False,
            "authorized": False,
            "promoted": False,
        },
        "governance": {
            "capability_state": "profile_pack",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "deepagents_runtime_start": "DISABLED",
            "agent_construction": "DISABLED",
            "subagent_construction": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "mcp_tool_calls": "DISABLED",
            "verification_execution": "DISABLED",
            "artifact_is_authority": False,
            "executed": False,
            "authorized": False,
            "promoted": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_profile_pack(pack: dict[str, Any]) -> str:
    return json_lib.dumps(pack, indent=2, sort_keys=True) + "\n"


def write_profile_pack(pack: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_pack(pack), encoding="utf-8")


def _validate_ref(value: Any, *, field: str, expected_kind: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if value.get("kind") != expected_kind:
        errors.append(f"{field}.kind must be {expected_kind}")
    if not isinstance(value.get("path", ""), str):
        errors.append(f"{field}.path must be a string")
    if not isinstance(value.get("sha256"), str) or not _SHA256_RE.match(value["sha256"]):
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    return errors


def _validate_sha_field(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        return [f"{field} must be a SHA-256 hex digest"]
    return []


def _validate_lifecycle_bindings(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bindings = data.get("lifecycle_bindings")
    if not isinstance(bindings, dict):
        return ["lifecycle_bindings must be an object"]

    digest_fields = (
        "manifest_sha256",
        "render_plan_sha256",
        "dry_run_sha256",
        "validation_report_sha256",
        "render_plan_manifest_sha256",
        "dry_run_manifest_sha256",
        "dry_run_render_plan_sha256",
        "validation_report_subject_sha256",
    )
    for field in digest_fields:
        errors.extend(_validate_sha_field(bindings.get(field), field=f"lifecycle_bindings.{field}"))

    ref_expectations = (
        ("manifest_ref", "manifest_sha256"),
        ("render_plan_ref", "render_plan_sha256"),
        ("dry_run_ref", "dry_run_sha256"),
        ("validation_report_ref", "validation_report_sha256"),
    )
    for ref_field, binding_field in ref_expectations:
        ref_sha = _ref_sha(data, ref_field)
        if isinstance(ref_sha, str) and bindings.get(binding_field) != ref_sha:
            errors.append(f"lifecycle_bindings.{binding_field} must match {ref_field}.sha256")

    manifest_sha = bindings.get("manifest_sha256")
    render_sha = bindings.get("render_plan_sha256")
    if bindings.get("render_plan_manifest_sha256") != manifest_sha:
        errors.append("lifecycle_bindings.render_plan_manifest_sha256 must match manifest_sha256")
    if bindings.get("dry_run_manifest_sha256") != manifest_sha:
        errors.append("lifecycle_bindings.dry_run_manifest_sha256 must match manifest_sha256")
    if bindings.get("dry_run_render_plan_sha256") != render_sha:
        errors.append("lifecycle_bindings.dry_run_render_plan_sha256 must match render_plan_sha256")

    subject_kind = bindings.get("validation_report_subject_kind")
    expected_subjects = {
        PROFILE_PACK_MANIFEST_KIND: bindings.get("manifest_sha256"),
        PROFILE_PACK_RENDER_PLAN_KIND: bindings.get("render_plan_sha256"),
        PROFILE_PACK_DRY_RUN_KIND: bindings.get("dry_run_sha256"),
    }
    if subject_kind not in expected_subjects:
        errors.append(
            "lifecycle_bindings.validation_report_subject_kind must reference manifest, render plan, or dry-run"
        )
    elif bindings.get("validation_report_subject_sha256") != expected_subjects[subject_kind]:
        errors.append("lifecycle_bindings.validation_report_subject_sha256 must match the referenced lifecycle digest")

    return errors


def _validate_governance(governance: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != "profile_pack":
        errors.append("governance.capability_state must be profile_pack")
    for key in (
        "runtime_execution",
        "goose_runtime_start",
        "deepagents_runtime_start",
        "agent_construction",
        "subagent_construction",
        "model_execution",
        "shell_execution",
        "target_repo_writes",
        "memory_mutation",
        "mcp_tool_calls",
        "verification_execution",
    ):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "executed", "authorized", "promoted"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_profile_pack(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile pack must be a JSON object"]
    if data.get("kind") != PROFILE_PACK_KIND:
        errors.append(f"kind must be {PROFILE_PACK_KIND}")
    if data.get("schema_version") != PROFILE_PACK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROFILE_PACK_SCHEMA_VERSION}")
    if data.get("pack_state") != "PACKED_ONLY":
        errors.append("pack_state must be PACKED_ONLY")
    for field in ("pack_id", "target_profile", "task"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    errors.extend(
        _validate_ref(data.get("manifest_ref"), field="manifest_ref", expected_kind=PROFILE_PACK_MANIFEST_KIND)
    )
    errors.extend(
        _validate_ref(data.get("render_plan_ref"), field="render_plan_ref", expected_kind=PROFILE_PACK_RENDER_PLAN_KIND)
    )
    errors.extend(_validate_ref(data.get("dry_run_ref"), field="dry_run_ref", expected_kind=PROFILE_PACK_DRY_RUN_KIND))
    errors.extend(
        _validate_ref(
            data.get("validation_report_ref"),
            field="validation_report_ref",
            expected_kind=PROFILE_PACK_VALIDATION_REPORT_KIND,
        )
    )
    errors.extend(_validate_lifecycle_bindings(data))

    lifecycle = data.get("lifecycle")
    if not isinstance(lifecycle, dict):
        errors.append("lifecycle must be an object")
    else:
        expected = {
            "planned": True,
            "rendered": True,
            "dry_run": True,
            "validated": True,
            "executed": False,
            "authorized": False,
            "promoted": False,
        }
        for key, value in expected.items():
            if lifecycle.get(key) is not value:
                errors.append(f"lifecycle.{key} must be {str(value).lower()}")

    errors.extend(_validate_governance(data.get("governance")))
    return errors


def validate_profile_pack_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_pack(data)
