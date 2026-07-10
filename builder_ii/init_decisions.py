"""Decision registry for the ``builder init`` unified onboarding orchestrator (plan item 2.2).

Nine onboarding decisions, split by how ``builder init`` treats them:

- four PROMPTED decisions (the existing 4-decision wizard surface): output directory,
  target profile, model backend, model alias. Prompted interactively when not provided by
  flag, and every answer — typed or flag-provided — is validated against the live registry
  for that decision (target profiles, backends, model aliases), never accepted as free text.
- five DEFAULTED decisions with documented defaults: agent profile, verification profile,
  artifact root, runtime mode, allow-artifact-root-inside-target. These resolve through the
  standard config source precedence (``resolve_config_sources``) and are echoed in the init
  summary together with the flag that overrides each; init does not prompt for them.

``builder init`` composes the existing governed onboarding pipeline
(``run_onboarding_pipeline``): plan -> overlay -> rollback snapshot -> intent report. It
never applies. The apply step is a separately invoked, digest-confirmed command
(``builder-setup apply``) using the same digest-prefix-typing confirmation grammar as the
HITL patch/rollback approvals (plan item 1.1) — the process that renders a digest must not
also harvest the confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass

from builder_ii.agent_profiles import agent_profile_names
from builder_ii.config import BACKENDS, MODEL_ALIASES
from builder_ii.target_profiles import target_names
from builder_ii.verification_profiles import verification_profiles

DEFAULT_INIT_OUTPUT_DIR = ".builder/setup-artifacts"


def verification_profile_names() -> tuple[str, ...]:
    return tuple(profile.name for profile in verification_profiles())


@dataclass(frozen=True)
class PromptedDecision:
    """One of the four wizard decisions: prompted when missing, registry-validated always."""

    name: str
    resolution_field: str | None  # ConfigResolution field supplying the default, if any
    question: str
    allowed: tuple[str, ...]  # empty tuple = free-form (output directory)


@dataclass(frozen=True)
class DefaultedDecision:
    """One of the five documented-default decisions: resolved, echoed, never prompted."""

    name: str
    resolution_field: str
    override_flag: str


def prompted_decisions() -> tuple[PromptedDecision, ...]:
    return (
        PromptedDecision(
            name="output_dir",
            resolution_field=None,
            question="Output directory for onboarding artifacts",
            allowed=(),
        ),
        PromptedDecision(
            name="target_profile",
            resolution_field="active_target_profile",
            question="Target profile",
            allowed=target_names(),
        ),
        PromptedDecision(
            name="model_backend",
            resolution_field="model_backend",
            question="Local model backend",
            allowed=BACKENDS,
        ),
        PromptedDecision(
            name="model_alias",
            resolution_field="model_alias",
            question="Primary model alias",
            allowed=MODEL_ALIASES,
        ),
    )


def defaulted_decisions() -> tuple[DefaultedDecision, ...]:
    return (
        DefaultedDecision("agent_profile", "active_agent_profile", "--agent-profile"),
        DefaultedDecision("verification_profile", "active_verification_profile", "--verification-profile"),
        DefaultedDecision("artifact_root", "platform_artifact_root", "--artifact-root"),
        DefaultedDecision("runtime_mode", "runtime_mode", "--runtime-mode"),
        DefaultedDecision(
            "allow_artifact_root_inside_target",
            "allow_artifact_root_inside_target",
            "--allow-artifact-root-inside-target",
        ),
    )


def validate_decision_value(decision_name: str, value: str) -> list[str]:
    """Registry-validate one prompted-decision answer. Empty list = valid."""
    registries: dict[str, tuple[str, ...]] = {
        "target_profile": target_names(),
        "model_backend": BACKENDS,
        "model_alias": MODEL_ALIASES,
        "agent_profile": agent_profile_names(),
        "verification_profile": verification_profile_names(),
    }
    allowed = registries.get(decision_name)
    if allowed is None:
        if not value or not value.strip():
            return [f"{decision_name} must be a non-empty value"]
        return []
    if value not in allowed:
        return [f"{decision_name} must be one of: {', '.join(allowed)} (got {value!r})"]
    return []


def prompted_decision_options_provider(decision_name: str):
    """The live registry behind one prompted decision, as a *callable* reference.

    A wizard step may reference the registry that owns its values; it may never transcribe
    them into prompt text (see ``builder_ii/wizard_framework.py``). The lambdas read this
    module's globals at call time, so a registry change -- or a monkeypatched registry in
    the drift test -- reaches every prompt render and every validation with no wizard code
    change.
    """
    providers = {
        "target_profile": lambda: tuple(target_names()),
        "model_backend": lambda: tuple(BACKENDS),
        "model_alias": lambda: tuple(MODEL_ALIASES),
    }
    return providers.get(decision_name)


def init_wizard_step_definitions(defaults: dict[str, str | None] | None = None):
    """The four prompted decisions as :class:`~builder_ii.wizard_framework.WizardStep`s.

    ``defaults`` is supplied by ``builder init`` from config resolution at runtime; the
    definitions stay importable without one because the transcription pin in
    ``tests/test_wizard_framework.py`` needs only questions and providers. Question text,
    registry rendering, and acceptance are exactly what ``builder init`` has always shown:
    the question literal, allowed values rendered from the live registry at prompt time,
    and :func:`validate_decision_value` as the boundary.
    """
    from builder_ii.wizard_framework import WizardStep

    resolved = dict(defaults or {})
    steps = []
    for decision in prompted_decisions():
        steps.append(
            WizardStep(
                id=decision.name,
                question=decision.question,
                options_provider=prompted_decision_options_provider(decision.name),
                validator=(lambda value, _name=decision.name: validate_decision_value(_name, value)),
                default=resolved.get(decision.name),
                free_form=not decision.allowed,
            )
        )
    return tuple(steps)
