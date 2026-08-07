"""Bounded, path-jailed repo reads for the governed tool path.

The governed MCP server advertised exactly two tools -- ``echo`` and ``utc_static`` -- which
made the interposition seam real but left a governed Goose session unable to do anything at
all: it could not read a file, list a directory, or search the tree. The seam was honest and
useless. These are the read primitives that make a governed session worth starting, and they
are deliberately the *only* ones: no write, no shell, no network, no git.

Every function here is pure in-process Python. Nothing in this module spawns a subprocess --
which is why the receipts the gateway writes can keep declaring ``executes_shell: False`` and
``shell_execution: DISABLED`` without qualification. A ``git_status`` tool was considered and
left out for exactly that reason: it would have been the first subprocess on a path whose whole
contract is that it has none, and `builder-git-state` already covers that need outside the
low-risk lane.

The jail is the same one `goose_inspection.py` uses, for the same reason: a relative path that
resolves outside the target root, walks through ``..``, or enters ``.git``/``.builder`` is
refused before any I/O. Refusal is a value, not an exception -- the caller turns it into a
denied receipt, so a rejected read is as ledgered as a permitted one.

Bounds are per-call and total, because "read the repo" must not mean "read all of it into one
tool response": files are capped by bytes, listings and searches by entry/match/file count, and
every traversal is deterministically ordered so the same call yields the same output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Per-file read ceiling. Matches `goose_inspection.DEFAULT_MAX_READ_BYTES`.
DEFAULT_MAX_READ_BYTES = 65536

#: Directory-listing ceiling, so one call on a large tree cannot flood the transcript.
DEFAULT_MAX_ENTRIES = 500

#: Search ceilings: matches returned, and files opened while looking for them.
DEFAULT_MAX_MATCHES = 200
DEFAULT_MAX_SCANNED_FILES = 2000

#: Directories never traversed or read. `.git` is history and `.builder` is the governance
#: evidence itself -- a tool that could read the ledger it is being recorded in invites exactly
#: the confusion between acting and being audited that this codebase exists to keep apart.
_RESERVED_DIRECTORY_NAMES = (".git", ".builder")


@dataclass(frozen=True)
class ToolRefusal(Exception):
    """A read the jail refused. Carries operator-facing text; never a stack trace."""

    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.reason


def _reserved(path: Path) -> bool:
    return any(part in _RESERVED_DIRECTORY_NAMES for part in path.parts)


def resolve_in_jail(target_root: Path, raw_path: str, *, allow_root: bool = False) -> Path:
    """Resolve a caller-supplied relative path inside the target root, or refuse.

    Refuses absolute paths, ``..`` traversal, and reserved directories before touching the
    filesystem, then confirms the *resolved* path is still inside the root -- which is the check
    that catches a symlink pointing out of the tree, the one the string checks alone would miss.
    """
    candidate_rel = Path(raw_path.strip() or ".")
    if candidate_rel.is_absolute():
        raise ToolRefusal(f"path must be relative to the target root: {raw_path}")
    if ".." in candidate_rel.parts:
        raise ToolRefusal(f"path must not contain '..': {raw_path}")
    if _reserved(candidate_rel):
        raise ToolRefusal(f"path must not enter {' or '.join(_RESERVED_DIRECTORY_NAMES)}: {raw_path}")
    if not allow_root and str(candidate_rel) == ".":
        raise ToolRefusal("path must name a file")

    try:
        root = Path(target_root).expanduser().resolve()
        resolved = (root / candidate_rel).resolve()
        resolved.relative_to(root)
    except ValueError:
        # Covers the symlink-out-of-tree case: the string was clean, the resolution was not.
        raise ToolRefusal(f"path escapes the target root: {raw_path}") from None
    except OSError as exc:
        raise ToolRefusal(f"failed to resolve path {raw_path}: {exc}") from None

    # A symlink whose *resolved* target is inside the root is fine; one that left is refused
    # above. Re-checking the reserved names on the resolved path closes the link-into-.git case.
    if _reserved(resolved.relative_to(Path(target_root).expanduser().resolve())):
        raise ToolRefusal(f"path resolves into a reserved directory: {raw_path}")
    return resolved


def read_file(target_root: Path, raw_path: str, *, max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
    """Return a file's text, bounded by ``max_bytes``, or refuse."""
    resolved = resolve_in_jail(target_root, raw_path)
    if not resolved.exists():
        raise ToolRefusal(f"path not found: {raw_path}")
    if not resolved.is_file():
        raise ToolRefusal(f"path is not a file: {raw_path}")
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise ToolRefusal(f"failed to read {raw_path}: {exc}") from None

    if len(data) > max_bytes:
        # Truncate rather than refuse: a large file the agent asked for by name should return
        # its head, and the gateway's own output cap plus `output_truncated` record the cut.
        data = data[:max_bytes]
    return data.decode("utf-8", errors="replace")


