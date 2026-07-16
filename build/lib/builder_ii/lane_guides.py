from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import typer
from rich.console import Console
from rich.table import Table

lane_app = typer.Typer(help="Print reusable builder-II lane prompts.")
console = Console()


@dataclass(frozen=True)
class LaneGuide:
    name: str
    model_alias: str
    use_when: str
    output_contract: str
    template: str


_GUIDES: dict[str, LaneGuide] = {
    "review_failure": LaneGuide(
        name="review_failure",
        model_alias="phi-reasoning",
        use_when="A test, command, or local runtime check failed and the operator needs a concise diagnosis.",
        output_contract="Return root cause, evidence, smallest fix, and next validation command. Do not invent repo state.",
        template=(
            "You are reviewing a builder-II failure.\n"
            "Goal: identify the smallest safe next fix.\n"
            "Rules: use only the supplied log/context; distinguish confirmed facts from guesses; do not claim to edit files.\n"
            "Return exactly four sections: Root cause, Evidence, Minimal fix, Validation.\n\n"
            "Context:\n{context}"
        ),
    ),
    "draft_patch_plan": LaneGuide(
        name="draft_patch_plan",
        model_alias="qwen-coder",
        use_when="A small implementation slice is known and the operator needs a bounded patch plan before editing.",
        output_contract="Return files to touch, exact change shape, tests, and risk boundary.",
        template=(
            "You are drafting a small builder-II patch plan.\n"
            "Goal: produce a bounded implementation plan, not code unless asked.\n"
            "Rules: keep scope narrow; preserve existing safety rails; include tests; call out unknowns.\n"
            "Return exactly four sections: Files, Changes, Tests, Risks.\n\n"
            "Task:\n{context}"
        ),
    ),
    "audit_invariants": LaneGuide(
        name="audit_invariants",
        model_alias="phi-reasoning",
        use_when="A proposed change may affect CORE or builder-II safety invariants.",
        output_contract="Return invariant checks, violations, uncertainty, and validation commands.",
        template=(
            "You are auditing builder-II/CORE invariants.\n"
            "Rules: refusal-first; no speculative pass/fail; identify exact evidence required.\n"
            "Check for: stochastic routing, autonomous edits, unsafe model switching, unvalidated tool execution, and missing verification.\n"
            "Return exactly four sections: Checked invariants, Possible violations, Required evidence, Validation.\n\n"
            "Change/context:\n{context}"
        ),
    ),
    "summarize_diff": LaneGuide(
        name="summarize_diff",
        model_alias="phi-reasoning",
        use_when="A diff or PR needs a concise operator summary before merge.",
        output_contract="Return what changed, why it matters, validation, and merge caution.",
        template=(
            "You are summarizing a builder-II diff for merge review.\n"
            "Rules: summarize only supplied diff/context; no unsupported claims; identify validation actually shown.\n"
            "Return exactly four sections: Changed, Why it matters, Validation, Caution.\n\n"
            "Diff/context:\n{context}"
        ),
    ),
    "prepare_handoff": LaneGuide(
        name="prepare_handoff",
        model_alias="qwen-coder",
        use_when="Work is stopping and another session/operator needs exact continuity.",
        output_contract="Return branch, commits/PRs, commands run, current blockers, and next action.",
        template=(
            "You are preparing a builder-II handoff note.\n"
            "Rules: be concrete; include exact branch/PR/test status when supplied; mark unknowns clearly.\n"
            "Return exactly five sections: Branch/PR, What changed, Validation, Known issues, Next action.\n\n"
            "Context:\n{context}"
        ),
    ),
    "probe_model_fit": LaneGuide(
        name="probe_model_fit",
        model_alias="phi-reasoning",
        use_when="The operator needs to choose which local lane should handle a task.",
        output_contract="Return recommended alias, reason, boundary, and fallback.",
        template=(
            "You are selecting a builder-II local model lane.\n"
            "Available defaults: phi-reasoning for probe/review; qwen-coder for targeted code planning/review; Gemma only as sidecar; heavy lanes explicit opt-in only.\n"
            "Return exactly four sections: Recommended lane, Reason, Boundary, Fallback.\n\n"
            "Task:\n{context}"
        ),
    ),
}


def lane_guides() -> tuple[LaneGuide, ...]:
    return tuple(_GUIDES[name] for name in sorted(_GUIDES))


def guide_names() -> tuple[str, ...]:
    return tuple(guide.name for guide in lane_guides())


def get_guide(name: str) -> LaneGuide:
    try:
        return _GUIDES[name]
    except KeyError as exc:
        valid = ", ".join(guide_names())
        raise ValueError(f"unknown lane guide {name!r}; expected one of: {valid}") from exc


def render_guide(name: str, *, context: str = "<paste context here>") -> str:
    guide = get_guide(name)
    return guide.template.format(context=context)


def _rows(guides: Iterable[LaneGuide]) -> Table:
    table = Table("Name", "Model", "Use when")
    for guide in guides:
        table.add_row(guide.name, guide.model_alias, guide.use_when)
    return table


@lane_app.command("list")
def list_guides() -> None:
    """List available reusable lane prompts."""
    console.print(_rows(lane_guides()))


@lane_app.command("show")
def show_guide(
    name: str = typer.Argument(..., help="Guide name; run `builder-task list`."),
    context: str = typer.Option("<paste context here>", "--context", "-c", help="Context to insert into the template."),
) -> None:
    """Print one reusable lane prompt."""
    try:
        guide = get_guide(name)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"# {guide.name}")
    console.print(f"# model: {guide.model_alias}")
    console.print(f"# use_when: {guide.use_when}")
    console.print(f"# output_contract: {guide.output_contract}\n")
    console.print(render_guide(name, context=context))
