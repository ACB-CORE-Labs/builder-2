from __future__ import annotations

import json as json_lib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.target_profiles import TargetName, target_names

ResearchProfileName = Literal["research_planner", "source_mapper", "evidence_synthesizer", "report_reviewer"]
RESEARCH_PLAN_KIND = "builder_ii.research_plan"
RESEARCH_PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ResearchProfile:
    name: ResearchProfileName
    description: str
    source_strategy: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    report_contract: tuple[str, ...]
    known_unknowns: tuple[str, ...]
    failure_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source_strategy": list(self.source_strategy),
            "evidence_requirements": list(self.evidence_requirements),
            "report_contract": list(self.report_contract),
            "known_unknowns": list(self.known_unknowns),
            "failure_mode": self.failure_mode,
        }


def research_profiles() -> tuple[ResearchProfile, ...]:
    return (
        ResearchProfile(
            name="research_planner",
            description="Plans bounded research tasks without running search or tools.",
            source_strategy=("define research question", "list source categories", "record source gaps"),
            evidence_requirements=("explicit question", "source categories", "claim boundary"),
            report_contract=("research plan", "known unknowns", "review blockers"),
            known_unknowns=("actual source contents are not collected",),
            failure_mode="If scope is unclear, require human clarification before collection.",
        ),
        ResearchProfile(
            name="source_mapper",
            description="Maps candidate source types and repository locations without fetching them.",
            source_strategy=("map docs", "map repositories", "rank sources by authority"),
            evidence_requirements=("source rationale", "authority ranking", "collection remains disabled"),
            report_contract=("source map", "collection steps", "permission notes"),
            known_unknowns=("source contents remain unknown",),
            failure_mode="If source authority is ambiguous, mark the source as review-required.",
        ),
        ResearchProfile(
            name="evidence_synthesizer",
            description="Plans how evidence would be synthesized after approved collection.",
            source_strategy=("group evidence by claim", "flag contradictions", "track citation needs"),
            evidence_requirements=("claim categories", "contradiction handling", "citation expectations"),
            report_contract=("synthesis plan", "uncertainty notes", "unresolved claims"),
            known_unknowns=("no evidence has been collected",),
            failure_mode="If evidence is incomplete, mark claims unresolved.",
        ),
        ResearchProfile(
            name="report_reviewer",
            description="Plans review criteria for research reports.",
            source_strategy=("check authority", "check unsupported claims", "check target fit"),
            evidence_requirements=("review criteria", "unsupported claims", "recommendation boundary"),
            report_contract=("report review plan", "publication blockers", "approval notes"),
            known_unknowns=("report body is not reviewed unless supplied later",),
            failure_mode="If evidence is missing, block promotion of conclusions.",
        ),
    )


def research_profile_names() -> tuple[ResearchProfileName, ...]:
    return tuple(profile.name for profile in research_profiles())


def get_research_profile(name: ResearchProfileName) -> ResearchProfile:
    profiles = {profile.name: profile for profile in research_profiles()}
    try:
        return profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown research profile: {name}") from exc


def validate_research_profiles() -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[str] = set()
    for profile in research_profiles():
        if profile.name in seen:
            errors.append(f"duplicate research profile: {profile.name}")
        seen.add(profile.name)
        if not profile.source_strategy:
            errors.append(f"research profile {profile.name} missing source strategy")
        if not profile.evidence_requirements:
            errors.append(f"research profile {profile.name} missing evidence requirements")
        if not profile.report_contract:
            errors.append(f"research profile {profile.name} missing report contract")
    for expected in ("research_planner", "source_mapper", "evidence_synthesizer", "report_reviewer"):
        if expected not in seen:
            errors.append(f"missing research profile: {expected}")
    return tuple(errors)


def create_research_plan_artifact(
    *,
    target: TargetName,
    profile_name: ResearchProfileName,
    task: str,
    topic: str = "",
    source_hint: tuple[str, ...] = (),
) -> dict[str, Any]:
    profile = get_research_profile(profile_name)
    return {
        "kind": RESEARCH_PLAN_KIND,
        "schema_version": RESEARCH_PLAN_SCHEMA_VERSION,
        "target": target,
        "profile": profile.to_dict(),
        "task": task,
        "topic": topic,
        "source_hints": [item.strip() for item in source_hint if item.strip()],
        "source_strategy": list(profile.source_strategy),
        "evidence_requirements": list(profile.evidence_requirements),
        "report_contract": list(profile.report_contract),
        "known_unknowns": list(profile.known_unknowns),
        "failure_mode": profile.failure_mode,
        "governance": {
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "agent_construction": "DISABLED",
            "search_execution": "DISABLED",
            "mcp_execution": "DISABLED",
            "source_collection": "DISABLED",
            "shell_execution": "DISABLED",
            "file_writes": "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH",
            "commit_push": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_research_plan_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_research_plan_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_research_plan_artifact(artifact), encoding="utf-8")


def validate_research_plan_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["research plan artifact must be a JSON object"]
    if artifact.get("kind") != RESEARCH_PLAN_KIND:
        errors.append(f"kind must be {RESEARCH_PLAN_KIND}")
    if artifact.get("schema_version") != RESEARCH_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RESEARCH_PLAN_SCHEMA_VERSION}")
    if artifact.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if not artifact.get("task"):
        errors.append("task is required")
    profile = artifact.get("profile")
    if not isinstance(profile, dict):
        errors.append("profile must be an object")
    elif profile.get("name") not in research_profile_names():
        errors.append("profile.name must be known")
    for field in ("source_strategy", "evidence_requirements", "report_contract", "known_unknowns"):
        value = artifact.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty list")
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
            "agent_construction",
            "search_execution",
            "mcp_execution",
            "source_collection",
            "shell_execution",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_research_plan_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_research_plan_artifact(data)
