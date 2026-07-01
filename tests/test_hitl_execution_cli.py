from __future__ import annotations

import inspect
import json as json_lib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import builder_ii.hitl_execution_cli as cli_mod
from builder_ii.hitl_execution_cli import hitl_app
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
)


def test_module_does_not_import_subprocess() -> None:
    """The module must never import or reference subprocess."""
    src = inspect.getsource(cli_mod)
    assert "import subprocess" not in src
    assert "from subprocess" not in src
    assert "subprocess." not in src


def test_cli_does_not_expose_forbidden_commands() -> None:
    """The CLI must not expose arbitrary execute, run, or shell commands."""
    forbidden = {"execute", "run", "shell"}
    for cmd in hitl_app.registered_commands:
        assert cmd.name not in forbidden, f"Forbidden command '{cmd.name}' is exposed!"


def test_docs_deny_execution_and_authority() -> None:
    """The documentation must state that the CLI only creates governance artifacts and does not execute or grant authority."""
    doc_path = Path(__file__).parent.parent / "docs" / "HITL_EXECUTION_CLI.md"
    assert doc_path.exists(), f"Missing docs file: {doc_path}"
    doc_text = doc_path.read_text(encoding="utf-8")

    assert "creates governance artifacts only" in doc_text.lower()
    assert "does not execute commands" in doc_text.lower()
    assert "does not grant authority" in doc_text.lower()
    assert "not permission to execute" in doc_text.lower()
    assert "not evidence that execution occurred" in doc_text.lower()
    assert "builder-ii is a generic governed local agent/developer platform" in doc_text.lower()
    assert "builder-ii is not core" in doc_text.lower()
    assert "not a second core runtime" in doc_text.lower()
    assert "core is only a target profile" in doc_text.lower()


def test_request_writes_valid_artifact_and_validates(tmp_path: Path) -> None:
    """The request command must write a valid request artifact, and validation should succeed on it."""
    output_dir = tmp_path / "deep" / "nested" / "path"
    output_file = output_dir / "request.json"

    # Run CLI command to create request
    result = CliRunner().invoke(
        hitl_app,
        [
            "request",
            "--target-name", "generic",
            "--command-proposal-ref", "proposal-001",
            "--approval-record-ref", "approval-001",
            "--preflight-record-ref", "preflight-001",
            "--requested-by", "operator",
            "--requested-at", "2026-06-27T00:00:00Z",
            "--explicit-operator-intent", "intent-001",
            "--command-preview", "ls -la",
            "--output", str(output_file),
        ],
    )

    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    assert output_file.exists(), "Output file was not written"
    
    # Read output and verify contents
    data = json_lib.loads(output_file.read_text(encoding="utf-8"))
    assert data["kind"] == HITL_EXECUTION_REQUEST_KIND
    assert data["command_proposal_ref"] == "proposal-001"
    assert data["current_state"] == "REQUEST_RECORDED_ONLY"

    # Validate via CLI
    val_result = CliRunner().invoke(hitl_app, ["validate", str(output_file)])
    assert val_result.exit_code == 0, f"Validation failed: {val_result.stdout}"
    assert "Artifact is valid" in val_result.stdout


def test_receipt_writes_valid_artifact_and_validates(tmp_path: Path) -> None:
    """The receipt command must write a valid NOT_EXECUTED receipt, and validation should succeed on it."""
    output_dir = tmp_path / "deep" / "nested" / "path"
    output_file = output_dir / "receipt.json"

    # Run CLI command to create receipt
    result = CliRunner().invoke(
        hitl_app,
        [
            "receipt",
            "--target-name", "generic",
            "--request-ref", "request-001",
            "--output", str(output_file),
        ],
    )

    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"
    assert output_file.exists(), "Output file was not written"

    # Read output and verify contents
    data = json_lib.loads(output_file.read_text(encoding="utf-8"))
    assert data["kind"] == HITL_EXECUTION_RECEIPT_KIND
    assert data["request_ref"] == "request-001"
    assert data["execution_state"] == "NOT_EXECUTED"

    # Validate via CLI
    val_result = CliRunner().invoke(hitl_app, ["validate", str(output_file)])
    assert val_result.exit_code == 0, f"Validation failed: {val_result.stdout}"
    assert "Artifact is valid" in val_result.stdout


def test_validate_fails_on_unknown_kind(tmp_path: Path) -> None:
    """Validation must fail on an unknown kind of artifact."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(
        json_lib.dumps({"kind": "builder_ii.some_unknown_kind", "schema_version": 1}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(hitl_app, ["validate", str(bad_file)])
    assert result.exit_code != 0
    assert "unknown or unsupported artifact kind" in result.stdout


def test_invalid_request_fields_fail_closed(tmp_path: Path) -> None:
    """If required fields are missing/invalid, creation/validation must fail and no output file should be written."""
    output_file = tmp_path / "not-written.json"

    # Run CLI command with empty/invalid command-proposal-ref
    result = CliRunner().invoke(
        hitl_app,
        [
            "request",
            "--target-name", "generic",
            "--command-proposal-ref", "",  # Empty proposal ref is invalid
            "--approval-record-ref", "approval-001",
            "--preflight-record-ref", "preflight-001",
            "--requested-by", "operator",
            "--requested-at", "2026-06-27T00:00:00Z",
            "--explicit-operator-intent", "intent-001",
            "--command-preview", "ls -la",
            "--output", str(output_file),
        ],
    )

    assert result.exit_code != 0
    assert not output_file.exists(), "File should not be written for invalid inputs"
    assert "Validation error: command_proposal_ref is required" in result.stdout


def test_validate_nonexistent_file() -> None:
    """Validating a nonexistent path must fail."""
    result = CliRunner().invoke(hitl_app, ["validate", "nonexistent.json"])
    assert result.exit_code != 0
    assert "file not found" in result.stdout


def test_validate_invalid_json(tmp_path: Path) -> None:
    """Validating an invalid JSON file must fail."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{invalid", encoding="utf-8")

    result = CliRunner().invoke(hitl_app, ["validate", str(bad_file)])
    assert result.exit_code != 0
    assert "invalid JSON" in result.stdout


def test_validate_non_dict_json(tmp_path: Path) -> None:
    """Validating a JSON list or other non-dict must fail."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("[1, 2, 3]", encoding="utf-8")

    result = CliRunner().invoke(hitl_app, ["validate", str(bad_file)])
    assert result.exit_code != 0
    assert "artifact must be a JSON object" in result.stdout
