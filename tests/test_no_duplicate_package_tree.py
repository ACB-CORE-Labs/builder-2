"""One copy of the package, and no build tree, in the committed repo.

`build/` held 286 committed files: setuptools' staging copy of `builder_ii/`, landed because
`.gitignore` covered `dist/` and not `build/`. Nothing imported it, so it broke nothing and was
invisible for exactly that reason -- 275 of its files were byte-identical to their live
counterparts and 11 were not, including `command_authority.py` (5326 lines against the live 5347)
and `tui/widgets/palette.py` (154 against 180).

Inert is not harmless. An audit grepped the repo, matched `on_static_click` in the fossil's
`palette.py`, and reported a dead mouse-click handler as a live defect; the live palette had
already been correct for two merges. The fossil's only power is to be read and believed. That is
the same failure this repo keeps meeting -- something that looks like the source and is not, with
no gate positioned to tell the difference. `scripts/ci.sh` scopes compileall, ruff and bandit to
`builder_ii`, so a second package tree is unlinted, unscanned and untested by construction.

These lanes read the *index*, never the filesystem. A developer who runs `python -m build` has a
real `build/` on disk and a clean repo; a test that globbed would fail them for doing nothing
wrong, and a test people are right to ignore is worse than no test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Regenerable staging trees. `target/` (Rust) is already ignored and pinned by nothing here
# because it never held a copy of the Python package.
_ARTIFACT_ROOTS = ("build/", "dist/")


def _tracked_files() -> list[str]:
    """Paths git actually has committed -- not what happens to be sitting on this disk."""
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.splitlines()


def test_no_second_copy_of_the_package_is_committed() -> None:
    """The property, not one instance of it: `builder_ii/` exists once.

    Pinning "no build/" would leave the next duplicate free to arrive under any other name.
    command_authority.py is the probe because it is the module a stale copy does the most damage
    to -- it is what an auditor reads to learn which tier a command holds.
    """
    tracked = _tracked_files()
    assert len(tracked) > 500, f"only {len(tracked)} tracked files -- is git ls-files running in the repo?"

    copies = [
        path for path in tracked if path.endswith("builder_ii/governance/authority/authority_registry.py")
    ]
    assert copies == ["builder_ii/governance/authority/authority_registry.py"], (
        f"the package tree is duplicated in the repo: {copies}. A second copy is scanned by no gate "
        f"(ci.sh scopes compileall/ruff/bandit to builder_ii) and read as source by every audit."
    )


def test_no_build_artifact_tree_is_committed() -> None:
    """Regenerable staging output must never be tracked, whatever it contains."""
    offenders = [
        path for path in _tracked_files() if any(path.startswith(root) for root in _ARTIFACT_ROOTS)
    ]
    assert not offenders, (
        f"{len(offenders)} build-artifact files are committed (e.g. {offenders[:3]}); "
        f"these regenerate from source and must stay out of the index"
    )


def test_gitignore_covers_the_python_build_tree() -> None:
    """Deleting the tree is not the fix -- not ignoring it is why it landed.

    `dist/` was ignored and `build/` was not, so the next `python -m build` re-offered the whole
    staging tree to `git add -A`. Without this line the deletion buys one commit of quiet.
    """
    ignored = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for entry in _ARTIFACT_ROOTS:
        assert entry in ignored, f".gitignore must list {entry!r} or the tree returns on the next build"
