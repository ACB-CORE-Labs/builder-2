import inspect
import json
from pathlib import Path

import builder_ii.hitl_execution_records as hitl_records_mod
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
    create_hitl_execution_receipt,
    create_hitl_execution_request,
    dumps_hitl_execution_receipt,
    dumps_hitl_execution_request,
    validate_hitl_execution_receipt,
    validate_hitl_execution_receipt_file,
    validate_hitl_execution_request,
    validate_hitl_execution_request_file,
    write_hitl_execution_receipt,
    write_hitl_execution_request,
)

# ===================================================================
#  Module safety checks
# ===================================================================


def test_module_does_not_import_subprocess() -> None:
    """The module must never import or reference subprocess."""
    src = inspect.getsource(hitl_records_mod)
    assert "import subprocess" not in src
    assert "from subprocess" not in src
    assert "subprocess." not in src


def test_module_does_not_execute_anything() -> None:
    src = inspect.getsource(hitl_records_mod)
    assert "os.system" not in src
    assert "exec(" not in src
    assert "eval(" not in src
    assert "shutil." not in src


# ===================================================================
#  Execution Request — valid creation and validation
# ===================================================================


def test_valid_request_validates() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="proposal-001",
        approval_record_ref="approval-001",
        preflight_record_ref="preflight-001",
        requested_by="operator",
        requested_at="2026-06-27T00:00:00Z",
        explicit_operator_intent="run lint check",
        command_preview="uv run ruff check .",
    )
    assert req["kind"] == HITL_EXECUTION_REQUEST_KIND
    assert validate_hitl_execution_request(req) == []


def test_request_current_state_and_runtime() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    assert req["current_state"] == "REQUEST_RECORDED_ONLY"
    assert req["runtime_execution"] == "DISABLED"
    assert req["artifact_is_authority"] is False


