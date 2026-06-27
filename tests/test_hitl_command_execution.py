import inspect
import json
import sys
from pathlib import Path

import pytest

import builder_ii.hitl_command_execution as hitl_mod
from builder_ii.hitl_command_execution import (
    HITL_COMMAND_EXECUTION_SPEC_KIND,
    create_hitl_command_execution_spec,
    dumps_hitl_command_execution_spec,
    validate_hitl_command_execution_spec,
    validate_hitl_command_execution_spec_file,
)


def test_valid_spec_validates() -> None:
    spec = create_hitl_command_execution_spec(task="test hitl design spec", reason="unit test")
    assert spec["kind"] == HITL_COMMAND_EXECUTION_SPEC_KIND
    assert validate_hitl_command_execution_spec(spec) == []


def test_runtime_shell_model_source_writes_disabled() -> None:
    spec = create_hitl_command_execution_spec()
    assert spec["current_state"]["runtime"] == "DISABLED"

    gov = spec["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["source_writes"] == "DISABLED"
    assert gov["git_mutation"] == "DISABLED"
    assert gov["commit_push"] == "DISABLED"
    assert gov["network_mcp_execution"] == "DISABLED"
    assert gov["goose_runtime_activation"] == "DISABLED"
    assert gov["deepagents_runtime"] == "DISABLED"
    assert gov["subprocess_execution"] == "DISABLED"

    denied = spec["denied_current_behavior"]
    assert "no subprocess" in denied
    assert "no shell execution" in denied
    assert "no command execution" in denied
    assert "no model execution" in denied
    assert "no source writes" in denied


def test_artifact_not_authority_and_coupling_none() -> None:
    spec = create_hitl_command_execution_spec()
    assert spec["governance"]["artifact_is_authority"] is False
    assert spec["governance"]["core_workbench_coupling"] == "NONE"


def test_spec_does_not_import_or_use_subprocess() -> None:
    # Ensure subprocess is not imported by the spec module
    src = inspect.getsource(hitl_mod)
    assert "import subprocess" not in src
    assert "from subprocess" not in src
    assert "subprocess." not in src


def test_spec_does_not_execute_anything() -> None:
    src = inspect.getsource(hitl_mod)
    assert "os.system" not in src
    assert "exec(" not in src
    assert "eval(" not in src
    assert "shutil." not in src


def test_forbidden_language_claims_absent_from_docs() -> None:
    doc_path = Path(__file__).parent.parent / "docs" / "HITL_COMMAND_EXECUTION.md"
    assert doc_path.exists()
    doc_text = doc_path.read_text(encoding="utf-8")

    # Required positive identity statements
    assert "builder-II is a generic governed local agent/developer platform." in doc_text
    assert "It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime." in doc_text
    assert "CORE is only a target profile." in doc_text

    # Forbidden claims / activations
    lower_doc = doc_text.lower()
    assert "builder-ii is core workbench" not in lower_doc
    assert "runtime execution is enabled" not in lower_doc
    assert "subprocess.run(" not in doc_text
    assert "deephaven" not in lower_doc
    assert "voice/tts/stt" not in lower_doc


def test_validation_rejects_bad_spec() -> None:
    spec = create_hitl_command_execution_spec()
    spec["current_state"]["runtime"] = "ENABLED"
    spec["governance"]["artifact_is_authority"] = True
    spec["governance"]["core_workbench_coupling"] = "TIGHT"

    errors = validate_hitl_command_execution_spec(spec)
    assert "current_state.runtime must be DISABLED" in errors
    assert "governance.artifact_is_authority must be false" in errors
    assert "governance.core_workbench_coupling must be NONE" in errors


def test_file_io_helpers(tmp_path: Path) -> None:
    spec = create_hitl_command_execution_spec()
    out = tmp_path / "spec.json"
    hitl_mod.write_hitl_command_execution_spec(spec, out)
    assert out.exists()
    assert validate_hitl_command_execution_spec_file(out) == []

    missing = tmp_path / "nonexistent.json"
    assert any("file not found" in err for err in validate_hitl_command_execution_spec_file(missing))
