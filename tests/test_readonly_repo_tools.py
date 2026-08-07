"""The path jail and bounds behind the governed read tools.

These are the tools that make a governed Goose session able to do real work, so the jail is the
security boundary of the whole lane: everything a governed session can see, it sees through
here. The tests are written adversarially -- absolute paths, `..` traversal, symlinks that
resolve out of the tree, links into `.git` -- because a jail that only stops the honest caller
is not a jail.
"""

from __future__ import annotations

from pathlib import Path

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
    with pytest.raises(ToolRefusal, match="reserved|must not enter"):
        tools.read_file(repo, ".git/config")


def test_builder_evidence_directory_is_refused(repo: Path) -> None:
    # A tool that can read the ledger it is being recorded in confuses acting with being
    # audited; the governance evidence is off-limits to the governed session.
    with pytest.raises(ToolRefusal, match="reserved|must not enter"):
        tools.read_file(repo, ".builder/ledger.json")


def test_a_symlink_pointing_outside_the_root_is_refused(repo: Path, tmp_path_factory) -> None:
    """The string is clean; only resolution reveals the escape."""
    outside_dir = tmp_path_factory.mktemp("outside")
    secret = outside_dir / "secret.txt"
    secret.write_text("exfiltrated", encoding="utf-8")
    (repo / "innocent.txt").symlink_to(secret)

    with pytest.raises(ToolRefusal, match="escapes the target root"):
        tools.read_file(repo, "innocent.txt")


def test_a_symlink_into_git_is_refused(repo: Path) -> None:
    (repo / "peek").symlink_to(repo / ".git" / "config")
    with pytest.raises(ToolRefusal, match="reserved|escapes"):
        tools.read_file(repo, "peek")


def test_a_symlink_that_stays_inside_the_root_is_allowed(repo: Path) -> None:
    # The jail bounds where reads may land, not how the caller spells the path.
    (repo / "alias.py").symlink_to(repo / "src" / "app.py")
    assert "def main()" in tools.read_file(repo, "alias.py")


# --- read_file --------------------------------------------------------------------------


def test_read_file_returns_contents(repo: Path) -> None:
    assert tools.read_file(repo, "src/app.py") == "def main():\n    return 'hello'\n"


def test_read_file_refuses_a_missing_path(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="not found"):
        tools.read_file(repo, "src/nope.py")


def test_read_file_refuses_a_directory(repo: Path) -> None:
    with pytest.raises(ToolRefusal, match="not a file"):
        tools.read_file(repo, "src")


def test_read_file_truncates_at_the_byte_cap(repo: Path) -> None:
    (repo / "big.txt").write_text("x" * 5000, encoding="utf-8")
    assert len(tools.read_file(repo, "big.txt", max_bytes=100)) == 100


def test_read_file_survives_undecodable_bytes(repo: Path) -> None:
    # Binary content must not raise out of the governed path; it degrades to replacement chars.
    (repo / "blob.bin").write_bytes(b"\xff\xfe\x00binary")
    assert isinstance(tools.read_file(repo, "blob.bin"), str)


# --- list_dir ---------------------------------------------------------------------------


def test_list_dir_marks_directories_and_hides_reserved_ones(repo: Path) -> None:
    listing = tools.list_dir(repo, ".").splitlines()
    assert "src/" in listing
    assert "README.md" in listing
    assert ".git/" not in listing and ".builder/" not in listing


def test_list_dir_is_deterministic(repo: Path) -> None:
    assert tools.list_dir(repo, ".") == tools.list_dir(repo, ".")


def test_list_dir_bounds_large_directories(repo: Path) -> None:
    crowded = repo / "many"
    crowded.mkdir()
    for i in range(50):
        (crowded / f"f{i:03d}.txt").write_text("x", encoding="utf-8")

    listing = tools.list_dir(repo, "many", max_entries=10).splitlines()
    assert len(listing) == 11  # 10 entries plus the truncation notice
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
    # The string lives only in .git/config, so a repo-wide search must find nothing. Asserting
    # on the absence of the word alone would pass trivially: the "no matches" line echoes the
    # pattern back, so the real claim is that no *result row* cites a reserved path.
    out = tools.grep(repo, "secret")
    assert out.startswith("no matches")
    assert ".git" not in out and ".builder" not in out


def test_grep_bounds_its_match_count(repo: Path) -> None:
    noisy = repo / "noisy.txt"
    noisy.write_text("\n".join("needle" for _ in range(100)), encoding="utf-8")

    out = tools.grep(repo, "needle", max_matches=5)
    assert len([ln for ln in out.splitlines() if "noisy.txt" in ln]) == 5
    assert "truncated" in out


def test_grep_can_be_scoped_to_a_subtree(repo: Path) -> None:
    (repo / "other").mkdir()
    (repo / "other" / "note.txt").write_text("hello elsewhere\n", encoding="utf-8")

    out = tools.grep(repo, "hello", path="other")
    assert "other/note.txt" in out
    assert "src/app.py" not in out