def test_request_governance_denies_all_execution() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    gov = req["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["subprocess_execution"] == "DISABLED"
    assert gov["command_execution"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["source_writes"] == "DISABLED"
    assert gov["git_mutation"] == "DISABLED"
    assert gov["commit_push"] == "DISABLED"
    assert gov["network_mcp_execution"] == "DISABLED"
    assert gov["goose_runtime_activation"] == "DISABLED"
    assert gov["deepagents_runtime"] == "DISABLED"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"


def test_request_fails_missing_refs() -> None:
    req = create_hitl_execution_request()  # all refs default to ""
    errors = validate_hitl_execution_request(req)
    assert "command_proposal_ref is required" in errors
    assert "approval_record_ref is required" in errors
    assert "preflight_record_ref is required" in errors


def test_request_fails_if_governance_claims_execution_enabled() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    req["governance"]["runtime_execution"] = "ENABLED"
    errors = validate_hitl_execution_request(req)
    assert any("runtime_execution" in e and "DISABLED" in e for e in errors)


def test_request_fails_if_artifact_is_authority_true() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    req["artifact_is_authority"] = True
    errors = validate_hitl_execution_request(req)
    assert "artifact_is_authority must be false" in errors


def test_request_fails_if_coupling_not_none() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    req["governance"]["core_workbench_coupling"] = "TIGHT"
    errors = validate_hitl_execution_request(req)
    assert "governance.core_workbench_coupling must be NONE" in errors


# ===================================================================
#  Execution Receipt — valid creation and validation
# ===================================================================


def test_valid_receipt_validates() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    assert receipt["kind"] == HITL_EXECUTION_RECEIPT_KIND
    assert validate_hitl_execution_receipt(receipt) == []


def test_receipt_execution_state_not_executed() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    assert receipt["execution_state"] == "NOT_EXECUTED"
    assert receipt["exit_code"] is None
    assert receipt["stdout_ref"] is None
    assert receipt["stderr_ref"] is None
    assert receipt["started_at"] is None
    assert receipt["completed_at"] is None
    assert receipt["performed_actions"] == []
    assert receipt["current_state"] == "RECEIPT_TEMPLATE_ONLY"
    assert receipt["artifact_is_authority"] is False


def test_receipt_governance_denies_all_execution() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    gov = receipt["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["subprocess_execution"] == "DISABLED"
    assert gov["command_execution"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["source_writes"] == "DISABLED"
    assert gov["git_mutation"] == "DISABLED"
    assert gov["commit_push"] == "DISABLED"
    assert gov["network_mcp_execution"] == "DISABLED"
    assert gov["goose_runtime_activation"] == "DISABLED"
    assert gov["deepagents_runtime"] == "DISABLED"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"


def test_receipt_fails_missing_request_ref() -> None:
    receipt = create_hitl_execution_receipt()
    errors = validate_hitl_execution_receipt(receipt)
    assert "request_ref is required" in errors


def test_receipt_fails_if_execution_state_not_not_executed() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["execution_state"] = "COMPLETED"
    errors = validate_hitl_execution_receipt(receipt)
    assert "execution_state must be NOT_EXECUTED" in errors


def test_receipt_fails_if_exit_code_implies_execution() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["exit_code"] = 0
    errors = validate_hitl_execution_receipt(receipt)
    assert "exit_code must be null (no execution)" in errors


def test_receipt_fails_if_stdout_implies_execution() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["stdout_ref"] = "some-stdout-ref"
    errors = validate_hitl_execution_receipt(receipt)
    assert "stdout_ref must be null (no execution)" in errors


def test_receipt_fails_if_stderr_implies_execution() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["stderr_ref"] = "some-stderr-ref"
    errors = validate_hitl_execution_receipt(receipt)
    assert "stderr_ref must be null (no execution)" in errors


def test_receipt_fails_if_timestamps_imply_execution() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["started_at"] = "2026-06-27T00:00:00Z"
    receipt["completed_at"] = "2026-06-27T00:00:01Z"
    errors = validate_hitl_execution_receipt(receipt)
    assert "started_at must be null (no execution)" in errors
    assert "completed_at must be null (no execution)" in errors


def test_receipt_fails_if_governance_claims_execution_enabled() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["governance"]["runtime_execution"] = "ENABLED"
    errors = validate_hitl_execution_receipt(receipt)
    assert any("runtime_execution" in e and "DISABLED" in e for e in errors)


def test_receipt_fails_if_artifact_is_authority_true() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["artifact_is_authority"] = True
    errors = validate_hitl_execution_receipt(receipt)
    assert "artifact_is_authority must be false" in errors


def test_receipt_fails_if_coupling_not_none() -> None:
    receipt = create_hitl_execution_receipt(request_ref="request-001")
    receipt["governance"]["core_workbench_coupling"] = "TIGHT"
    errors = validate_hitl_execution_receipt(receipt)
    assert "governance.core_workbench_coupling must be NONE" in errors


# ===================================================================
#  Docs compliance
# ===================================================================


def test_docs_contain_required_statements() -> None:
    doc_path = Path(__file__).parent.parent / "docs" / "HITL_EXECUTION_RECORDS.md"
    assert doc_path.exists(), f"Missing docs file: {doc_path}"
    doc_text = doc_path.read_text(encoding="utf-8")

    # Platform identity
    assert "builder-II is a generic governed local agent/developer platform." in doc_text
    assert "It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime." in doc_text
    assert "CORE is only a target profile." in doc_text

    # Design-only / no-execution claims
    assert "design/record artifacts only" in doc_text
    assert "do not execute commands" in doc_text.lower()
    assert "do not grant authority" in doc_text.lower()

    # Future chain requirements
    lower_doc = doc_text.lower()
    for step in (
        "command proposal",
        "approval",
        "preflight",
        "explicit execution request",
        "execution receipt",
        "postflight/handoff",
        "rollback",
        "verification",
    ):
        assert step in lower_doc, f"Missing future chain step in docs: {step}"

    # Disabled executions
    assert "shell" in lower_doc and "disabled" in lower_doc
    assert "subprocess" in lower_doc
    assert "model execution" in lower_doc
    assert "git mutation" in lower_doc
    assert "goose runtime" in lower_doc
    assert "deepagents runtime" in lower_doc

    # Forbidden claims
    assert "builder-ii is core workbench" not in lower_doc
    assert "runtime execution is enabled" not in lower_doc
    assert "subprocess.run(" not in doc_text
    assert "deephaven" not in lower_doc
    assert "voice/tts/stt" not in lower_doc


# ===================================================================
#  File I/O helpers
# ===================================================================


def test_request_file_io(tmp_path: Path) -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    out = tmp_path / "request.json"
    write_hitl_execution_request(req, out)
    assert out.exists()
    assert validate_hitl_execution_request_file(out) == []

    missing = tmp_path / "nonexistent.json"
    assert any("file not found" in err for err in validate_hitl_execution_request_file(missing))


def test_receipt_file_io(tmp_path: Path) -> None:
    receipt = create_hitl_execution_receipt(request_ref="r")
    out = tmp_path / "receipt.json"
    write_hitl_execution_receipt(receipt, out)
    assert out.exists()
    assert validate_hitl_execution_receipt_file(out) == []

    missing = tmp_path / "nonexistent.json"
    assert any("file not found" in err for err in validate_hitl_execution_receipt_file(missing))


def test_dumps_produces_valid_json() -> None:
    req = create_hitl_execution_request(
        command_proposal_ref="p",
        approval_record_ref="a",
        preflight_record_ref="pf",
    )
    receipt = create_hitl_execution_receipt(request_ref="r")

    req_json = json.loads(dumps_hitl_execution_request(req))
    receipt_json = json.loads(dumps_hitl_execution_receipt(receipt))

    assert req_json["kind"] == HITL_EXECUTION_REQUEST_KIND
    assert receipt_json["kind"] == HITL_EXECUTION_RECEIPT_KIND
