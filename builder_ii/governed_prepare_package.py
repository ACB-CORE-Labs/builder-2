from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.context_packs import (
    CONTEXT_PACK_KIND,
    create_context_pack,
    validate_context_pack,
)
from builder_ii.deepagents_bridge_readiness import (
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    create_deepagents_bridge_readiness_report,
    validate_deepagents_bridge_readiness_report,
)
from builder_ii.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    create_goose_readonly_session_plan,
    validate_goose_readonly_session_plan,
)
from builder_ii.handoff_notes import (
    HANDOFF_NOTE_KIND,
    create_artifact_ref,
    create_handoff_note,
    validate_handoff_note,
)
from builder_ii.profile_resolution import ProfileResolver
from builder_ii.repo_map import (
    REPO_MAP_KIND,
    create_repo_map,
    validate_repo_map,
)
from builder_ii.session_workflow import (
    SESSION_WORKFLOW_PLAN_KIND,
    create_session_workflow_plan,
    validate_session_workflow_plan,
)
from builder_ii.verification_profile_reports import (
    VERIFICATION_PROFILE_REPORT_KIND,
    create_verification_profile_report,
    validate_verification_profile_report,
)

GOVERNED_PREPARE_PACKAGE_KIND = "builder_ii.governed_prepare_package"
GOVERNED_PREPARE_PACKAGE_SCHEMA_VERSION = 1
GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND = "builder_ii.governed_prepare_package_summary"
GOVERNED_PREPARE_PACKAGE_SUMMARY_SCHEMA_VERSION = 1


def _dumps_json(data: dict[str, Any]) -> str:
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"


def _sha256_file(path: Path) -> str:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, (dict, list)):
            raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
            return hashlib.sha256(raw).hexdigest()
    except Exception:
        pass
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_artifact(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dumps_json(data), encoding="utf-8")


def _artifact_ref_for(path: Path, *, kind: str, output_dir: Path, name: str = "") -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path.relative_to(output_dir)),
        "sha256": _sha256_file(path),
        "name": name,
    }


def _is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _validate_or_raise(label: str, errors: list[str]) -> None:
    if errors:
        raise ValueError(f"invalid {label}: " + "; ".join(errors))


