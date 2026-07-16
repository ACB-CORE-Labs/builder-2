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
    from builder_ii.config_sources import CONFIG_FIELD_SPECS

    keys: list[str] = []
    for spec in CONFIG_FIELD_SPECS:
        if spec.primary_env:
            keys.append(spec.primary_env)
        keys.extend(alias for alias in spec.legacy_env_aliases if alias)
    return tuple(dict.fromkeys(keys))


@contextmanager
def isolated_config_environment() -> Iterator[None]:
    """Run a block with no config environment variable set, and restore the environment after.

    Snapshot and restore the *whole* environment, not merely the keys removed on entry: a block that
    calls `load_settings()` adds keys that were never there to begin with, and a per-key undo would
    faithfully restore each one for whatever runs next.
    """
    snapshot = dict(os.environ)
    for key in config_environment_keys():
        os.environ.pop(key, None)
    try:
        yield
    finally:
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
