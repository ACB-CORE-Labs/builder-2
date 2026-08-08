"""Bounded, path-jailed repository reads for the governed tool path.

This module is the read boundary of a governed Goose session.  It therefore treats the
filesystem as hostile input rather than assuming that a syntactically relative path is
safe.  The V1 rule is deliberately simple and mechanically auditable: **no symlink is
ever followed**.  Absolute paths, ``..``, ``.git``/``.builder``, symlink components,
and non-regular files are refused before content I/O.

All tools are pure in-process Python: no shell, subprocess, network, git invocation, or
mutation.  Bounds constrain actual I/O, not only the returned string.  ``read_file``
reads at most ``max_bytes + 1``; ``grep`` bounds files visited, bytes per file, total
bytes examined, matches, and output rows.  Traversal is deterministic.

A refusal is a value surfaced by the governed gateway as a denied receipt/event.  The
jail itself grants no authority.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_READ_BYTES = 65_536
DEFAULT_MAX_ENTRIES = 500
DEFAULT_MAX_MATCHES = 200
DEFAULT_MAX_SCANNED_FILES = 2_000
DEFAULT_MAX_SCANNED_BYTES = 16 * 1024 * 1024

_RESERVED_DIRECTORY_NAMES = (".git", ".builder")


@dataclass(frozen=True)
class ToolRefusal(Exception):
    """A read the jail refused. Carries operator-facing text; never a stack trace."""

    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.reason


def _reserved(path: Path) -> bool:
    return any(part in _RESERVED_DIRECTORY_NAMES for part in path.parts)


def _validate_relative(raw_path: str, *, allow_root: bool) -> Path:
    cleaned = raw_path.strip() or "."
    relative = Path(cleaned)
    if relative.is_absolute():
        raise ToolRefusal(f"path must be relative to the target root: {raw_path}")
    if ".." in relative.parts:
        raise ToolRefusal(f"path must not contain '..': {raw_path}")
    if _reserved(relative):
        raise ToolRefusal(
            f"path must not enter {' or '.join(_RESERVED_DIRECTORY_NAMES)}: {raw_path}"
        )
    if not allow_root and str(relative) == ".":
        raise ToolRefusal("path must name a file")
    return relative


def _reject_symlink_components(root: Path, relative: Path, raw_path: str) -> None:
    """Refuse any existing symlink component without dereferencing it.

    ``Path.resolve`` is intentionally not used for the candidate: resolving first follows
    the very link we are trying to treat as untrusted.  The target root itself is trusted
    configuration and is resolved once; every user-controlled component is then inspected
    with ``lstat`` from that root outward.
    """

    current = root
    for part in relative.parts:
        if part in ("", "."):
            continue
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            # Missing paths are diagnosed by the concrete operation after the lexical jail
            # has already been proven.  There can be no later existing component beneath a
            # missing parent.
            return
        except OSError as exc:
            raise ToolRefusal(f"failed to inspect path {raw_path}: {exc}") from None
        if stat.S_ISLNK(mode):
            raise ToolRefusal(f"symlinks are not traversable in the governed read jail: {raw_path}")


def resolve_in_jail(target_root: Path, raw_path: str, *, allow_root: bool = False) -> Path:
    """Return a lexical path inside ``target_root`` after a no-symlink component check."""

    relative = _validate_relative(raw_path, allow_root=allow_root)
    try:
        root = Path(target_root).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ToolRefusal(f"failed to resolve target root: {exc}") from None
    if not root.is_dir():
        raise ToolRefusal(f"target root is not a directory: {root}")

    candidate = root / relative
    # No '..' survived validation, so this lexical containment check does not dereference
    # user-controlled links.  It is a belt-and-suspenders guard against future normalization
    # changes to _validate_relative.
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ToolRefusal(f"path escapes the target root: {raw_path}") from None

    _reject_symlink_components(root, relative, raw_path)
    return candidate


def _read_bounded_bytes(path: Path, *, max_bytes: int, raw_path: str) -> tuple[bytes, bool]:
    if max_bytes <= 0:
        raise ToolRefusal("max_bytes must be positive")
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        raise ToolRefusal(f"path not found: {raw_path}") from None
    except OSError as exc:
        raise ToolRefusal(f"failed to inspect {raw_path}: {exc}") from None
    if stat.S_ISLNK(mode):
        raise ToolRefusal(f"symlinks are not traversable in the governed read jail: {raw_path}")
    if not stat.S_ISREG(mode):
        raise ToolRefusal(f"path is not a regular file: {raw_path}")

    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        raise ToolRefusal(f"failed to read {raw_path}: {exc}") from None
    return data[:max_bytes], len(data) > max_bytes


def read_file(target_root: Path, raw_path: str, *, max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
    """Return at most ``max_bytes`` of file text without performing unbounded file I/O."""

    path = resolve_in_jail(target_root, raw_path)
    data, _truncated = _read_bounded_bytes(path, max_bytes=max_bytes, raw_path=raw_path)
    return data.decode("utf-8", errors="replace")


def list_dir(
    target_root: Path, raw_path: str = ".", *, max_entries: int = DEFAULT_MAX_ENTRIES
) -> str:
    """Return a deterministic bounded listing without following directory symlinks."""

    if max_entries <= 0:
        raise ToolRefusal("max_entries must be positive")
    directory = resolve_in_jail(target_root, raw_path, allow_root=True)
    try:
        mode = directory.lstat().st_mode
    except FileNotFoundError:
        raise ToolRefusal(f"path not found: {raw_path}") from None
    except OSError as exc:
        raise ToolRefusal(f"failed to inspect {raw_path}: {exc}") from None
    if not stat.S_ISDIR(mode):
        raise ToolRefusal(f"path is not a directory: {raw_path}")

    try:
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
    except OSError as exc:
        raise ToolRefusal(f"failed to list {raw_path}: {exc}") from None

    lines: list[str] = []
    visible = [entry for entry in entries if entry.name not in _RESERVED_DIRECTORY_NAMES]
    for entry in visible[:max_entries]:
        try:
            if entry.is_symlink():
                lines.append(f"{entry.name}@")
            elif entry.is_dir(follow_symlinks=False):
                lines.append(f"{entry.name}/")
            else:
                lines.append(entry.name)
        except OSError:
            # A racing entry is represented as a plain name rather than dereferenced.
            lines.append(entry.name)
    if len(visible) > max_entries:
        lines.append(f"... listing truncated at {max_entries} entries")
    return "\n".join(lines) if lines else "(empty directory)"


def _iter_regular_files(root: Path, *, jail_root: Path):
    """Yield regular files under ``root`` deterministically, never following symlinks."""

    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            mode = current.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISLNK(mode):
            continue
        if stat.S_ISREG(mode):
            yield current
            continue
        if not stat.S_ISDIR(mode):
            continue
        try:
            with os.scandir(current) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name, reverse=True)
        except OSError:
            continue
        for entry in entries:
            if entry.name in _RESERVED_DIRECTORY_NAMES:
                continue
            child = Path(entry.path)
            try:
                child.relative_to(jail_root)
            except ValueError:
                continue
            if entry.is_symlink():
                continue
            # reverse-sorted insertion makes the LIFO traversal lexically ascending.
            stack.append(child)


def grep(
    target_root: Path,
    pattern: str,
    *,
    path: str = ".",
    max_matches: int = DEFAULT_MAX_MATCHES,
    max_scanned_files: int = DEFAULT_MAX_SCANNED_FILES,
    max_scanned_bytes: int = DEFAULT_MAX_SCANNED_BYTES,
    max_bytes_per_file: int = DEFAULT_MAX_READ_BYTES,
) -> str:
    """Search for a literal substring under deterministic file/byte/match bounds."""

    if not pattern:
        raise ToolRefusal("grep needs a non-empty pattern")
    if min(max_matches, max_scanned_files, max_scanned_bytes, max_bytes_per_file) <= 0:
        raise ToolRefusal("grep bounds must be positive")

    root = Path(target_root).expanduser().resolve(strict=True)
    search_root = resolve_in_jail(root, path, allow_root=True)
    if not search_root.exists():
        raise ToolRefusal(f"path not found: {path}")

    matches: list[str] = []
    scanned_files = 0
    scanned_bytes = 0
    truncated = False

    for file_path in _iter_regular_files(search_root, jail_root=root):
        if scanned_files >= max_scanned_files or scanned_bytes >= max_scanned_bytes:
            truncated = True
            break

        relative = file_path.relative_to(root)
        remaining_total = max_scanned_bytes - scanned_bytes
        read_cap = min(max_bytes_per_file, remaining_total)
        if read_cap <= 0:
            truncated = True
            break

        try:
            data, file_truncated = _read_bounded_bytes(
                file_path, max_bytes=read_cap, raw_path=str(relative)
            )
        except ToolRefusal:
            continue
        scanned_files += 1
        scanned_bytes += len(data)
        if file_truncated:
            truncated = True

        text = data.decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern not in line:
                continue
            if len(matches) >= max_matches:
                truncated = True
                break
            matches.append(f"{relative}:{line_number}:{line.strip()[:400]}")
        if len(matches) >= max_matches:
            break

    if not matches:
        suffix = (
            f"; scan truncated after {scanned_files} files / {scanned_bytes} bytes"
            if truncated
            else ""
        )
        return f"no matches for {pattern!r} under {path}{suffix}"
    if truncated:
        matches.append(
            "... results truncated "
            f"(scanned {scanned_files} files / {scanned_bytes} bytes)"
        )
    return "\n".join(matches)
