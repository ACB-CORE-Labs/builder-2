"""Decision registry for the ``builder init`` unified onboarding orchestrator (plan item 2.2).

**Nine onboarding decisions, one record each.** Wizard v2 (Ladder 5) prompts all nine, with the
same precedence the four always had: flag > interactive registry-validated prompt > resolved
default. Before it, four were prompted and five were resolved silently and echoed -- so five
decisions that shape where artifacts land and whether a runtime may start were made *for* the
operator and shown to them afterwards.

Each decision is one :class:`Decision`. It used to be six things:

- ``prompted_decisions()`` -- name, question, and a snapshot of allowed values
- ``defaulted_decisions()`` -- name, resolution field, override flag
- ``validate_decision_value`` -- a dict of name -> registry
- ``prompted_decision_options_provider`` -- a *different* dict of name -> registry
- ``builder init``'s echo tuple ``("target_profile", "model_backend", ...)``
- ``builder init``'s ``if defaulted.name == ...`` flag-override chain

Those disagreed. ``agent_profile`` and ``verification_profile`` had a validation registry and no
options provider, so they could be rejected but never rendered; ``runtime_mode``'s registry lived
in ``config_sources`` and was a *set*, which has no order to render. Everything is now derived from
the one record, which is what makes nine decisions cost no more than four.

The invariant ``wizard_framework`` carries applies to every one of them: a decision names the
registry that owns its values (``options_provider``, a callable) and never transcribes them.

``builder init`` composes the existing governed onboarding pipeline
(``run_onboarding_pipeline``): plan -> overlay -> rollback snapshot -> intent report. It
never applies. The apply step is a separately invoked, digest-confirmed command
(``builder-setup apply``) using the same digest-prefix-typing confirmation grammar as the
HITL patch/rollback approvals (plan item 1.1) — the process that renders a digest must not
also harvest the confirmation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from builder_ii.agent_profiles import agent_profile_names
from builder_ii.config import BACKENDS, MODEL_ALIASES
from builder_ii.config_sources import RUNTIME_MODES
from builder_ii.target_profiles import target_names
from builder_ii.verification_profiles import verification_profiles

DEFAULT_INIT_OUTPUT_DIR = ".builder/setup-artifacts"

# `allow_artifact_root_inside_target` is a bool in config. A wizard answer is a string, and the
# echo already renders it with `str(value).lower()`, so these are the two literals it can be.
BOOL_ANSWERS: tuple[str, ...] = ("false", "true")


def verification_profile_names() -> tuple[str, ...]:
    return tuple(profile.name for profile in verification_profiles())


@dataclass(frozen=True)
class Decision:
    """One onboarding decision, in one place.

    ``options_provider`` is a *callable* reference to the registry that owns the allowed values,
    read at prompt time and at validation time. It is never a snapshot: a registry change, or a
    monkeypatched registry in the drift test, reaches every prompt render and every validation
    with no wizard code change. ``options_provider=None`` means genuinely free-form -- a filesystem
    path -- not "a registry we forgot to wire".
    """

    name: str
    question: str
    resolution_field: str | None  # ConfigResolution field supplying the default, if any
    override_flag: str
    options_provider: Callable[[], tuple[str, ...]] | None = None
    # MODEL_ALIASES has ~50 entries. The step still references the registry, so validation and
    # drift keep working, and a rejection surfaces the full list through the error message.
    render_options_in_question: bool = True

    @property
    def free_form(self) -> bool:
        return self.options_provider is None

    def allowed(self) -> tuple[str, ...]:
        return tuple(self.options_provider()) if self.options_provider is not None else ()


def decisions() -> tuple[Decision, ...]:
    """The nine, in prompt order. Wizard v2 prompts all of them."""
    return (
        Decision(
            name="output_dir",
            question="Output directory for onboarding artifacts",
            resolution_field=None,
            override_flag="--output-dir",
        ),
        Decision(
            name="target_profile",
            question="Target profile",
            resolution_field="active_target_profile",
            override_flag="--target-profile",
            options_provider=lambda: tuple(target_names()),
        ),
        Decision(
            name="model_backend",
            question="Local model backend",
            resolution_field="model_backend",
            override_flag="--model-backend",
            options_provider=lambda: tuple(BACKENDS),
        ),
        Decision(
            name="model_alias",
            question="Primary model alias",
            resolution_field="model_alias",
            override_flag="--model-alias",
            options_provider=lambda: tuple(MODEL_ALIASES),
        ),
        Decision(
            name="agent_profile",
            question="Agent profile",
            resolution_field="active_agent_profile",
            override_flag="--agent-profile",
            options_provider=lambda: tuple(agent_profile_names()),
        ),
        Decision(
            name="verification_profile",
            question="Verification profile",
            resolution_field="active_verification_profile",
            override_flag="--verification-profile",
            options_provider=lambda: tuple(verification_profile_names()),
        ),
        Decision(
            name="artifact_root",
            question="Platform artifact root",
            resolution_field="platform_artifact_root",
            override_flag="--artifact-root",
        ),
        Decision(
            name="runtime_mode",
            question="Runtime mode",
            resolution_field="runtime_mode",
            override_flag="--runtime-mode",
            options_provider=lambda: tuple(RUNTIME_MODES),
        ),
        Decision(
            name="allow_artifact_root_inside_target",
            question="Allow the artifact root inside the target repository",
            resolution_field="allow_artifact_root_inside_target",
            override_flag="--allow-artifact-root-inside-target",
            options_provider=lambda: BOOL_ANSWERS,
        ),
    )


def get_decision(decision_name: str) -> Decision | None:
    for decision in decisions():
        if decision.name == decision_name:
            return decision
    return None


def validate_decision_value(decision_name: str, value: str) -> list[str]:
    """Registry-validate one decision answer against the registry that owns it. Empty list = valid.

    The registry is read from the decision record, never from a second dict beside it. The old
    second dict had entries for `agent_profile` and `verification_profile` that the options
    provider lacked, so those two could be rejected but never rendered.
    """
    decision = get_decision(decision_name)
    if decision is None:
        return [f"unknown decision: {decision_name}"]

    if decision.free_form:
        if not value or not value.strip():
            return [f"{decision_name} must be a non-empty value"]
        return []

    allowed = decision.allowed()
    if value not in allowed:
        return [f"{decision_name} must be one of: {', '.join(allowed)} (got {value!r})"]
    return []


def prompted_decision_options_provider(decision_name: str) -> Callable[[], tuple[str, ...]] | None:
    """The live registry behind one decision, as a callable reference."""
    decision = get_decision(decision_name)
    return decision.options_provider if decision is not None else None


def init_wizard_step_definitions(defaults: dict[str, str | None] | None = None):
    """All nine decisions as :class:`~builder_ii.wizard_framework.WizardStep`s.

    ``defaults`` is supplied by ``builder init`` from config resolution at runtime; the
    definitions stay importable without one because the transcription pin in
    ``tests/test_wizard_framework.py`` needs only questions and providers. Question text,
    registry rendering, and acceptance are what ``builder init`` has always shown for the four:
    the question literal, allowed values rendered from the live registry at prompt time,
    and :func:`validate_decision_value` as the boundary. The other five now show the same.
    """
    from builder_ii.wizard_framework import WizardStep

    resolved = dict(defaults or {})
    return tuple(
        WizardStep(
            id=decision.name,
            question=decision.question,
            options_provider=decision.options_provider,
            validator=(lambda value, _name=decision.name: validate_decision_value(_name, value)),
            default=resolved.get(decision.name),
            free_form=decision.free_form,
            render_options_in_question=decision.render_options_in_question,
        )
        for decision in decisions()
    )
