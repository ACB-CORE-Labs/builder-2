import json as json_lib
from pathlib import Path

from builder_ii.promotion_readiness_records import (
    create_promotion_readiness_record,
    dumps_promotion_readiness_record,
    validate_promotion_readiness_record,
    validate_promotion_readiness_record_file,
    write_promotion_readiness_record,
)


def _ready_record() -> dict:
    return create_promotion_readiness_record(
        capability_name="artifact_index",
        docs_refs=["docs/ARTIFACT_INDEX.md"],
        tests_refs=["tests/test_artifact_index_records.py"],
        cli_refs=["builder-index"],
        failure_mode_refs=["invalid artifacts are reported as incomplete"],
        approval_boundary_refs=["artifact_is_authority=false"],
        output_artifact_refs=["artifact-index.json"],
        rollback_refs=["delete artifact-index.json"],
        verification_refs=["uv run pytest -q"],
        notes="ready for promotion review",
    )


def test_create_ready_promotion_readiness_shape() -> None:
    record = _ready_record()

    assert record["kind"] == "builder_ii.promotion_readiness_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["capability_state"] == "promotion_readiness_record"
    assert record["capability_name"] == "artifact_index"
    assert record["target_state"] == "enabled"
    assert record["status"] == "ready"
    assert record["ready"] is True
    assert record["missing"] == []
    assert len(record["checks"]) == 8
    assert all(check["ready"] is True for check in record["checks"])
    assert all(isinstance(check["refs"], list) for check in record["checks"])
    assert all(isinstance(check["missing"], list) for check in record["checks"])
    assert all(check["missing"] == [] for check in record["checks"])
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"] == {
        "capability_state": "promotion_readiness_record",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "source_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "artifact_is_authority": False,
        "core_workbench_coupling": "NONE",
    }
    assert validate_promotion_readiness_record(record) == []


def test_create_blocked_promotion_readiness_shape() -> None:
    record = create_promotion_readiness_record(capability_name="artifact_index", docs_refs=["docs/ARTIFACT_INDEX.md"])

    assert record["status"] == "blocked"
    assert record["ready"] is False
    assert "tests refs are required" in record["missing"]
    assert "cli_surface refs are required" in record["missing"]
    assert validate_promotion_readiness_record(record) == []


def test_promotion_readiness_json_round_trip() -> None:
    data = json_lib.loads(dumps_promotion_readiness_record(_ready_record()))

    assert data["ready"] is True
    assert validate_promotion_readiness_record(data) == []


def test_promotion_readiness_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "promotion-readiness.json"
    record = _ready_record()
    write_promotion_readiness_record(record, path)

    assert path.exists()
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.promotion_readiness_record"
    assert validate_promotion_readiness_record(data) == []


