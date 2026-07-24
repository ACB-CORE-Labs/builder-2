from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"

for path in (ROOT, TESTS):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


# A headless test must not open a window. `StratumApp`'s splash floats a real Cocoa panel through a
# Swift subprocess (`builder_ii.tui.widgets.splash.run_native_hero_splash`) whenever `swift` is on
# PATH and the hero JPEG is present -- both true on the Apple Silicon host this repo targets. Four
# tests constructed `StratumApp()` bare and each paid ~5.4s of wall clock blocking on that window:
# `test_stratum_app_theme_chargers` takes 6.36s with it and 0.93s without, and timing out under host
# load is what made it look like a flake.
#
# The call sites now pass `show_splash=False`; this closes the class rather than those four
# instances, so a test written next year cannot quietly reintroduce a GUI subprocess into the suite.
# It disables only the *native* path -- the splash still composes its ASCII form, so `test_splash.py`
# keeps testing something real. `setdefault` leaves a developer deliberately exercising Cocoa free to
# export a 1.
os.environ.setdefault("BUILDER_SPLASH_NATIVE", "0")


def config_environment_keys() -> tuple[str, ...]:
    """Every environment variable the config layer reads, derived from the specs that name them.

    Derived, never transcribed: a spec that gains a primary name or a legacy alias is isolated
    without anyone editing a list here. A hand-written copy is a second place for the truth to live,
    and the one that drifts is this one.
    """
    from builder_ii.core.config_sources import CONFIG_FIELD_SPECS

    keys: list[str] = []
    for spec in CONFIG_FIELD_SPECS:
        if spec.primary_env:
            keys.append(spec.primary_env)
        keys.extend(alias for alias in spec.legacy_env_aliases if alias)
    return tuple(dict.fromkeys(keys))


def is_repo_root_dotenv(path: object) -> bool:
    """True when `path` is this repo's own `.env` -- the one file tests must never inherit."""
    if path is None:
        return False
    try:
        return Path(str(path)).resolve(strict=False) == (ROOT / ".env").resolve(strict=False)
    except (TypeError, OSError, ValueError):
        return False


@contextmanager
def isolated_config_environment() -> Iterator[None]:
    """Run a block with no config environment variable set, and restore the environment after.

    Snapshot and restore the *whole* environment, not merely the keys removed on entry: a block that
    calls `load_settings()` adds keys that were never there to begin with, and a per-key undo would
    faithfully restore each one for whatever runs next.

    Stripping variables is not enough: `load_settings()` re-reads the developer's repo-root `.env`
    *during* the block (`load_dotenv(root / ".env")`), and `resolve_config_sources` does the same
    through `dotenv_values`. A checkout whose `.env` holds `BUILDER_MODEL_BACKEND=groq` -- the
    documented cloud-fallback recipe in docs/GOOSE_CONVENTION_LAYER.md -- failed 19 tests that way
    (`KeyError('groq-gpt-oss-120b')`, session-config validators rejecting a non-local backend),
    every one of them green in CI, which has no `.env`. So both readers are guarded here for the
    repo-root `.env` only: a test that writes its own `.env` under a tmp path is exercising dotenv
    behaviour on purpose, and still sees it.
    """
    from builder_ii.core import config as config_module
    from builder_ii.core import config_sources as config_sources_module

    snapshot = dict(os.environ)
    for key in config_environment_keys():
        os.environ.pop(key, None)

    real_load_dotenv = config_module.load_dotenv
    real_dotenv_values = config_sources_module.dotenv_values

    def load_dotenv_ignoring_repo_env(dotenv_path: object = None, *args: object, **kwargs: object) -> bool:
        if is_repo_root_dotenv(dotenv_path):
            return False
        return real_load_dotenv(dotenv_path, *args, **kwargs)  # type: ignore[arg-type]

    def dotenv_values_ignoring_repo_env(dotenv_path: object = None, *args: object, **kwargs: object) -> dict:
        if is_repo_root_dotenv(dotenv_path):
            return {}
        return dict(real_dotenv_values(dotenv_path, *args, **kwargs))  # type: ignore[arg-type]

    config_module.load_dotenv = load_dotenv_ignoring_repo_env
    config_sources_module.dotenv_values = dotenv_values_ignoring_repo_env
    try:
        yield
    finally:
        config_module.load_dotenv = real_load_dotenv
        config_sources_module.dotenv_values = real_dotenv_values
        os.environ.clear()
        os.environ.update(snapshot)


@pytest.fixture(autouse=True)
def isolate_config_environment() -> Iterator[None]:
    """No test inherits the developer's shell, or the developer's `.env`.

    `builder_ii.config.load_settings` calls `load_dotenv(root / ".env", override=False)`, and unlike
    `dotenv_values` that mutates `os.environ` for the whole process. One test that reaches it exports
    the developer's `.env` into every test that runs after it, in definition order, silently.

    On a checkout whose `.env` holds `CORE_REPO_PATH=../core` -- a legacy alias for `target_repo`,
    and a *relative* path -- any later `builder init` against a temporary project root resolves
    `target_repo` to `<tmpdir>/core`, finds it absent, and exits 1. Three tests failed exactly that
    way, and every one of them passed in isolation.

    CI clones fresh and has no `.env`, so CI never saw it. `bash scripts/ci.sh` on a developer host
    did. A gate battery whose verdict depends on who runs it is the concrete form of the receipt's
    own `independent_observer: false`.
    """
    with isolated_config_environment():
        yield
