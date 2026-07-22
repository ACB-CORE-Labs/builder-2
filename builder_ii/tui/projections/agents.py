"""Deepagents profile roster projection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentProfileView:
    name: str
    description: str
    authority: str
    allowed_tools: tuple[str, ...]
    yaml_path: str | None


@dataclass(frozen=True)
class AgentRosterView:
    profiles: tuple[AgentProfileView, ...]
    readiness_verdict: str
    dependency_state: str
    required_gates: tuple[str, ...]
    disabled_capabilities: tuple[str, ...]
    error: str | None = None


def project_agent_roster(*, target: str = "generic", profiles_dir: Path | None = None) -> AgentRosterView:
    profiles: list[AgentProfileView] = []
    readiness_verdict = "—"
    dependency_state = "—"
    required_gates: tuple[str, ...] = ()
    disabled_capabilities: tuple[str, ...] = ()
    error: str | None = None

    yaml_index: dict[str, Path] = {}
    search_roots: list[Path] = []
    if profiles_dir is not None:
        search_roots.append(profiles_dir)
    # Conventional repo location relative to package
    pkg_root = Path(__file__).resolve().parents[2].parent  # builder_ii/tui/projections -> repo root
    search_roots.append(pkg_root / "profiles" / "deepagents")
    for root in search_roots:
        if root.is_dir():
            for path in root.glob("*.yaml"):
                yaml_index[path.stem] = path

    try:
        from builder_ii.routing.agent_profiles import agent_profiles

        for p in agent_profiles():
            yaml_path = yaml_index.get(p.name)
            profiles.append(
                AgentProfileView(
                    name=p.name,
                    description=p.description,
                    authority=p.authority,
                    allowed_tools=tuple(p.allowed_tools),
                    yaml_path=str(yaml_path) if yaml_path else None,
                )
            )
    except Exception as exc:
        error = f"agent profiles: {exc}"

    try:
        from builder_ii.adapters.deepagents.deepagents_bridge_readiness import create_deepagents_bridge_readiness_report

        report = create_deepagents_bridge_readiness_report(
            target_profile=target,
            agent_profile_compatibility_summary=f"{len(profiles)} profiles loaded",
        )
        readiness_verdict = str(report.get("readiness_verdict") or "—")
        dependency_state = str(report.get("optional_dependency_state") or "—")
        gates = report.get("required_promotion_gates") or []
        caps = report.get("disabled_capabilities") or []
        required_gates = tuple(str(g) for g in gates)
        disabled_capabilities = tuple(str(c) for c in caps)
    except Exception as exc:
        if error:
            error = f"{error}; readiness: {exc}"
        else:
            error = f"readiness: {exc}"

    return AgentRosterView(
        profiles=tuple(profiles),
        readiness_verdict=readiness_verdict,
        dependency_state=dependency_state,
        required_gates=required_gates,
        disabled_capabilities=disabled_capabilities,
        error=error,
    )


def compose_assign_command(profile_name: str, *, target: str = "generic") -> str:
    """Exact compose string for the governed assign-subagent CLI (operator fills remaining flags)."""
    return (
        f"uv run builder-deepagents assign-subagent --target {target} "
        f"--subagent-profile {profile_name} --task \"…\" "
        f"--work-plan .builder/artifacts/work-plan.json"
    )


def compose_deepagents_commands(*, target: str = "generic") -> dict[str, str]:
    """Catalog of common governed deepagents compose lines."""
    return {
        "forge": "uv run builder-deepagents forge",
        "forge_dry": (
            "uv run builder-deepagents forge --dry-run --non-interactive "
            "--name example --profile generic"
        ),
        "policy": (
            f"uv run builder-deepagents policy --target {target} "
            f"--output .builder/artifacts/deepagents-policy.json"
        ),
        "readiness": "uv run builder-deepagents readiness --output .builder/artifacts/deepagents-readiness.json",
        "work_plan": "uv run builder-deepagents work-plan --help",
    }
