"""HITL Approve/Reject compose helpers — pure, no Textual I/O.

STRATUM never harvests digests or mutates approval state. These helpers only
build fully-bound CLI strings (or refuse) so the Command Composer is never
prefilled with a bare incomplete prefix such as ``builder-hitl approve-patch``
without ``--proposal`` / ``--output``.

Reject for a patch proposal is ``builder-hitl refuse-patch`` (passive refusal
artifact), **not** promotion ``rejection-record`` (wrong kind / wrong ceremony).
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HitlComposeResult:
    """Outcome of attempting to compose a HITL A/R CLI line."""

    command: str | None
    """Fully-bound CLI string, or None when compose is refused."""

    refused: bool
    reason: str
    """Operator-facing explanation (shown via notify)."""


def _quote(path: str | Path) -> str:
    return shlex.quote(str(path))


def _proposal_path_from_gate(proposal: dict[str, Any] | None) -> str | None:
    if not proposal:
        return None
    path = proposal.get("path")
    if isinstance(path, Path):
        path = str(path)
    if isinstance(path, str) and path.strip():
        return path.strip()
    return None


def _proposal_kind(proposal: dict[str, Any] | None) -> str:
    if not proposal:
        return ""
    artifact = proposal.get("artifact")
    if isinstance(artifact, dict):
        kind = artifact.get("kind")
        if isinstance(kind, str):
            return kind
    kind = proposal.get("kind")
    return kind if isinstance(kind, str) else ""


def default_approve_output_path(proposal_path: str, artifacts_dir: Path | None) -> Path:
    """Deterministic default approval path next to the proposal or under artifacts."""
    prop = Path(proposal_path)
    sibling = prop.with_name(f"{prop.stem}-approval.json")
    if sibling.parent.is_dir() or prop.parent.exists():
        return sibling
    if artifacts_dir is not None:
        return artifacts_dir / "hitl-patch-approval.json"
    return Path(".builder/artifacts/hitl-patch-approval.json")


def default_refuse_output_path(proposal_path: str, artifacts_dir: Path | None) -> Path:
    prop = Path(proposal_path)
    sibling = prop.with_name(f"{prop.stem}-refusal.json")
    if sibling.parent.is_dir() or prop.parent.exists():
        return sibling
    if artifacts_dir is not None:
        return artifacts_dir / "hitl-patch-refusal.json"
    return Path(".builder/artifacts/hitl-patch-refusal.json")


def compose_hitl_approve(
    proposal: dict[str, Any] | None,
    *,
    artifacts_dir: Path | None = None,
) -> HitlComposeResult:
    """Compose a complete ``builder-hitl approve-patch`` line, or refuse if unbound."""
    path = _proposal_path_from_gate(proposal)
    if not path:
        return HitlComposeResult(
            command=None,
            refused=True,
            reason=(
                "HITL Approve refused: no bound proposal path. "
                "STRATUM will not compose a bare `builder-hitl approve-patch` prefix."
            ),
        )
    out = default_approve_output_path(path, artifacts_dir)
    cmd = (
        f"uv run builder-hitl approve-patch "
        f"--proposal {_quote(path)} --output {_quote(out)}"
    )
    return HitlComposeResult(
        command=cmd,
        refused=False,
        reason=(
            "TUI cannot harvest confirmation for a digest it renders; "
            "composing bound `builder-hitl approve-patch` for your terminal."
        ),
    )


def compose_hitl_reject(
    proposal: dict[str, Any] | None,
    *,
    artifacts_dir: Path | None = None,
    rationale: str = "operator refused via STRATUM compose",
) -> HitlComposeResult:
    """Compose a patch-refuse ceremony, or refuse if unbound / wrong family.

    Patch proposals → ``builder-hitl refuse-patch`` (kind-correct passive refusal).
    Never composes promotion ``rejection-record`` for a patch proposal.
    """
    path = _proposal_path_from_gate(proposal)
    if not path:
        return HitlComposeResult(
            command=None,
            refused=True,
            reason=(
                "HITL Reject refused: no bound proposal path. "
                "STRATUM will not compose a bare or wrong-kind rejection CLI."
            ),
        )

    kind = _proposal_kind(proposal).lower()
    # Promotion-bridge only — still require bound request path + full flags.
    if "promotion" in kind and "request" in kind:
        out = (
            Path(path).with_name(f"{Path(path).stem}-rejection.json")
            if Path(path).parent.exists()
            else (artifacts_dir or Path(".builder/artifacts")) / "hitl-promotion-rejection.json"
        )
        cmd = (
            f"uv run builder-hitl rejection-record "
            f"--request-path {_quote(path)} --output {_quote(out)} "
            f"--rationale {_quote(rationale)}"
        )
        return HitlComposeResult(
            command=cmd,
            refused=False,
            reason=(
                "STRATUM is display-only; composing bound promotion "
                "`builder-hitl rejection-record` for your terminal."
            ),
        )

    # Default / patch proposal path: refuse-patch, never promotion rejection-record.
    out = default_refuse_output_path(path, artifacts_dir)
    cmd = (
        f"uv run builder-hitl refuse-patch "
        f"--proposal {_quote(path)} --output {_quote(out)} "
        f"--rationale {_quote(rationale)}"
    )
    return HitlComposeResult(
        command=cmd,
        refused=False,
        reason=(
            "STRATUM is display-only and cannot mutate approval state; "
            "composing bound `builder-hitl refuse-patch` (not promotion rejection-record)."
        ),
    )
