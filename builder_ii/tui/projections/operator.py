"""Operator dashboard projection for STRATUM idle mode."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from builder_ii.tui.projections.chain import epistemic_from_chain, project_chain

#: Canonical memory-index filename under an artifacts dir. Same file the operator status report
#: reads (`operator_status.py`); named once here so the idle HUD cannot drift from it.
MEMORY_INDEX_FILENAME = "memory-index.json"


@dataclass(frozen=True)
class NextActionView:
    capability: str
    state: str
    reason: str
    safe_command: str | None


@dataclass(frozen=True)
class OperatorDashboardView:
    platform: str
    target: str
    model: str
    backend: str
    session: str
    chain_length: int
    chain_valid: bool | None
    memory_atoms: int
    ledger_active: bool
    next_action: NextActionView | None
    epistemic: dict[str, str]
    capability_summary: str
    warnings: tuple[str, ...] = ()


def project_operator_dashboard(
    *,
    artifacts_dir: Path | None,
    target: str = "generic",
    model: str = "—",
    backend: str = "—",
    session: str = "idle",
) -> OperatorDashboardView:
    chain = project_chain(artifacts_dir)
    epistemic = epistemic_from_chain(chain)

    next_action: NextActionView | None = None
    capability_summary = "—"
    warnings: list[str] = []
    memory_atoms = 0

    try:
        from builder_ii.operator_status import create_operator_status_report

        status = create_operator_status_report(target=target)
        counts = status.get("capability_counts") or {}
        if isinstance(counts, dict) and counts:
            parts = [f"{k}:{v}" for k, v in sorted(counts.items())]
            capability_summary = " · ".join(parts)
        mem = status.get("memory_status") or {}
        if isinstance(mem, dict):
            memory_atoms = int(mem.get("atom_count") or 0)
        for w in status.get("warnings") or []:
            warnings.append(str(w))
    except Exception as exc:
        warnings.append(f"operator_status unavailable: {exc}")

    try:
        from builder_ii.operator_next import create_operator_next_action_report

        report = create_operator_next_action_report()
        actions = report.get("ordered_next_actions") or []
        if actions:
            first = actions[0]
            cmds = first.get("safe_commands") or []
            next_action = NextActionView(
                capability=str(first.get("capability", "—")),
                state=str(first.get("state", "—")),
                reason=str(first.get("reason", "")),
                safe_command=str(cmds[0]) if cmds else None,
            )
        capability_summary = report.get("current_state_summary") or capability_summary
    except Exception as exc:
        warnings.append(f"operator_next unavailable: {exc}")

    return OperatorDashboardView(
        platform="builder-II",
        target=target,
        model=model,
        backend=backend,
        session=session,
        chain_length=chain.file_count,
        chain_valid=chain.chain_valid,
        memory_atoms=memory_atoms,
        ledger_active=bool(artifacts_dir and artifacts_dir.exists()),
        next_action=next_action,
        epistemic=epistemic,
        capability_summary=str(capability_summary),
        warnings=tuple(warnings),
    )


def chain_validity_display(chain_valid: bool | None) -> tuple[str, str]:
    """Return (display_text, token) for chain validity — never invents truth."""
    if chain_valid is True:
        return "TRUE", "pass"
    if chain_valid is False:
        return "FALSE", "fail"
    return "—", "hint"


def count_artifact_files(artifacts_dir: Path | None) -> int:
    """Number of ``*.json`` artifacts under ``artifacts_dir`` — the STRATUM idle report's chain
    length, computed cheaply.

    This is the same file count ``_verify_current_chain_async`` reports (it counts the very same
    ``glob("*.json")`` before verifying), but a *count* is not a validity claim and needs no
    verification: it can be read on the UI thread without invoking the heavy chain verifier. ``0``
    means the directory was read and holds no artifacts — never a fabricated placeholder.
    """
    if artifacts_dir is None or not artifacts_dir.exists():
        return 0
    return sum(1 for path in artifacts_dir.glob("*.json") if path.is_file())


def memory_atom_display(artifacts_dir: Path | None) -> str:
    """Real memory-index ``atom_count`` as a string, or ``"—"`` when there is no index to read.

    ``"0"`` is shown *only* when an index exists and truthfully carries zero atoms; the absence of
    an index reads as ``"—"`` (unknown), never as a fabricated zero — the same distinction
    ``chain_validity_display`` draws between ``FALSE`` and ``—``. This reads the same
    ``memory-index.json`` / ``atom_count`` that the operator status report and ``builder-platform``
    surface, so the idle HUD cannot disagree with them.
    """
    if artifacts_dir is None:
        return "—"
    index_path = artifacts_dir / MEMORY_INDEX_FILENAME
    if not index_path.is_file():
        return "—"
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return "—"
    count = data.get("atom_count") if isinstance(data, dict) else None
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return "—"
    return str(count)


def idle_report_stats(artifacts_dir: Path | None) -> tuple[str, str]:
    """``(memory_atoms, chain_length)`` for the STRATUM idle HUD — best-effort.

    These are the only synchronous filesystem reads on the TUI mount path, so a read that raises
    must degrade to ``"—"`` rather than propagate and crash the app at mount — the same posture the
    ``_verify_current_chain_async`` sibling read takes with its own ``try/except``. On a real
    ``Path`` (or ``None``) the underlying readers never raise; the guard is what lets mount survive
    a caller that hands over something other than a real path.

    The honest per-value logic still lives in ``memory_atom_display`` / ``count_artifact_files`` and
    is unit-tested there on real paths; this only adds the never-raise integration contract.
    """
    try:
        return memory_atom_display(artifacts_dir), str(count_artifact_files(artifacts_dir))
    except Exception:
        return "—", "—"
