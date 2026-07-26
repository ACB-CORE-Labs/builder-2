"""``builder chain`` -- the governed walkthrough of the full patch loop, stage by stage.

WHAT THIS REPLACED, and why the replacement looks nothing like it:

The previous version of this module was a `subprocess.run` wizard that drove the whole loop
through to ``builder-hitl apply-patch``. It had four defects that together made it worse than
having no command at all:

1. It could not run. Its first statement is ``enforce_command_authority("builder chain")`` and
   ``builder chain`` had no record in the registry, so every invocation raised an unhandled
   ``CommandAuthorityError`` traceback -- after prompting the operator for a task description.
2. It swallowed every failure after step 1 with a bare ``pass`` ("Just continue anyway if it
   doesn't match the exact cli") and then printed "Chain wizard completed successfully!". A
   command that reports success it did not verify is the exact defect this codebase exists to
   make unrepresentable.
3. Its argv was wrong. It called ``builder-hitl propose-patch --from-last``; that command has no
   ``--from-last`` and requires ``--diff-file``, ``--output``, ``--description`` and ``--reason``.
   Every run of step 4 would have failed even with authority.
4. ``tests/test_chain_cli.py`` tested a different module (``chain_summary_cli``), so none of this
   was covered.

So this is now a **composing** walkthrough, matching what STRATUM already does: it explains the
loop, names the command that performs each stage, and reports the authority and ratification level
each stage carries. It runs nothing. That is a *narrowing* of authority -- the subprocess path to
patch application is gone -- not a new capability.

THE INVARIANT THIS MODULE CARRIES:

    A stage may not transcribe its command's options; it may only name the command.

The same rule ``wizard_framework`` enforces on prompt text, for the same reason: the old module's
transcribed flags were wrong, and nothing could see that they were wrong. A stage names its
command and sends the operator to ``--help``, which cannot go stale.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.governance.authority import enforce_command_authority, get_command_record
from builder_ii.governance.ratification_points import get_ratification_point

chain_app = typer.Typer(
    name="chain",
    help="Walk the governed patch loop stage by stage. Composes and explains; runs nothing.",
    invoke_without_command=True,
)


@dataclass(frozen=True)
class ChainStage:
    """One stage of the governed patch loop.

    ``command`` is looked up in the command-authority registry at render time so the tier and
    promotion state shown are the live ones, and ``ratification_point`` is resolved the same way,
    so a stage cannot claim a confirmation is delegable when the registry says otherwise.
    """

    number: int
    title: str
    produces: str
    command: str
    ratification_point: str | None = None


CHAIN_STAGES: tuple[ChainStage, ...] = (
    ChainStage(
        number=1,
        title="Plan",
        produces="a governed orchestration plan artifact",
        command="builder orchestration plan",
    ),
    ChainStage(
        number=2,
        title="Assign",
        produces="a rendered assignment bound to the plan and a target profile",
        command="builder orchestration render-assignment",
    ),
    ChainStage(
        number=3,
        title="Run",
        produces="a run envelope, events, receipt, and replay under an approved envelope",
        command="builder-deepagents run-approved",
    ),
    ChainStage(
        number=4,
        title="Propose",
        produces="a patch proposal bound to a diff and its digest",
        command="builder-hitl propose-patch",
    ),
    ChainStage(
        number=5,
        title="Approve",
        produces="a digest-bound approval: evidence that a human decided",
        command="builder-hitl approve-patch",
        ratification_point="hitl.approve_patch.patch_digest",
    ),
    ChainStage(
        number=6,
        title="Apply",
        produces="the applied patch plus its execution artifacts",
        command="builder-hitl apply-patch",
    ),
)


def _authority_line(command: str) -> str:
    """Live tier/state for a stage's command, or an explicit absence.

    An unregistered command is reported as such rather than omitted: `builder chain` itself was
    unregistered and unrunnable for exactly as long as nobody printed that fact.
    """
    record = get_command_record(command)
    if record is None:
        return "authority:  NO REGISTERED RECORD -- this command cannot pass enforcement"
    return f"authority:  {record.tier} / `{record.promotion_state}`"


def _ratification_line(stage: ChainStage) -> str | None:
    if stage.ratification_point is None:
        return None
    point = get_ratification_point(stage.ratification_point)
    if point is None:
        return f"ratifies:   {stage.ratification_point} (NOT REGISTERED)"
    return f"ratifies:   {point.id} -- {point.what_is_ratified}"


@chain_app.callback()
def chain_walkthrough(
    task: str | None = typer.Option(None, "--task", help="Optional task description, echoed as the objective."),
) -> None:
    """Explain the governed patch loop: what each stage produces and what authority it carries."""
    enforce_command_authority("builder chain")

    lines = ["builder-II governed patch loop", ""]
    if task:
        lines.extend([f"objective: {task}", ""])
    lines.append("This walkthrough composes and explains. It runs nothing: each stage names the")
    lines.append("command that performs it, and you run that command yourself.")
    lines.append("")

    for stage in CHAIN_STAGES:
        lines.append(f"{stage.number}. {stage.title}")
        lines.append(f"   produces:   {stage.produces}")
        lines.append(f"   command:    {stage.command}")
        lines.append(f"   {_authority_line(stage.command)}")
        ratification = _ratification_line(stage)
        if ratification:
            lines.append(f"   {ratification}")
        lines.append(f"   options:    run `{stage.command} --help` for its exact options")
        lines.append("")

    lines.extend(
        [
            "Stage 5 mints human approval evidence and can never be delegated to a standing grant.",
            "See `builder-govern list-points` for what may be delegated and `builder-govern policy-show`",
            "for the ratification level currently in force at each point.",
        ]
    )
    echo_stdout("\n".join(lines) + "\n")
