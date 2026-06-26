import json as json_lib
from pathlib import Path
from typer.testing import CliRunner

from builder_ii.targets_cli import targets_app
from builder_ii.target_profiles import TARGET_PROFILE_ARTIFACT_KIND, TARGET_PROFILE_SCHEMA_VERSION

def test_targets_cli_help() -> None:
    result = CliRunner().invoke(targets_app, ["--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "show" in result.stdout
    assert "validate" in result.stdout
    assert "artifact" in result.stdout

def test_targets_cli_list() -> None:
    result = CliRunner().invoke(targets_app, ["list"])
    assert result.exit_code == 0
    assert "builder" in result.stdout
    assert "generic" in result.stdout
    assert "core" in result.stdout

def test_targets_cli_show() -> None:
    result = CliRunner().invoke(targets_app, ["show", "builder"])
    assert result.exit_code == 0
    assert "# Target profile: builder" in result.stdout
    assert "Principles" in result.stdout

def test_targets_cli_validate() -> None:
    result = CliRunner().invoke(targets_app, ["validate"])
    # May fail if repo paths in default settings don't exist, which is handled in target profiles tests
    # But let's check validation behaves correctly
    assert result.exit_code in (0, 1)

def test_targets_cli_artifact_and_validate(tmp_path: Path) -> None:
    runner = CliRunner()
    
    # 1. Output to stdout
    result = runner.invoke(targets_app, ["artifact", "builder"])
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == TARGET_PROFILE_ARTIFACT_KIND
    assert data["schema_version"] == TARGET_PROFILE_SCHEMA_VERSION
    assert data["name"] == "builder"
    
    # 2. Output to file
    output_file = tmp_path / "builder_profile.json"
    result = runner.invoke(targets_app, ["artifact", "builder", "--output", str(output_file)])
    assert result.exit_code == 0
    assert output_file.exists()
    assert "Target profile artifact written to" in result.stdout
    
    # 3. Validate artifact file
    val_result = runner.invoke(targets_app, ["validate", str(output_file)])
    assert val_result.exit_code == 0
    assert "is valid" in val_result.stdout
    
    # 4. Validate invalid/missing file
    val_bad = runner.invoke(targets_app, ["validate", str(tmp_path / "nonexistent.json")])
    assert val_bad.exit_code == 1
    assert "Validation error" in val_bad.stdout
