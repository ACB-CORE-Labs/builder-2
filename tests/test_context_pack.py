import json as json_lib
from pathlib import Path
from types import SimpleNamespace

import pytest

from builder_ii.context_pack import (
    ContextPackSelection,
    build_context_pack,
    render_context_manifest,
    repo_for_target,
    repomix_command,
    select_context_files,
)


def test_select_context_files_uses_defaults_for_empty_selection() -> None:
    repo = Path.cwd()
    files = select_context_files(repo, ContextPackSelection())

    assert "README.md" in files
    assert "builder_ii/context.py" in files


def test_select_context_files_accepts_specific_file_module() -> None:
    repo = Path.cwd()
    files = select_context_files(repo, ContextPackSelection(module="builder_ii/context_pack.py"))

    assert files == ("builder_ii/context_pack.py",)


def test_select_context_files_rejects_missing_module() -> None:
    repo = Path.cwd()

    with pytest.raises(FileNotFoundError, match="module not found"):
        select_context_files(repo, ContextPackSelection(module="does/not/exist.py"))


def test_repo_for_target_selects_core_or_builder() -> None:
    settings = SimpleNamespace(core_repo=Path("/tmp/core"), project_root=Path("/tmp/builder"))

    assert repo_for_target(settings, "core") == Path("/tmp/core")
    assert repo_for_target(settings, "builder") == Path("/tmp/builder")


def test_repomix_command_includes_output_and_selection() -> None:
    repo = Path("/tmp/core")
    cmd = repomix_command(repo, ("a.py", "b.py"), Path("out.xml"))

    assert "--output" in cmd
    assert "out.xml" in cmd
    assert "--include" in cmd
    assert "a.py,b.py" in cmd
    assert str(repo) in cmd


def test_render_context_manifest_mentions_task_target_and_command() -> None:
    text = render_context_manifest(
        repo=Path("/tmp/core"),
        target="core",
        selection=ContextPackSelection(task="review context", module="builder_ii", changed=True),
        selected_files=("builder_ii/context.py",),
        repomix_output=Path(".builder/context-pack.xml"),
        command=("repomix", "--output", ".builder/context-pack.xml"),
    )

    assert "review context" in text
    assert "target: `core`" in text
    assert "builder_ii/context.py" in text
    assert "Repomix command" in text


def test_build_context_pack_manifest_only_defaults_to_core(tmp_path: Path) -> None:
    settings = SimpleNamespace(core_repo=Path.cwd(), project_root=tmp_path)
    result = build_context_pack(
        settings,
        ContextPackSelection(task="manifest only", module="builder_ii/context_pack.py"),
        run_repomix=False,
    )

    assert result.ok
    assert result.target == "core"
    assert result.ran_repomix is False
    assert result.markdown_path.exists()
    assert "manifest only" in result.markdown_path.read_text(encoding="utf-8")
    assert result.selected_files == ("builder_ii/context_pack.py",)


def test_build_context_pack_can_target_builder_repo(tmp_path: Path) -> None:
    settings = SimpleNamespace(core_repo=Path("/tmp/core"), project_root=Path.cwd())
    result = build_context_pack(
        settings,
        ContextPackSelection(task="builder context", module="builder_ii/context_pack.py"),
        target="builder",
        markdown_output=tmp_path / "manifest.md",
        repomix_output=tmp_path / "context.xml",
        run_repomix=False,
    )

    assert result.target == "builder"
    assert result.repo == Path.cwd()
    assert result.selected_files == ("builder_ii/context_pack.py",)