def test_validate_rejects_authority_changes() -> None:
    record = _ready_record()
    record["record_state"] = "ACTIVE"
    record["current_state"] = "ENABLED"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["promote"]
    record["governance"]["runtime_execution"] = "ENABLED"
    record["governance"]["model_execution"] = "ENABLED"
    record["governance"]["source_writes"] = "ENABLED"
    record["governance"]["memory_mutation"] = "ENABLED"
    record["governance"]["artifact_is_authority"] = True
    record["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_promotion_readiness_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "current_state must be DISABLED" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.model_execution must be DISABLED" in errors
    assert "governance.source_writes must be DISABLED" in errors
    assert "governance.memory_mutation must be DISABLED" in errors
    assert "governance.artifact_is_authority must be false" in errors
    assert "governance.core_workbench_coupling must be NONE" in errors


def test_validate_rejects_capability_state_drift() -> None:
    record = _ready_record()
    record["capability_state"] = "active_capability"

    errors = validate_promotion_readiness_record(record)

    assert "capability_state must be promotion_readiness_record" in errors


def test_validate_rejects_missing_target_state() -> None:
    record = _ready_record()
    record["target_state"] = ""

    errors = validate_promotion_readiness_record(record)

    assert "target_state is required" in errors


def test_validate_rejects_status_ready_mismatch() -> None:
    record = _ready_record()
    record["status"] = "blocked"
    # ready is True but status says blocked

    errors = validate_promotion_readiness_record(record)

    assert "ready must match status" in errors


def test_validate_rejects_ready_non_boolean() -> None:
    record = _ready_record()
    record["ready"] = "yes"

    errors = validate_promotion_readiness_record(record)

    assert "ready must be a boolean" in errors


def test_validate_rejects_check_shape_drift() -> None:
    record = _ready_record()
    # Corrupt a check to have wrong types
    record["checks"][0] = {
        "name": "",
        "refs": "not-a-list",
        "ready": "yes",
        "missing": "not-a-list",
    }

    errors = validate_promotion_readiness_record(record)

    assert "checks[0].name must be a non-empty string" in errors
    assert "checks[0].refs must be a list" in errors
    assert "checks[0].ready must be a boolean" in errors
    assert "checks[0].missing must be a list" in errors


def test_validate_rejects_non_object_check() -> None:
    record = _ready_record()
    record["checks"][0] = "not-a-dict"

    errors = validate_promotion_readiness_record(record)

    assert "checks[0] must be an object" in errors


def test_validate_rejects_check_ready_refs_inconsistency() -> None:
    record = _ready_record()
    # ready=True but refs=[] is inconsistent
    record["checks"][0] = {
        "name": "docs",
        "refs": [],
        "ready": True,
        "missing": [],
    }

    errors = validate_promotion_readiness_record(record)

    assert "checks[0].ready must match whether refs is non-empty" in errors
    assert "checks[0] must have missing items when refs are empty" in errors


def test_validate_rejects_check_with_refs_and_missing() -> None:
    record = _ready_record()
    # Has refs but also has missing items — inconsistent
    record["checks"][0] = {
        "name": "docs",
        "refs": ["docs/ARTIFACT_INDEX.md"],
        "ready": True,
        "missing": ["docs refs are required"],
    }

    errors = validate_promotion_readiness_record(record)

    assert "checks[0] must not have missing items when refs are present" in errors


def test_validate_rejects_aggregate_missing_drift() -> None:
    record = _ready_record()
    # Make a check blocked but remove the missing entry from top-level missing
    record["checks"][1] = {
        "name": "tests",
        "refs": [],
        "ready": False,
        "missing": ["tests refs are required"],
    }
    # Top-level missing is still [] but should contain "tests refs are required"
    record["missing"] = []
    record["status"] = "blocked"
    record["ready"] = False

    errors = validate_promotion_readiness_record(record)

    assert "missing must include check-level item: tests refs are required" in errors


def test_validate_rejects_missing_required_check() -> None:
    record = _ready_record()
    # Remove one required check
    record["checks"] = [check for check in record["checks"] if check["name"] != "docs"]

    errors = validate_promotion_readiness_record(record)

    assert "missing check: docs" in errors


def test_validate_rejects_checks_not_list() -> None:
    record = _ready_record()
    record["checks"] = "not-a-list"

    errors = validate_promotion_readiness_record(record)

    assert "checks must be a list" in errors


def test_validate_rejects_non_object_governance() -> None:
    record = _ready_record()
    record["governance"] = []

    errors = validate_promotion_readiness_record(record)

    assert "governance must be an object" in errors


def test_validate_rejects_non_object() -> None:
    assert "promotion readiness record must be a JSON object" in validate_promotion_readiness_record([])


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any(
        "file not found" in error for error in validate_promotion_readiness_record_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_promotion_readiness_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "promotion readiness record must be a JSON object" in validate_promotion_readiness_record_file(not_object)


def test_validate_file_valid(tmp_path: Path) -> None:
    path = tmp_path / "readiness.json"
    write_promotion_readiness_record(_ready_record(), path)

    assert validate_promotion_readiness_record_file(path) == []


def test_blocked_record_has_consistent_missing() -> None:
    """A blocked record's top-level missing must contain all check-level missing items."""
    record = create_promotion_readiness_record(
        capability_name="artifact_index",
        docs_refs=["docs/ARTIFACT_INDEX.md"],
        # All others missing
    )

    assert record["status"] == "blocked"
    assert record["ready"] is False
    # Check that missing contains check-level items
    for check in record["checks"]:
        for item in check["missing"]:
            assert item in record["missing"]
    assert validate_promotion_readiness_record(record) == []


def test_empty_capability_name_produces_blocked_record() -> None:
    record = create_promotion_readiness_record(
        capability_name="",
        docs_refs=["docs/ARTIFACT_INDEX.md"],
        tests_refs=["tests/test.py"],
        cli_refs=["builder-index"],
        failure_mode_refs=["incomplete"],
        approval_boundary_refs=["false"],
        output_artifact_refs=["out.json"],
        rollback_refs=["delete"],
        verification_refs=["pytest"],
    )

    assert record["status"] == "blocked"
    assert record["ready"] is False
    assert "capability_name is required" in record["missing"]
    # Validator catches it too
    assert "capability_name is required" in validate_promotion_readiness_record(record)
