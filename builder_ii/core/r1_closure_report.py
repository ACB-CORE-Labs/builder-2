import datetime
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.core.config_schema import (
    CONFIG_SCHEMA_KIND,
    attach_digest,
    digest_jsonable,
    validate_config_schema_artifact,
)
from builder_ii.core.config_sources import (
    CONFIG_SOURCE_RESOLUTION_KIND,
    validate_config_resolution_artifact,
)
from builder_ii.lifecycle.setup.onboarding_intent import (
    DISABLED_AUTHORITY,
    ONBOARDING_INTENT_KIND,
    validate_onboarding_intent_report_artifact,
)
from builder_ii.lifecycle.setup.setup_overlay import (
    SETUP_OVERLAY_PLAN_KIND,
    validate_setup_overlay_plan_artifact,
)
from builder_ii.lifecycle.setup.setup_plan import (
    SETUP_PLAN_KIND,
    validate_setup_plan_artifact,
)
from builder_ii.lifecycle.setup.setup_rollback import (
    SETUP_ROLLBACK_SNAPSHOT_KIND,
    validate_setup_rollback_snapshot_artifact,
)

R1_CLOSURE_REPORT_KIND = "builder_ii.r1_closure_report"
R1_CLOSURE_REPORT_SCHEMA_VERSION = 1


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def format_docs_violation(violation: Any) -> str:
    if isinstance(violation, dict) and {"path", "line_number", "reason"}.issubset(violation):
        return f"docs violation in {violation['path']}:{violation['line_number']}: {violation['reason']}"
    return f"docs violation: {violation}"


