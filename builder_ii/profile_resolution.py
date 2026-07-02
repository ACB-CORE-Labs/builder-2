from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.agent_profiles import (
    AgentProfile,
    get_agent_profile,
)
from builder_ii.config import Settings
from builder_ii.init_content import CORE_INIT_SYSTEM_PROMPT
from builder_ii.target_profiles import (
    _BUILDER_CONTEXT_DEFAULTS,
    _CORE_CONTEXT_DEFAULTS,
    _GENERIC_CONTEXT_DEFAULTS,
    TargetName,
    TargetProfile,
    target_names,
    target_profile,
)
from builder_ii.verification_profiles import (
    VerificationProfile,
    get_verification_profile,
)


class ProfileResolutionError(ValueError):
    """Base exception for profile resolution errors."""
    pass

class UnknownProfileError(ProfileResolutionError):
    """Raised when a profile name is unknown."""
    pass

class MissingFileError(ProfileResolutionError, FileNotFoundError):
    """Raised when a required file or directory is missing."""
    pass

class ValidationError(ProfileResolutionError):
    """Raised when profiles are incompatible or invalid."""
    pass


@dataclass(frozen=True)
class PromptProfile:
    name: str
    description: str
    system_prompt: str
    compatible_targets: tuple[TargetName, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "compatible_targets": list(self.compatible_targets),
        }


def prompt_profiles() -> tuple[PromptProfile, ...]:
    return (
        PromptProfile(
            name="generic_default",
            description="Generic software development prompt focusing on clean and correct edits.",
            system_prompt="You are a local developer assistant. Focus on code readability, test coverage, and documentation consistency.",
            compatible_targets=("generic",),
        ),
        PromptProfile(
            name="builder_default",
            description="builder-II self-development prompt emphasizing safety rails.",
            system_prompt="You are a local builder-II self-development assistant. Prefer generic-first behavior and preserve safety rails.",
            compatible_targets=("builder",),
        ),
        PromptProfile(
            name="core_default",
            description="CORE development prompt enforcing math and CGA constraints.",
            system_prompt=CORE_INIT_SYSTEM_PROMPT,
            compatible_targets=("core",),
        ),
    )


def get_prompt_profile(name: str) -> PromptProfile:
    profiles = {profile.name: profile for profile in prompt_profiles()}
    try:
        return profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown prompt profile: {name}") from exc


@dataclass(frozen=True)
class ResolutionResult:
    target_profile: TargetProfile
    agent_profile: AgentProfile
    prompt_profile: PromptProfile
    verification_profile: VerificationProfile
    repo_path: str
    context_defaults: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        from builder_ii.agent_profiles import create_agent_profile_record

        t_profile_dict = self.target_profile.to_artifact_dict()
        t_profile_dict["repo"] = self.repo_path
        t_profile_dict["context_defaults"] = list(self.context_defaults)

        return {
            "target_profile": t_profile_dict,
            "selected_agent_profile": create_agent_profile_record(
                self.agent_profile, self.target_profile, task="governed session"
            ),
            "selected_prompt_profile": self.prompt_profile.to_dict(),
            "selected_verification_profile": self.verification_profile.to_artifact_dict(
                target=self.target_profile.name, task="governed session"
            ),
            "repo_path": self.repo_path,
            "context_defaults": list(self.context_defaults),
        }


class ProfileResolver:
    def __init__(self, settings: Settings, *, generic_repo: Path | None = None):
        self.settings = settings
        self.generic_repo = generic_repo

    def resolve_target(self, name: str) -> TargetProfile:
        if name not in target_names():
            raise UnknownProfileError(f"unknown target profile: {name}")
        try:
            return target_profile(self.settings, name, generic_repo=self.generic_repo)  # type: ignore[arg-type]
        except ValueError as exc:
            raise UnknownProfileError(str(exc)) from exc

    def resolve_agent(self, name: str, target_name: str) -> AgentProfile:
        try:
            profile = get_agent_profile(name)  # type: ignore[arg-type]
        except ValueError as exc:
            raise UnknownProfileError(str(exc)) from exc

        if target_name not in profile.compatible_targets:
            raise ValidationError(
                f"Agent profile '{name}' is not compatible with target '{target_name}'"
            )
        return profile

    def resolve_prompt(self, name: str, target_name: str) -> PromptProfile:
        try:
            profile = get_prompt_profile(name)
        except ValueError as exc:
            raise UnknownProfileError(str(exc)) from exc

        if target_name not in profile.compatible_targets:
            raise ValidationError(
                f"Prompt profile '{name}' is not compatible with target '{target_name}'"
            )
        return profile

    def resolve_verification(self, name: str, target_name: str) -> VerificationProfile:
        try:
            profile = get_verification_profile(name)  # type: ignore[arg-type]
        except ValueError as exc:
            raise UnknownProfileError(str(exc)) from exc

        if target_name not in profile.compatible_targets:
            raise ValidationError(
                f"Verification profile '{name}' is not compatible with target '{target_name}'"
            )
        return profile

    def resolve(
        self,
        target_name: str,
        *,
        agent_profile_name: str | None = None,
        prompt_profile_name: str | None = None,
        verification_profile_name: str | None = None,
        repo_path: str | Path | None = None,
    ) -> ResolutionResult:
        # 1. Resolve Target
        t_profile = self.resolve_target(target_name)

        # Determine actual repo path and check directory existence
        resolved_repo_str = repo_path or str(t_profile.repo)
        resolved_repo_path = Path(resolved_repo_str).resolve()

        if not resolved_repo_path.exists():
            raise MissingFileError(f"repository path does not exist: {resolved_repo_path}")
        if not resolved_repo_path.is_dir():
            raise ValidationError(f"repository path is not a directory: {resolved_repo_path}")

        # 2. Resolve Agent Profile (with defaults)
        if agent_profile_name is None:
            agent_defaults: dict[str, str] = {
                "generic": "repo_mapper",
                "builder": "context_planner",
                "core": "code_reviewer",
            }
            agent_profile_name = agent_defaults[target_name]
        a_profile = self.resolve_agent(agent_profile_name, target_name)

        # 3. Resolve Prompt Profile (with defaults)
        if prompt_profile_name is None:
            prompt_defaults: dict[str, str] = {
                "generic": "generic_default",
                "builder": "builder_default",
                "core": "core_default",
            }
            prompt_profile_name = prompt_defaults[target_name]
        p_profile = self.resolve_prompt(prompt_profile_name, target_name)

        # 4. Resolve Verification Profile (with defaults)
        if verification_profile_name is None:
            verification_defaults: dict[str, str] = {
                "generic": "generic_basic",
                "builder": "builder_fast",
                "core": "core_smoke",
            }
            verification_profile_name = verification_defaults[target_name]
        v_profile = self.resolve_verification(verification_profile_name, target_name)

        # 5. Resolve Context Defaults (existing files within actual resolved_repo_path)
        defaults_map = {
            "generic": _GENERIC_CONTEXT_DEFAULTS,
            "builder": _BUILDER_CONTEXT_DEFAULTS,
            "core": _CORE_CONTEXT_DEFAULTS,
        }
        raw_defaults = defaults_map[target_name]
        context_defaults = tuple(
            path for path in raw_defaults if (resolved_repo_path / path).exists()
        )

        return ResolutionResult(
            target_profile=t_profile,
            agent_profile=a_profile,
            prompt_profile=p_profile,
            verification_profile=v_profile,
            repo_path=str(resolved_repo_path),
            context_defaults=context_defaults,
        )
