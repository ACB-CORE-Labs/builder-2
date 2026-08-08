"""Durable same-directory atomic writes for governed evidence.

Governance artifacts are useful only when a reader can distinguish a committed file from
one truncated by process death.  These helpers write to a temporary sibling, flush and
``fsync`` it, then ``os.replace`` into the final path.  The parent directory is synced on
platforms that permit it so the rename itself is durable across a crash.

The helpers do not grant authority or validate artifact semantics; callers must validate
objects before commit and may layer content-addressed naming on top.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync; unsupported filesystems/platforms may refuse it."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Atomically replace ``path`` with exactly ``data`` after flushing the temp file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temp_path = Path(temp_name)
    try:
        try:
            os.fchmod(fd, mode)
        except OSError:
            pass
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
        _fsync_directory(destination.parent)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


def atomic_write_json(
    path: Path,
    data: dict[str, Any],
    *,
    sort_keys: bool = True,
    mode: int = 0o600,
) -> None:
    atomic_write_text(
        path,
        json.dumps(data, indent=2, sort_keys=sort_keys) + "\n",
        mode=mode,
    )


__all__ = ["atomic_write_bytes", "atomic_write_json", "atomic_write_text"]
