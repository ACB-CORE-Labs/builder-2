"""Pins the TTY-scraping ban that `docs/CAPABILITY_PROMOTION.md` §7 declares.

The registry row states `pexpect` is absent and `scripts/tui_driver.py` is deleted, and names this
file as what enforces it. Without these lanes that row is a promise, and the next contributor who
reaches for `pexpect.spawn` to "just check the TUI comes up" gets no resistance from the repo --
only from a reviewer who happens to remember the rule.

The ban is not stylistic. The retired driver exited `0` while capturing 306 characters of terminal
mode-setting preamble and zero characters of the app it claimed to smoke-test, because it slept
1.5s and read for 0.8s against a splash that compiles a Swift binary. That is the failure a pty
scraper invites: its verdict is a function of host timing, so it reports the host rather than the
code. `docs/CAPABILITY_PROMOTION.md` §7 carries the measurement.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# `import pexpect`, `from pexpect import ...`, `import pexpect as ...`. Deliberately not a bare
# substring search: the word appears legitimately in prose (this file, the registry, the retirement
# rationale), and a substring rule that fires on its own explanation gets deleted rather than obeyed.
_IMPORT_PEXPECT = re.compile(r"^\s*(?:import\s+pexpect|from\s+pexpect(?:\.\w+)*\s+import)\b", re.MULTILINE)


def _python_sources(root: Path = ROOT) -> list[Path]:
    # Skip venv/git/build trees and NESTED agent worktrees under this checkout's own
    # .claude/worktrees (those may carry retired drivers from other experiments and are
    # not product source). Match on parts *relative to root*, never absolute parts:
    # builder-II's own worktrees live at .../.claude/worktrees/<name>, and the ban's
    # execution doctrine runs the full battery from exactly such a worktree, so `root`
    # itself may sit under a ".claude/worktrees" (or "target", "node_modules") path
    # component. Keying on absolute parts would then match every file and vacate the scan
    # — the failure this test's own vacuity guard is built to catch.
    skip_parts = {".venv", ".git", "target", "node_modules"}
    sources: list[Path] = []
    for path in root.rglob("*.py"):
        rel_parts = path.relative_to(root).parts
        if skip_parts.intersection(rel_parts):
            continue
        if ".claude" in rel_parts:
            claude_i = rel_parts.index(".claude")
            if claude_i + 1 < len(rel_parts) and rel_parts[claude_i + 1] == "worktrees":
                continue
        sources.append(path)
    return sources


def test_pexpect_is_not_a_declared_dependency() -> None:
    """`pexpect` must not return through `pyproject.toml`, in any group."""
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    declared: list[str] = list(manifest["project"].get("dependencies", []))
    for group, requirements in manifest.get("dependency-groups", {}).items():
        declared.extend(f"{group}:{req}" for req in requirements)

    offenders = [req for req in declared if "pexpect" in req]
    assert not offenders, f"pexpect is declared again: {offenders}"

    # Guard against a manifest shape change silently emptying the list above and making the
    # assertion pass by scanning nothing.
    assert len(declared) > 10, f"only found {len(declared)} requirements -- is this parsing pyproject?"


def test_the_pty_scraping_driver_stays_deleted() -> None:
    """The specific artifact §7 names as deleted."""
    assert not (ROOT / "scripts" / "tui_driver.py").exists(), (
        "scripts/tui_driver.py is back; docs/CAPABILITY_PROMOTION.md §7 says it is deleted, and it "
        "exited 0 while observing nothing"
    )


def test_no_module_imports_pexpect() -> None:
    """Deleting the driver is not the ban -- nothing may import pexpect anywhere."""
    sources = _python_sources()
    # Vacuity guard: a wrong ROOT would glob nothing and pass loudly.
    assert len(sources) > 200, f"only scanned {len(sources)} python files -- ROOT is wrong ({ROOT})"

    offenders = [
        str(path.relative_to(ROOT))
        for path in sources
        if _IMPORT_PEXPECT.search(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not offenders, f"pexpect imported in: {offenders}"


def test_source_discovery_survives_a_dot_claude_worktree_root(tmp_path: Path) -> None:
    """`_python_sources` must scan a checkout that itself lives under `.claude/worktrees`.

    builder-II's own worktrees live at `.../.claude/worktrees/<name>`, and the ban's
    execution doctrine ("isolated worktree per PR + full battery") runs from exactly such a
    checkout. A skip rule keyed on absolute path parts matched every file there and vacated
    the scan (0 files, caught only by the vacuity guard above). This pins the fix: scan the
    checkout, but still skip a NESTED agent worktree inside it.
    """
    root = tmp_path / ".claude" / "worktrees" / "review-x"
    (root / "builder_ii").mkdir(parents=True)
    (root / "builder_ii" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("y = 2\n", encoding="utf-8")
    # A nested sub-worktree that MUST still be skipped (another checkout's retired driver).
    nested = root / ".claude" / "worktrees" / "inner"
    nested.mkdir(parents=True)
    (nested / "retired_driver.py").write_text("import pexpect\n", encoding="utf-8")

    names = {p.name for p in _python_sources(root)}
    assert {"app.py", "test_x.py"} <= names, f"must scan a checkout under .claude/worktrees; found {sorted(names)}"
    assert "retired_driver.py" not in names, "must still skip a NESTED agent worktree inside the checkout"


def test_the_registry_still_carries_the_ban() -> None:
    """The lanes above are enforcement; this asserts they are enforcing something still written.

    Without this, deleting the §7 row would leave three green tests pinning a rule the governance
    doc no longer makes -- enforcement outliving its mandate, which is how dead rules accumulate.
    """
    registry = (ROOT / "docs" / "CAPABILITY_PROMOTION.md").read_text(encoding="utf-8")
    assert "Visual assertions are not evidence" in registry
    assert "tests/test_no_tty_scraping.py" in registry, "§7 must still name this file as its enforcement"
