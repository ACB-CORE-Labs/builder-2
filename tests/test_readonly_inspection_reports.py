import hashlib
import json as json_lib
from pathlib import Path

from builder_ii.readonly_inspection_cli import readonly_app
from typer.testing import CliRunner

from builder_ii.readonly_inspection_reports import (
    READONLY_INSPECTION_REPORT_KIND,
    READONLY_INSPECTION_REPORT_SCHEMA_VERSION,
    create_readonly_inspection_report,
    dumps_readonly_inspection_report,
    validate_readonly_inspection_report,
    validate_readonly_inspection_report_file,
    write_readonly_inspection_report,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_create_report_records_metadata_and_digest_only(tmp_path: Path) -> None:
    source = tmp_path / "example.py"
    source.write_text("print('hello')\n", encoding="utf-8")

    report = create_readonly_inspection_report(
        target="builder",
        purpose="review",
        paths=[source],
        root=tmp_path,
        operator_note="focused review",
    )

    assert report["kind"] == READONLY_INSPECTION_REPORT_KIND
    assert report["schema_version"] == READONLY_INSPECTION_REPORT_SCHEMA_VERSION
    assert report["current_state"] == "RUNTIME_CANDIDATE"
    assert report["scope"] == {
        "mode": "EXPLICIT_PATHS_ONLY",
        "recursive_discovery": False,
        "glob_expansion": False,
        "content_capture": False,
    }
    assert report["counts"] == {"inputs": 1, "recorded": 1, "rejected": 0, "missing": 0}
    assert report["files"][0]["relative_path"] == "example.py"
    assert report["files"][0]["bytes"] == len("print('hello')\n")
    assert report["files"][0]["sha256"] == _sha(source)
    assert "print" not in dumps_readonly_inspection_report(report)
    assert validate_readonly_inspection_report(report) == []


def test_report_rejects_paths_outside_declared_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    report = create_readonly_inspection_report(target="builder", purpose="review", paths=[outside], root=root)

    assert report["counts"] == {"inputs": 1, "recorded": 0, "rejected": 1, "missing": 0}
    assert report["files"][0]["status"] == "rejected"
    assert "path is outside declared root" in report["files"][0]["errors"]
    assert validate_readonly_inspection_report(report) == []


def test_report_records_missing_and_directory_without_content_capture(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    directory = tmp_path / "dir"
    directory.mkdir()

    report = create_readonly_inspection_report(target="generic", purpose="orientation", paths=[missing, directory])

    assert report["counts"] == {"inputs": 2, "recorded": 0, "rejected": 1, "missing": 1}
    assert [entry["status"] for entry in report["files"]] == ["missing", "rejected"]
    assert validate_readonly_inspection_report(report) == []


def test_json_and_file_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("hello", encoding="utf-8")
    report = json_lib.loads(
        dumps_readonly_inspection_report(
            create_readonly_inspection_report(target="builder", purpose="review", paths=[source])
        )
    )
    assert validate_readonly_inspection_report(report) == []

    output = tmp_path / "report.json"
    write_readonly_inspection_report(report, output)
    assert validate_readonly_inspection_report_file(output) == []


def test_validator_rejects_scope_and_governance_drift(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("hello", encoding="utf-8")
    report = create_readonly_inspection_report(target="builder", purpose="review", paths=[source])
    report["scope"]["recursive_discovery"] = True
    report["scope"]["content_capture"] = True
    report["performed_actions"].append("read_file_contents")
    report["governance"]["shell_execution"] = "ENABLED"
    report["governance"]["model_execution"] = "ENABLED"
    report["governance"]["artifact_is_authority"] = True
    report["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_readonly_inspection_report(report)

    assert "scope.recursive_discovery must be false" in errors
    assert "scope.content_capture must be false" in errors
    assert "performed_actions must record only explicit metadata/hash reads" in errors
    assert "governance.shell_execution must be DISABLED" in errors
    assert "governance.model_execution must be DISABLED" in errors
    assert "governance.artifact_is_authority must be false" in errors
    assert "governance.core_workbench_coupling must be NONE" in errors


def test_cli_stdout_output_and_validate(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("hello", encoding="utf-8")
    runner = CliRunner()

    stdout_result = runner.invoke(
        readonly_app, ["report", "--target", "builder", "--purpose", "review", "--path", str(source)]
    )
    assert stdout_result.exit_code == 0
    data = json_lib.loads(stdout_result.stdout)
    assert data["kind"] == READONLY_INSPECTION_REPORT_KIND
    assert data["counts"]["recorded"] == 1

    output = tmp_path / "inspection.json"
    file_result = runner.invoke(
        readonly_app,
        ["report", "--target", "builder", "--purpose", "review", "--path", str(source), "--output", str(output)],
    )
    assert file_result.exit_code == 0
    assert output.exists()

    validate_result = runner.invoke(readonly_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_report_registered_in_artifact_index_and_chain_verifier(tmp_path: Path) -> None:
    from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
    from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
    from builder_ii.artifact_index_records import create_artifact_index_record

    source = tmp_path / "file.txt"
    source.write_text("hello", encoding="utf-8")
    report = create_readonly_inspection_report(target="builder", purpose="review", paths=[source])

    assert READONLY_INSPECTION_REPORT_KIND in INDEX_VALIDATORS
    assert READONLY_INSPECTION_REPORT_KIND in CHAIN_VALIDATORS
    assert INDEX_VALIDATORS[READONLY_INSPECTION_REPORT_KIND](report) == []
    assert CHAIN_VALIDATORS[READONLY_INSPECTION_REPORT_KIND](report) == []

    output = tmp_path / "readonly-report.json"
    write_readonly_inspection_report(report, output)
    index = create_artifact_index_record(tmp_path)

    assert index["counts"]["total"] == 1
    assert index["counts"]["known"] == 1
    assert index["counts"]["valid"] == 1
    assert index["artifacts"][0]["kind"] == READONLY_INSPECTION_REPORT_KIND
