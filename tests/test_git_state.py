import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.git_state import (
    GIT_STATE_RECORD_KIND,
    GIT_STATE_RECORD_SCHEMA_VERSION,
    create_git_state_record,
    validate_git_state_record,
    validate_git_state_record_file,
    write_git_state_record,
)
from builder_ii.git_state_cli import git_state_app


def test_git_state_record_creation_and_validation(tmp_path: Path) -> None:
    # 1. Test clean state creation and validation
    record_clean = create_git_state_record(
        target="builder",
        branch="main",
        commit_sha="a3a56589976694ccdcc845ca4ddc40c6f60f5663",
        state="clean",
        modified_files=[],
        untracked_files=[],
    )

    assert record_clean["kind"] == GIT_STATE_RECORD_KIND
    assert record_clean["schema_version"] == GIT_STATE_RECORD_SCHEMA_VERSION
    assert record_clean["target"] == "builder"
    assert record_clean["branch"] == "main"
    assert record_clean["commit_sha"] == "a3a56589976694ccdcc845ca4ddc40c6f60f5663"
    assert record_clean["state"] == "clean"
    assert record_clean["modified_files"] == []
    assert record_clean["untracked_files"] == []
    assert record_clean["governance"]["core_workbench_coupling"] == "NONE"
    assert record_clean["governance"]["runtime_execution"] == "DISABLED"

    errors = validate_git_state_record(record_clean)
    assert not errors, f"Clean record should be valid: {errors}"

    # 2. Test dirty state creation and validation
    record_dirty = create_git_state_record(
        target="core",
        branch="feature-xyz",
        commit_sha="9fb7667dd95704817f690cfb7210d432c4e68c59",
        state="dirty",
        modified_files=["src/main.py"],
        untracked_files=["tests/temp_test.py"],
    )

    assert record_dirty["state"] == "dirty"
    assert record_dirty["modified_files"] == ["src/main.py"]
    assert record_dirty["untracked_files"] == ["tests/temp_test.py"]

    errors_dirty = validate_git_state_record(record_dirty)
    assert not errors_dirty, f"Dirty record should be valid: {errors_dirty}"

    # 3. Test writing and file validation
    out_file = tmp_path / "git-state-clean.json"
    write_git_state_record(record_clean, out_file)
    assert out_file.exists()

    file_errors = validate_git_state_record_file(out_file)
    assert not file_errors, f"File should be valid: {file_errors}"


