"""Prove the open core remains usable when the commercial plugin is absent."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from builder_ii.core.config import load_settings
from builder_ii.core.governed_prepare_package import (
    create_governed_prepare_package,
    validate_governed_prepare_package,
)

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MODULE = "builder_ii_code_vault"
OPTIONAL_IMPORT_SURFACES = (
    "builder_ii.cli.code_vault_cli",
    "builder_ii.tui.projections.codevault",
)


class _PluginBlocker:
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == PLUGIN_MODULE or fullname.startswith(PLUGIN_MODULE + "."):
            raise ModuleNotFoundError(f"optional plugin blocked: {fullname}")
        return None


@pytest.fixture
def plugin_absent():
    saved = sys.modules.copy()
    blocker = _PluginBlocker()
    sys.meta_path.insert(0, blocker)
    for name in list(sys.modules):
        if name == PLUGIN_MODULE or name.startswith(PLUGIN_MODULE + ".") or name in OPTIONAL_IMPORT_SURFACES:
            del sys.modules[name]
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        for name in list(sys.modules):
            if name not in saved:
                del sys.modules[name]
        sys.modules.update(saved)


def test_optional_import_surfaces_load_without_plugin(plugin_absent) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(PLUGIN_MODULE)
    for name in OPTIONAL_IMPORT_SURFACES:
        assert importlib.import_module(name) is sys.modules[name]


def test_open_core_prepare_package_does_not_probe_plugin(plugin_absent, tmp_path: Path) -> None:
    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")

    package = create_governed_prepare_package(
        load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=tmp_path / "prepare",
        task="absence pin",
    )

    assert validate_governed_prepare_package(package) == []
    assert len(package["artifact_refs"]) == 7