def test_context_pack_record_and_validation(tmp_path: Path) -> None:
    from builder_ii.context_pack import (
        CONTEXT_PACK_RECORD_KIND,
        CONTEXT_PACK_RECORD_SCHEMA_VERSION,
        create_context_pack_record,
        validate_context_pack_record,
        validate_context_pack_record_file,
        write_context_pack_record,
    )

    settings = SimpleNamespace(core_repo=Path.cwd(), project_root=tmp_path)
    result = build_context_pack(
        settings,
        ContextPackSelection(task="test validation", module="builder_ii/context_pack.py"),
        run_repomix=False,
    )
    record = create_context_pack_record(result, task="test validation")
    assert record["kind"] == CONTEXT_PACK_RECORD_KIND
    assert record["schema_version"] == CONTEXT_PACK_RECORD_SCHEMA_VERSION
    assert record["target"] == "core"

    errors = validate_context_pack_record(record)
    assert not errors, f"Record should be valid: {errors}"

    output_file = tmp_path / "context-pack.json"
    write_context_pack_record(record, output_file)
    assert output_file.exists()

    file_errors = validate_context_pack_record_file(output_file)
    assert not file_errors, f"File should be valid: {file_errors}"


def test_context_pack_validation_failures(tmp_path: Path) -> None:
    from builder_ii.context_pack import validate_context_pack_record, validate_context_pack_record_file

    assert "context pack record must be a JSON object" in validate_context_pack_record([])

    bad_dict = {
        "kind": "wrong_kind",
        "schema_version": 1,
        "target": "core",
    }
    errors = validate_context_pack_record(bad_dict)
    assert any("kind must be" in err for err in errors)

    bad_target = {
        "kind": "builder_ii.context_pack_record",
        "schema_version": 1,
        "target": "invalid_target",
        "selected_files": [],
        "governance": {
            "capability_state": "context_pack_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    errors = validate_context_pack_record(bad_target)
    assert any("target must be one of" in err for err in errors)

    # bad core_workbench_coupling
    bad_coupling = {
        "kind": "builder_ii.context_pack_record",
        "schema_version": 1,
        "target": "core",
        "selected_files": [],
        "governance": {
            "capability_state": "context_pack_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "INVALID",
        },
    }
    errors = validate_context_pack_record(bad_coupling)
    assert any("core_workbench_coupling must be NONE or NOT_AUTHORIZED" in err for err in errors)

    # selected_files list validation failures
    bad_files = {
        "kind": "builder_ii.context_pack_record",
        "schema_version": 1,
        "target": "core",
        "selected_files": ["ok.py", "", 123],
        "governance": {
            "capability_state": "context_pack_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    errors = validate_context_pack_record(bad_files)
    assert any("selected_files must be a list of non-empty strings" in err for err in errors)

    assert "file not found" in validate_context_pack_record_file(tmp_path / "missing.json")[0]


def test_context_pack_cli_commands(tmp_path: Path) -> None:
    from builder_ii.context_cli import context_app
    from typer.testing import CliRunner

    runner = CliRunner()

    # Help command
    help_res = runner.invoke(context_app, ["--help"])
    assert help_res.exit_code == 0
    assert "artifact" in help_res.stdout
    assert "validate" in help_res.stdout

    # Emit artifact to stdout
    tmp_path / "context-pack-stdout.json"
    result = runner.invoke(
        context_app,
        [
            "artifact",
            "--task",
            "cli test",
            "--module",
            "builder_ii/context_pack.py",
            "--target",
            "builder",
            "--no-repomix",
        ],
    )
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.context_pack_record"
    assert data["task"] == "cli test"

    # Emit artifact to file
    out_file = tmp_path / "context-pack-record.json"
    result_file = runner.invoke(
        context_app,
        [
            "artifact",
            "--task",
            "cli test file",
            "--module",
            "builder_ii/context_pack.py",
            "--target",
            "builder",
            "--no-repomix",
            "--output",
            str(out_file),
        ],
    )
    assert result_file.exit_code == 0
    assert out_file.exists()
    assert "Context pack record written to" in result_file.stdout

    # Validate command
    val_res = runner.invoke(context_app, ["validate", str(out_file)])
    assert val_res.exit_code == 0
    assert "is valid" in val_res.stdout

    # Validate invalid path
    val_bad = runner.invoke(context_app, ["validate", str(tmp_path / "nonexistent.json")])
    assert val_bad.exit_code == 1