def test_git_state_validation_failures(tmp_path: Path) -> None:
    # 1. Non-dict record
    assert "git state record must be a JSON object" in validate_git_state_record([])

    # 2. Basic bad fields
    bad_base = {
        "kind": "wrong_kind",
        "schema_version": 99,
        "target": "invalid_target",
        "branch": "",
        "commit_sha": "not_40_hex",
        "state": "invalid_state",
        "modified_files": "not_a_list",
        "untracked_files": ["ok.py", ""],  # contains empty string
    }
    errors = validate_git_state_record(bad_base)
    assert any("kind must be" in err for err in errors)
    assert any("schema_version must be" in err for err in errors)
    assert any("target must be one of" in err for err in errors)
    assert any("branch must be a non-empty string" in err for err in errors)
    assert any("commit_sha must be 40 lowercase/uppercase hex chars" in err for err in errors)
    assert any("state must be clean or dirty" in err for err in errors)
    assert any("modified_files must be a list" in err for err in errors)
    assert any("untracked_files must be a list of non-empty strings" in err for err in errors)

    # 3. Clean/dirty consistency rules
    # clean but has modified files
    bad_clean = {
        "kind": GIT_STATE_RECORD_KIND,
        "schema_version": GIT_STATE_RECORD_SCHEMA_VERSION,
        "target": "generic",
        "branch": "main",
        "commit_sha": "a3a56589976694ccdcc845ca4ddc40c6f60f5663",
        "state": "clean",
        "modified_files": ["modified.py"],
        "untracked_files": [],
        "governance": {
            "capability_state": "git_state_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }
    errors = validate_git_state_record(bad_clean)
    assert "if state is clean, modified_files and untracked_files must both be empty" in errors

    # dirty but has no modified/untracked files
    bad_dirty = {
        "kind": GIT_STATE_RECORD_KIND,
        "schema_version": GIT_STATE_RECORD_SCHEMA_VERSION,
        "target": "generic",
        "branch": "main",
        "commit_sha": "a3a56589976694ccdcc845ca4ddc40c6f60f5663",
        "state": "dirty",
        "modified_files": [],
        "untracked_files": [],
        "governance": {
            "capability_state": "git_state_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }
    errors = validate_git_state_record(bad_dirty)
    assert "if state is dirty, at least one modified or untracked file must be present" in errors

    # 4. Governance block validation
    bad_gov = {
        "kind": GIT_STATE_RECORD_KIND,
        "schema_version": GIT_STATE_RECORD_SCHEMA_VERSION,
        "target": "generic",
        "branch": "main",
        "commit_sha": "a3a56589976694ccdcc845ca4ddc40c6f60f5663",
        "state": "clean",
        "modified_files": [],
        "untracked_files": [],
        "governance": {
            "capability_state": "wrong_state",
            "runtime_execution": "ENABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": True,
            "core_workbench_coupling": "SOME",
        }
    }
    errors = validate_git_state_record(bad_gov)
    assert any("governance.capability_state must be git_state_record" in err for err in errors)
    assert any("governance.runtime_execution must be DISABLED" in err for err in errors)
    assert any("governance.artifact_is_authority must be false" in err for err in errors)
    assert any("governance.core_workbench_coupling must be NONE" in err for err in errors)

    # 5. Missing file error
    assert "file not found" in validate_git_state_record_file(tmp_path / "missing.json")[0]


def test_git_state_cli_commands(tmp_path: Path) -> None:
    runner = CliRunner()

    # 1. Help option
    help_res = runner.invoke(git_state_app, ["--help"])
    assert help_res.exit_code == 0
    assert "artifact" in help_res.stdout
    assert "validate" in help_res.stdout

    # 2. Create clean state artifact to stdout
    result = runner.invoke(
        git_state_app,
        [
            "artifact",
            "--target",
            "builder",
            "--branch",
            "main",
            "--commit-sha",
            "a3a56589976694ccdcc845ca4ddc40c6f60f5663",
            "--state",
            "clean",
        ],
    )
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == GIT_STATE_RECORD_KIND
    assert data["state"] == "clean"
    assert data["modified_files"] == []

    # 3. Create dirty state artifact to file
    out_file = tmp_path / "git-state-dirty.json"
    result_file = runner.invoke(
        git_state_app,
        [
            "artifact",
            "--target",
            "core",
            "--branch",
            "dev",
            "--commit-sha",
            "9fb7667dd95704817f690cfb7210d432c4e68c59",
            "--state",
            "dirty",
            "--modified",
            "app.py",
            "--untracked",
            "new_doc.md",
            "--output",
            str(out_file),
        ],
    )
    assert result_file.exit_code == 0
    assert out_file.exists()
    assert "Git state record written to" in result_file.stdout

    # Check written file contents
    written_data = json_lib.loads(out_file.read_text(encoding="utf-8"))
    assert written_data["state"] == "dirty"
    assert written_data["modified_files"] == ["app.py"]
    assert written_data["untracked_files"] == ["new_doc.md"]

    # 4. Validate command success
    val_res = runner.invoke(git_state_app, ["validate", str(out_file)])
    assert val_res.exit_code == 0
    assert "is valid" in val_res.stdout

    # 5. Validate command failure (missing file)
    val_fail = runner.invoke(git_state_app, ["validate", str(tmp_path / "missing.json")])
    assert val_fail.exit_code == 1
    assert "Validation error" in val_fail.stdout
