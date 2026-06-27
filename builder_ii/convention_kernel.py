from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from builder_ii.config import Settings
from builder_ii.goose_projection import create_goose_projection, validate_goose_projection
from builder_ii.goose_wrapper_plan import create_goose_wrapper_plan, validate_goose_wrapper_plan
from builder_ii.profile_resolution import AgentProfileName, TargetName, VerificationProfileName
from builder_ii.session_config import create_session_configuration, validate_session_configuration

CONVENTION_KERNEL_BUNDLE_KIND = "builder_ii.convention_kernel_bundle"
CONVENTION_KERNEL_BUNDLE_SCHEMA_VERSION = 1

Disabled = Literal["DISABLED"]
NoCoupling = Literal["NONE"]


class AuthorityMode(str, Enum):
    """Compatibility enum for pre-hardening callers.

    The hardened kernel only emits PLANNED_ONLY bundles. Approval/receipt states
    belong in explicit approval or evidence artifacts, not this coordinator.
    """

    PLANNED_ONLY = "PLANNED_ONLY"


@dataclass(frozen=True)
class GovernanceBlock:
    """Canonical fail-closed governance block for convention-layer coordination."""

    runtime_execution: Disabled = "DISABLED"
    goose_runtime_start: Disabled = "DISABLED"
    deepagents_runtime_start: Disabled = "DISABLED"
    agent_construction: Disabled = "DISABLED"
    subagent_construction: Disabled = "DISABLED"
    model_execution: Disabled = "DISABLED"
    shell_execution: Disabled = "DISABLED"
    source_writes: Disabled = "DISABLED"
    memory_mutation: Disabled = "DISABLED"
    artifact_is_authority: bool = False
    core_workbench_coupling: NoCoupling = "NONE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_execution": self.runtime_execution,
            "goose_runtime_start": self.goose_runtime_start,
            "deepagents_runtime_start": self.deepagents_runtime_start,
            "agent_construction": self.agent_construction,
            "subagent_construction": self.subagent_construction,
            "model_execution": self.model_execution,
            "shell_execution": self.shell_execution,
            "source_writes": self.source_writes,
            "memory_mutation": self.memory_mutation,
            "artifact_is_authority": self.artifact_is_authority,
            "core_workbench_coupling": self.core_workbench_coupling,
        }

    @classmethod
    def from_mapping(cls, governance: dict[str, Any]) -> "GovernanceBlock":
        return cls(
            runtime_execution=governance.get("runtime_execution", "DISABLED"),
            goose_runtime_start=governance.get("goose_runtime_start", "DISABLED"),
            deepagents_runtime_start=governance.get("deepagents_runtime_start", "DISABLED"),
            agent_construction=governance.get("agent_construction", "DISABLED"),
            subagent_construction=governance.get("subagent_construction", "DISABLED"),
            model_execution=governance.get("model_execution", "DISABLED"),
            shell_execution=governance.get("shell_execution", "DISABLED"),
            source_writes=governance.get("source_writes", "DISABLED"),
            memory_mutation=governance.get("memory_mutation", "DISABLED"),
            artifact_is_authority=governance.get("artifact_is_authority", False),
            core_workbench_coupling=governance.get("core_workbench_coupling", "NONE"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        for key, value in self.to_dict().items():
            if key == "artifact_is_authority":
                if value is not False:
                    errors.append("governance.artifact_is_authority must be false")
            elif key == "core_workbench_coupling":
                if value != "NONE":
                    errors.append("governance.core_workbench_coupling must be NONE")
            elif value != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        return errors

    def is_safe_for_projection(self) -> bool:
        return not self.validate()

    def require_safe(self) -> None:
        errors = self.validate()
        if errors:
            raise ValueError("unsafe governance block: " + "; ".join(errors))


@dataclass(frozen=True)
class ResolvedSessionSpine:
    """Typed view over the native builder_ii.session_configuration artifact."""

    target_profile: str
    repo_path: str
    agent_profile: str
    prompt_profile: str | None
    verification_profile: str
    authority_mode: str | AuthorityMode
    context_pack_ref: str | None
    model_policy: dict[str, Any]
    goose_projection_policy: dict[str, Any] = field(default_factory=dict)
    required_evidence: list[str] = field(default_factory=list)
    governance: GovernanceBlock = field(default_factory=GovernanceBlock)
    artifact: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_artifact(cls, artifact: dict[str, Any]) -> "ResolvedSessionSpine":
        errors = validate_session_configuration(artifact)
        if errors:
            raise ValueError("session configuration is invalid: " + "; ".join(errors))
        governance = GovernanceBlock.from_mapping(artifact["governance"])
        governance.require_safe()
        return cls(
            target_profile=artifact["target_profile"]["name"],
            repo_path=artifact["repo_path"],
            agent_profile=artifact["selected_agent_profile"]["name"],
            prompt_profile=artifact["selected_prompt_profile"]["name"],
            verification_profile=artifact["selected_verification_profile"]["name"],
            authority_mode=artifact["authority_mode"],
            context_pack_ref=artifact.get("context", {}).get("context_pack_ref", ""),
            model_policy=dict(artifact["model_policy"]),
            goose_projection_policy=dict(artifact.get("goose_projection_policy", {})),
            required_evidence=list(artifact.get("required_evidence", [])),
            governance=governance,
            artifact=artifact,
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.target_profile:
            errors.append("target_profile is required")
        if not self.repo_path:
            errors.append("repo_path is required")
        if not self.agent_profile:
            errors.append("agent_profile is required")
        errors.extend(self.governance.validate())
        if self.artifact:
            errors.extend(validate_session_configuration(self.artifact))
        return errors


@dataclass(frozen=True)
class GooseNativeProjection:
    """Typed view over the native builder_ii.goose_projection artifact."""

    provider: str
    model: str
    planner_provider: str = ""
    planner_model: str = ""
    recipe_path: str = ""
    working_directory: str = "."
    session_name: str = ""
    context_pack_ref: str | None = ""
    builder_model_tier: str = ""
    builder_session_mode: str = ""
    governance: GovernanceBlock = field(default_factory=GovernanceBlock)
    artifact: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_artifact(cls, artifact: dict[str, Any]) -> "GooseNativeProjection":
        errors = validate_goose_projection(artifact)
        if errors:
            raise ValueError("goose projection is invalid: " + "; ".join(errors))
        surface = artifact["goose_native_surface"]
        env = surface["env"]
        governance = GovernanceBlock.from_mapping(artifact["governance"])
        governance.require_safe()
        return cls(
            provider=env["GOOSE_PROVIDER"],
            model=env["GOOSE_MODEL"],
            planner_provider=env["GOOSE_PLANNER_PROVIDER"],
            planner_model=env["GOOSE_PLANNER_MODEL"],
            recipe_path=surface["recipe_path"],
            working_directory=surface["working_directory"],
            session_name=surface["session_name"],
            context_pack_ref=surface["context_pack_ref"],
            builder_model_tier=env["BUILDER_MODEL_TIER"],
            builder_session_mode=env["BUILDER_SESSION_MODE"],
            governance=governance,
            artifact=artifact,
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.provider:
            errors.append("provider is required")
        if not self.model:
            errors.append("model is required")
        if not self.recipe_path and self.artifact:
            errors.append("recipe_path is required")
        errors.extend(self.governance.validate())
        if self.artifact:
            errors.extend(validate_goose_projection(self.artifact))
        return errors


@dataclass(frozen=True)
class ConventionKernelBundle:
    """Reviewable bundle emitted by the convention kernel coordinator."""

    session_configuration: dict[str, Any]
    goose_projection: dict[str, Any]
    goose_wrapper_plan: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": CONVENTION_KERNEL_BUNDLE_KIND,
            "schema_version": CONVENTION_KERNEL_BUNDLE_SCHEMA_VERSION,
            "bundle_state": "PLANNED_ONLY",
            "session_configuration_kind": self.session_configuration["kind"],
            "goose_projection_kind": self.goose_projection["kind"],
            "goose_wrapper_plan_kind": self.goose_wrapper_plan["kind"],
            "target": self.session_configuration["target_profile"]["name"],
            "repo_path": self.session_configuration["repo_path"],
            "agent_profile": self.session_configuration["selected_agent_profile"]["name"],
            "authority_mode": self.session_configuration["authority_mode"],
            "operator_review_required": self.goose_wrapper_plan["operator_launch"]["requires_operator_execution"],
            "executes_now": self.goose_wrapper_plan["operator_launch"]["executes_now"],
            "artifacts": {
                "session_configuration": self.session_configuration,
                "goose_projection": self.goose_projection,
                "goose_wrapper_plan": self.goose_wrapper_plan,
            },
            "governance": GovernanceBlock().to_dict(),
        }


def validate_convention_kernel_bundle(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["convention kernel bundle must be a JSON object"]
    if data.get("kind") != CONVENTION_KERNEL_BUNDLE_KIND:
        errors.append(f"kind must be {CONVENTION_KERNEL_BUNDLE_KIND}")
    if data.get("schema_version") != CONVENTION_KERNEL_BUNDLE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONVENTION_KERNEL_BUNDLE_SCHEMA_VERSION}")
    if data.get("bundle_state") != "PLANNED_ONLY":
        errors.append("bundle_state must be PLANNED_ONLY")
    if data.get("operator_review_required") is not True:
        errors.append("operator_review_required must be true")
    if data.get("executes_now") is not False:
        errors.append("executes_now must be false")

    for field_name in (
        "session_configuration_kind",
        "goose_projection_kind",
        "goose_wrapper_plan_kind",
        "target",
        "repo_path",
        "agent_profile",
        "authority_mode",
    ):
        if not isinstance(data.get(field_name), str) or not data[field_name]:
            errors.append(f"{field_name} must be a non-empty string")

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
    else:
        errors.extend(validate_session_configuration(artifacts.get("session_configuration")))
        errors.extend(validate_goose_projection(artifacts.get("goose_projection")))
        errors.extend(validate_goose_wrapper_plan(artifacts.get("goose_wrapper_plan")))

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(GovernanceBlock.from_mapping(governance).validate())
    return errors


class ConventionKernel:
    """Coordinator for the builder-II convention layer over Codename Goose."""

    def resolve_spine(
        self,
        settings: Settings | TargetName | None = None,
        target_profile: TargetName | str | None = None,
        agent_profile: str | None = None,
        *,
        agent_profile_name: AgentProfileName | None = None,
        prompt_profile_name: str | None = None,
        verification_profile_name: VerificationProfileName | None = None,
        repo_path: str | None = None,
        task: str = "",
        authority_mode: Literal["read_only", "planned_patch"] = "read_only",
        model_alias: str | None = None,
        context_pack: str | None = None,
        generic_repo: Path | None = None,
    ) -> ResolvedSessionSpine:
        if isinstance(settings, Settings):
            if target_profile is None:
                raise ValueError("target_profile is required when settings are provided")
            artifact = create_session_configuration(
                settings,
                target_profile,  # type: ignore[arg-type]
                agent_profile_name=agent_profile_name,
                prompt_profile_name=prompt_profile_name,
                verification_profile_name=verification_profile_name,
                repo_path=repo_path,
                task=task,
                authority_mode=authority_mode,
                model_alias=model_alias,
                context_pack=context_pack,
                generic_repo=generic_repo,
            )
            return ResolvedSessionSpine.from_artifact(artifact)

        legacy_target = str(settings or target_profile or "generic")
        legacy_repo = str(target_profile if isinstance(settings, str) and target_profile is not None else repo_path or ".")
        legacy_agent = agent_profile or agent_profile_name or "default"
        return ResolvedSessionSpine(
            target_profile=legacy_target,
            repo_path=legacy_repo,
            agent_profile=str(legacy_agent),
            prompt_profile=prompt_profile_name,
            verification_profile=verification_profile_name or "default",
            authority_mode=AuthorityMode.PLANNED_ONLY,
            context_pack_ref=context_pack,
            model_policy={},
            governance=GovernanceBlock(),
        )

    def project_to_goose(
        self,
        settings_or_spine: Settings | ResolvedSessionSpine,
        spine: ResolvedSessionSpine | None = None,
    ) -> GooseNativeProjection:
        if spine is None:
            if not isinstance(settings_or_spine, ResolvedSessionSpine):
                raise ValueError("spine is required")
            legacy_spine = settings_or_spine
            if not legacy_spine.governance.is_safe_for_projection():
                raise ValueError("Governance block does not permit safe projection")
            return GooseNativeProjection(
                provider="unbound",
                model="unbound",
                working_directory=legacy_spine.repo_path,
                session_name=f"{legacy_spine.target_profile}-{legacy_spine.agent_profile}",
                governance=legacy_spine.governance,
            )

        settings = settings_or_spine
        if not isinstance(settings, Settings):
            raise ValueError("settings must be provided for native Goose projection")
        spine.governance.require_safe()
        artifact = create_goose_projection(settings, spine.artifact)
        return GooseNativeProjection.from_artifact(artifact)

    def prepare_wrapper_plan(self, projection: GooseNativeProjection) -> dict[str, Any]:
        projection.governance.require_safe()
        wrapper_plan = create_goose_wrapper_plan(projection.artifact)
        wrapper_errors = validate_goose_wrapper_plan(wrapper_plan)
        if wrapper_errors:
            raise ValueError("goose wrapper plan is invalid: " + "; ".join(wrapper_errors))
        return wrapper_plan

    def prepare_bundle(self, settings: Settings, target_profile: TargetName, **kwargs: Any) -> ConventionKernelBundle:
        spine = self.resolve_spine(settings, target_profile, **kwargs)
        projection = self.project_to_goose(settings, spine)
        wrapper_plan = self.prepare_wrapper_plan(projection)
        bundle = ConventionKernelBundle(
            session_configuration=spine.artifact,
            goose_projection=projection.artifact,
            goose_wrapper_plan=wrapper_plan,
        )
        bundle_errors = validate_convention_kernel_bundle(bundle.to_dict())
        if bundle_errors:
            raise ValueError("convention kernel bundle is invalid: " + "; ".join(bundle_errors))
        return bundle

    def validate_artifact(self, artifact: Any) -> list[str]:
        if not isinstance(artifact, dict):
            return ["artifact must be a JSON object"]
        kind = artifact.get("kind")
        if kind == CONVENTION_KERNEL_BUNDLE_KIND:
            return validate_convention_kernel_bundle(artifact)
        if kind == "builder_ii.session_configuration":
            return validate_session_configuration(artifact)
        if kind == "builder_ii.goose_projection":
            return validate_goose_projection(artifact)
        if kind == "builder_ii.goose_wrapper_plan":
            return validate_goose_wrapper_plan(artifact)
        return [f"unsupported artifact kind for convention kernel: {kind}"]


kernel = ConventionKernel()


def create_safe_spine(
    settings: Settings,
    target_profile: TargetName,
    *,
    agent_profile_name: AgentProfileName | None = None,
    prompt_profile_name: str | None = None,
    verification_profile_name: VerificationProfileName | None = None,
    repo_path: str | None = None,
    task: str = "",
    authority_mode: Literal["read_only", "planned_patch"] = "read_only",
    model_alias: str | None = None,
    context_pack: str | None = None,
    generic_repo: Path | None = None,
) -> ResolvedSessionSpine:
    return kernel.resolve_spine(
        settings,
        target_profile,
        agent_profile_name=agent_profile_name,
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,
        repo_path=repo_path,
        task=task,
        authority_mode=authority_mode,
        model_alias=model_alias,
        context_pack=context_pack,
        generic_repo=generic_repo,
    )
