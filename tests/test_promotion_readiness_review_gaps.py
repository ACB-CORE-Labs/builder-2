from builder_ii.promotion_readiness_records import create_promotion_readiness_record, validate_promotion_readiness_record


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
    )


def test_validate_rejects_check_list_item_shape() -> None:
    record = _ready_record()
    record["checks"][0]["refs"] = ["", 7]
    record["checks"][1]["refs"] = []
    record["checks"][1]["ready"] = False
    record["checks"][1]["missing"] = ["", 7]

    errors = validate_promotion_readiness_record(record)

    assert "checks[0].refs must be a list of non-empty strings" in errors
    assert "checks[1].missing must be a list of non-empty strings" in errors


def test_validate_rejects_top_level_string_shape() -> None:
    record = _ready_record()
    record["capability_name"] = []
    record["target_state"] = {}
    record["missing"] = [""]

    errors = validate_promotion_readiness_record(record)

    assert "capability_name is required" in errors
    assert "target_state is required" in errors
    assert "missing must be a list of non-empty strings" in errors


def test_validate_rejects_governance_capability_state_drift() -> None:
    record = _ready_record()
    record["governance"]["capability_state"] = "wrong"

    errors = validate_promotion_readiness_record(record)

    assert "governance.capability_state must be promotion_readiness_record" in errors
