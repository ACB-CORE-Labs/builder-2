"""The user-facing golden path: which onboarding stage a project is at, and what to run next.

The stage table used to exist twice -- once as the ``if`` ladder in :func:`get_onboarding_state`
and once, transcribed, as a literal list inside ``builder course``. Two copies of a sequence is a
copy that drifts, and the rendered one had already lost the description text. :data:`GOLDEN_PATH`
is now the single source both read, so a stage added here appears in every surface that walks it.

Every stage predicate is a filesystem existence check and nothing else: this module recommends a
command, it never runs one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.lifecycle.setup.operator_next import create_operator_next_action_report

READY_STATE = "READY"


@dataclass(frozen=True)
class GoldenPathStage:
    """One onboarding stage: how to tell it is done, and the safe command that does it.

    ``is_satisfied`` takes the project root rather than closing over the working directory so a
    caller can ask about a project other than the one it happens to be standing in.
    """

    state: str
    title: str
    description: str
    safe_command: str
    is_satisfied: Callable[[Path], bool]


def _has_env(root: Path) -> bool:
    return (root / ".env").exists()


def _has_setup_plan(root: Path) -> bool:
    return (root / ".builder" / "artifacts" / "setup-plan.json").exists()


def _has_setup_receipt(root: Path) -> bool:
    return (root / ".builder" / "artifacts" / "setup-receipt.json").exists()


def _has_session(root: Path) -> bool:
    session_root = root / ".builder" / "session"
    return session_root.exists() and bool(list(session_root.iterdir()))


GOLDEN_PATH: tuple[GoldenPathStage, ...] = (
    GoldenPathStage(
        state="NO_ENV",
        title="Initialize Configuration",
        description="The first step is to configure your environment variables.",
        safe_command="cp .env.example .env",
        is_satisfied=_has_env,
    ),
    GoldenPathStage(
        state="NO_PLAN",
        title="Create Initialization Plan",
        description="Generate the initial setup plan for your project.",
        safe_command="builder init",
        is_satisfied=_has_setup_plan,
    ),
    GoldenPathStage(
        state="NO_RECEIPT",
        title="Apply Initialization Plan",
        description="Apply the setup plan to initialize your artifact directories.",
        safe_command="builder-setup apply",
        is_satisfied=_has_setup_receipt,
    ),
    GoldenPathStage(
        state="NO_SESSION",
        title="Prepare First Session Package",
        description="Create your first governed session package to fill the artifact chain.",
        safe_command='builder-session prepare-package generic -o .builder/session --task "first governed session"',
        is_satisfied=_has_session,
    ),
)

#: The terminal stage. Not in `GOLDEN_PATH` because it has no predicate of its own: it is what
#: being past every stage means.
READY_STAGE = GoldenPathStage(
    state=READY_STATE,
    title="Open Stratum",
    description="Your project is initialized. Open Stratum to inspect the artifact chain and compose commands.",
    safe_command="builder stratum",
    is_satisfied=lambda _root: True,
)


def current_stage(root: Path | None = None) -> GoldenPathStage:
    """The first unsatisfied stage, or :data:`READY_STAGE` when every stage is satisfied."""
    project_root = Path(root) if root is not None else Path(".")
    for stage in GOLDEN_PATH:
        if not stage.is_satisfied(project_root):
            return stage
    return READY_STAGE


def get_onboarding_state(root: Path | None = None) -> dict[str, Any]:
    """Evaluate the project's setup state and return the next recommended command."""
    stage = current_stage(root)
    return {
        "title": stage.title,
        "description": stage.description,
        "safe_command": stage.safe_command,
        "state": stage.state,
    }


def create_user_next_action_report() -> dict[str, Any]:
    """Generates the next action report prioritizing user onboarding over platform matrix."""
    onboarding = get_onboarding_state()

    if onboarding["state"] != READY_STATE:
        return {
            "ordered_next_actions": [
                {
                    "capability": "Project Setup: " + onboarding["title"],
                    "state": onboarding["state"],
                    "safe_commands": [onboarding["safe_command"]],
                    "description": onboarding["description"],
                }
            ]
        }

    # If the user is fully onboarded, we check if they are missing core platform development steps.
    try:
        report = create_operator_next_action_report()
        actions = report.get("ordered_next_actions", [])
        if actions:
            # If the only recommendation is to look at the matrix, the user is likely not a core developer
            # or they have finished their core work. Suppress this for normal operators.
            if actions[0].get("safe_commands") == ["builder-platform matrix"]:
                return {"ordered_next_actions": []}
            return report
    except Exception:
        pass

    return {"ordered_next_actions": []}
