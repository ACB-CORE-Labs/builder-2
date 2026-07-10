"""Generic wizard framework: the state machine behind builder-II's interactive onboarding surfaces.

Ladder 5 PR-1. This generalizes the step engine that already existed in miniature in
``builder_ii/deepagents_forge_wizard.py`` (``ForgeStep`` with ``is_required``/``validate``/
``apply_to``, plus a driver carrying ``current_step``/``get_progress``/``apply``/``skip``/
``back``/``is_complete``) into a spec-agnostic module that ``builder init`` and
``builder-setup wizard`` are re-expressed on. The forge wizard itself is deliberately NOT
migrated here: it is a separate, tested surface, and PR-1 is behavior-preserving.

THE INVARIANT THIS MODULE EXISTS TO CARRY:

    A wizard step may never name its allowed values; it may only reference the registry
    that owns them.

A prompt string that transcribes its allowed values is a doc that claims a capability the
code may not back, and ``builder-platform audit-docs`` cannot see it -- that is exactly how
``builder-setup wizard`` came to offer 3 of 8 live backends. So a :class:`WizardStep`
carries its values as ``options_provider``, a *callable* reference to the owning registry,
and :meth:`WizardStep.render_question` composes the prompt text from that registry at
prompt time. Adding a ninth backend then updates every wizard automatically, and a stale
prompt becomes unrepresentable. ``tests/test_wizard_framework.py`` pins the invariant: a
step's literal ``question`` text must not contain a member of any known decision registry.

``free_form`` steps (an output directory; the PR-1 as-is port of the setup wizard's lying
prompts, exempted by name in the pin until PR-2 fixes them) have no provider and no
registry validation -- they exist so that porting a defective wizard does not require
fixing it in the same commit as the extraction.

This module renders prompts and validates answers. It never applies anything: the wizards
built on it emit governed artifacts and stop, and the apply step remains a separately
invoked, digest-confirmed command -- the process that renders a digest must not also
harvest the confirmation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field


class WizardAborted(Exception):
    """Raised by the prompt loop when a required step exhausts its answer attempts."""

    def __init__(self, step_id: str) -> None:
        super().__init__(f"no valid answer for wizard step {step_id!r}")
        self.step_id = step_id


@dataclass(frozen=True)
class WizardStep:
    """One wizard decision: a literal question, a registry reference, and a validator.

    ``question`` is the human-facing prompt text and must never transcribe allowed values;
    ``options_provider`` is the live registry reference they are rendered from instead.
    ``validator`` returns a list of error strings (empty = valid) so the CLIs keep their
    exact existing error messages; a step with ``validator=None`` accepts any answer.
    """

    id: str
    question: str
    options_provider: Callable[[], tuple[str, ...]] | None = None
    validator: Callable[[str], list[str]] | None = None
    default: str | None = None
    # A default that cannot be known before an earlier step is answered. `builder init` shows the
    # agent and verification profiles that *this* target profile implies, and the operator has not
    # chosen a target when the wizard is built. Snapshotting the default there showed -- and, on
    # Enter, recorded -- another target's profiles. Read at prompt time, from the answers so far,
    # for the same reason `options_provider` is read at prompt time rather than snapshotted.
    default_from: Callable[[dict[str, str]], str | None] | None = None
    free_form: bool = False
    # Presentation, not policy: a large registry (MODEL_ALIASES has 50 entries) may choose
    # not to enumerate into the prompt line. The step still references its registry through
    # options_provider -- validation and drift both keep working -- and a rejection surfaces
    # the full registry through the validator's error message. What a step may never do is
    # enumerate a SUBSET: rendering is all-from-the-registry or nothing, so a prompt cannot
    # claim fewer values than exist. That subset claim is the lie this framework exists to
    # make unrepresentable.
    render_options_in_question: bool = True

    def allowed_values(self) -> tuple[str, ...]:
        if self.options_provider is None:
            return ()
        return tuple(self.options_provider())

    def resolved_default(self, answers: dict[str, str]) -> str | None:
        """The default to show, given every answer taken so far."""
        if self.default_from is None:
            return self.default
        return self.default_from(answers)

    def render_question(self) -> str:
        """Compose the prompt text from the live registry at prompt time, never earlier."""
        allowed = self.allowed_values()
        if allowed and self.render_options_in_question:
            return f"{self.question} ({', '.join(allowed)})"
        return self.question

    def validate(self, value: str) -> list[str]:
        if self.validator is None:
            return []
        return self.validator(value)


@dataclass
class WizardEngine:
    """Cursor/history state machine over an ordered tuple of steps.

    The shape is ``ForgeWizard``'s: ``current_step``, ``get_progress``, ``apply``,
    ``skip``, ``back``, ``is_complete``, with branching generalized into ``skip_when``
    (the forge wizard's hitl_gates auto-skip is one instance of it). Answers accumulate
    in a plain dict rather than onto a domain spec, which is what makes it generic.
    """

    steps: tuple[WizardStep, ...]
    skip_when: Callable[[WizardStep, dict[str, str]], bool] | None = None
    answers: dict[str, str] = field(default_factory=dict)
    cursor: int = 0
    history: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.steps = tuple(self.steps)
        seen: set[str] = set()
        for step in self.steps:
            if step.id in seen:
                raise ValueError(f"duplicate wizard step id: {step.id!r}")
            seen.add(step.id)
        self.cursor = self._skip_preanswered(0)

    def preanswer(self, step_id: str, value: str) -> None:
        """Record an answer supplied outside the prompt loop (a CLI flag).

        Deliberately no validation here: both existing wizards validate flag answers on
        their own terms before the loop (``builder init`` fails closed with exit 2;
        ``builder-setup wizard`` historically accepts flags as-is), and PR-1 preserves
        both behaviors exactly.
        """
        if step_id not in {step.id for step in self.steps}:
            raise KeyError(f"unknown wizard step id: {step_id!r}")
        self.answers[step_id] = value
        if not self.is_complete():
            self.cursor = self._skip_preanswered(self.cursor)

    def current_step(self) -> WizardStep:
        return self.steps[self.cursor]

    def get_progress(self) -> tuple[int, int]:
        return self.cursor + 1, len(self.steps)

    def is_complete(self) -> bool:
        return self.cursor >= len(self.steps)

    def apply(self, value: str) -> list[str]:
        """Validate ``value`` for the current step; record it and advance when valid."""
        step = self.current_step()
        errors = step.validate(value)
        if errors:
            return errors
        self.answers[step.id] = value
        self.history.append(self.cursor)
        self.cursor = self._skip_preanswered(self.cursor + 1)
        return []

    def skip(self) -> bool:
        """Advance past the current step without an answer. Free-form steps only."""
        step = self.current_step()
        if not step.free_form:
            return False
        self.history.append(self.cursor)
        self.cursor = self._skip_preanswered(self.cursor + 1)
        return True

    def back(self) -> bool:
        if self.history:
            self.cursor = self.history.pop()
            return True
        return False

    def _skip_preanswered(self, index: int) -> int:
        while index < len(self.steps):
            step = self.steps[index]
            if step.id in self.answers:
                index += 1
                continue
            if self.skip_when is not None and self.skip_when(step, dict(self.answers)):
                index += 1
                continue
            return index
        return index


def run_typer_prompt_loop(
    engine: WizardEngine,
    *,
    prompt_fn: Callable[..., object],
    invalid_echo: Callable[[str], None] | None = None,
    max_attempts: int | None = None,
    strip_answers: bool = True,
) -> tuple[dict[str, str], bool]:
    """Drive an engine through a Typer-style prompt function until complete.

    Returns ``(answers, prompted_any)``. ``prompted_any`` is True iff at least one step was
    interactively asked -- ``builder init`` uses it to record ``onboarding_mode`` as
    ``"wizard"`` rather than ``"init"``. ``max_attempts`` counts total asks per step
    (``builder init`` allows 3); exhausting them raises :class:`WizardAborted` so the
    caller can print its own abort message and exit without writing artifacts.
    ``strip_answers=False`` preserves ``builder-setup wizard``'s historical behavior of
    taking prompt answers exactly as typed.
    """
    prompted_any = False
    while not engine.is_complete():
        step = engine.current_step()
        question = step.render_question()
        prompted_any = True
        attempts = 0
        while True:
            answer = str(prompt_fn(question, default=step.resolved_default(engine.answers)))
            if strip_answers:
                answer = answer.strip()
            errors = engine.apply(answer)
            if not errors:
                break
            if invalid_echo is not None:
                for error in errors:
                    invalid_echo(error)
            attempts += 1
            if max_attempts is not None and attempts >= max_attempts:
                raise WizardAborted(step.id)
    return dict(engine.answers), prompted_any


def known_decision_registries() -> dict[str, tuple[str, ...]]:
    """Every registry a wizard decision may validate against, by decision name.

    This is the sweep list for the transcription pin in ``tests/test_wizard_framework.py``:
    no step's literal ``question`` text may contain a member of any of these. Routed through
    ``builder_ii.init_decisions`` module globals so a monkeypatched registry (the drift
    test) is visible here too.
    """
    from builder_ii import init_decisions

    return {
        "target_profile": tuple(init_decisions.target_names()),
        "model_backend": tuple(init_decisions.BACKENDS),
        "model_alias": tuple(init_decisions.MODEL_ALIASES),
        "agent_profile": tuple(init_decisions.agent_profile_names()),
        "verification_profile": tuple(init_decisions.verification_profile_names()),
    }


def transcribed_registry_members(question: str, registries: Iterable[tuple[str, ...]]) -> list[str]:
    """Registry members appearing verbatim (word-bounded) in a step's literal question text.

    Word-bounded so that e.g. the alias ``llama`` does not false-positive inside the
    backend ``ollama``. Used by the enforcement pin; returning the members (not a bool)
    makes the pin's failure message name exactly what was transcribed.
    """
    import re

    hits: list[str] = []
    for registry in registries:
        for member in registry:
            if re.search(rf"(?<![\w-]){re.escape(member)}(?![\w-])", question):
                hits.append(member)
    return sorted(set(hits))
