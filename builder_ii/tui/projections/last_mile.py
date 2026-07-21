"""Last-mile HUD projection — budget · seam · ledger tail · measured cost.

Read-only. Never debits budgets, never invokes the seam, never appends events.
Scans known on-disk artifact locations under ``.builder/`` and fails closed to
honest absence markers (``—`` / ``none``) when data is missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LastMileHudView:
    budget: str
    seam: str
    ledger_tail: str
    cost: str
    budget_detail: str = ""
    seam_detail: str = ""
    cost_detail: str = ""


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _builder_root(artifacts_dir: Path | None) -> Path | None:
    """Return ``.builder`` only when the path is clearly under that layout.

    Must not walk into arbitrary parents (e.g. pytest tmp roots) or the HUD
    would invent budget/seam signals from unrelated trees on the host.
    """
    if artifacts_dir is None:
        return None
    # artifacts_dir is typically <root>/.builder/artifacts
    if artifacts_dir.name == "artifacts" and artifacts_dir.parent.name == ".builder":
        return artifacts_dir.parent
    if artifacts_dir.name == ".builder":
        return artifacts_dir
    parent = artifacts_dir.parent
    if parent.name == ".builder":
        return parent
    return None


def _find_latest_by_kind(roots: list[Path], kind: str) -> tuple[Path, dict[str, Any]] | None:
    hits: list[tuple[float, Path, dict[str, Any]]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            data = _read_json(path)
            if data is None:
                continue
            if str(data.get("kind", "")) != kind:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            hits.append((mtime, path, data))
    if not hits:
        return None
    hits.sort(key=lambda x: x[0], reverse=True)
    _m, path, data = hits[0]
    return path, data


def _project_budget(roots: list[Path]) -> tuple[str, str]:
    from builder_ii.routing.model_budget import MODEL_BUDGET_KIND, remaining, validate_model_budget

    hit = _find_latest_by_kind(roots, MODEL_BUDGET_KIND)
    if hit is None:
        return "—", "no model_budget on disk"
    _path, budget = hit
    if validate_model_budget(budget):
        return "—", "model_budget present but invalid"
    try:
        rem = remaining(budget)
    except Exception:
        return "—", "model_budget unreadable"
    state = str(budget.get("budget_state") or "?")
    tok = int(rem.get("total_tokens") or 0)
    usd = float(rem.get("usd") or 0.0)
    line = f"{state} · {tok} tok · ${usd:.4f} rem"
    detail = f"spent ${float(budget.get('spent_usd') or 0):.4f} / max ${float(budget.get('max_usd') or 0):.4f}"
    return line, detail


def _project_seam(roots: list[Path]) -> tuple[str, str]:
    """Seam mode from latest run_manifest / receipt markers — honest absence when none."""
    from builder_ii.core.run_manifest import RUN_MANIFEST_KIND

    hit = _find_latest_by_kind(roots, RUN_MANIFEST_KIND)
    if hit is None:
        # Look for gateway receipt-like kinds
        for kind_frag, label in (
            ("model_execution_receipt", "receipt"),
            ("invoke_local", "local"),
            ("invoke_cloud", "cloud"),
        ):
            for root in roots:
                if not root.is_dir():
                    continue
                for path in root.rglob("*.json"):
                    data = _read_json(path)
                    if data is None:
                        continue
                    kind = str(data.get("kind") or "").lower()
                    if kind_frag in kind:
                        mode = str(data.get("invoke_mode") or data.get("seam_mode") or label)
                        return str(mode), path.name
        return "none", "no seam receipt / run_manifest"
    _path, manifest = hit
    model = str(manifest.get("model_id") or "—")
    return f"manifest · {model}", _path.name


def _project_ledger_tail(roots: list[Path], builder_root: Path | None) -> str:
    event_dirs: list[Path] = []
    for root in roots:
        events = root / "events"
        if events.is_dir():
            event_dirs.append(events)
    if builder_root is not None:
        sessions = builder_root / "sessions"
        if sessions.is_dir():
            for sess in sessions.iterdir():
                ev = sess / "events"
                if ev.is_dir():
                    event_dirs.append(ev)

    latest: tuple[float, str] | None = None
    for edir in event_dirs:
        for path in edir.glob("*.json"):
            data = _read_json(path)
            if data is None:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            summary = str(
                data.get("message")
                or data.get("summary")
                or data.get("event_type")
                or path.name
            )[:48]
            if latest is None or mtime > latest[0]:
                latest = (mtime, summary)
    if latest is None:
        return "—"
    return latest[1]


def _project_cost(roots: list[Path]) -> tuple[str, str]:
    """Measured cost from latest cost_report fields on disk, else —."""
    best: tuple[float, str, str] | None = None
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            data = _read_json(path)
            if data is None:
                continue
            report = data.get("cost_report") if isinstance(data.get("cost_report"), dict) else None
            if report is None and "estimated_usd_total" in data:
                report = data
            if report is None:
                continue
            usd = report.get("estimated_usd_total")
            tokens = report.get("total_tokens") or report.get("measured_total_tokens")
            if usd is None and tokens is None:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            parts: list[str] = []
            if tokens is not None:
                parts.append(f"{int(tokens)} tok")
            if usd is not None:
                try:
                    parts.append(f"${float(usd):.4f}")
                except (TypeError, ValueError):
                    parts.append(f"${usd}")
            honesty = "measured" if report.get("measured") or report.get("tokenizer_id") else "est"
            line = f"{' · '.join(parts)} ({honesty})" if parts else "—"
            if best is None or mtime > best[0]:
                best = (mtime, line, path.name)
    if best is None:
        return "—", "no cost_report on disk"
    return best[1], best[2]


def project_last_mile_hud(artifacts_dir: Path | None) -> LastMileHudView:
    """Project always-on last-mile strip from on-disk substrate."""
    builder = _builder_root(artifacts_dir)
    roots: list[Path] = []
    if artifacts_dir is not None:
        roots.append(artifacts_dir)
    if builder is not None:
        for name in ("artifacts", "session", "receipts", "goose", "budget", "ledger"):
            p = builder / name
            if p.is_dir() and p not in roots:
                roots.append(p)
        roots.append(builder)

    budget, budget_detail = _project_budget(roots)
    seam, seam_detail = _project_seam(roots)
    ledger = _project_ledger_tail(roots, builder)
    cost, cost_detail = _project_cost(roots)

    return LastMileHudView(
        budget=budget,
        seam=seam,
        ledger_tail=ledger,
        cost=cost,
        budget_detail=budget_detail,
        seam_detail=seam_detail,
        cost_detail=cost_detail,
    )


def format_last_mile_hud_lines(view: LastMileHudView) -> tuple[str, str, str, str]:
    """Plain label lines for widgets / tests (no Rich markup)."""
    return (
        f"budget  {view.budget}",
        f"seam    {view.seam}",
        f"ledger  {view.ledger_tail}",
        f"cost    {view.cost}",
    )
