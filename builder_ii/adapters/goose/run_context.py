"""Run identity and immutable context for governed Goose execution.

A timestamp is useful metadata and a poor identity: two runs may start in the same second,
and a path is a location rather than an identity.  Governed runs therefore receive a
random UUID-derived ``run_id`` and a session id derived from it.  Artifact identities stay
content digests; the run id merely namespaces lifecycle/control state.

This object grants no authority.  It is immutable descriptive context shared by the CLI,
runtime harness, and operator control plane.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunContext:
    run_id: str
    session_id: str
    target_root: Path
    builder_root: Path

    @classmethod
    def create(
        cls,
        *,
        target_root: Path,
        builder_root: Path | None = None,
        run_id: str | None = None,
    ) -> "RunContext":
        resolved_target = Path(target_root).expanduser().resolve()
        resolved_builder = (
            Path(builder_root).expanduser().resolve()
            if builder_root is not None
            else resolved_target / ".builder"
        )
        candidate = (run_id or uuid.uuid4().hex).strip().lower()
        if not candidate:
            raise ValueError("run_id must be non-empty")
        # Path-safe, explicit alphabet.  Callers may inject deterministic ids in tests, but
        # ambient/user strings cannot smuggle separators into evidence directories.
        if not all(char.isalnum() or char in ("-", "_") for char in candidate):
            raise ValueError("run_id may contain only letters, digits, '-' and '_'")
        return cls(
            run_id=candidate,
            session_id=f"goose_{candidate}",
            target_root=resolved_target,
            builder_root=resolved_builder,
        )


__all__ = ["RunContext"]