def create_governed_prepare_package(
    settings: Settings,
    target_name: str,
    *,
    output_dir: Path,
    repo_path: str | None = None,
    agent_profile_name: str | None = None,
    prompt_profile_name: str | None = None,
    verification_profile_name: str | None = None,
    task: str = "",
    include_deepagents_readiness: bool = True,
) -> dict[str, Any]:
    """Create a governed local preparation package.

    This function writes only explicit artifact files under ``output_dir``.
    It does not execute commands, invoke Goose, delegate to deepagents, or
    modify the target repository.
    """

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    task_text = task or "prepare governed local developer session"

    session_plan = create_session_workflow_plan(
        settings,
        target_name,  # type: ignore[arg-type]
        agent_profile_name=agent_profile_name,  # type: ignore[arg-type]
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,  # type: ignore[arg-type]
        repo_path=repo_path,
    )
    _validate_or_raise("session workflow plan", validate_session_workflow_plan(session_plan))

    goose_plan = create_goose_readonly_session_plan(
        settings,
        target_name,  # type: ignore[arg-type]
        agent_profile_name=agent_profile_name,  # type: ignore[arg-type]
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,  # type: ignore[arg-type]
        repo_path=repo_path,
        task=task_text,
    )
    _validate_or_raise("Goose read-only session plan", validate_goose_readonly_session_plan(goose_plan))

    verification_report = create_verification_profile_report(
        settings,
        target_name,  # type: ignore[arg-type]
        agent_profile_name=agent_profile_name,  # type: ignore[arg-type]
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,  # type: ignore[arg-type]
        repo_path=repo_path,
        task=task_text,
        goose_readonly_session_plan=goose_plan,
    )
    _validate_or_raise(
        "verification profile report",
        validate_verification_profile_report(verification_report),
    )

    session_path = output_dir / "session-workflow.json"
    goose_path = output_dir / "goose-readonly-session.json"
    verification_path = output_dir / "verification-profile-report.json"

    _write_json_artifact(session_plan, session_path)
    _write_json_artifact(goose_plan, goose_path)
    _write_json_artifact(verification_report, verification_path)

    session_ref = _artifact_ref_for(
        session_path,
        kind=SESSION_WORKFLOW_PLAN_KIND,
        output_dir=output_dir,
        name="session workflow plan",
    )
    goose_ref = _artifact_ref_for(
        goose_path,
        kind=GOOSE_READONLY_SESSION_PLAN_KIND,
        output_dir=output_dir,
        name="Goose read-only session plan",
    )
    verification_ref = _artifact_ref_for(
        verification_path,
        kind=VERIFICATION_PROFILE_REPORT_KIND,
        output_dir=output_dir,
        name="verification profile report",
    )

    resolver = ProfileResolver(settings)
    resolved = resolver.resolve(target_name=target_name, repo_path=repo_path)  # type: ignore[arg-type]
    resolved_repo = Path(resolved.repo_path)

    repo_map = create_repo_map(resolved_repo, target_name=target_name)
    _validate_or_raise("repo map", validate_repo_map(repo_map))

    context_pack = create_context_pack(repo_map, target_name=target_name, task=task_text)
    _validate_or_raise("context pack", validate_context_pack(context_pack))

    repo_map_path = output_dir / "repo-map.json"
    context_pack_path = output_dir / "context-pack.json"

    _write_json_artifact(repo_map, repo_map_path)
    _write_json_artifact(context_pack, context_pack_path)

    repo_map_ref = _artifact_ref_for(
        repo_map_path,
        kind=REPO_MAP_KIND,
        output_dir=output_dir,
        name="bounded repo map",
    )
    context_pack_ref = _artifact_ref_for(
        context_pack_path,
        kind=CONTEXT_PACK_KIND,
        output_dir=output_dir,
        name="bounded context pack",
    )

    handoff_note = create_handoff_note(
        target_name=target_name,
        status="READY_FOR_REVIEW",
        summary="Governed preparation package created. No target-repo execution was performed.",
        changed_files_summary=["Created explicit governed preparation artifacts under the requested output directory."],
        verification_summary="Verification report is planned-only. No checks were executed by this package.",
        session_ref=create_artifact_ref(**session_ref),
        goose_readonly_session_ref=create_artifact_ref(**goose_ref),
        verification_report_ref=create_artifact_ref(**verification_ref),
        open_risks=[
            "Human operator must run and evidence any verification commands out-of-band.",
            "Any future writes or execution remain HITL-gated.",
        ],
        next_recommended_action="Inspect generated artifacts, run planned verification manually, then record evidence.",
    )
    _validate_or_raise("handoff note", validate_handoff_note(handoff_note))

    handoff_path = output_dir / "handoff-note.json"
    _write_json_artifact(handoff_note, handoff_path)
    handoff_ref = _artifact_ref_for(
        handoff_path,
        kind=HANDOFF_NOTE_KIND,
        output_dir=output_dir,
        name="governed handoff note",
    )

    artifact_refs = [
        session_ref,
        goose_ref,
        verification_ref,
        repo_map_ref,
        context_pack_ref,
        handoff_ref,
    ]

    if include_deepagents_readiness:
        deepagents_report = create_deepagents_bridge_readiness_report(
            target_profile=target_name,
            agent_profile_compatibility_summary=(
                "Prepared for readiness inspection only. No deepagents delegation or runtime activation was performed."
            ),
            readiness_verdict="NOT_READY",
        )
        _validate_or_raise(
            "deepagents bridge readiness report",
            validate_deepagents_bridge_readiness_report(deepagents_report),
        )
        deepagents_path = output_dir / "deepagents-bridge-readiness.json"
        _write_json_artifact(deepagents_report, deepagents_path)
        artifact_refs.append(
            _artifact_ref_for(
                deepagents_path,
                kind=DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
                output_dir=output_dir,
                name="optional deepagents bridge readiness report",
            )
        )

    package = {
        "kind": GOVERNED_PREPARE_PACKAGE_KIND,
        "schema_version": GOVERNED_PREPARE_PACKAGE_SCHEMA_VERSION,
        "target_name": target_name,
        "repo_path": repo_path,
        "task": task_text,
        "output_dir": str(output_dir),
        "artifact_refs": artifact_refs,
        "package_state": "PREPARED_ONLY",
        "runtime_execution_performed": False,
        "target_repo_writes_performed": False,
        "governance": {
            "capability_state": "governed_prepare_package",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "goose_activation": "DISABLED",
            "deepagents_delegation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }

    _validate_or_raise("governed prepare package", validate_governed_prepare_package(package))

    package_path = output_dir / "prepare-package.json"
    _write_json_artifact(package, package_path)

    return package


def validate_governed_prepare_package(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["governed prepare package must be a JSON object"]

    if data.get("kind") != GOVERNED_PREPARE_PACKAGE_KIND:
        errors.append(f"kind must be {GOVERNED_PREPARE_PACKAGE_KIND}")
    if data.get("schema_version") != GOVERNED_PREPARE_PACKAGE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOVERNED_PREPARE_PACKAGE_SCHEMA_VERSION}")

    if data.get("target_name") not in {"generic", "builder", "core"}:
        errors.append("target_name must be one of: generic, builder, core")

    artifact_refs = data.get("artifact_refs")
    if not isinstance(artifact_refs, list) or not artifact_refs:
        errors.append("artifact_refs must be a non-empty list")
    else:
        for index, ref in enumerate(artifact_refs):
            prefix = f"artifact_refs[{index}]"
            if not isinstance(ref, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(ref.get("kind"), str) or not ref["kind"]:
                errors.append(f"{prefix}.kind must be a non-empty string")
            if not isinstance(ref.get("path"), str) or not ref["path"]:
                errors.append(f"{prefix}.path must be a non-empty string")
            if not isinstance(ref.get("sha256"), str) or len(ref["sha256"]) != 64:
                errors.append(f"{prefix}.sha256 must be a 64-character string")
            if not isinstance(ref.get("name", ""), str):
                errors.append(f"{prefix}.name must be a string when present")

    if data.get("package_state") != "PREPARED_ONLY":
        errors.append("package_state must be PREPARED_ONLY")
    if data.get("runtime_execution_performed") is not False:
        errors.append("runtime_execution_performed must be false or NOT_AUTHORIZED")
    if data.get("target_repo_writes_performed") is not False:
        errors.append("target_repo_writes_performed must be false or NOT_AUTHORIZED")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "governed_prepare_package":
            errors.append("governance.capability_state must be governed_prepare_package")
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY":
            errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY")
        if governance.get("target_repo_writes") != "DISABLED":
            errors.append("governance.target_repo_writes must be DISABLED or NOT_AUTHORIZED")
        if governance.get("goose_activation") != "DISABLED":
            errors.append("governance.goose_activation must be DISABLED or NOT_AUTHORIZED")
        if governance.get("deepagents_delegation") != "DISABLED":
            errors.append("governance.deepagents_delegation must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_governed_prepare_package_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_governed_prepare_package(data)


def validate_governed_prepare_package_directory(path: Path) -> list[str]:
    """Validate a governed prepare package manifest and referenced artifacts.

    ``path`` may point either to a package directory or directly to a
    ``prepare-package.json`` manifest. This validator does not execute any
    command. It only reads explicit package artifacts, checks reference
    containment, recomputes hashes, and validates each referenced JSON artifact
    by its declared kind.
    """

    manifest_path = path / "prepare-package.json" if path.is_dir() else path
    errors: list[str] = []

    if not manifest_path.exists():
        return [f"prepare package manifest not found: {manifest_path}"]
    if not manifest_path.is_file():
        return [f"prepare package manifest is not a file: {manifest_path}"]

    try:
        package = json_lib.loads(manifest_path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid prepare package JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read prepare package manifest: {exc}"]

    errors.extend(validate_governed_prepare_package(package))

    package_dir = manifest_path.parent.resolve()
    artifact_refs = package.get("artifact_refs")
    if not isinstance(artifact_refs, list):
        return errors

    from builder_ii.orchestration_assignment import (
        AGENT_ASSIGNMENT_PLAN_KIND,
        ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
        ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
        ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND,
        validate_agent_assignment_plan,
        validate_orchestration_assignment_dry_run,
        validate_orchestration_assignment_plan,
        validate_orchestration_assignment_validation_report,
    )

    kind_validators = {
        SESSION_WORKFLOW_PLAN_KIND: validate_session_workflow_plan,
        GOOSE_READONLY_SESSION_PLAN_KIND: validate_goose_readonly_session_plan,
        VERIFICATION_PROFILE_REPORT_KIND: validate_verification_profile_report,
        HANDOFF_NOTE_KIND: validate_handoff_note,
        DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND: validate_deepagents_bridge_readiness_report,
        REPO_MAP_KIND: validate_repo_map,
        CONTEXT_PACK_KIND: validate_context_pack,
        AGENT_ASSIGNMENT_PLAN_KIND: validate_agent_assignment_plan,
        ORCHESTRATION_ASSIGNMENT_PLAN_KIND: validate_orchestration_assignment_plan,
        ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND: validate_orchestration_assignment_dry_run,
        ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND: validate_orchestration_assignment_validation_report,
    }

    for index, ref in enumerate(artifact_refs):
        prefix = f"artifact_refs[{index}]"
        if not isinstance(ref, dict):
            continue

        ref_path_value = ref.get("path")
        ref_kind = ref.get("kind")
        expected_sha = ref.get("sha256")

        if not isinstance(ref_path_value, str) or not ref_path_value:
            continue

        ref_path = Path(ref_path_value)
        if ref_path.is_absolute():
            errors.append(f"{prefix}.path must be relative to the prepare package directory")
            continue

        artifact_path = (package_dir / ref_path).resolve()
        if not _is_within_directory(artifact_path, package_dir):
            errors.append(f"{prefix}.path escapes the prepare package directory")
            continue

        if not artifact_path.exists():
            errors.append(f"{prefix}.path does not exist: {ref_path_value}")
            continue
        if not artifact_path.is_file():
            errors.append(f"{prefix}.path is not a file: {ref_path_value}")
            continue

        actual_sha = _sha256_file(artifact_path)
        if isinstance(expected_sha, str) and expected_sha and actual_sha != expected_sha:
            errors.append(f"{prefix}.sha256 mismatch for {ref_path_value}")

        try:
            artifact_data = json_lib.loads(artifact_path.read_text(encoding="utf-8"))
        except json_lib.JSONDecodeError as exc:
            errors.append(f"{prefix}.artifact is not valid JSON: {exc}")
            continue
        except Exception as exc:
            errors.append(f"{prefix}.artifact could not be read: {exc}")
            continue

        if not isinstance(ref_kind, str):
            continue

        validator = kind_validators.get(ref_kind)
        if validator is None:
            errors.append(f"{prefix}.kind has no prepare-package artifact validator: {ref_kind}")
            continue

        for artifact_error in validator(artifact_data):
            errors.append(f"{prefix}.artifact invalid for {ref_kind}: {artifact_error}")

    return errors


def summarize_governed_prepare_package_directory(path: Path) -> dict[str, Any]:
    """Summarize a validated governed prepare package for human inspection.

    The summary path is read-only over the package contents. It refuses to
    summarize invalid packages and never executes package instructions,
    verification commands, Goose, deepagents, shell commands, or runtime work.
    """

    errors = validate_governed_prepare_package_directory(path)
    if errors:
        raise ValueError("invalid governed prepare package: " + "; ".join(errors))

    manifest_path = path / "prepare-package.json" if path.is_dir() else path
    manifest_path = manifest_path.resolve()
    package_dir = manifest_path.parent

    package = json_lib.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_refs = list(package.get("artifact_refs", []))
    artifact_kinds = sorted({ref.get("kind", "") for ref in artifact_refs if isinstance(ref, dict)})

    artifacts: list[dict[str, Any]] = []
    for ref in artifact_refs:
        if not isinstance(ref, dict):
            continue
        artifacts.append(
            {
                "kind": ref.get("kind", ""),
                "path": ref.get("path", ""),
                "name": ref.get("name", ""),
                "sha256": ref.get("sha256", ""),
            }
        )

    summary = {
        "kind": GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND,
        "schema_version": GOVERNED_PREPARE_PACKAGE_SUMMARY_SCHEMA_VERSION,
        "package_manifest": str(manifest_path),
        "package_directory": str(package_dir),
        "target_name": package.get("target_name"),
        "repo_path": package.get("repo_path"),
        "task": package.get("task"),
        "package_state": package.get("package_state"),
        "validation_state": "VALIDATED",
        "artifact_count": len(artifacts),
        "artifact_kinds": artifact_kinds,
        "artifacts": artifacts,
        "runtime_execution_performed": package.get("runtime_execution_performed"),
        "target_repo_writes_performed": package.get("target_repo_writes_performed"),
        "operator_report": {
            "summary": "Governed prepare package is structurally valid and artifact hashes match.",
            "verification_status": "Planned verification has not been executed by this summary.",
            "next_actions": [
                "Inspect generated artifacts.",
                "Run planned verification commands manually if appropriate.",
                "Record verification evidence before claiming checks passed.",
                "Keep any future execution or writes HITL-gated.",
            ],
        },
        "governance": {
            "capability_state": "governed_prepare_package_summary",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT SUMMARY OUTPUT PATH",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "goose_activation": "DISABLED",
            "deepagents_delegation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }

    summary_errors = validate_governed_prepare_package_summary(summary)
    if summary_errors:
        raise ValueError("invalid governed prepare package summary: " + "; ".join(summary_errors))
    return summary


def validate_governed_prepare_package_summary(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["governed prepare package summary must be a JSON object"]

    if data.get("kind") != GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND:
        errors.append(f"kind must be {GOVERNED_PREPARE_PACKAGE_SUMMARY_KIND}")
    if data.get("schema_version") != GOVERNED_PREPARE_PACKAGE_SUMMARY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOVERNED_PREPARE_PACKAGE_SUMMARY_SCHEMA_VERSION}")

    if data.get("validation_state") != "VALIDATED":
        errors.append("validation_state must be VALIDATED")
    if data.get("target_name") not in {"generic", "builder", "core"}:
        errors.append("target_name must be one of: generic, builder, core")
    if data.get("package_state") != "PREPARED_ONLY":
        errors.append("package_state must be PREPARED_ONLY")
    if data.get("runtime_execution_performed") is not False:
        errors.append("runtime_execution_performed must be false or NOT_AUTHORIZED")
    if data.get("target_repo_writes_performed") is not False:
        errors.append("target_repo_writes_performed must be false or NOT_AUTHORIZED")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list")
    else:
        for index, artifact in enumerate(artifacts):
            prefix = f"artifacts[{index}]"
            if not isinstance(artifact, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ("kind", "path", "sha256"):
                if not isinstance(artifact.get(field), str) or not artifact[field]:
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            if not isinstance(artifact.get("name", ""), str):
                errors.append(f"{prefix}.name must be a string when present")

    if data.get("artifact_count") != len(artifacts or []):
        errors.append("artifact_count must match artifacts length")

    artifact_kinds = data.get("artifact_kinds")
    if not isinstance(artifact_kinds, list) or any(not isinstance(kind, str) or not kind for kind in artifact_kinds):
        errors.append("artifact_kinds must be a list of non-empty strings")

    operator_report = data.get("operator_report")
    if not isinstance(operator_report, dict):
        errors.append("operator_report must be an object")
    else:
        if not isinstance(operator_report.get("summary"), str) or not operator_report["summary"]:
            errors.append("operator_report.summary must be a non-empty string")
        if (
            not isinstance(operator_report.get("verification_status"), str)
            or not operator_report["verification_status"]
        ):
            errors.append("operator_report.verification_status must be a non-empty string")
        next_actions = operator_report.get("next_actions")
        if not isinstance(next_actions, list) or not next_actions:
            errors.append("operator_report.next_actions must be a non-empty list")
        elif any(not isinstance(action, str) or not action for action in next_actions):
            errors.append("operator_report.next_actions must be a list of non-empty strings")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "governed_prepare_package_summary":
            errors.append("governance.capability_state must be governed_prepare_package_summary")
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT SUMMARY OUTPUT PATH":
            errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT SUMMARY OUTPUT PATH")
        if governance.get("target_repo_writes") != "DISABLED":
            errors.append("governance.target_repo_writes must be DISABLED or NOT_AUTHORIZED")
        if governance.get("goose_activation") != "DISABLED":
            errors.append("governance.goose_activation must be DISABLED or NOT_AUTHORIZED")
        if governance.get("deepagents_delegation") != "DISABLED":
            errors.append("governance.deepagents_delegation must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def dumps_governed_prepare_package_summary(summary: dict[str, Any]) -> str:
    errors = validate_governed_prepare_package_summary(summary)
    if errors:
        raise ValueError("invalid governed prepare package summary: " + "; ".join(errors))
    return _dumps_json(summary)


def dumps_governed_prepare_package(package: dict[str, Any]) -> str:
    return _dumps_json(package)