def _check_command_string(command: Any, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(command, str) or not command.strip():
        return [f"deferred command must be a non-empty string starting with '{prefix}'"]
    if not command.startswith(prefix):
        errors.append(f"deferred command must start with '{prefix}'")
    if "--approve-digest" not in command:
        errors.append("deferred command must contain '--approve-digest'")
    forbidden = ("&&", "||", ";", "|", "`", "$(", "\n", "\r")
    for symbol in forbidden:
        if symbol in command:
            errors.append(f"deferred command contains forbidden chaining/shell operator or character '{symbol}'")
    return errors


def finalize_r1_closure_report(
    *,
    target_profile: str | None = None,
    artifact_root: str,
    output_dir: str,
    config_schema_status: dict[str, Any],
    config_resolution_status: dict[str, Any],
    setup_plan_status: dict[str, Any],
    overlay_plan_status: dict[str, Any],
    rollback_snapshot_status: dict[str, Any],
    onboarding_intent_status: dict[str, Any],
    command_authority_status: dict[str, Any],
    platform_matrix_status: dict[str, Any],
    docs_truth_status: dict[str, Any],
    deferred_apply_command: str,
    deferred_rollback_command: str,
    validations_run: list[str] | None = None,
    errors: list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if generated_at is None:
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if validations_run is None:
        validations_run = [
            "config_schema",
            "config_resolution",
            "setup_plan",
            "overlay_plan",
            "rollback_snapshot",
            "onboarding_intent",
            "command_authority",
            "platform_matrix",
            "docs_truth",
        ]

    collected_errors: list[str] = list(errors) if errors is not None else []
    status_dicts = [
        config_schema_status,
        config_resolution_status,
        setup_plan_status,
        overlay_plan_status,
        rollback_snapshot_status,
        onboarding_intent_status,
        command_authority_status,
        platform_matrix_status,
        docs_truth_status,
    ]
    for status in status_dicts:
        if not isinstance(status, dict):
            collected_errors.append("status entry must be a dictionary")
            continue
        if not status.get("valid", False):
            if "errors" in status and isinstance(status["errors"], list):
                collected_errors.extend(f"status error: {e}" for e in status["errors"])
            elif "violations" in status and isinstance(status["violations"], list):
                collected_errors.extend(format_docs_violation(v) for v in status["violations"])
            else:
                collected_errors.append("subsystem status reported valid=False")

    valid = len(collected_errors) == 0
    report: dict[str, Any] = {
        "kind": R1_CLOSURE_REPORT_KIND,
        "schema_version": R1_CLOSURE_REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "target_profile": target_profile or "standard",
        "artifact_root": artifact_root,
        "output_dir": output_dir,
        "config_schema_status": config_schema_status,
        "config_resolution_status": config_resolution_status,
        "setup_plan_status": setup_plan_status,
        "overlay_plan_status": overlay_plan_status,
        "rollback_snapshot_status": rollback_snapshot_status,
        "onboarding_intent_status": onboarding_intent_status,
        "command_authority_status": command_authority_status,
        "platform_matrix_status": platform_matrix_status,
        "docs_truth_status": docs_truth_status,
        "deferred_apply_command": deferred_apply_command,
        "deferred_rollback_command": deferred_rollback_command,
        "disabled_authority": dict(DISABLED_AUTHORITY),
        "validations_run": list(validations_run),
        "errors": collected_errors,
        "valid": valid,
    }
    return attach_digest(report, digest_key="r1_closure_digest")


def dumps_r1_closure_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_r1_closure_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_r1_closure_report(report), encoding="utf-8")


def _is_valid_docs_violation(violation: Any) -> bool:
    if isinstance(violation, str):
        return True
    return isinstance(violation, dict) and {"path", "line_number", "reason"}.issubset(violation)


def validate_r1_closure_report_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["R1 closure report must be a JSON object"]
    if data.get("kind") != R1_CLOSURE_REPORT_KIND:
        errors.append(f"kind must be {R1_CLOSURE_REPORT_KIND}")
    if data.get("schema_version") != R1_CLOSURE_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {R1_CLOSURE_REPORT_SCHEMA_VERSION}")
    if not isinstance(data.get("generated_at"), str) or not data.get("generated_at"):
        errors.append("generated_at must be a non-empty string")
    if not isinstance(data.get("artifact_root"), str) or not data.get("artifact_root"):
        errors.append("artifact_root must be a non-empty string")
    if not isinstance(data.get("output_dir"), str) or not data.get("output_dir"):
        errors.append("output_dir must be a non-empty string")

    valid = data.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    report_errors = data.get("errors")
    if not isinstance(report_errors, list) or not all(isinstance(e, str) for e in report_errors):
        errors.append("errors must be a list of strings")
    elif valid is True and len(report_errors) > 0:
        errors.append("errors must be empty when valid is True")
    elif valid is False and len(report_errors) == 0:
        errors.append("errors must not be empty when valid is False")

    evidence_fields = (
        "config_schema_status",
        "config_resolution_status",
        "setup_plan_status",
        "overlay_plan_status",
        "rollback_snapshot_status",
        "onboarding_intent_status",
    )
    for field in evidence_fields:
        status = data.get(field)
        if not isinstance(status, dict):
            errors.append(f"{field} must be a dictionary")
            continue
        status_valid = status.get("valid")
        if not isinstance(status_valid, bool):
            errors.append(f"{field}.valid must be a boolean")
        elif valid is True and status_valid is not True:
            errors.append(f"{field}.valid must be True when report valid is True")

        path_val = status.get("path")
        if not isinstance(path_val, str) or not path_val:
            errors.append(f"{field}.path must be a non-empty string")

        digest_val = status.get("digest")
        if not _is_sha256_hex(digest_val):
            errors.append(f"{field}.digest must be a valid 64-character SHA-256 hex string")

    live_fields = (
        "command_authority_status",
        "platform_matrix_status",
        "docs_truth_status",
    )
    for field in live_fields:
        status = data.get(field)
        if not isinstance(status, dict):
            errors.append(f"{field} must be a dictionary")
            continue
        status_valid = status.get("valid")
        if not isinstance(status_valid, bool):
            errors.append(f"{field}.valid must be a boolean")
        elif valid is True and status_valid is not True:
            errors.append(f"{field}.valid must be True when report valid is True")

        if field == "docs_truth_status":
            violations = status.get("violations")
            if not isinstance(violations, list) or not all(_is_valid_docs_violation(v) for v in violations):
                errors.append(f"{field}.violations must be a list of strings or docs violation dictionaries")
        else:
            status_errors = status.get("errors")
            if not isinstance(status_errors, list) or not all(isinstance(e, str) for e in status_errors):
                errors.append(f"{field}.errors must be a list of strings")

    disabled_auth = data.get("disabled_authority")
    if not isinstance(disabled_auth, dict) or disabled_auth != DISABLED_AUTHORITY:
        errors.append("disabled_authority claims overclaim or drift detected")

    errors.extend(_check_command_string(data.get("deferred_apply_command"), "builder-setup apply "))
    errors.extend(_check_command_string(data.get("deferred_rollback_command"), "builder-setup rollback "))

    digest = data.get("r1_closure_digest")
    if not _is_sha256_hex(digest):
        errors.append("r1_closure_digest must be a 64-character SHA-256 hex string")
    else:
        expected_digest = digest_jsonable(data, digest_key="r1_closure_digest")
        if digest != expected_digest:
            errors.append(f"r1_closure_digest drift detected: expected {expected_digest}, got {digest}")

    return errors


def validate_r1_closure_evidence_chain(data: dict[str, Any], base_dir: Path) -> list[str]:
    errors = validate_r1_closure_report_artifact(data)
    if errors:
        return errors

    evidence_mappings = (
        ("config_schema_status", CONFIG_SCHEMA_KIND, "digest", validate_config_schema_artifact),
        ("config_resolution_status", CONFIG_SOURCE_RESOLUTION_KIND, "digest", validate_config_resolution_artifact),
        ("setup_plan_status", SETUP_PLAN_KIND, "plan_digest", validate_setup_plan_artifact),
        ("overlay_plan_status", SETUP_OVERLAY_PLAN_KIND, "overlay_plan_digest", validate_setup_overlay_plan_artifact),
        (
            "rollback_snapshot_status",
            SETUP_ROLLBACK_SNAPSHOT_KIND,
            "snapshot_digest",
            validate_setup_rollback_snapshot_artifact,
        ),
        (
            "onboarding_intent_status",
            ONBOARDING_INTENT_KIND,
            "onboarding_intent_digest",
            validate_onboarding_intent_report_artifact,
        ),
    )

    for field, expected_kind, digest_key, validator_func in evidence_mappings:
        status = data.get(field, {})
        if not isinstance(status, dict):
            continue
        path_str = status.get("path")
        if not isinstance(path_str, str) or not path_str:
            errors.append(f"{field}: missing path in status")
            continue

        candidate_paths = [
            Path(path_str),
            base_dir / Path(path_str).name,
            base_dir / path_str,
        ]
        target_path: Path | None = None
        for candidate in candidate_paths:
            if candidate.exists() and candidate.is_file():
                target_path = candidate
                break

        if target_path is None:
            errors.append(f"{field}: evidence file missing on disk: {path_str}")
            continue

        try:
            loaded_data = json_lib.loads(target_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{field}: malformed JSON in evidence file {target_path}: {e}")
            continue

        if loaded_data.get("kind") != expected_kind:
            errors.append(
                f"{field} artifact ({target_path.name}): expected kind '{expected_kind}', got '{loaded_data.get('kind')}'"
            )
        art_errors = validator_func(loaded_data)
        if art_errors:
            errors.extend(f"{field} artifact ({target_path.name}): {err}" for err in art_errors)
        else:
            status_digest = status.get("digest")
            if not isinstance(status_digest, str) or not status_digest:
                errors.append(f"{field}: digest missing in status")
                continue

            actual_digest = loaded_data.get(digest_key)
            if not actual_digest and field == "rollback_snapshot_status":
                actual_digest = loaded_data.get("snapshot_id")

            if not actual_digest:
                errors.append(f"{field}: digest missing in evidence artifact payload")
                continue

            if field == "rollback_snapshot_status":
                snapshot_id = loaded_data.get("snapshot_id")
                snapshot_digest = loaded_data.get("snapshot_digest")
                if status_digest not in (snapshot_id, snapshot_digest):
                    errors.append(
                        f"{field}: digest mismatch for {target_path.name} (status has {status_digest}, file has snapshot_id={snapshot_id}, snapshot_digest={snapshot_digest})"
                    )
            else:
                if status_digest != actual_digest:
                    errors.append(
                        f"{field}: digest mismatch for {target_path.name} (status has {status_digest}, file has {actual_digest})"
                    )

    return errors


def validate_r1_closure_report_file(path: Path, check_evidence_chain: bool = True) -> list[str]:
    if not path.exists():
        return [f"report file does not exist: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"malformed JSON in report file: {e}"]
    if check_evidence_chain:
        return validate_r1_closure_evidence_chain(data, base_dir=path.parent)
    return validate_r1_closure_report_artifact(data)
