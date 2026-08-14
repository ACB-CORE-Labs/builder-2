import inspect
import json
from pathlib import Path

import builder_ii.lifecycle.candidate.execution_postflight_records as postflight_records_mod
from builder_ii.lifecycle.candidate.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
    create_execution_postflight_record,
    create_execution_verification_record,
    dumps_execution_postflight_record,
    dumps_execution_verification_record,
    validate_execution_postflight_record,
    validate_execution_postflight_record_file,
    validate_execution_verification_record,
    validate_execution_verification_record_file,
    write_execution_postflight_record,
    write_execution_verification_record,
)

# ===================================================================
#  Module safety checks
# ===================================================================


def test_module_does_not_import_subprocess() -> None:
    """The module must never import or reference subprocess."""
    src = inspect.getsource(postflight_records_mod)
    assert "import subprocess" not in src
    assert "from subprocess" not in src
    assert "subprocess." not in src


def test_module_does_not_execute_anything() -> None:
    src = inspect.getsource(postflight_records_mod)
    assert "os.system" not in src
    assert "exec(" not in src
    assert "eval(" not in src
    assert "shutil." not in src


# ===================================================================
#  Non-dict validation fails clearly
# ===================================================================


def test_non_dict_validation_fails_clearly() -> None:
    for non_dict in (None, "string", [1, 2, 3], 42):
        errs1 = validate_execution_postflight_record(non_dict)
        assert len(errs1) == 1
        assert "must be a JSON object" in errs1[0]

        errs2 = validate_execution_verification_record(non_dict)
        assert len(errs2) == 1
        assert "must be a JSON object" in errs2[0]


# ===================================================================
#  Execution Postflight — valid creation and validation
# ===================================================================


def test_valid_postflight_record_validates() -> None:
    rec = create_execution_postflight_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        preflight_ref="preflight-001",
        approval_ref="approval-001",
        expected_outcome="files updated, test passing",
        observed_state_ref="state-001",
    )
    assert rec["kind"] == EXECUTION_POSTFLIGHT_RECORD_KIND
    assert validate_execution_postflight_record(rec) == []


def test_postflight_missing_refs_fails() -> None:
    # Missing request_ref
    rec = create_execution_postflight_record(
        request_ref="",
        receipt_ref="receipt-001",
        preflight_ref="preflight-001",
        approval_ref="approval-001",
    )
    assert "request_ref is required" in validate_execution_postflight_record(rec)[0]

    # Missing receipt_ref
    rec = create_execution_postflight_record(
        request_ref="req-001",
        receipt_ref="",
        preflight_ref="preflight-001",
        approval_ref="approval-001",
    )
    assert "receipt_ref is required" in validate_execution_postflight_record(rec)[0]

    # Missing preflight_ref
    rec = create_execution_postflight_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        preflight_ref="",
        approval_ref="approval-001",
    )
    assert "preflight_ref is required" in validate_execution_postflight_record(rec)[0]

    # Missing approval_ref
    rec = create_execution_postflight_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        preflight_ref="preflight-001",
        approval_ref="",
    )
    assert "approval_ref is required" in validate_execution_postflight_record(rec)[0]


def test_postflight_state_must_be_not_run() -> None:
    rec = create_execution_postflight_record(
        request_ref="req-001", receipt_ref="rcpt", preflight_ref="pf", approval_ref="ap"
    )
    rec["postflight_state"] = "RUN"
    assert "postflight_state must be NOT_RUN" in validate_execution_postflight_record(rec)


def test_postflight_performed_actions_non_empty_fails() -> None:
    rec = create_execution_postflight_record(
        request_ref="req-001", receipt_ref="rcpt", preflight_ref="pf", approval_ref="ap"
    )
    rec["performed_actions"] = ["wrote file"]
    assert "performed_actions must be empty" in validate_execution_postflight_record(rec)


def test_postflight_artifact_is_authority_true_fails() -> None:
    rec = create_execution_postflight_record(
        request_ref="req-001", receipt_ref="rcpt", preflight_ref="pf", approval_ref="ap"
    )
    rec["artifact_is_authority"] = True
    assert "artifact_is_authority must be false or NOT_AUTHORIZED" in validate_execution_postflight_record(rec)


def test_postflight_each_governance_field_enabled_fails() -> None:
    rec = create_execution_postflight_record(
        request_ref="req-001", receipt_ref="rcpt", preflight_ref="pf", approval_ref="ap"
    )
    gov_keys = [
        "runtime_execution",
        "shell_execution",
        "command_execution",
        "model_execution",
        "source_writes",
        "git_mutation",
        "network_access",
        "goose_runtime_activation",
        "deepagents_runtime",
    ]
    for key in gov_keys:
        rec_copy = json.loads(json.dumps(rec))
        rec_copy["governance"][key] = "ENABLED"
        assert any(key in e and "DISABLED" in e for e in validate_execution_postflight_record(rec_copy))


# ===================================================================
#  Execution Verification — valid creation and validation
# ===================================================================


