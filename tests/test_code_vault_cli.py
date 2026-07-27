"""Pin the fail-closed CodeVault plugin seam.

CodeVault is excised from the open core distribution; `builder_ii.cli.code_vault_cli` is a
shim over the commercial `builder_ii_code_vault` package. Its refusal when that package is
absent *is* the severability guarantee: core must stay importable without the plugin, must
expose no CodeVault capability it cannot back, and must exit non-zero rather than return a
success that fabricates a frame, digest, or recall it never computed.

The refusal must also say *why*. A bare "No such command 'frame'" reads as a typo and sends
the operator hunting for a misspelling; only naming CodeVault distinguishes a severed
capability from a missing one. Nothing else in the suite covers the fallback branch, so
without this file the seam could regress to a hard import (breaking core outright), to a
silent no-op success (claiming a capability that was severed), or back to an unreachable
upgrade message, with the battery still green.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest
import typer
from typer.testing import CliRunner

from builder_ii.cli import code_vault_cli

PLUGIN_MODULE = "builder_ii_code_vault"

# A sample of the 31 commands the plugin really registers -- headline capabilities, one paired
# validator, and one hyphenated name. Real names, not invented ones: core cannot import the
# plugin to enumerate them (that is the severance), so this list is a fixed sample by design.
# It need not track the plugin's full surface; the fallback swallows any argv, so these stand
# in for "anything the operator might type".
CODE_VAULT_SUBCOMMANDS = [
    "frame",
    "digest",
    "lint",
    "recall",
    "context",
    "demo",
    "validate-frame",
    "extractor-manifest",
]


@pytest.fixture
def shim_without_plugin(monkeypatch):
    # `None` in sys.modules makes `import builder_ii_code_vault` raise ImportError, so the
    # fallback branch is exercised whether or not the commercial plugin is installed here.
    monkeypatch.setitem(sys.modules, PLUGIN_MODULE, None)
    try:
        yield importlib.reload(code_vault_cli)
    finally:
        # Undo before reloading, so the module is left bound to whatever this environment
        # really supports rather than to the fallback this fixture forced.
        monkeypatch.undo()
        importlib.reload(code_vault_cli)


def test_absent_plugin_leaves_core_importable(shim_without_plugin) -> None:
    assert shim_without_plugin.code_vault_app is not None


def test_absent_plugin_registers_no_code_vault_capability(shim_without_plugin) -> None:
    registered = {
        info.name or info.callback.__name__ for info in shim_without_plugin.code_vault_app.registered_commands
    }

    assert registered.isdisjoint(CODE_VAULT_SUBCOMMANDS)


@pytest.mark.parametrize("argv", [[], *([sub] for sub in CODE_VAULT_SUBCOMMANDS)])
def test_absent_plugin_refuses_and_names_the_cause(shim_without_plugin, argv: list[str]) -> None:
    result = CliRunner().invoke(shim_without_plugin.code_vault_app, argv)

    assert result.exit_code != 0, result.output
    assert "codevault is not installed" in result.output.lower(), result.output


def test_present_plugin_app_is_used_verbatim(monkeypatch) -> None:
    # The other half of the seam. If the import path ever drifts from what the plugin ships,
    # the shim swallows the ImportError and tells a customer who *has* paid for CodeVault that
    # it is "not installed" -- a silent downgrade the absence tests above cannot see, because
    # to them a fallback is the correct answer.
    plugin_app = typer.Typer()
    package = ModuleType(PLUGIN_MODULE)
    cli_package = ModuleType(f"{PLUGIN_MODULE}.cli")
    plugin_cli = ModuleType(f"{PLUGIN_MODULE}.cli.code_vault_cli")
    plugin_cli.code_vault_app = plugin_app
    cli_package.code_vault_cli = plugin_cli
    package.cli = cli_package

    monkeypatch.setitem(sys.modules, PLUGIN_MODULE, package)
    monkeypatch.setitem(sys.modules, f"{PLUGIN_MODULE}.cli", cli_package)
    monkeypatch.setitem(sys.modules, f"{PLUGIN_MODULE}.cli.code_vault_cli", plugin_cli)
    try:
        assert importlib.reload(code_vault_cli).code_vault_app is plugin_app
    finally:
        monkeypatch.undo()
        importlib.reload(code_vault_cli)
