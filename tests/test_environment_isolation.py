"""The test suite must not inherit the developer's environment.

`builder_ii.config.load_settings` calls `load_dotenv(root / ".env", override=False)`, which mutates
`os.environ` for the whole process. One test that reaches it exports the developer's `.env` into
every test after it. On this repo's own `.env` -- `CORE_REPO_PATH=../core`, a legacy alias for
`target_repo` -- three tests failed, each passing in isolation, and the full battery was green in a
fresh worktree and in CI, both of which have no `.env`.

These pins fail with no `.env` present, so CI catches a regression here too. A pin that only fires on
one developer's machine is not a pin.
"""

from __future__ import annotations

import os
from pathlib import Path

from conftest import ROOT, config_environment_keys, is_repo_root_dotenv, isolated_config_environment


def test_the_isolated_keys_are_derived_from_the_specs_that_name_them() -> None:
    """A hand-written key list drifts. This one cannot: it is read off the field specs."""
    from builder_ii.core.config_sources import CONFIG_FIELD_SPECS

    expected: set[str] = set()
    for spec in CONFIG_FIELD_SPECS:
        if spec.primary_env:
            expected.add(spec.primary_env)
        expected.update(alias for alias in spec.legacy_env_aliases if alias)

    assert set(config_environment_keys()) == expected
    assert len(config_environment_keys()) == len(set(config_environment_keys())), "no duplicates"

    # The two that actually caused the outage, named so the pin is not vacuous.
    assert "CORE_REPO_PATH" in expected, "the legacy alias for target_repo"
    assert "BUILDER_TARGET_PROFILE" in expected


def test_the_context_manager_strips_config_keys_and_restores_the_environment_exactly() -> None:
    """Strips on entry, restores on exit -- including keys the block itself invented."""
    before = dict(os.environ)
    os.environ["CORE_REPO_PATH"] = "../core"

    with isolated_config_environment():
        assert "CORE_REPO_PATH" not in os.environ, "a config key present on entry is stripped"
        os.environ["BUILDER_TARGET_PROFILE"] = "core"  # what load_dotenv does: invents a new key

    assert os.environ["CORE_REPO_PATH"] == "../core", "the environment is restored exactly"
    assert "BUILDER_TARGET_PROFILE" not in os.environ, "a key invented inside the block does not leak"

    os.environ.clear()
    os.environ.update(before)


def test_a_test_may_poison_the_process_environment() -> None:
    """Stands in for any test that calls `load_settings()`. The next test must not see this."""
    os.environ["CORE_REPO_PATH"] = "../core"
    os.environ["BUILDER_TARGET_PROFILE"] = "core"
    assert os.environ["CORE_REPO_PATH"] == "../core"


def test_and_the_next_test_starts_clean() -> None:
    """Runs immediately after the poisoner, in definition order. Fails if the fixture is removed."""
    assert "CORE_REPO_PATH" not in os.environ
    assert "BUILDER_TARGET_PROFILE" not in os.environ
    for key in config_environment_keys():
        assert key not in os.environ, f"{key} leaked into this test"


def test_repo_root_dotenv_reads_are_guarded_inside_isolation(tmp_path: Path) -> None:
    """Stripping variables is not enough: `load_settings()` re-reads the repo-root `.env` mid-test.

    A checkout whose `.env` held `BUILDER_MODEL_BACKEND=groq` (the documented cloud-fallback recipe)
    failed 19 tests that were green in CI. The guard blanks exactly one file -- this repo's own
    `.env` -- and leaves a test's tmp-path `.env` fully readable, so dotenv behaviour itself stays
    testable.
    """
    from builder_ii.core import config as config_module
    from builder_ii.core import config_sources as config_sources_module

    assert is_repo_root_dotenv(ROOT / ".env")
    assert not is_repo_root_dotenv(tmp_path / ".env")
    assert not is_repo_root_dotenv(None)

    with isolated_config_environment():
        # The repo-root `.env` is answered without reading the file or mutating os.environ,
        # whether or not the developer has one.
        assert config_module.load_dotenv(ROOT / ".env") is False
        assert config_sources_module.dotenv_values(ROOT / ".env") == {}
        for key in config_environment_keys():
            assert key not in os.environ, f"{key} leaked from the repo-root .env"

        # A `.env` a test writes itself is real dotenv territory and still loads.
        own_env = tmp_path / ".env"
        own_env.write_text("BUILDER_TARGET_PROFILE=core\n", encoding="utf-8")
        assert config_sources_module.dotenv_values(own_env) == {"BUILDER_TARGET_PROFILE": "core"}
        assert config_module.load_dotenv(own_env) is True
        assert os.environ["BUILDER_TARGET_PROFILE"] == "core"

    assert "BUILDER_TARGET_PROFILE" not in os.environ, "the guard context restores the environment exactly"


def test_the_leak_that_was_shipping_reproduced_from_first_principles(tmp_path: Path) -> None:
    """Why it mattered: a relative `CORE_REPO_PATH` resolves against whatever root is being used.

    `builder init --root <tmpdir>` then resolves `target_repo` to `<tmpdir>/../core`, which does not
    exist, and config resolution fails before a single decision is prompted. Nothing about the
    command was wrong; it had inherited a path from a file it never read.
    """
    from builder_ii.core.config_sources import resolve_config_sources

    project_root = tmp_path / "generic"
    project_root.mkdir()

    clean = resolve_config_sources(project_root=project_root)
    assert clean.errors == (), "baseline: an isolated environment resolves cleanly"

    os.environ["CORE_REPO_PATH"] = "../core"
    poisoned = resolve_config_sources(project_root=project_root)

    assert poisoned.errors, "a leaked relative target_repo must be visible, not silently accepted"
    assert any("target_repo does not exist" in error for error in poisoned.errors)
    assert any(str(tmp_path / "core") in error for error in poisoned.errors)
