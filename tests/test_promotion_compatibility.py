from typer.testing import CliRunner

from builder_ii.agent_profiles import AGENT_PROFILE_RECORD_KIND
from builder_ii.context_pack import CONTEXT_PACK_RECORD_KIND
from builder_ii.git_state import GIT_STATE_RECORD_KIND
from builder_ii.promotion_compatibility import create_support_artifact_ref
from builder_ii.promotion_decision_records import create_promotion_decision_record, validate_promotion_decision_record
from builder_ii.promotion_readiness_cli import promotion_app
from builder_ii.promotion_readiness_records import create_promotion_readiness_record, validate_promotion_readiness_record
from builder_ii.target_profiles import TARGET_PROFILE_ARTIFACT_KIND
from builder_ii.verification_profiles import VERIFICATION_ARTIFACT_KIND


def _support_refs(target: str = "builder") -> list[dict]:
    records = [
        {"kind": TARGET_PROFILE_ARTIFACT_KIND, "name": target},
        {"kind": VERIFICATION_ARTIFACT_KIND, "target": target, "name": "builder_full"},
        {"kind": CONTEXT_PACK_RECORD_KIND, "target": target},
        {"kind": AGENT_PROFILE_RECORD_KIND, "target": target, "name": "patch_planner"},
        {"kind": GIT_STATE_RECORD_KIND, "target": target},
    ]
    return [create_support_artifact_ref(record, path=f"artifact-{index}.json") for index, record in enumerate(records)]


def _ready_kwargs() -> dict:
    return {
        "capability_name": "bounded_readonly_inspection",
        "target_state": "enabled",
        "docs_refs": ["docs/OPERATOR_PLAYBOOK.md"],
        "tests_refs": ["tests/test_promotion_compatibility.py"],
        "cli_refs": ["builder-promotion"],
        "failure_mode_refs": ["compatibility blockers are recorded"],
        "approval_boundary_refs": ["artifact_is_authority=false"],
        "output_artifact_refs": ["promotion-readiness.json"],
        "rollback_refs": ["discard promotion decision artifact"],
        "verification_refs": ["uv run pytest tests/test_promotion_compatibility.py -q"],
    }


def test_readiness_accepts_complete_target_compatible_support_set() -> None:
    record = create_promotion_readiness_record(target="builder", support_artifacts=_support_refs("builder"), **_ready_kwargs())

    assert record["target"] == "builder"
    assert record["status"] == "ready"
    assert record["ready"] is True
    assert record["support_artifacts"]
    assert validate_promotion_readiness_record(record) == []


def test_readiness_blocks_missing_support_artifact_kind() -> None:
    support = _support_refs("builder")[:-1]
    record = create_promotion_readiness_record(target="builder", support_artifacts=support, **_ready_kwargs())

    assert record["status"] == "blocked"
    assert record["ready"] is False
    assert any("missing support artifact kind" in item for item in record["missing"])
    assert validate_promotion_readiness_record(record) == []


def test_readiness_rejects_support_artifact_target_mismatch() -> None:
    support = _support_refs("builder")
    support[2]["target"] = "core"
    record = create_promotion_readiness_record(target="builder", support_artifacts=support, **_ready_kwargs())

    assert record["status"] == "blocked"
    assert any("target must match readiness target builder" in item for item in record["missing"])
    assert validate_promotion_readiness_record(record) == []


def test_validation_rejects_ready_with_incompatible_support_artifacts() -> None:
    record = create_promotion_readiness_record(target="builder", support_artifacts=_support_refs("builder")[:-1], **_ready_kwargs())
    record["status"] = "ready"
    record["ready"] = True
    record["missing"] = []

    errors = validate_promotion_readiness_record(record)

    assert "ready must be false when support_artifacts are incompatible" in errors
    assert any("missing must include compatibility item" in error for error in errors)


def test_promotion_decision_carries_support_artifact_metadata() -> None:
    readiness = create_promotion_readiness_record(target="builder", support_artifacts=_support_refs("builder"), **_ready_kwargs())
    decision = create_promotion_decision_record(readiness, readiness_path="readiness.json", decision="approved", decided_by="operator")

    assert decision["approved"] is True
    assert decision["readiness"]["target"] == "builder"
    assert decision["readiness"]["support_artifact_count"] == 5
    assert GIT_STATE_RECORD_KIND in decision["readiness"]["support_artifact_kinds"]
    assert validate_promotion_decision_record(decision) == []


def test_promotion_cli_accepts_explicit_support_artifact_refs() -> None:
    support_args: list[str] = []
    for ref in _support_refs("builder"):
        support_args.extend(["--support-artifact", f"{ref['kind']},{ref['path']},{ref['sha256']},{ref['target']},{ref['name']}"])

    result = CliRunner().invoke(
        promotion_app,
        [
            "record",
            "--capability-name",
            "bounded_readonly_inspection",
            "--target",
            "builder",
            "--docs-ref",
            "docs/OPERATOR_PLAYBOOK.md",
            "--tests-ref",
            "tests/test_promotion_compatibility.py",
            "--cli-ref",
            "builder-promotion",
            "--failure-mode-ref",
            "compatibility blockers are recorded",
            "--approval-boundary-ref",
            "artifact_is_authority=false",
            "--output-artifact-ref",
            "promotion-readiness.json",
            "--rollback-ref",
            "discard promotion decision artifact",
            "--verification-ref",
            "uv run pytest tests/test_promotion_compatibility.py -q",
            *support_args,
        ],
    )

    assert result.exit_code == 0
    assert '"target": "builder"' in result.stdout
    assert '"support_artifacts"' in result.stdout
