from __future__ import annotations

import inspect
import json
from pathlib import Path

import builder_ii.lifecycle.candidate.rollback_artifacts as rollback_mod
from builder_ii.lifecycle.candidate.rollback_artifacts import (
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    create_rollback_plan,
    create_rollback_receipt,
    dumps_rollback_plan,
    dumps_rollback_receipt,
    validate_rollback_plan,
    validate_rollback_plan_file,
    validate_rollback_receipt,
    validate_rollback_receipt_file,
    write_rollback_plan,
    write_rollback_receipt,
)


def test_valid_plan_validates() -> None:
    plan = create_rollback_plan(
        related_artifact_refs=["artifact-1"],
        rollback_strategy="restore previous artifact state",
        operator_note="operator reviewed rollback plan",
    )
    assert plan["kind"] == ROLLBACK_PLAN_KIND
    assert validate_rollback_plan(plan) == []


def test_valid_receipt_validates() -> None:
    receipt = create_rollback_receipt(rollback_plan_ref="rollback-plan-1")
    assert receipt["kind"] == ROLLBACK_RECEIPT_KIND
    assert validate_rollback_receipt(receipt) == []


def test_plan_fails_with_empty_related_artifact_refs() -> None:
    plan = create_rollback_plan(related_artifact_refs=[], rollback_strategy="restore")
    assert "related_artifact_refs must be a non-empty list of non-empty strings" in validate_rollback_plan(plan)


def test_plan_fails_with_empty_rollback_strategy() -> None:
    plan = create_rollback_plan(related_artifact_refs=["artifact-1"], rollback_strategy="")
    assert "rollback_strategy must be a non-empty string" in validate_rollback_plan(plan)


def test_receipt_fails_with_empty_rollback_plan_ref() -> None:
    receipt = create_rollback_receipt(rollback_plan_ref="")
    assert "rollback_plan_ref must be a non-empty string" in validate_rollback_receipt(receipt)


def test_receipt_fails_if_rollback_state_not_not_executed() -> None:
    receipt = create_rollback_receipt(rollback_plan_ref="rollback-plan-1")
    receipt["rollback_state"] = "EXECUTED"
    assert "rollback_state must be NOT_EXECUTED" in validate_rollback_receipt(receipt)


def test_plan_and_receipt_reject_performed_actions() -> None:
    plan = create_rollback_plan(related_artifact_refs=["artifact-1"], rollback_strategy="restore")
    plan["performed_actions"] = ["rollback"]
    assert "performed_actions must be empty" in validate_rollback_plan(plan)

    receipt = create_rollback_receipt(rollback_plan_ref="rollback-plan-1")
    receipt["performed_actions"] = ["rollback"]
    assert "performed_actions must be empty" in validate_rollback_receipt(receipt)


def test_plan_governance_enabled_fields_fail() -> None:
    for key in (
        "runtime_execution",
        "shell_execution",
        "model_execution",
        "source_writes",
        "git_mutation",
        "network_access",
        "goose_runtime_activation",
        "deepagents_runtime",
    ):
        plan = create_rollback_plan(related_artifact_refs=["artifact-1"], rollback_strategy="restore")
        plan["governance"][key] = "ENABLED"
        assert f"governance.{key} must be DISABLED or NOT_AUTHORIZED" in validate_rollback_plan(plan)


def test_receipt_governance_enabled_fields_fail() -> None:
    for key in (
        "runtime_execution",
        "shell_execution",
        "model_execution",
        "source_writes",
        "git_mutation",
        "network_access",
        "goose_runtime_activation",
        "deepagents_runtime",
    ):
        receipt = create_rollback_receipt(rollback_plan_ref="rollback-plan-1")
        receipt["governance"][key] = "ENABLED"
        assert f"governance.{key} must be DISABLED or NOT_AUTHORIZED" in validate_rollback_receipt(receipt)


def test_artifact_authority_and_workbench_coupling_fail() -> None:
    plan = create_rollback_plan(related_artifact_refs=["artifact-1"], rollback_strategy="restore")
    plan["artifact_is_authority"] = True
    assert "artifact_is_authority must be false or NOT_AUTHORIZED" in validate_rollback_plan(plan)

    receipt = create_rollback_receipt(rollback_plan_ref="rollback-plan-1")
    receipt["governance"]["core_workbench_coupling"] = "COUPLED"
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in validate_rollback_receipt(receipt)


def test_file_round_trips(tmp_path: Path) -> None:
    plan = create_rollback_plan(related_artifact_refs=["artifact-1"], rollback_strategy="restore")
    plan_path = tmp_path / "nested" / "rollback-plan.json"
    write_rollback_plan(plan, plan_path)
    assert validate_rollback_plan_file(plan_path) == []

    receipt = create_rollback_receipt(rollback_plan_ref="rollback-plan-1")
    receipt_path = tmp_path / "nested" / "rollback-receipt.json"
    write_rollback_receipt(receipt, receipt_path)
    assert validate_rollback_receipt_file(receipt_path) == []


def test_file_validation_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert any("file not found" in err for err in validate_rollback_plan_file(missing))
    assert any("file not found" in err for err in validate_rollback_receipt_file(missing))

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not-json", encoding="utf-8")
    assert any("invalid JSON" in err for err in validate_rollback_plan_file(invalid))
    assert any("invalid JSON" in err for err in validate_rollback_receipt_file(invalid))


def test_dumps_include_trailing_newline_and_valid_json() -> None:
    plan_text = dumps_rollback_plan(
        create_rollback_plan(related_artifact_refs=["artifact-1"], rollback_strategy="restore")
    )
    receipt_text = dumps_rollback_receipt(create_rollback_receipt(rollback_plan_ref="rollback-plan-1"))

    assert plan_text.endswith("\n")
    assert receipt_text.endswith("\n")
    assert json.loads(plan_text)["kind"] == ROLLBACK_PLAN_KIND
    assert json.loads(receipt_text)["kind"] == ROLLBACK_RECEIPT_KIND


def test_non_dict_validation_errors() -> None:
    assert validate_rollback_plan(None) == ["rollback plan artifact must be a JSON object"]
    assert validate_rollback_receipt(None) == ["rollback receipt artifact must be a JSON object"]


def test_docs_state_governance_boundaries() -> None:
    doc = (Path(__file__).parent.parent / "docs" / "ROLLBACK_ARTIFACTS.md").read_text(encoding="utf-8")
    lower_doc = doc.lower()

    assert "builder-II is a generic governed local agent/developer platform." in doc
    assert "It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime." in doc
    assert "CORE is only a target profile." in doc
    assert "governance records only" in lower_doc
    assert "shell_execution" in doc
    assert "git_mutation" in doc
    assert "goose_runtime_activation" in doc
    assert "deepagents_runtime" in doc
    assert "core_workbench_coupling" in doc
    assert "execute rollback" in lower_doc
    assert "does not grant authority" in lower_doc


def test_module_does_not_import_or_call_subprocess() -> None:
    source = inspect.getsource(rollback_mod)
    forbidden = [
        "import subprocess",
        "from subprocess",
    ]
    for item in forbidden:
        assert item not in source, f"Found forbidden import: {item}"