def list_dir(target_root: Path, raw_path: str = ".", *, max_entries: int = DEFAULT_MAX_ENTRIES) -> str:
    """Return a deterministic, bounded directory listing, or refuse.

    Directories are suffixed ``/`` so the caller can tell them apart without a second call.
    """
    resolved = resolve_in_jail(target_root, raw_path, allow_root=True)
    if not resolved.exists():
        raise ToolRefusal(f"path not found: {raw_path}")
    if not resolved.is_dir():
        raise ToolRefusal(f"path is not a directory: {raw_path}")

    try:
        entries = sorted(resolved.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        raise ToolRefusal(f"failed to list {raw_path}: {exc}") from None

    lines: list[str] = []
    for entry in entries:
        if entry.name in _RESERVED_DIRECTORY_NAMES:
            continue
        if len(lines) >= max_entries:
            lines.append(f"... listing truncated at {max_entries} entries")
            break
        lines.append(f"{entry.name}/" if entry.is_dir() else entry.name)
    return "\n".join(lines) if lines else "(empty directory)"


def grep(
    target_root: Path,
    pattern: str,
    *,
    path: str = ".",
    max_matches: int = DEFAULT_MAX_MATCHES,
    max_scanned_files: int = DEFAULT_MAX_SCANNED_FILES,
) -> str:
    """Return ``path:line:text`` for a literal substring match, bounded and deterministic.

    A literal substring, not a regex: a caller-supplied regex on an unbounded tree is a CPU
    denial-of-service the governed lane has no way to interrupt, and the agent can narrow with
    ``path`` instead. Traversal order is sorted so repeated calls agree.
    """
    if not pattern:
        raise ToolRefusal("grep needs a non-empty pattern")
    root_dir = resolve_in_jail(target_root, path, allow_root=True)
    if not root_dir.exists():
        raise ToolRefusal(f"path not found: {path}")

    jail_root = Path(target_root).expanduser().resolve()
    candidates = [root_dir] if root_dir.is_file() else sorted(
        (p for p in root_dir.rglob("*") if p.is_file()), key=lambda p: str(p)
    )

    matches: list[str] = []
    scanned = 0
    truncated = False
    for file_path in candidates:
        try:
            relative = file_path.relative_to(jail_root)
        except ValueError:
            continue
        if _reserved(relative):
            continue
        if scanned >= max_scanned_files:
            truncated = True
            break
        scanned += 1
        try:
            if file_path.stat().st_size > DEFAULT_MAX_READ_BYTES:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern in line:
                if len(matches) >= max_matches:
                    truncated = True
                    break
                matches.append(f"{relative}:{line_number}:{line.strip()[:400]}")
        if truncated:
            break

    if not matches:
        return f"no matches for {pattern!r} under {path}"
    if truncated:
        matches.append(f"... results truncated (scanned {scanned} files)")
    return "\n".join(matches)
