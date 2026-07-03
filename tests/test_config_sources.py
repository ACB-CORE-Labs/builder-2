"""tests/test_config_sources.py

Regression and boundary tests for the generic config source resolver.

Coverage
--------
1. Target defaults — generic, builder, core
2. Override precedence — env > dotenv > config-file > target-default
3. source_kind reporting — target_profile_default where applicable
4. Secret redaction and digest behaviour
5. Boundary guard — config_sources.py must not contain CORE-specific strings

Governance
----------
* No model execution.
* No commit/push authority.
* No shell execution.
* Pure unit tests; no network access required.
"""

from __future__ import annotations

import importlib
import inspect
import os
import textwrap
from pathlib import Path

import pytest

from builder_ii.config_sources import (
    SOURCE_BUILTIN,
    SOURCE_CLI,
    SOURCE_CONFIG_FILE,
    SOURCE_DOTENV,
    SOURCE_ENV,
    SOURCE_TARGET_PROFILE_DEFAULT,
    ConfigSourceResolver,
)
from builder_ii.target_profile_defaults import (
    default_agent_profile_for,
    default_target_repo_for,
    get_target_defaults,
    list_known_targets,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _resolver(
    target=None,
    cli=None,
    config_file_path=None,
    dotenv_path=None,
    env_prefix="BUILDER_",
):
    return ConfigSourceResolver(
        active_target=target,
        cli_overrides=cli or {},
        config_file_path=config_file_path,
        dotenv_path=dotenv_path,
        env_prefix=env_prefix,
    )


# ===========================================================================
# 1. Target defaults
# ===========================================================================


class TestGenericTargetDefaults:
    def test_repo_defaults_to_project_root(self):
        r = _resolver(target="generic")
        rv = r.target_repo()
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT
        project_root = Path(__file__).parent.parent.resolve()
        assert rv.value == project_root

    def test_agent_defaults_to_repo_mapper(self):
        r = _resolver(target="generic")
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT
        assert rv.value == "repo_mapper"


class TestBuilderTargetDefaults:
    def test_repo_defaults_to_project_root(self):
        r = _resolver(target="builder")
        rv = r.target_repo()
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT
        project_root = Path(__file__).parent.parent.resolve()
        assert rv.value == project_root

    def test_agent_defaults_to_patch_planner(self):
        r = _resolver(target="builder")
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT
        assert rv.value == "patch_planner"


class TestCoreTargetDefaults:
    """CORE target defaults must come from target_profile_defaults, not from
    config_sources itself."""

    def test_repo_default_comes_from_profile_layer(self):
        r = _resolver(target="core")
        rv = r.target_repo()
        # Source must be target_profile_default, not builtin
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT

    def test_agent_default_comes_from_profile_layer(self):
        r = _resolver(target="core")
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT

    def test_core_defaults_owned_by_profile_module(self):
        """The core defaults must be accessible via target_profile_defaults."""
        defaults = get_target_defaults("core")
        assert "default_target_repo" in defaults
        assert "default_agent_profile" in defaults
        # Verify the agent name is adapter-owned (not an empty string)
        assert defaults["default_agent_profile"]

    def test_core_repo_is_sibling_of_project_root(self):
        project_root = Path(__file__).parent.parent.resolve()
        core_repo = default_target_repo_for("core")
        assert core_repo == project_root.parent / "core"


# ===========================================================================
# 2. Override precedence
# ===========================================================================


class TestOverridePrecedence:
    def test_env_overrides_target_default(self, monkeypatch):
        monkeypatch.setenv("BUILDER_DEFAULT_AGENT_PROFILE", "custom_from_env")
        r = _resolver(target="generic")
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_ENV
        assert rv.value == "custom_from_env"

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("BUILDER_DEFAULT_AGENT_PROFILE", "from_env")
        r = _resolver(target="generic", cli={"default_agent_profile": "from_cli"})
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_CLI
        assert rv.value == "from_cli"

    def test_config_file_overrides_target_default(self, tmp_path):
        cfg = tmp_path / "builder.toml"
        cfg.write_text('default_agent_profile = "from_config_file"\n')
        r = _resolver(target="generic", config_file_path=cfg)
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_CONFIG_FILE
        assert rv.value == "from_config_file"

    def test_dotenv_overrides_target_default(self, tmp_path):
        dotenv = tmp_path / ".env"
        dotenv.write_text("BUILDER_DEFAULT_AGENT_PROFILE=from_dotenv\n")
        r = _resolver(target="generic", dotenv_path=dotenv)
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_DOTENV
        assert rv.value == "from_dotenv"

    def test_env_overrides_core_target_default(self, monkeypatch):
        monkeypatch.setenv("BUILDER_DEFAULT_TARGET_REPO", "/custom/path")
        r = _resolver(target="core")
        rv = r.target_repo()
        assert rv.source_kind == SOURCE_ENV
        assert rv.value == "/custom/path"

    def test_full_precedence_chain(self, monkeypatch, tmp_path):
        """CLI > env > dotenv > config_file > target_default > builtin."""
        monkeypatch.setenv("BUILDER_DEFAULT_AGENT_PROFILE", "env_val")
        dotenv = tmp_path / ".env"
        dotenv.write_text("BUILDER_DEFAULT_AGENT_PROFILE=dotenv_val\n")
        cfg = tmp_path / "builder.toml"
        cfg.write_text('default_agent_profile = "cfg_val"\n')

        # CLI wins
        r = _resolver(
            target="generic",
            cli={"default_agent_profile": "cli_val"},
            dotenv_path=dotenv,
            config_file_path=cfg,
        )
        assert r.agent_profile().source_kind == SOURCE_CLI
        assert r.agent_profile().value == "cli_val"


# ===========================================================================
# 3. source_kind reporting
# ===========================================================================


class TestSourceKindReporting:
    def test_target_profile_default_source_kind(self):
        r = _resolver(target="builder")
        rv = r.agent_profile()
        assert rv.source_kind == SOURCE_TARGET_PROFILE_DEFAULT

    def test_source_detail_includes_target_name(self):
        r = _resolver(target="builder")
        rv = r.agent_profile()
        assert "builder" in rv.source_detail

    def test_builtin_fallback_when_unknown_target(self):
        r = _resolver(target="unknown_target_xyz")
        rv = r.resolve("default_agent_profile", "fallback_agent")
        # unknown target → no target_default entry → falls to builtin
        assert rv.source_kind == SOURCE_BUILTIN

    def test_resolve_many_returns_report(self):
        r = _resolver(target="generic")
        report = r.resolve_many(
            [
                ("default_agent_profile", "repo_mapper"),
                ("default_target_repo", Path(".")),
            ]
        )
        assert report.active_target == "generic"
        assert len(report.resolved) == 2


# ===========================================================================
# 4. Secret redaction and digest
# ===========================================================================


class TestSecretHandling:
    def test_secret_key_is_redacted_in_display(self, monkeypatch):
        monkeypatch.setenv("BUILDER_API_KEY", "super_secret_123")
        r = _resolver()
        rv = r.resolve("api_key")
        assert rv.redacted
        assert rv.display_value() == "[REDACTED]"
        # Raw value should still be accessible
        assert rv.value == "super_secret_123"

    def test_non_secret_key_is_not_redacted(self):
        r = _resolver(target="generic")
        rv = r.agent_profile()
        assert not rv.redacted
        assert rv.display_value() != "[REDACTED]"

    def test_digest_returns_hex_string(self):
        r = _resolver(target="generic")
        d = r.digest_for("default_agent_profile")
        assert d is not None
        assert len(d) == 16
        assert all(c in "0123456789abcdef" for c in d)

    def test_digest_none_when_key_missing(self):
        r = _resolver()
        d = r.digest_for("nonexistent_key_xyz")
        assert d is None


# ===========================================================================
# 5. Boundary guard
# ===========================================================================


class TestConfigSourcesBoundaryGuard:
    """Structural tests that prevent CORE-specific strings from re-entering
    config_sources.py.  These tests parse the module source directly."""

    @staticmethod
    def _get_config_sources_source() -> str:
        import builder_ii.config_sources as mod

        return inspect.getsource(mod)

    def test_no_core_repo_path_literal(self):
        """config_sources.py must not contain the literal CORE repo path."""
        src = self._get_config_sources_source()
        # The path "project_root.parent / \"core\"" must live only in
        # target_profile_defaults.py, never in config_sources.py.
        assert 'parent / "core"' not in src, (
            "BOUNDARY VIOLATION: config_sources.py contains a hardcoded CORE "
            'repo path (parent / "core"). Move it to target_profile_defaults.py."
        )

    def test_no_core_patch_planner_literal(self):
        """config_sources.py must not contain the string 'core.patch_planner'."""
        src = self._get_config_sources_source()
        assert "core.patch_planner" not in src, (
            "BOUNDARY VIOLATION: config_sources.py contains 'core.patch_planner'. "
            "Move it to target_profile_defaults.py."
        )

    def test_no_hardcoded_target_agent_map(self):
        """config_sources.py must not contain a hardcoded target→agent dict."""
        src = self._get_config_sources_source()
        # A hardcoded map would typically look like {"core": "core.patch_planner"}
        assert '"core": "core.' not in src, (
            "BOUNDARY VIOLATION: config_sources.py contains a hardcoded "
            "target-to-agent mapping. Move to target_profile_defaults.py."
        )

    def test_no_hardcoded_target_repo_map(self):
        """config_sources.py must not contain a hardcoded target→repo dict."""
        src = self._get_config_sources_source()
        assert '"core": project_root' not in src, (
            "BOUNDARY VIOLATION: config_sources.py contains a hardcoded "
            "target-to-repo mapping. Move to target_profile_defaults.py."
        )

    def test_target_profile_defaults_imported(self):
        """config_sources.py must import from target_profile_defaults."""
        src = self._get_config_sources_source()
        assert "target_profile_defaults" in src, (
            "config_sources.py must delegate target defaults to "
            "target_profile_defaults; the import is missing."
        )


# ===========================================================================
# 6. target_profile_defaults module contract
# ===========================================================================


class TestTargetProfileDefaultsContract:
    def test_all_known_targets_have_defaults(self):
        for t in list_known_targets():
            d = get_target_defaults(t)
            assert "default_target_repo" in d
            assert "default_agent_profile" in d

    def test_unknown_target_falls_back_gracefully(self):
        d = get_target_defaults("nonexistent_target")
        assert "default_target_repo" in d
        assert "default_agent_profile" in d

    def test_none_target_falls_back_gracefully(self):
        d = get_target_defaults(None)
        assert d["default_agent_profile"] == "repo_mapper"

    def test_returns_copy_not_mutable_original(self):
        d1 = get_target_defaults("generic")
        d1["default_agent_profile"] = "mutated"
        d2 = get_target_defaults("generic")
        assert d2["default_agent_profile"] != "mutated"
