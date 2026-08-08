"""Adversarial tests for the governed repository read jail.

The jail is a security boundary, not caller etiquette.  V1 follows no symlink at all and
bounds actual bytes examined, so a clean-looking relative path cannot use filesystem
indirection to escape and a huge file cannot turn a 64 KiB response cap into unbounded I/O.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from builder_ii.core import readonly_repo_tools as tools
from builder_ii.core.readonly_repo_tools import ToolRefusal


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 'hello'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n\tsecret = yes\n", encoding="utf-8")
    (tmp_path / ".builder").mkdir()
    (tmp_path / ".builder" / "ledger.json").write_text("{}", encoding="utf-8")
    return tmp_path


# --- the jail ---------------------------------------------------------------------------


def test_absolute_paths_are_refused(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="must be relative"):
        tools.read_file(repo, "/etc/passwd")


def test_parent_traversal_is_refused(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match=r"must not contain"):
        tools.read_file(repo, "../outside.txt")


def test_git_directory_is_refused(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="must not enter"):
        tools.read_file(repo, ".git/config")


def test_builder_evidence_directory_is_refused(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="must not enter"):
        tools.read_file(repo, ".builder/ledger.json")


def test_a_symlink_pointing_outside_the_root_is_refused(repo: Path, tmp_path_factory: Any) -> None:
    outside_dir = tmp_path_factory.mktemp("outside")
    secret = outside_dir / "secret.txt"
    secret.write_text("exfiltrated", encoding="utf-8")
    (repo / "innocent.txt").symlink_to(secret)

    with pytest.raises(ToolRefusal, match="symlinks are not traversable"):
        tools.read_file(repo, "innocent.txt")


def test_a_symlink_into_git_is_refused(repo: Path) -> None:
    (repo / "peek").symlink_to(repo / ".git" / "config")
    with pytest.raises(ToolRefusal, match="symlinks are not traversable"):
        tools.read_file(repo, "peek")


def test_a_symlink_that_stays_inside_the_root_is_still_refused(repo: Path) -> None:
    """V1 chooses the mechanically simple rule: no symlink traversal, even internal links."""
    (repo / "alias.py").symlink_to(repo / "src" / "app.py")
    with pytest.raises(ToolRefusal, match="symlinks are not traversable"):
        tools.read_file(repo, "alias.py")


def test_a_symlinked_parent_directory_is_refused(repo: Path) -> None:
    (repo / "src-link").symlink_to(repo / "src", target_is_directory=True)
    with pytest.raises(ToolRefusal, match="symlinks are not traversable"):
        tools.read_file(repo, "src-link/app.py")


# --- read_file --------------------------------------------------------------------------


def test_read_file_returns_contents(repo: Path) -> None:
    assert tools.read_file(repo, "src/app.py") == "def main():\n    return 'hello'\n"


def test_read_file_refuses_a_missing_path(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="not found"):
        tools.read_file(repo, "src/nope.py")


def test_read_file_refuses_a_directory(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="regular file"):
        tools.read_file(repo, "src")


def test_read_file_truncates_at_the_byte_cap(repo: Path) -> None:
    (repo / "big.txt").write_text("x" * 5000, encoding="utf-8")
    assert len(tools.read_file(repo, "big.txt", max_bytes=100)) == 100


def test_read_file_bounds_actual_io_not_only_returned_output(
    repo: Path, monkeypatch: Any
) -> None:
    big = repo / "huge.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    original_open = Path.open
    requested: list[int] = []

    class _TrackedHandle:
        def __init__(self, handle: Any):
            self._handle = handle

        def __enter__(self) -> "_TrackedHandle":
            self._handle.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self._handle.__exit__(*args)

        def read(self, size: int = -1) -> bytes:
            requested.append(size)
            return self._handle.read(size)

    def tracked_open(path: Path, *args: Any, **kwargs: Any):
        handle = original_open(path, *args, **kwargs)
        return _TrackedHandle(handle) if path == big else handle

    monkeypatch.setattr(Path, "open", tracked_open)
    assert len(tools.read_file(repo, "huge.txt", max_bytes=4096)) == 4096
    assert requested == [4097]


def test_read_file_survives_undecodable_bytes(repo: Path) -> None:
    (repo / "blob.bin").write_bytes(b"\xff\xfe\x00binary")
    assert isinstance(tools.read_file(repo, "blob.bin"), str)


def test_read_file_refuses_non_regular_files(repo: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo unavailable on this platform")
    fifo = repo / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(ToolRefusal, match="regular file"):
        tools.read_file(repo, "pipe")


# --- list_dir ---------------------------------------------------------------------------


def test_list_dir_marks_directories_and_hides_reserved_ones(repo: Path) -> None:
    listing = tools.list_dir(repo, ".").splitlines()
    assert "src/" in listing
    assert "README.md" in listing
    assert ".git/" not in listing and ".builder/" not in listing


def test_list_dir_marks_but_never_follows_symlinks(repo: Path) -> None:
    (repo / "alias").symlink_to(repo / "src", target_is_directory=True)
    listing = tools.list_dir(repo).splitlines()
    assert "alias@" in listing
    assert "alias/" not in listing


def test_list_dir_is_deterministic(repo: Path) -> None:
    assert tools.list_dir(repo, ".") == tools.list_dir(repo, ".")


def test_list_dir_bounds_large_directories(repo: Path) -> None:
    crowded = repo / "many"
    crowded.mkdir()
    for i in range(50):
        (crowded / f"f{i:03d}.txt").write_text("x", encoding="utf-8")

    listing = tools.list_dir(repo, "many", max_entries=10).splitlines()
    assert len(listing) == 11
    assert "truncated" in listing[-1]


def test_list_dir_reports_an_empty_directory_honestly(repo: Path) -> None:
    (repo / "hollow").mkdir()
    assert tools.list_dir(repo, "hollow") == "(empty directory)"


# --- grep -------------------------------------------------------------------------------


def test_grep_finds_matches_with_path_and_line(repo: Path) -> None:
    out = tools.grep(repo, "hello")
    assert "src/app.py:2:" in out
    assert "return 'hello'" in out


def test_grep_reports_no_matches_without_pretending_to_fail(repo: Path) -> None:
    assert "no matches" in tools.grep(repo, "zzz-not-present")


def test_grep_refuses_an_empty_pattern(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="non-empty pattern"):
        tools.grep(repo, "")


def test_grep_never_searches_reserved_directories(repo: Path) -> None:
    out = tools.grep(repo, "secret")
    assert out.startswith("no matches")
    assert ".git" not in out and ".builder" not in out


def test_grep_never_follows_a_symlinked_file(repo: Path, tmp_path_factory: Any) -> None:
    outside = tmp_path_factory.mktemp("grep-outside") / "secret.txt"
    outside.write_text("needle-outside\n", encoding="utf-8")
    (repo / "looks-local.txt").symlink_to(outside)
    assert tools.grep(repo, "needle-outside").startswith("no matches")


def test_grep_never_follows_a_symlinked_directory(repo: Path, tmp_path_factory: Any) -> None:
    outside = tmp_path_factory.mktemp("grep-dir")
    (outside / "secret.txt").write_text("needle-outside\n", encoding="utf-8")
    (repo / "vendor").symlink_to(outside, target_is_directory=True)
    assert tools.grep(repo, "needle-outside").startswith("no matches")


def test_grep_bounds_its_match_count(repo: Path) -> None:
    noisy = repo / "noisy.txt"
    noisy.write_text("\n".join("needle" for _ in range(100)), encoding="utf-8")

    out = tools.grep(repo, "needle", max_matches=5)
    assert len([line for line in out.splitlines() if "noisy.txt" in line]) == 5
    assert "truncated" in out


def test_grep_bounds_total_bytes_scanned(repo: Path) -> None:
    for index in range(3):
        (repo / f"large-{index}.txt").write_text("x" * 1000, encoding="utf-8")
    out = tools.grep(
        repo,
        "not-present",
        max_scanned_bytes=1200,
        max_bytes_per_file=1000,
    )
    assert "scan truncated" in out


def test_grep_can_be_scoped_to_a_subtree(repo: Path) -> None:
    (repo / "other").mkdir()
    (repo / "other" / "note.txt").write_text("hello elsewhere\n", encoding="utf-8")

    out = tools.grep(repo, "hello", path="other")
    assert "other/note.txt" in out
    assert "src/app.py" not in out
