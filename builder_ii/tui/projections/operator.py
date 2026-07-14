"""Operator dashboard projection for STRATUM idle mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from builder_ii.tui.projections.chain import epistemic_from_chain, project_chain


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
