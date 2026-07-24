import json as json_lib
from pathlib import Path

from builder_ii.session_cli import session_app
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    create_goose_readonly_session_plan,
    validate_goose_readonly_session_plan,
    validate_goose_readonly_session_plan_file,
)
from builder_ii.core.config import load_settings
from builder_ii.core.context_pack import (
    ContextPackSelection,
    build_context_pack,
    create_context_pack_record,
)

runner = CliRunner()


def test_create_goose_readonly_session_plan_defaults() -> None:
    settings = load_settings()

    # Generic defaults
    plan_generic = create_goose_readonly_session_plan(settings, "generic")
    assert plan_generic["kind"] == GOOSE_READONLY_SESSION_PLAN_KIND
    assert plan_generic["target_profile"]["name"] == "generic"
    assert plan_generic["selected_agent_profile"]["name"] == "repo_mapper"
    assert plan_generic["selected_prompt_profile"]["name"] == "generic_default"
    assert plan_generic["selected_verification_profile"]["name"] == "generic_basic"
    assert plan_generic["runtime_mode"] == "read_only"
    assert plan_generic["shell_execution"] == "DISABLED"
    assert plan_generic["autonomous_writes"] == "DISABLED"
    assert "inspect project config for test command" in plan_generic["goose_instructions"]
    assert "GOOSE GOVERNED READ-ONLY SESSION INSTRUCTIONS" in plan_generic["goose_instructions"]

    errors = validate_goose_readonly_session_plan(plan_generic)
    assert errors == []


def test_create_goose_readonly_session_plan_with_context(tmp_path: Path) -> None:
    settings = load_settings()
    selection = ContextPackSelection(task="test task", changed=False)

    # Build a mock context pack
    result = build_context_pack(
        settings,
        selection,
        target="generic",
        markdown_output=Path(".builder/context-pack.md"),
        repomix_output=Path(".builder/context-pack.xml"),
        run_repomix=False,
    )
    c_record = create_context_pack_record(result, task="test task")

    plan = create_goose_readonly_session_plan(
        settings,
        "generic",
        context_pack_record=c_record,
        task="run some audits",
    )
    assert plan["context_pack"] == c_record
    assert "Context Pack Details" in plan["goose_instructions"]
    assert "Selected/Default files to inspect:" in plan["goose_instructions"]

    errors = validate_goose_readonly_session_plan(plan)
    assert errors == []


def test_validation_gates() -> None:
    settings = load_settings()
    plan = create_goose_readonly_session_plan(settings, "builder")

    # Valid plan
    assert validate_goose_readonly_session_plan(plan) == []

    # Invalid kind
    bad_plan = plan.copy()
    bad_plan["kind"] = "builder_ii.invalid_kind"
    assert any("kind must be" in e for e in validate_goose_readonly_session_plan(bad_plan))

    # Invalid mode
    bad_mode = plan.copy()
    bad_mode["runtime_mode"] = "write"
    assert any("runtime_mode must be read_only" in e for e in validate_goose_readonly_session_plan(bad_mode))

    # Enabled execution
    bad_exec = plan.copy()
    bad_exec["shell_execution"] = "ENABLED"
    assert any(
        "shell_execution must be DISABLED or NOT_AUTHORIZED" in e
        for e in validate_goose_readonly_session_plan(bad_exec)
    )

    # Bad governance
    bad_gov = plan.copy()
    bad_gov["governance"] = plan["governance"].copy()
    bad_gov["governance"]["runtime_execution"] = "ENABLED"
    assert any(
        "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in e
        for e in validate_goose_readonly_session_plan(bad_gov)
    )


def test_validate_file_helpers(tmp_path: Path) -> None:
    settings = load_settings()
    plan = create_goose_readonly_session_plan(settings, "builder")

    # Write plan to file
    plan_file = tmp_path / "goose-readonly-plan.json"
    plan_file.write_text(json_lib.dumps(plan), encoding="utf-8")
    assert validate_goose_readonly_session_plan_file(plan_file) == []

    # Missing file
    assert any("file not found" in e for e in validate_goose_readonly_session_plan_file(tmp_path / "missing.json"))

    # Bad json
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("invalid json", encoding="utf-8")
    assert any("invalid JSON" in e for e in validate_goose_readonly_session_plan_file(bad_json_file))


def test_cli_goose_readonly_plan() -> None:
    result = runner.invoke(session_app, ["goose-readonly-plan", "generic"])
    assert result.exit_code == 0
    data = json_lib.loads(result.output)
    assert data["kind"] == GOOSE_READONLY_SESSION_PLAN_KIND
    assert data["target_profile"]["name"] == "generic"
    assert data["runtime_mode"] == "read_only"


def test_cli_goose_readonly_plan_output_and_validate(tmp_path: Path) -> None:
    output_file = tmp_path / "goose-plan.json"
    result = runner.invoke(
        session_app,
        [
            "goose-readonly-plan",
            "builder",
            "--agent",
            "repo_mapper",
            "--prompt",
            "builder_default",
            "--verification",
            "builder_fast",
            "--task",
            "verify code mapping",
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0
    assert "Goose read-only session plan written to" in result.output

    # Check file exists and has correct values
    data = json_lib.loads(output_file.read_text(encoding="utf-8"))
    assert data["target_profile"]["name"] == "builder"
    assert data["selected_agent_profile"]["name"] == "repo_mapper"
    assert data["selected_prompt_profile"]["name"] == "builder_default"
    assert data["selected_verification_profile"]["name"] == "builder_fast"
    assert data["task"] == "verify code mapping"

    # Validate file via CLI
    val_result = runner.invoke(session_app, ["validate-goose-readonly-plan", str(output_file)])
    assert val_result.exit_code == 0
    assert "is valid" in val_result.output


def test_cli_goose_readonly_plan_with_context_pack(tmp_path: Path) -> None:
    settings = load_settings()
    selection = ContextPackSelection(task="cli test task", changed=False)
    result_cp = build_context_pack(
        settings,
        selection,
        target="generic",
        markdown_output=Path(".builder/context-pack.md"),
        repomix_output=Path(".builder/context-pack.xml"),
        run_repomix=False,
    )
    c_record = create_context_pack_record(result_cp, task="cli test task")
    c_record_file = tmp_path / "context-pack-record.json"
    c_record_file.write_text(json_lib.dumps(c_record), encoding="utf-8")

    output_file = tmp_path / "goose-plan-context.json"
    result = runner.invoke(
        session_app,
        [
            "goose-readonly-plan",
            "generic",
            "--context-pack",
            str(c_record_file),
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0

    data = json_lib.loads(output_file.read_text(encoding="utf-8"))
    assert data["context_pack"] == c_record
    assert "Context Pack Details:" in data["goose_instructions"]
