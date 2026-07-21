from __future__ import annotations

import hashlib
import json as json_lib
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import takewhile
from pathlib import Path
from typing import Any, Literal

from builder_ii.adapters.deepagents.deepagents_bridge_readiness import (
    DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
    create_deepagents_bridge_readiness_report,
)
from builder_ii.adapters.goose.goose_projection import create_goose_projection, validate_goose_projection
from builder_ii.adapters.goose.goose_readonly_session import (
    GOOSE_READONLY_SESSION_PLAN_KIND,
    create_goose_readonly_session_plan,
)
from builder_ii.adapters.goose.goose_wrapper_plan import (
    create_goose_wrapper_plan,
    validate_goose_wrapper_plan,
)
from builder_ii.core.config import Settings
from builder_ii.core.context_packs import CONTEXT_PACK_KIND, create_architecture_aware_context_pack, create_context_pack
from builder_ii.core.handoff_notes import HANDOFF_NOTE_KIND, create_artifact_ref, create_handoff_note
from builder_ii.core.repo_map import REPO_MAP_KIND, create_repo_map
from builder_ii.core.session_config import create_session_configuration, validate_session_configuration
from builder_ii.core.session_workflow import (
    SESSION_WORKFLOW_PLAN_KIND,
    create_session_workflow_plan,
)
from builder_ii.governance.authority import (
    CAPABILITY_FLAGS,
    COMMAND_AUTHORITY_REGISTRY,
    TIER_2,
    TIER_3,
    TIER_4,
    CommandAuthorityRecord,
    command_name_words,
)
from builder_ii.lifecycle.candidate.verification_profile_reports import (
    VERIFICATION_PROFILE_REPORT_KIND,
    create_verification_profile_report,
)
from builder_ii.lifecycle.candidate.verification_profiles import VerificationProfileName
from builder_ii.lifecycle.setup.target_profiles import TargetName
from builder_ii.routing.agent_profiles import AgentProfileName

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
    runtime_activation: str = "DISABLED"
    goose_runtime_start: Disabled = "DISABLED"
    deepagents_runtime_start: Disabled = "DISABLED"
    agent_construction: Disabled = "DISABLED"
    subagent_construction: Disabled = "DISABLED"
    model_execution: Disabled = "DISABLED"
    shell_execution: Disabled = "DISABLED"
    source_writes: Disabled = "DISABLED"
    target_repo_writes: Disabled = "DISABLED"
    memory_mutation: Disabled = "DISABLED"
    artifact_is_authority: bool = False
    core_workbench_coupling: NoCoupling = "NONE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_execution": self.runtime_execution,
            "runtime_activation": self.runtime_activation,
            "goose_runtime_start": self.goose_runtime_start,
            "deepagents_runtime_start": self.deepagents_runtime_start,
            "agent_construction": self.agent_construction,
            "subagent_construction": self.subagent_construction,
            "model_execution": self.model_execution,
            "shell_execution": self.shell_execution,
            "source_writes": self.source_writes,
            "target_repo_writes": self.target_repo_writes,
            "memory_mutation": self.memory_mutation,
            "artifact_is_authority": self.artifact_is_authority,
            "core_workbench_coupling": self.core_workbench_coupling,
        }

    @classmethod
    def from_mapping(cls, governance: dict[str, Any]) -> "GovernanceBlock":
        return cls(
            runtime_execution=governance.get("runtime_execution", "DISABLED"),
            runtime_activation=governance.get("runtime_activation", "DISABLED"),
            goose_runtime_start=governance.get("goose_runtime_start", "DISABLED"),
            deepagents_runtime_start=governance.get("deepagents_runtime_start", "DISABLED"),
            agent_construction=governance.get("agent_construction", "DISABLED"),
            subagent_construction=governance.get("subagent_construction", "DISABLED"),
            model_execution=governance.get("model_execution", "DISABLED"),
            shell_execution=governance.get("shell_execution", "DISABLED"),
            source_writes=governance.get("source_writes", "DISABLED"),
            target_repo_writes=governance.get("target_repo_writes", "DISABLED"),
            memory_mutation=governance.get("memory_mutation", "DISABLED"),
            artifact_is_authority=governance.get("artifact_is_authority", False),
            core_workbench_coupling=governance.get("core_workbench_coupling", "NONE"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        for key, value in self.to_dict().items():
            if key == "artifact_is_authority":
                if value is not False:
                    errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
            elif key == "core_workbench_coupling":
                if value != "NONE":
                    errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
            elif key == "runtime_activation":
                if value not in ("DISABLED", "NOT_AUTHORIZED"):
                    errors.append("governance.runtime_activation must be DISABLED or NOT_AUTHORIZED")
            elif value != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
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
        errors.append("executes_now must be false or NOT_AUTHORIZED")

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


CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND = "builder_ii.convention_kernel_platform_bundle"
CONVENTION_KERNEL_PLATFORM_BUNDLE_SCHEMA_VERSION = 1


def check_artifact_governance_safety(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["artifact must be a dictionary"]
    gov = artifact.get("governance")
    if not isinstance(gov, dict):
        return ["missing governance block in artifact"]

    # Critical keys that must always be explicitly present
    required_critical = {
        "runtime_execution",
        "model_execution",
        "shell_execution",
        "source_writes",
        "memory_mutation",
        "artifact_is_authority",
        "core_workbench_coupling",
    }
    for key in required_critical:
        if key not in gov:
            errors.append(f"governance block missing required critical key: {key}")

    # Kind-specific relevance checks
    kind = artifact.get("kind", "")
    if kind == CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND:
        for key in (
            "runtime_activation",
            "goose_runtime_start",
            "deepagents_runtime_start",
            "target_repo_writes",
        ):
            if key not in gov:
                errors.append(f"platform bundle governance block missing key: {key}")
    elif kind == "builder_ii.governed_prepare_package":
        for key in ("target_repo_writes",):
            if key not in gov:
                errors.append(f"prepare package governance block missing key: {key}")
    elif kind == "builder_ii.session_configuration":
        for key in ("goose_runtime_start",):
            if key not in gov:
                errors.append(f"session configuration governance block missing key: {key}")

    for key, val in gov.items():
        if key in (
            "runtime_execution",
            "goose_runtime_start",
            "deepagents_runtime_start",
            "agent_construction",
            "subagent_construction",
            "model_execution",
            "shell_execution",
            "memory_mutation",
            "target_repo_writes",
            "goose_activation",
            "deepagents_delegation",
            "command_execution",
            "commit_push",
        ):
            if val != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        elif key == "runtime_activation":
            if val not in ("DISABLED", "NOT_AUTHORIZED"):
                errors.append("governance.runtime_activation must be DISABLED or NOT_AUTHORIZED")
        elif key == "source_writes":
            if val not in (
                "DISABLED",
                "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY",
                "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
            ):
                errors.append(
                    "governance.source_writes must be DISABLED or NOT_AUTHORIZED, DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY, or DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH"
                )
        elif key == "artifact_is_authority":
            if val is not False:
                errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        elif key == "core_workbench_coupling":
            if val != "NONE":
                errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def _artifact_ref_from_dict(kind: str, path: str, name: str, artifact: dict[str, Any]) -> dict[str, Any]:
    raw = json_lib.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    return {
        "kind": kind,
        "path": path,
        "sha256": sha,
        "name": name,
    }


def find_matching_record(command_str: str) -> CommandAuthorityRecord | None:
    """Resolve a command string to the record that governs it.

    Matching is on word boundaries, via `command_name_words`, so that `builder-goose validate-x` is
    not read as a subcommand of `builder-goose validate`.
    """
    cmd_words = command_name_words(command_str.strip())
    if not cmd_words:
        return None

    matching_record = None
    for record in COMMAND_AUTHORITY_REGISTRY:
        rec_words = command_name_words(record.name)
        if len(rec_words) <= len(cmd_words) and cmd_words[: len(rec_words)] == rec_words:
            if matching_record is None or len(rec_words) > len(command_name_words(matching_record.name)):
                matching_record = record

    if not matching_record:
        return None

    remaining_words = cmd_words[len(command_name_words(matching_record.name)) :]
    is_exact = not remaining_words or remaining_words[0].startswith("-")
    if is_exact:
        return matching_record

    if matching_record.authority_delegates_to_subcommands:
        # The group stands in for a subcommand nobody registered. Its tier and promotion state are a
        # ceiling the subcommand cannot exceed, so those carry down. Its capability flags describe
        # the group and are cleared: `builder-runtime` declares `runtime_start`, and an unregistered
        # `builder-runtime <x>` must not inherit the right to start a runtime by name alone.
        #
        # The record answers "what authority applies to `command_str`", so it bears that name and
        # inherits *from* the group. Leaving the group's own name on it would say `builder-goose`
        # inherits from `builder-goose` -- a copy reported as a declaration, and a flagless record
        # bearing the name of a group that declares flags. `inheritance_errors` rejects both.
        cleared: dict[str, Any] = {flag: False for flag in CAPABILITY_FLAGS}
        path_words = tuple(takewhile(lambda word: not word.startswith("-"), cmd_words))
        return replace(
            matching_record,
            name=" ".join(path_words),
            authority_is_inherited=True,
            inherited_from=matching_record.name,
            **cleared,
        )

    return None


def validate_convention_kernel_platform_bundle(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["convention kernel platform bundle must be a JSON object"]
    if data.get("kind") != CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND:
        errors.append(f"kind must be {CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND}")
    if data.get("schema_version") != CONVENTION_KERNEL_PLATFORM_BUNDLE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONVENTION_KERNEL_PLATFORM_BUNDLE_SCHEMA_VERSION}")
    if data.get("bundle_state") != "PLANNED_ONLY":
        errors.append("bundle_state must be PLANNED_ONLY")
    if data.get("operator_review_required") is not True:
        errors.append("operator_review_required must be true")
    if data.get("executes_now") is not False:
        errors.append("executes_now must be false or NOT_AUTHORIZED")
    if data.get("verification_status") not in ("NOT_RUN", "planned-only"):
        errors.append("verification_status must be NOT_RUN or planned-only")

    # Check key fields in the top level
    for field_name in (
        "target",
        "repo_path",
    ):
        if not isinstance(data.get(field_name), str) or not data[field_name]:
            errors.append(f"{field_name} must be a non-empty string")

    # Check composed artifacts are dictionary objects and preserve safe governance.
    for name in (
        "session_configuration",
        "repo_map",
        "context_pack",
        "prepare_package",
        "goose_projection",
        "goose_wrapper_plan",
        "verification_profile_report",
        "handoff_note",
    ):
        art = data.get(name)
        if not isinstance(art, dict):
            errors.append(f"{name} must be a JSON object")
        else:
            for governance_error in check_artifact_governance_safety(art):
                errors.append(f"{name}: {governance_error}")

    # optional deepagents_readiness
    da = data.get("deepagents_readiness")
    if da is not None and not isinstance(da, dict):
        errors.append("deepagents_readiness must be a JSON object if present")

    hf = data.get("hierarchical_frame")
    if hf is not None and not isinstance(hf, dict):
        errors.append("hierarchical_frame must be a JSON object if present")
    elif isinstance(hf, dict):
        for governance_error in check_artifact_governance_safety(hf):
            errors.append(f"hierarchical_frame: {governance_error}")

    # check command_authority_check block
    cac = data.get("command_authority_check")
    if not isinstance(cac, dict):
        errors.append("command_authority_check must be a JSON object")
    else:
        if cac.get("kind") != "builder_ii.command_authority_check":
            errors.append("command_authority_check.kind must be builder_ii.command_authority_check")
        if not isinstance(cac.get("referenced_commands"), list):
            errors.append("command_authority_check.referenced_commands must be a list")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        # Check that it validates cleanly
        errors.extend(check_artifact_governance_safety(data))
    return errors


@dataclass(frozen=True)
class ConventionKernelPlatformBundle:
    """Canonical platform spine bundle emitted by the convention kernel coordinator."""

    target_profile: dict[str, Any]
    command_authority_check: dict[str, Any]
    session_configuration: dict[str, Any]
    repo_map: dict[str, Any]
    context_pack: dict[str, Any]
    prepare_package: dict[str, Any]
    goose_projection: dict[str, Any]
    goose_wrapper_plan: dict[str, Any]
    verification_profile_report: dict[str, Any]
    handoff_note: dict[str, Any]
    hierarchical_frame: dict[str, Any] | None = None
    deepagents_readiness: dict[str, Any] | None = None
    governance: GovernanceBlock = field(default_factory=GovernanceBlock)

    def to_dict(self) -> dict[str, Any]:
        res = {
            "kind": CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND,
            "schema_version": CONVENTION_KERNEL_PLATFORM_BUNDLE_SCHEMA_VERSION,
            "bundle_state": "PLANNED_ONLY",
            "target": self.session_configuration["target_profile"]["name"],
            "repo_path": self.session_configuration["repo_path"],
            "operator_review_required": True,
            "executes_now": False,
            "verification_status": "planned-only",
            "target_profile": self.target_profile,
            "command_authority_check": self.command_authority_check,
            "session_configuration": self.session_configuration,
            "repo_map": self.repo_map,
            "context_pack": self.context_pack,
            "prepare_package": self.prepare_package,
            "goose_projection": self.goose_projection,
            "goose_wrapper_plan": self.goose_wrapper_plan,
            "verification_profile_report": self.verification_profile_report,
            "handoff_note": self.handoff_note,
            "governance": self.governance.to_dict(),
        }
        if self.hierarchical_frame is not None:
            res["hierarchical_frame"] = self.hierarchical_frame
        if self.deepagents_readiness is not None:
            res["deepagents_readiness"] = self.deepagents_readiness
        return res


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
        legacy_repo = str(
            target_profile if isinstance(settings, str) and target_profile is not None else repo_path or "."
        )
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

    def validate_platform_spine(self, bundle: Any) -> list[str]:
        return validate_convention_kernel_platform_bundle(bundle)

    def prepare_platform_spine(
        self,
        settings: Settings,
        target_profile: TargetName | str,
        *,
        repo_path: str | None = None,
        agent_profile_name: str | None = None,
        prompt_profile_name: str | None = None,
        verification_profile_name: str | None = None,
        task: str = "",
        include_deepagents_readiness: bool = True,
        include_code_vault: bool = True,
        generic_repo: Path | None = None,
        authority_mode: Literal["read_only", "planned_patch"] = "read_only",
        model_alias: str | None = None,
        operator_managed_commands: list[str] | None = None,
    ) -> ConventionKernelPlatformBundle:
        # 1. Resolve spine & session configuration
        spine = self.resolve_spine(
            settings,
            target_profile,
            agent_profile_name=agent_profile_name,
            prompt_profile_name=prompt_profile_name,
            verification_profile_name=verification_profile_name,
            repo_path=repo_path,
            task=task,
            authority_mode=authority_mode,
            model_alias=model_alias,
            context_pack=None,
            generic_repo=generic_repo,
        )
        session_config_art = spine.artifact

        # 2. Extract resolver and get repo_path
        from builder_ii.lifecycle.setup.profile_resolution import ProfileResolver

        resolver = ProfileResolver(settings)
        resolved = resolver.resolve(
            target_name=target_profile,  # type: ignore[arg-type]
            agent_profile_name=agent_profile_name,
            prompt_profile_name=prompt_profile_name,
            verification_profile_name=verification_profile_name,
            repo_path=repo_path,
        )
        resolved_repo = Path(resolved.repo_path)
        task_text = task or "prepare governed local developer session"

        # 3. Create component artifacts in memory
        target_profile_dict = resolved.target_profile.to_artifact_dict()
        repo_map_art = create_repo_map(resolved_repo, target_name=target_profile)  # type: ignore[arg-type]

        hierarchical_frame_art = None
        # Attempt import if requested
        if include_code_vault:
            try:
                import builder_ii_code_vault.hierarchy  # noqa: F401
            except ImportError:
                include_code_vault = False

        if include_code_vault:
            from builder_ii_code_vault.hierarchy import (
                create_hierarchical_frame,
                dumps_hierarchical_frame,
                validate_hierarchical_frame,
            )
            from builder_ii_code_vault.repo_map_adapter import hierarchical_input_from_repo_map

            frame_input = hierarchical_input_from_repo_map(
                repo_map_art,
                repo_root=resolved_repo,
                enrich_symbols=True,
            )
            hierarchical_frame = create_hierarchical_frame(frame_input, target_name=str(target_profile))
            frame_errors = validate_hierarchical_frame(hierarchical_frame)
            if frame_errors:
                raise ValueError("created invalid hierarchical frame: " + "; ".join(frame_errors))
            hierarchical_frame_art = json_lib.loads(dumps_hierarchical_frame(hierarchical_frame))
            context_pack_art = create_architecture_aware_context_pack(
                repo_map_art,
                target_name=str(target_profile),
                hierarchical_frame=hierarchical_frame,
                task=task_text,
            )
        else:
            context_pack_art = create_context_pack(repo_map_art, target_name=target_profile, task=task_text)  # type: ignore[arg-type]

        session_workflow_art = create_session_workflow_plan(
            settings,
            target_profile,  # type: ignore[arg-type]
            agent_profile_name=agent_profile_name,
            prompt_profile_name=prompt_profile_name,
            verification_profile_name=verification_profile_name,
            repo_path=repo_path,
        )

        # Create goose projection & wrapper plan
        goose_proj = self.project_to_goose(settings, spine)
        goose_wrapper_art = self.prepare_wrapper_plan(goose_proj)

        # Create goose readonly session plan
        goose_readonly_session_art = create_goose_readonly_session_plan(
            settings,
            target_profile,  # type: ignore[arg-type]
            agent_profile_name=agent_profile_name,
            prompt_profile_name=prompt_profile_name,
            verification_profile_name=verification_profile_name,
            repo_path=repo_path,
            task=task_text,
        )

        # Create verification profile report
        verification_report_art = create_verification_profile_report(
            settings,
            target_profile,  # type: ignore[arg-type]
            agent_profile_name=agent_profile_name,
            prompt_profile_name=prompt_profile_name,
            verification_profile_name=verification_profile_name,
            repo_path=repo_path,
            task=task_text,
            goose_readonly_session_plan=goose_readonly_session_art,
        )

        # Compute deterministic hashes for the sub-artifacts
        session_ref = _artifact_ref_from_dict(
            SESSION_WORKFLOW_PLAN_KIND,
            "session-workflow.json",
            "session workflow plan",
            session_workflow_art,
        )
        goose_ref = _artifact_ref_from_dict(
            GOOSE_READONLY_SESSION_PLAN_KIND,
            "goose-readonly-session.json",
            "Goose read-only session plan",
            goose_readonly_session_art,
        )
        verification_ref = _artifact_ref_from_dict(
            VERIFICATION_PROFILE_REPORT_KIND,
            "verification-profile-report.json",
            "verification profile report",
            verification_report_art,
        )
        repo_map_ref = _artifact_ref_from_dict(
            REPO_MAP_KIND,
            "repo-map.json",
            "bounded repo map",
            repo_map_art,
        )
        context_pack_ref = _artifact_ref_from_dict(
            CONTEXT_PACK_KIND,
            "context-pack.json",
            "bounded context pack",
            context_pack_art,
        )
        hierarchical_frame_ref = None
        if hierarchical_frame_art is not None:
            from builder_ii_code_vault.hierarchy import HIERARCHICAL_FRAME_KIND
            hierarchical_frame_ref = _artifact_ref_from_dict(
                HIERARCHICAL_FRAME_KIND,
                "hierarchical-frame.json",
                "CodeVault hierarchical frame",
                hierarchical_frame_art,
            )

        handoff_note_art = create_handoff_note(
            target_name=target_profile,  # type: ignore[arg-type]
            status="READY_FOR_REVIEW",
            summary="Governed platform spine created. Planned-only session.",
            changed_files_summary=["Governed platform spine planning session."],
            verification_summary="Verification report is planned-only. No checks were executed.",
            session_ref=create_artifact_ref(**session_ref),
            goose_readonly_session_ref=create_artifact_ref(**goose_ref),
            verification_report_ref=create_artifact_ref(**verification_ref),
            open_risks=[
                "Human operator must run and evidence any verification commands out-of-band.",
            ],
            next_recommended_action="Inspect generated artifacts, run planned verification manually.",
        )

        handoff_ref = _artifact_ref_from_dict(
            HANDOFF_NOTE_KIND,
            "handoff-note.json",
            "governed handoff note",
            handoff_note_art,
        )

        deepagents_readiness_art = None
        deepagents_ref = None
        if include_deepagents_readiness:
            deepagents_readiness_art = create_deepagents_bridge_readiness_report(
                target_profile=target_profile,  # type: ignore[arg-type]
                agent_profile_compatibility_summary=("Prepared for readiness inspection only."),
                readiness_verdict="NOT_READY",
            )
            deepagents_ref = _artifact_ref_from_dict(
                DEEPAGENTS_BRIDGE_READINESS_REPORT_KIND,
                "deepagents-bridge-readiness.json",
                "optional deepagents bridge readiness report",
                deepagents_readiness_art,
            )

        # Compile all sub-artifacts in a prepare_package structure
        artifact_refs = [
            session_ref,
            goose_ref,
            verification_ref,
            repo_map_ref,
            context_pack_ref,
            handoff_ref,
        ]
        if hierarchical_frame_ref is not None:
            artifact_refs.append(hierarchical_frame_ref)
        if deepagents_ref is not None:
            artifact_refs.append(deepagents_ref)

        prepare_package_art = {
            "kind": "builder_ii.governed_prepare_package",
            "schema_version": 1,
            "target_name": target_profile,
            "repo_path": repo_path,
            "task": task_text,
            "output_dir": ".",
            "artifact_refs": artifact_refs,
            "package_state": "PREPARED_ONLY",
            "runtime_execution_performed": False,
            "target_repo_writes_performed": False,
            "governance": {
                "capability_state": "governed_prepare_package",
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY",
                "target_repo_writes": "DISABLED",
                "memory_mutation": "DISABLED",
                "goose_activation": "DISABLED",
                "deepagents_delegation": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            },
        }

        # 4. Check unsafe governance on all composed artifacts
        all_composed = [
            session_config_art,
            repo_map_art,
            context_pack_art,
            session_workflow_art,
            goose_proj.artifact,
            goose_wrapper_art,
            goose_readonly_session_art,
            verification_report_art,
            handoff_note_art,
            prepare_package_art,
        ]
        if hierarchical_frame_art is not None:
            all_composed.append(hierarchical_frame_art)
        if deepagents_readiness_art is not None:
            all_composed.append(deepagents_readiness_art)

        for art in all_composed:
            gov_errors = check_artifact_governance_safety(art)
            if gov_errors:
                raise ValueError("unsafe governance block in composed artifact: " + "; ".join(gov_errors))

        # 5. Extract and validate commands against registry
        referenced_cmds: list[str] = []
        referenced_cmds.extend(session_workflow_art.get("planned_commands", []))
        referenced_cmds.extend(verification_report_art.get("verification_profile", {}).get("proposed_commands", []))

        referenced_cmds = sorted(list(set(referenced_cmds)))

        operator_managed_set = set(operator_managed_commands or [])
        if operator_managed_commands is None:
            operator_managed_set = {
                f"builder-context pack --target {target_profile}",
                "builder start --task 'local development session' --mode coding",
                f"builder-handoff bundle --bundle-name handoff-session-{target_profile}",
                "builder-handoff bundle --bundle-name handoff-session-generic",
                "builder-handoff bundle --bundle-name handoff-session-builder",
                "builder-handoff bundle --bundle-name handoff-session-core",
            }
            for profile_cmd in resolved.verification_profile.proposed_commands:
                operator_managed_set.add(profile_cmd)

        command_checks: list[dict[str, Any]] = []
        all_registered = True
        for cmd in referenced_cmds:
            record = find_matching_record(cmd)
            is_marked = (cmd in operator_managed_set) or (record and record.name in operator_managed_set)

            if not record:
                if not is_marked:
                    raise ValueError(f"command '{cmd}' is unregistered in the command authority registry")
                all_registered = False
                command_checks.append(
                    {
                        "command": cmd,
                        "record_name": "unregistered",
                        "tier": "unregistered",
                        "promotion_state": "unregistered",
                        "approval_mode": "none",
                        "allowed_in_planned_only": False,
                        "status": "not_invoked_requires_operator_invocation",
                        "authority_is_inherited": False,
                        "inherited_from": "",
                    }
                )
                continue

            is_tier_2_plus = record.tier in (TIER_2, TIER_3, TIER_4)
            if is_tier_2_plus and not is_marked:
                raise ValueError(
                    f"command '{cmd}' is classified above permitted tier and lacks explicit 'not invoked / operator-managed only' marking"
                )

            command_checks.append(
                {
                    "command": cmd,
                    "record_name": record.name,
                    "tier": record.tier,
                    "promotion_state": record.promotion_state,
                    "approval_mode": record.approval_mode,
                    "allowed_in_planned_only": not is_tier_2_plus,
                    "status": "not_invoked_requires_operator_invocation" if is_tier_2_plus else "available",
                    "authority_is_inherited": record.authority_is_inherited,
                    "inherited_from": record.inherited_from,
                }
            )

        command_authority_check = {
            "kind": "builder_ii.command_authority_check",
            "schema_version": 1,
            "all_referenced_commands_registered": all_registered,
            "referenced_commands": command_checks,
            "verification_status": "planned-only",
        }

        # 6. Build the platform bundle
        bundle = ConventionKernelPlatformBundle(
            target_profile=target_profile_dict,
            command_authority_check=command_authority_check,
            session_configuration=session_config_art,
            repo_map=repo_map_art,
            context_pack=context_pack_art,
            hierarchical_frame=hierarchical_frame_art,
            prepare_package=prepare_package_art,
            goose_projection=goose_proj.artifact,
            goose_wrapper_plan=goose_wrapper_art,
            verification_profile_report=verification_report_art,
            handoff_note=handoff_note_art,
            deepagents_readiness=deepagents_readiness_art,
            governance=GovernanceBlock(),
        )

        bundle_dict = bundle.to_dict()
        errors = validate_convention_kernel_platform_bundle(bundle_dict)
        if errors:
            raise ValueError("invalid platform spine bundle: " + "; ".join(errors))

        return bundle

    def validate_artifact(self, artifact: Any) -> list[str]:
        if not isinstance(artifact, dict):
            return ["artifact must be a JSON object"]
        kind = artifact.get("kind")
        if kind == CONVENTION_KERNEL_BUNDLE_KIND:
            return validate_convention_kernel_bundle(artifact)
        if kind == CONVENTION_KERNEL_PLATFORM_BUNDLE_KIND:
            return validate_convention_kernel_platform_bundle(artifact)
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
