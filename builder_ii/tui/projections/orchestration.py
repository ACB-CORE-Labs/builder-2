"""Orchestration plan / obligation / assignment projection (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ORCH_KIND_FRAGMENTS = (
    "orchestration_plan",
    "orchestration_assignment",
    "orchestration_obligation",
    "lane_policy",
    "agent_assignment",
)


@dataclass(frozen=True)
class OrchArtifactView:
    kind: str
    path: str
    summary: str


@dataclass(frozen=True)
class OrchestrationView:
    plans: tuple[OrchArtifactView, ...]
    obligations: tuple[OrchArtifactView, ...]
    other: tuple[OrchArtifactView, ...]
    compose_plan: str
    compose_lane_policy: str
    compose_status: str
    error: str | None = None


def _summarize(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("task", "target", "orchestration_mode", "status", "obligation_id", "lane"):
        val = data.get(key)
        if val is not None and val != "":
            parts.append(f"{key}={val}")
    roles = data.get("roles") or data.get("role_sequence")
    if isinstance(roles, list) and roles:
        parts.append("roles=" + ",".join(str(r) for r in roles[:4]))
    return " · ".join(parts) if parts else str(data.get("kind", "—"))


def _scan(artifacts_dir: Path | None) -> list[tuple[Path, dict[str, Any]]]:
    if artifacts_dir is None or not artifacts_dir.exists():
        return []
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(artifacts_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        kind = str(data.get("kind", "")).lower()
        if any(frag in kind for frag in _ORCH_KIND_FRAGMENTS):
            found.append((path, data))
    return found


def project_orchestration(
    *,
    artifacts_dir: Path | None,
    target: str = "generic",
) -> OrchestrationView:
    plans: list[OrchArtifactView] = []
    obligations: list[OrchArtifactView] = []
    other: list[OrchArtifactView] = []
    error: str | None = None
    try:
        for path, data in _scan(artifacts_dir):
            kind = str(data.get("kind", "—"))
            view = OrchArtifactView(kind=kind, path=str(path), summary=_summarize(data))
            kl = kind.lower()
            if "obligation" in kl:
                obligations.append(view)
            elif "plan" in kl or "assignment" in kl:
                plans.append(view)
            else:
                other.append(view)
    except Exception as exc:
        error = str(exc)

    return OrchestrationView(
        plans=tuple(plans[:20]),
        obligations=tuple(obligations[:20]),
        other=tuple(other[:20]),
        compose_plan=(
            f"uv run builder-orchestration plan {target} "
            f'--task "…" --roles repo_mapper,code_reviewer '
            f"-o .builder/artifacts/orch-plan.json"
        ),
        compose_lane_policy=(
            "uv run builder-orchestration lane-policy -o .builder/artifacts/lane-policy.json"
        ),
        compose_status="uv run builder-orchestration status --help",
        error=error,
    )