def test_valid_verification_record_validates() -> None:
    rec = create_execution_verification_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        postflight_ref="postflight-001",
        verification_state="NOT_RUN",
        verification_summary="Verification has not yet been executed.",
        evidence_refs=["evidence-001"],
    )
    assert rec["kind"] == EXECUTION_VERIFICATION_RECORD_KIND
    assert validate_execution_verification_record(rec) == []

    # verification_state can be PASS
    rec["verification_state"] = "PASS"
    assert validate_execution_verification_record(rec) == []

    # verification_state can be FAIL
    rec["verification_state"] = "FAIL"
    assert validate_execution_verification_record(rec) == []


def test_verification_missing_postflight_ref_fails() -> None:
    rec = create_execution_verification_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        postflight_ref="",
    )
    assert "postflight_ref is required" in validate_execution_verification_record(rec)[0]


def test_verification_invalid_state_fails() -> None:
    rec = create_execution_verification_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        postflight_ref="postflight-001",
        verification_state="UNKNOWN_STATE",
    )
    assert "verification_state must be NOT_RUN, PASS, or FAIL" in validate_execution_verification_record(rec)


def test_verification_performed_actions_non_empty_fails() -> None:
    rec = create_execution_verification_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        postflight_ref="postflight-001",
    )
    rec["performed_actions"] = ["verified"]
    assert "performed_actions must be empty" in validate_execution_verification_record(rec)


def test_verification_artifact_is_authority_true_fails() -> None:
    rec = create_execution_verification_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        postflight_ref="postflight-001",
    )
    rec["artifact_is_authority"] = True
    assert "artifact_is_authority must be false or NOT_AUTHORIZED" in validate_execution_verification_record(rec)


def test_verification_each_governance_field_enabled_fails() -> None:
    rec = create_execution_verification_record(
        request_ref="req-001",
        receipt_ref="receipt-001",
        postflight_ref="postflight-001",
    )
    gov_keys = [
        "runtime_execution",
        "shell_execution",
        "command_execution",
        "model_execution",
        "source_writes",
        "git_mutation",
        "network_access",
        "goose_runtime_activation",
        "deepagents_runtime",
    ]
    for key in gov_keys:
        rec_copy = json.loads(json.dumps(rec))
        rec_copy["governance"][key] = "ENABLED"
        assert any(key in e and "DISABLED" in e for e in validate_execution_verification_record(rec_copy))


# ===================================================================
#  Docs compliance
# ===================================================================


def test_docs_deny_execution_and_authority() -> None:
    doc_path = Path(__file__).parent.parent / "docs" / "EXECUTION_POSTFLIGHT_RECORDS.md"
    assert doc_path.exists(), f"Missing docs file: {doc_path}"
    doc_text = doc_path.read_text(encoding="utf-8")

    # Platform identity
    assert "builder-II is generic-first" in doc_text
    assert "builder-II is not CORE Workbench/UI/UX" in doc_text
    assert "CORE is only a target profile" in doc_text

    # Design-only / no-execution claims
    assert "these are postflight/verification record specs only" in doc_text.lower()
    assert "they do not prove execution occurred" in doc_text.lower()
    assert "they do not execute verification commands" in doc_text.lower()
    assert "they do not run tests" in doc_text.lower()
    assert "they do not grant authority" in doc_text.lower()

    # Pass state supplied externally
    assert "verification_state: PASS is only an externally supplied record state" in doc_text


# ===================================================================
#  File I/O helpers
# ===================================================================


def test_postflight_file_io(tmp_path: Path) -> None:
    rec = create_execution_postflight_record(
        request_ref="req", receipt_ref="rcpt", preflight_ref="pf", approval_ref="ap"
    )
    out = tmp_path / "postflight.json"
    write_execution_postflight_record(rec, out)
    assert out.exists()
    assert validate_execution_postflight_record_file(out) == []

    missing = tmp_path / "nonexistent.json"
    assert any("file not found" in err for err in validate_execution_postflight_record_file(missing))


def test_verification_file_io(tmp_path: Path) -> None:
    rec = create_execution_verification_record(request_ref="req", receipt_ref="rcpt", postflight_ref="pf")
    out = tmp_path / "verification.json"
    write_execution_verification_record(rec, out)
    assert out.exists()
    assert validate_execution_verification_record_file(out) == []

    missing = tmp_path / "nonexistent.json"
    assert any("file not found" in err for err in validate_execution_verification_record_file(missing))


def test_dumps_produces_valid_json() -> None:
    rec1 = create_execution_postflight_record(
        request_ref="req", receipt_ref="rcpt", preflight_ref="pf", approval_ref="ap"
    )
    rec2 = create_execution_verification_record(request_ref="req", receipt_ref="rcpt", postflight_ref="pf")

    rec1_json = json.loads(dumps_execution_postflight_record(rec1))
    rec2_json = json.loads(dumps_execution_verification_record(rec2))

    assert rec1_json["kind"] == EXECUTION_POSTFLIGHT_RECORD_KIND
    assert rec2_json["kind"] == EXECUTION_VERIFICATION_RECORD_KIND
