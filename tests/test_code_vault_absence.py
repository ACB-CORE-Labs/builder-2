"""Pin the open-core claim: builder-II works with the CodeVault plugin ABSENT.

CI never installs `builder_ii_code_vault` (it is not in uv.lock), so every CI
run is a de-facto absence proof — but developer machines with the plugin
installed silently change what the same green suite proves. This file makes the
absence claim machine-checked on ANY machine by blocking the plugin at the
import system, then asserting the three layers of the severance:

  1. every core module that probes the plugin still imports fresh;
  2. the governed artifact flows still build (context pack, prepare package)
     with `include_code_vault=True` — the DEFAULT — degrading to the core-only
     path instead of crashing or fabricating a frame;
  3. the root seam stubs refuse loudly (RuntimeError / exit 1 with the upgrade
     message) rather than pretending the capability exists.

`tests/test_code_vault_cli.py` pins the Typer seam's refusal by poisoning
`sys.modules`; this file blocks at `sys.meta_path` instead so it also holds on
machines where the plugin IS physically installed, and re-imports the guarded
core modules under the block so a future eager `import builder_ii_code_vault`
at module top level fails here and nowhere else.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

BLOCKED_PREFIX = "builder_ii_code_vault"

# Every core module that references the plugin (guarded probe, registry pull,
# TYPE_CHECKING alias, or seam stub). Each must import cleanly under the block.
CORE_SURVIVORS = (
    "builder_ii.artifact_chain_verification",
    "builder_ii.artifact_index_records",
    "builder_ii.cli.code_vault_cli",
    "builder_ii.cli.session_cli",
    "builder_ii.cli.tui_inspection_cli",
    "builder_ii.code_vault_demo_loop",
    "builder_ii.code_vault_receipt_bridge",
    "builder_ii.code_vault_tui",
    "builder_ii.context_packs",
    "builder_ii.convention_kernel",
    "builder_ii.governed_prepare_package",
    "builder_ii.platform_completion_audit",
    "builder_ii.semantic_readonly",
    "builder_ii.tui.projections.codevault",
    "builder_ii.utility_baseline_runner",
    "builder_ii.workflow_orchestrator",
)


class _PluginBlocker:
    """meta_path finder that refuses the plugin even when it is installed."""

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname == BLOCKED_PREFIX or fullname.startswith(BLOCKED_PREFIX + "."):
            raise ModuleNotFoundError(f"blocked by test_code_vault_absence: {fullname}")
        return None


@pytest.fixture
def plugin_absent():
    saved = sys.modules.copy()
    blocker = _PluginBlocker()
    sys.meta_path.insert(0, blocker)
    # Purge the plugin and the guarded core modules so both re-import under the
    # block; anything imported before the block does not count as evidence.
    for name in list(sys.modules):
        if name == BLOCKED_PREFIX or name.startswith(BLOCKED_PREFIX + "."):
            del sys.modules[name]
        elif name in CORE_SURVIVORS:
            del sys.modules[name]
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        # Restore the exact pre-test module objects. Re-imported copies must not
        # leak: two module objects for one name split class identity (isinstance
        # across the suite) and registry state.
        for name in list(sys.modules):
            if name not in saved:
                del sys.modules[name]
        sys.modules.update(saved)


def test_the_blocker_actually_blocks(plugin_absent) -> None:
    """Guards every other assertion here against becoming vacuously green."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(BLOCKED_PREFIX)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(BLOCKED_PREFIX + ".hierarchy")


def test_every_guarded_core_module_imports_without_the_plugin(plugin_absent) -> None:
    for name in CORE_SURVIVORS:
        module = importlib.import_module(name)
        assert module is sys.modules[name], name


def test_context_pack_builds_and_omits_enrichment_without_the_plugin(plugin_absent, tmp_path: Path) -> None:
    repo_map_mod = importlib.import_module("builder_ii.repo_map")
    context_packs = importlib.import_module("builder_ii.context_packs")

    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")
    (repo / "main.py").write_text("print('hello')\n", encoding="utf-8")

    repo_map = repo_map_mod.create_repo_map(repo, target_name="generic")
    pack = context_packs.create_context_pack(repo_map, target_name="generic", task="absence pin")

    assert context_packs.validate_context_pack(pack) == []
    assert "code_vault_enrichment" not in pack


def test_prepare_package_degrades_with_default_include_code_vault(plugin_absent, tmp_path: Path) -> None:
    """include_code_vault=True is the DEFAULT: absence must degrade, not crash.

    test_governed_prepare_package.py pins the include_code_vault=False path;
    this pins that the default path reaches the same 7-artifact package when
    the plugin cannot be imported (no hierarchical frame file, no frame ref,
    no enrichment) — the severance is a downgrade, not a different API.
    """
    config = importlib.import_module("builder_ii.config")
    gpp = importlib.import_module("builder_ii.governed_prepare_package")

    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")
    output_dir = tmp_path / "prepare"

    package = gpp.create_governed_prepare_package(
        config.load_settings(project_root=ROOT),
        "generic",
        repo_path=str(repo),
        output_dir=output_dir,
        task="absence pin",
        include_code_vault=True,
    )

    assert gpp.validate_governed_prepare_package(package) == []
    assert len(package["artifact_refs"]) == 7
    assert not (output_dir / "hierarchical-frame.json").exists()
    assert not any("CodeVault" in str(ref.get("name", "")) for ref in package["artifact_refs"])

    context_pack = json.loads((output_dir / "context-pack.json").read_text(encoding="utf-8"))
    assert "code_vault_enrichment" not in context_pack


def test_seam_stubs_refuse_with_the_upgrade_message(plugin_absent) -> None:
    bridge = importlib.import_module("builder_ii.code_vault_receipt_bridge")
    demo = importlib.import_module("builder_ii.code_vault_demo_loop")
    baseline = importlib.import_module("builder_ii.utility_baseline_runner")

    for refusing_callable in (
        bridge.build_code_vault_corroboration_record,
        bridge.validate_code_vault_corroboration_record,
        demo.run_code_vault_demo_loop,
        baseline.run_baseline_arm,
        baseline.run_context_pack_without_codevault,
    ):
        with pytest.raises(RuntimeError, match="CodeVault is not installed"):
            refusing_callable()

    # Kind strings are data contracts and must survive severance unchanged.
    assert bridge.CODE_VAULT_CORROBORATION_RECORD_KIND == "builder_ii.code_vault_corroboration_record"
    assert demo.CODE_VAULT_DEMO_REPORT_KIND == "builder_ii.code_vault.determinism_demo_report"


def test_tui_stub_honours_the_dispatch_contract(plugin_absent, capsys) -> None:
    """tui_inspection_cli dispatches by getattr(module, "main") and exits with
    its return value; the absent stub must exit 1 and say why, not AttributeError."""
    tui = importlib.import_module("builder_ii.code_vault_tui")
    exit_code = tui.main(["status"])
    assert exit_code == 1
    assert "CodeVault is not installed" in capsys.readouterr().out
