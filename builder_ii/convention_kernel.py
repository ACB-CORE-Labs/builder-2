#!/usr/bin/env python3
"""
Convention Layer Kernel for CORE builder-II

This is the canonical abstraction for the governed convention layer over Codename Goose.

Design Principles:
- Semantic Rigor: Every state has precise, unambiguous meaning.
- Mechanical Sympathy: Respects real local dev workflows and Goose-native surfaces.
- Fail-Closed Governance: Unknown or escalated authority is rejected visibly.
- Projection Purity: Produces deterministic, inspectable Goose-native outputs without side effects.
- Evidence Chaining: All artifacts link into verifiable chains.

This kernel does NOT launch Goose, execute commands, or grant runtime authority.
It prepares, resolves, projects, validates, and records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal, Optional, Protocol


class AuthorityMode(str, Enum):
    PLANNED_ONLY = "PLANNED_ONLY"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"  # Only set after explicit operator action outside this kernel


@dataclass(frozen=True)
class GovernanceBlock:
    """Immutable governance declaration for every artifact and projection."""
    runtime_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"] = "DISABLED"
    model_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"] = "DISABLED"
    shell_execution: Literal["DISABLED", "PROPOSED", "AUTHORIZED"] = "DISABLED"
    source_writes: Literal["DISABLED", "PROPOSED", "AUTHORIZED"] = "DISABLED"
    git_mutation: Literal["DISABLED", "PROPOSED", "AUTHORIZED"] = "DISABLED"
    artifact_is_authority: bool = False
    core_workbench_coupling: Literal["NONE", "TARGET_ONLY"] = "NONE"
    deepagents_activation: Literal["DISABLED", "PROPOSED", "AUTHORIZED"] = "DISABLED"

    def is_safe_for_projection(self) -> bool:
        return (
            self.runtime_execution == "DISABLED"
            and self.model_execution == "DISABLED"
            and not self.artifact_is_authority
            and self.core_workbench_coupling in ("NONE", "TARGET_ONLY")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_execution": self.runtime_execution,
            "model_execution": self.model_execution,
            "shell_execution": self.shell_execution,
            "source_writes": self.source_writes,
            "git_mutation": self.git_mutation,
            "artifact_is_authority": self.artifact_is_authority,
            "core_workbench_coupling": self.core_workbench_coupling,
            "deepagents_activation": self.deepagents_activation,
        }


@dataclass(frozen=True)
class ResolvedSessionSpine:
    """Canonical resolved state before projection or execution consideration."""
    target_profile: str
    repo_path: str
    agent_profile: str
    prompt_profile: Optional[str]
    verification_profile: str
    authority_mode: AuthorityMode
    context_pack_ref: Optional[str]
    model_policy: dict[str, Any]  # Simplified; in real use would be richer ModelPolicy
    goose_projection_policy: dict[str, Any]
    required_evidence: list[str] = field(default_factory=list)
    handoff_expectation: dict[str, Any] = field(default_factory=dict)
    governance: GovernanceBlock = field(default_factory=GovernanceBlock)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.target_profile:
            errors.append("target_profile is required")
        if self.governance.artifact_is_authority:
            errors.append("artifact_is_authority must be False for spines")
        if not self.governance.is_safe_for_projection():
            errors.append("Governance block does not permit safe projection")
        return errors


@dataclass(frozen=True)
class GooseNativeProjection:
    """Deterministic, inspectable output suitable for Codename Goose."""
    provider: str
    model: str
    planner_provider: Optional[str] = None
    planner_model: Optional[str] = None
    recipe_path: Optional[str] = None
    working_directory: str = "."
    session_name: str = ""
    context_pack_ref: Optional[str] = None
    builtins: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)
    builder_model_tier: Optional[str] = None
    builder_session_mode: str = "governed"
    governance: GovernanceBlock = field(default_factory=GovernanceBlock)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.provider or not self.model:
            errors.append("provider and model are required for Goose projection")
        if not self.governance.is_safe_for_projection():
            errors.append("Governance block does not permit safe Goose projection")
        return errors


class ConventionKernel:
    """Core engine for the builder-II convention layer over Codename Goose."""

    def resolve_spine(
        self,
        target_profile: str,
        repo_path: str,
        agent_profile: str,
        **kwargs: Any,
    ) -> ResolvedSessionSpine:
        """Resolve a full session spine from inputs. Pure where possible."""
        # In full implementation this would call profile_resolution, context_pack, model_policy, etc.
        governance = GovernanceBlock(
            runtime_execution="DISABLED",
            model_execution="DISABLED",
            artifact_is_authority=False,
        )
        return ResolvedSessionSpine(
            target_profile=target_profile,
            repo_path=repo_path,
            agent_profile=agent_profile,
            prompt_profile=kwargs.get("prompt_profile"),
            verification_profile=kwargs.get("verification_profile", "default"),
            authority_mode=AuthorityMode.PLANNED_ONLY,
            context_pack_ref=kwargs.get("context_pack_ref"),
            model_policy=kwargs.get("model_policy", {}),
            goose_projection_policy=kwargs.get("goose_projection_policy", {}),
            required_evidence=kwargs.get("required_evidence", []),
            handoff_expectation=kwargs.get("handoff_expectation", {}),
            governance=governance,
        )

    def project_to_goose(
        self, spine: ResolvedSessionSpine
    ) -> GooseNativeProjection:
        """Pure projection from spine to Goose-native surface."""
        if not spine.governance.is_safe_for_projection():
            raise ValueError("Cannot project: governance does not permit safe projection")

        return GooseNativeProjection(
            provider=spine.model_policy.get("provider", "ollama"),
            model=spine.model_policy.get("model", "gemma:4b"),
            planner_provider=spine.goose_projection_policy.get("planner_provider"),
            planner_model=spine.goose_projection_policy.get("planner_model"),
            recipe_path=spine.goose_projection_policy.get("recipe_path"),
            working_directory=spine.repo_path,
            session_name=f"{spine.target_profile}-{spine.agent_profile}",
            context_pack_ref=spine.context_pack_ref,
            builder_model_tier=spine.model_policy.get("tier"),
            builder_session_mode="governed",
            governance=spine.governance,
        )

    def validate_artifact(self, artifact: Any) -> list[str]:
        """Generic validation hook. Real implementations delegate to specific validators."""
        if hasattr(artifact, "validate"):
            return artifact.validate()
        return []


# Convenience factory for common use
kernel = ConventionKernel()


def create_safe_spine(target_profile: str, repo_path: str, agent_profile: str, **kwargs: Any) -> ResolvedSessionSpine:
    """Helper for the common safe case."""
    return kernel.resolve_spine(target_profile, repo_path, agent_profile, **kwargs)
