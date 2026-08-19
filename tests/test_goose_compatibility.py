from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from builder_ii.adapters.goose.goose_compatibility import (
    parse_goose_version,
    probe_goose,
    validate_governed_recipe,
)
from builder_ii.adapters.goose.goose_receipts import create_goose_launch_receipt, validate_goose_launch_receipt


def test_parse_goose_version_requires_semver() -> None:
    assert parse_goose_version("goose 1.46.0") == (1, 46, 0)
    with pytest.raises(ValueError, match="Could not parse"):
        parse_goose_version("goose development build")
    with pytest.raises(ValueError, match="Could not parse"):
        parse_goose_version("goose version 1.46.0-dev")


def test_probe_accepts_tested_range_with_isolated_state(tmp_path: Path) -> None:
    result = MagicMock(returncode=0, stdout="goose version 1.46.0\n", stderr="")
    with patch("builder_ii.adapters.goose.goose_compatibility.subprocess.run", return_value=result) as run:
        compatibility = probe_goose("/opt/homebrew/bin/goose", tmp_path / "goose-state")
    assert compatibility.version == "1.46.0"
    assert compatibility.policy == ">=1.45.0,<1.47.0"
    assert run.call_args.kwargs["env"]["GOOSE_PATH_ROOT"] == str(tmp_path / "goose-state")


def test_probe_rejects_unsupported_version(tmp_path: Path) -> None:
    result = MagicMock(returncode=0, stdout="goose version 2.0.0\n", stderr="")
    with patch("builder_ii.adapters.goose.goose_compatibility.subprocess.run", return_value=result):
        with pytest.raises(RuntimeError, match="Unsupported Goose version"):
            probe_goose("/mock/goose", tmp_path / "goose-state")


@pytest.mark.parametrize(
    ("output", "accepted"),
    [("goose version 1.45.0\n", True), ("goose version 1.46.99\n", True), ("goose version 1.44.99\n", False), ("goose version 1.47.0\n", False)],
)
def test_probe_pins_policy_boundaries(tmp_path: Path, output: str, accepted: bool) -> None:
    result = MagicMock(returncode=0, stdout=output, stderr="")
    with patch("builder_ii.adapters.goose.goose_compatibility.subprocess.run", return_value=result):
        if accepted:
            assert probe_goose("/mock/goose", tmp_path / output.strip().replace(" ", "-"))
        else:
            with pytest.raises(RuntimeError, match="Unsupported Goose version"):
                probe_goose("/mock/goose", tmp_path / output.strip().replace(" ", "-"))


def test_probe_times_out_closed(tmp_path: Path) -> None:
    import subprocess

    with patch(
        "builder_ii.adapters.goose.goose_compatibility.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["goose", "--version"], 10),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            probe_goose("/mock/goose", tmp_path / "goose-state")


def test_recipe_admission_rejects_extra_extension(tmp_path: Path) -> None:
    recipe = tmp_path / "governed-readonly.yaml"
    recipe.write_text(
        "extensions:\n"
        "  - {type: stdio, name: builder_ii_governed, cmd: builder-mcp, args: [serve]}\n"
        "  - {type: builtin, name: developer}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly one extension"):
        validate_governed_recipe(recipe)


def test_recipe_admission_rejects_unreviewed_extension_key(tmp_path: Path) -> None:
    recipe = tmp_path / "governed-readonly.yaml"
    recipe.write_text(
        "extensions:\n"
        "  - {type: stdio, name: builder_ii_governed, cmd: builder-mcp, args: [serve], env: {X: y}}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unreviewed keys"):
        validate_governed_recipe(recipe)


def test_recipe_admission_rejects_missing_builder_mcp(tmp_path: Path) -> None:
    recipe = tmp_path / "governed-readonly.yaml"
    recipe.write_text(
        "extensions:\n"
        "  - {type: stdio, name: builder_ii_governed, cmd: builder-mcp, args: [serve]}\n",
        encoding="utf-8",
    )
    with patch("builder_ii.adapters.goose.goose_compatibility.shutil.which", return_value=None):
        with pytest.raises(FileNotFoundError, match="builder-mcp"):
            validate_governed_recipe(recipe)


def test_launch_receipt_requires_versioned_explicit_evidence() -> None:
    receipt = create_goose_launch_receipt(
        "goose_test", "builder", "patch_planner", 123, "2026-01-01T00:00:00+00:00", {"runtime": "goose_readonly"}
    )
    assert receipt["schema_version"] == 2
    assert validate_goose_launch_receipt(receipt) == []
    legacy = dict(receipt, schema_version=1)
    assert any("schema_version must be 2" in error for error in validate_goose_launch_receipt(legacy))
