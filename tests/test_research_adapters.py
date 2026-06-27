import hashlib
import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.artifact_index_records import create_artifact_index_record, validate_artifact_index_record
from builder_ii.research_adapters import (
    RESEARCH_ADAPTER_KIND,
    RESEARCH_ADAPTER_SCHEMA_VERSION,
    create_research_adapter_artifact,
    dumps_research_adapter_artifact,
    validate_research_adapter_artifact,
    validate_research_adapter_artifact_file,
    write_research_adapter_artifact,
)
from builder_ii.research_cli import research_app
from builder_ii.research_plans import create_research_plan_artifact, dumps_research_plan_artifact


def _digest(value: dict) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _plan() -> dict:
    return create_research_plan_artifact(
        target="builder",
        profile_name="research_planner",
        task="plan source review",
        topic="adapter test",
    )


def _adapter() -> dict:
    plan = _plan()
    return create_research_adapter_artifact(
        target="builder",
        topic="adapter test",
        research_question="What sources would need review?",
        plan_path="missing-plan.json",
        plan_sha256=_digest(plan),
        output_contract=["review-only adapter"],
        review_notes=["operator supplied digest"],
    )


def test_create_research_adapter_artifact_shape() -> None:
    artifact = _adapter()

    assert artifact["kind"] == RESEARCH_ADAPTER_KIND
    assert artifact["schema_version"] == RESEARCH_ADAPTER_SCHEMA_VERSION
    assert artifact["target"] == "builder"
    assert artifact["research_plan"]["path"] == "missing-plan.json"
    assert artifact["adapter_relation"] == "REFERENCE_ONLY"
    assert artifact["handoff_state"] == "NOT_INVOKED"
    assert artifact["performed_actions"] == []
    assert artifact["governance"]["runtime_execution"] == "DISABLED"
    assert artifact["governance"]["search_execution"] == "DISABLED"
    assert artifact["governance"]["source_collection"] == "DISABLED"
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_research_adapter_artifact(artifact) == []


def test_research_adapter_json_and_file_round_trip(tmp_path: Path) -> None:
    data = json_lib.loads(dumps_research_adapter_artifact(_adapter()))
    assert validate_research_adapter_artifact(data) == []

    output = tmp_path / "adapter.json"
    write_research_adapter_artifact(data, output)
    assert validate_research_adapter_artifact_file(output) == []


def test_validate_research_adapter_rejects_authority_changes() -> None:
    artifact = _adapter()
    artifact["adapter_relation"] = "EXECUTE"
    artifact["handoff_state"] = "INVOKED"
    artifact["performed_actions"] = ["invoke"]
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["model_execution"] = "ENABLED"
    artifact["governance"]["search_execution"] = "ENABLED"
    artifact["governance"]["source_collection"] = "ENABLED"
    artifact["governance"]["artifact_is_authority"] = True
    artifact["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_research_adapter_artifact(artifact)

    assert "adapter_relation must be REFERENCE_ONLY" in errors
    assert "handoff_state must be NOT_INVOKED" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.model_execution must be DISABLED" in errors
    assert "governance.search_execution must be DISABLED" in errors
    assert "governance.source_collection must be DISABLED" in errors
    assert "governance.artifact_is_authority must be false" in errors
    assert "governance.core_workbench_coupling must be NONE" in errors


def test_validate_research_adapter_does_not_require_plan_file_to_exist(tmp_path: Path) -> None:
    artifact = create_research_adapter_artifact(
        target="generic",
        topic="explicit reference",
        research_question="What would need review?",
        plan_path=tmp_path / "does-not-exist.json",
        plan_sha256="abc123",
    )

    assert validate_research_adapter_artifact(artifact) == []


def test_cli_adapter_stdout_and_validate(tmp_path: Path) -> None:
    runner = CliRunner()
    plan = _plan()
    result = runner.invoke(
        research_app,
        [
            "adapter",
            "--target",
            "builder",
            "--topic",
            "adapter test",
            "--research-question",
            "What sources would need review?",
            "--plan-path",
            "missing-plan.json",
            "--plan-sha256",
            _digest(plan),
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == RESEARCH_ADAPTER_KIND
    assert data["handoff_state"] == "NOT_INVOKED"

    output = tmp_path / "adapter.json"
    file_result = runner.invoke(
        research_app,
        [
            "adapter",
            "--target",
            "builder",
            "--topic",
            "adapter test",
            "--research-question",
            "What sources would need review?",
            "--plan-path",
            "missing-plan.json",
            "--plan-sha256",
            _digest(plan),
            "--output",
            str(output),
        ],
    )
    assert file_result.exit_code == 0
    assert output.exists()

    validate_result = runner.invoke(research_app, ["validate-adapter", str(output)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_artifact_index_recognizes_research_adapter(tmp_path: Path) -> None:
    write_research_adapter_artifact(_adapter(), tmp_path / "adapter.json")
    record = create_artifact_index_record(tmp_path)

    assert record["counts"] == {"total": 1, "known": 1, "unknown": 0, "valid": 1, "invalid": 0}
    assert record["artifacts"][0]["kind"] == RESEARCH_ADAPTER_KIND
    assert validate_artifact_index_record(record) == []


def test_research_plan_digest_fixture_is_stable_shape() -> None:
    plan_json = json_lib.loads(dumps_research_plan_artifact(_plan()))
    assert plan_json["kind"] == "builder_ii.research_plan"
    assert _digest(plan_json)
