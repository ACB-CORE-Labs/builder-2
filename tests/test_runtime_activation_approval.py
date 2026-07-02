from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.goose_projection import create_goose_projection
from builder_ii.goose_wrapper_plan import create_goose_wrapper_plan
from builder_ii.runtime_activation_approval import (
    RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
    create_runtime_activation_approval_spec,
    dumps_runtime_activation_approval_spec,
    validate_runtime_activation_approval_spec,
    validate_runtime_activation_approval_spec_file,
)
from builder_ii.session_config import create_session_configuration


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def _wrapper_plan(tmp_path: Path) -> dict:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(
        settings, "generic", repo_path=str(repo), task="prepare approval boundary", generic_repo=repo
    )
    projection = create_goose_projection(settings, config)
    return create_goose_wrapper_plan(projection)


def test_create_runtime_activation_approval_spec(tmp_path: Path) -> None:
    wrapper_plan = _wrapper_plan(tmp_path)
    spec = create_runtime_activation_approval_spec(wrapper_plan, requested_by="operator")

    assert spec["kind"] == RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND
    assert spec["approval_state"] == "PROPOSED_ONLY"
    assert spec["target"] == "generic"
    assert spec["approval_boundary"]["runtime_activation"] == "NOT_AUTHORIZED"
    assert spec["approval_boundary"]["model_execution"] == "NOT_AUTHORIZED"
    assert spec["approval_boundary"]["operator_approval_required"] is True
    assert spec["approval_boundary"]["approval_evidence_ref"] is None
    assert spec["operator_plan_summary"]["executes_now"] is False
    assert spec["operator_plan_summary"]["argv_preview"] == wrapper_plan["operator_launch"]["argv"]
    assert spec["governance"]["runtime_execution"] == "DISABLED"
    assert spec["governance"]["runtime_activation"] == "NOT_AUTHORIZED"
    assert spec["governance"]["model_execution"] == "DISABLED"
    assert spec["governance"]["artifact_is_authority"] is False
    assert validate_runtime_activation_approval_spec(spec) == []


def test_runtime_activation_approval_spec_rejects_approval_escalation(tmp_path: Path) -> None:
    spec = create_runtime_activation_approval_spec(_wrapper_plan(tmp_path))
    bad = copy.deepcopy(spec)
    bad["approval_state"] = "APPROVED_BY_OPERATOR"
    bad["approval_boundary"]["runtime_activation"] = "AUTHORIZED"
    bad["approval_boundary"]["approval_evidence_ref"] = "evidence.txt"
    bad["operator_plan_summary"]["executes_now"] = True
    bad["governance"]["runtime_execution"] = "ENABLED"

    errors = validate_runtime_activation_approval_spec(bad)

    assert "approval_state must be PROPOSED_ONLY" in errors
    assert "approval_boundary.runtime_activation must be NOT_AUTHORIZED" in errors
    assert "approval_boundary.approval_evidence_ref must be null" in errors
    assert "operator_plan_summary.executes_now must be false" in errors
    assert "governance.runtime_execution must be DISABLED" in errors


def test_runtime_activation_approval_spec_file_validation(tmp_path: Path) -> None:
    spec = create_runtime_activation_approval_spec(_wrapper_plan(tmp_path))
    output = tmp_path / "runtime-activation-approval-spec.json"
    output.write_text(dumps_runtime_activation_approval_spec(spec), encoding="utf-8")

    assert validate_runtime_activation_approval_spec_file(output) == []
    assert any(
        "file not found" in error for error in validate_runtime_activation_approval_spec_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_runtime_activation_approval_spec_file(bad_json))
