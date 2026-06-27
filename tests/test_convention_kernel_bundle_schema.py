from __future__ import annotations

from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.convention_kernel import kernel, validate_convention_kernel_bundle


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_kernel_bundle_validator_requires_top_level_metadata(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    bundle = kernel.prepare_bundle(settings, "generic", repo_path=str(repo), generic_repo=repo).to_dict()

    bundle["target"] = ""
    bundle.pop("session_configuration_kind")

    errors = validate_convention_kernel_bundle(bundle)

    assert "target must be a non-empty string" in errors
    assert "session_configuration_kind must be a non-empty string" in errors
