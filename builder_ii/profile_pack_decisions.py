"""The decisions `builder-profile-pack scaffold` takes, as wizard steps.

`builder-profile-pack scaffold` accepts its four decisions as flags and nothing else: an operator
who does not already know the target-profile registry has to read the source to find it. The wizard
asks them, rendering the allowed values from the live registry at prompt time.

Same invariant as every other wizard on `builder_ii.wizard_framework`: a step names the registry
that owns its values (`options_provider`, a callable) and never transcribes them into prompt text.
`profile_pack_cli._normalize_target` used to hold `{"generic", "builder", "core"}` as a set literal
*and* repeat it inside its error message -- two transcriptions of `target_names()`, both silently
stale the moment a fourth target profile is added. That is the same defect `builder-setup wizard`
had when it offered three of eight live backends (Ladder 5 PR-2).

The wizard emits exactly what `scaffold` emits: a passive profile-pack manifest, validated, written
only to an explicit output path. It never applies, and it holds no authority `scaffold` does not.
"""

from __future__ import annotations

from builder_ii.target_profiles import target_names
from builder_ii.wizard_framework import WizardStep

DEFAULT_PACK_ID = "builder-passive-profile-pack"
DEFAULT_TASK = "render passive profile-pack substrate"

# The scaffold decision names, in prompt order. `project_root` is not here: it is a fact about
# where the command runs, not a decision an operator makes about the pack.
DECISION_IDS: tuple[str, ...] = ("pack_id", "target", "task", "output")


def validate_target(value: str) -> list[str]:
    """Registry-validate a target profile. Empty list = valid.

    The registry is `target_names()`, read at call time. The error message is composed from it, so
    a fourth target profile appears in the message without anyone editing the message.
    """
    allowed = target_names()
    if value not in allowed:
        return [f"target must be one of: {', '.join(allowed)} (got {value!r})"]
    return []


def _require_non_empty(name: str):
    def validator(value: str) -> list[str]:
        return [] if value and value.strip() else [f"{name} must be a non-empty value"]

    return validator


def profile_pack_wizard_steps(defaults: dict[str, str | None] | None = None) -> tuple[WizardStep, ...]:
    """The four scaffold decisions, rendered from the live registries."""
    resolved = dict(defaults or {})
    return (
        WizardStep(
            id="pack_id",
            question="Profile pack id",
            validator=_require_non_empty("pack_id"),
            default=resolved.get("pack_id") or DEFAULT_PACK_ID,
            free_form=True,
        ),
        WizardStep(
            id="target",
            question="Target profile",
            options_provider=lambda: tuple(target_names()),
            validator=validate_target,
            default=resolved.get("target") or "builder",
        ),
        WizardStep(
            id="task",
            question="Task description",
            validator=_require_non_empty("task"),
            default=resolved.get("task") or DEFAULT_TASK,
            free_form=True,
        ),
        # No validator: an empty answer is meaningful here, and means "print to stdout".
        WizardStep(
            id="output",
            question="Write the manifest to this path (blank prints it to stdout)",
            default=resolved.get("output") or "",
            free_form=True,
        ),
    )
