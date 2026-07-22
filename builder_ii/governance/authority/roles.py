from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.lifecycle.setup.lane_guides import guide_names

roles_app = typer.Typer(help="Print read-only builder-II role manifests.")
console = Console()


@dataclass(frozen=True)
class BuilderRole:
    name: str
    model_alias: str
    lane_guides: tuple[str, ...]
    purpose: str
    authority: str
    forbidden: tuple[str, ...]
    escalation: str
    output_contract: str


_ROLES: dict[str, BuilderRole] = {
    "failure_reviewer": BuilderRole(
        name="failure_reviewer",
        model_alias="phi-reasoning",
        lane_guides=("review_failure",),
        purpose="Diagnose failed commands, tests, and runtime checks from supplied logs.",
        authority="May summarize evidence and propose the smallest safe next fix.",
        forbidden=("claiming repo inspection without supplied evidence", "editing files", "running commands"),
        escalation="Escalate to patch_planner only after root cause is identified and a bounded fix exists.",
        output_contract="Root cause, Evidence, Minimal fix, Validation.",
    ),
    "patch_planner": BuilderRole(
        name="patch_planner",
        model_alias="qwen-coder",
        lane_guides=("draft_patch_plan",),
        purpose="Turn a known small implementation slice into a bounded patch plan.",
        authority="May identify files, tests, and change shape for human/operator implementation.",
        forbidden=("whole-repo rewrites", "unreviewed autonomous edits", "scope expansion beyond supplied task"),
        escalation="Escalate to invariant_auditor when safety boundaries or CORE invariants may be affected.",
        output_contract="Files, Changes, Tests, Risks.",
    ),
    "invariant_auditor": BuilderRole(
        name="invariant_auditor",
        model_alias="phi-reasoning",
        lane_guides=("audit_invariants",),
        purpose="Check proposed changes against builder-II and CORE safety boundaries.",
        authority="May block progression by identifying missing evidence or unsafe assumptions.",
        forbidden=(
            "approving unknown tool execution",
            "treating candidate lanes as defaults",
            "ignoring verification gaps",
        ),
        escalation="Escalate to operator decision when a boundary cannot be verified from supplied context.",
        output_contract="Checked invariants, Possible violations, Required evidence, Validation.",
    ),
    "diff_summarizer": BuilderRole(
        name="diff_summarizer",
        model_alias="phi-reasoning",
        lane_guides=("summarize_diff",),
        purpose="Summarize a diff or PR before merge review.",
        authority="May describe supplied changes and call out validation gaps.",
        forbidden=("inventing test results", "assuming merge safety", "hiding cautions"),
        escalation="Escalate to invariant_auditor if the diff touches safety, routing, runtime, or verification behavior.",
        output_contract="Changed, Why it matters, Validation, Caution.",
    ),
    "handoff_scribe": BuilderRole(
        name="handoff_scribe",
        model_alias="qwen-coder",
        lane_guides=("prepare_handoff",),
        purpose="Prepare exact continuity notes for the next operator or session.",
        authority="May organize supplied branch, PR, validation, blocker, and next-step state.",
        forbidden=(
            "omitting known blockers",
            "turning unknowns into facts",
            "claiming future work will happen automatically",
        ),
        escalation="Escalate to failure_reviewer when the handoff contains unresolved failing logs.",
        output_contract="Branch/PR, What changed, Validation, Known issues, Next action.",
    ),
    "lane_router": BuilderRole(
        name="lane_router",
        model_alias="phi-reasoning",
        lane_guides=("probe_model_fit",),
        purpose="Choose the smallest appropriate local lane for a supplied task.",
        authority="May recommend a model alias and fallback, but may not auto-switch or start runtimes.",
        forbidden=(
            "routing Gemma as normal mlx-lm chat",
            "routing heavy lanes by default",
            "bypassing runtime reset discipline",
        ),
        escalation="Escalate to operator decision for heavy/candidate/sidecar lanes.",
        output_contract="Recommended lane, Reason, Boundary, Fallback.",
    ),
}


def builder_roles() -> tuple[BuilderRole, ...]:
    return tuple(_ROLES[name] for name in sorted(_ROLES))


def role_names() -> tuple[str, ...]:
    return tuple(role.name for role in builder_roles())


def get_role(name: str) -> BuilderRole:
    try:
        return _ROLES[name]
    except KeyError as exc:
        valid = ", ".join(role_names())
        raise ValueError(f"unknown role {name!r}; expected one of: {valid}") from exc


def validate_roles() -> tuple[str, ...]:
    known_guides = set(guide_names())
    problems: list[str] = []
    for role in builder_roles():
        if not role.lane_guides:
            problems.append(f"{role.name}: missing lane guide")
        for guide in role.lane_guides:
            if guide not in known_guides:
                problems.append(f"{role.name}: unknown lane guide {guide}")
        if role.model_alias not in {"phi-reasoning", "qwen-coder"}:
            problems.append(f"{role.name}: non-default model alias {role.model_alias}")
        if not role.forbidden:
            problems.append(f"{role.name}: missing forbidden boundary")
    return tuple(problems)


def _rows(roles: Iterable[BuilderRole]) -> Table:
    table = Table("Role", "Model", "Guides", "Purpose")
    for role in roles:
        table.add_row(role.name, role.model_alias, ", ".join(role.lane_guides), role.purpose)
    return table


@roles_app.command("list")
def list_roles() -> None:
    """List read-only builder-II role manifests."""
    console.print(_rows(builder_roles()))


@roles_app.command("show")
def show_role(name: str = typer.Argument(..., help="Role name; run `builder-roles list`.")) -> None:
    """Print one role manifest."""
    try:
        role = get_role(name)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"# {role.name}")
    console.print(f"model: {role.model_alias}")
    console.print(f"lane_guides: {', '.join(role.lane_guides)}")
    console.print(f"purpose: {role.purpose}")
    console.print(f"authority: {role.authority}")
    console.print(f"forbidden: {', '.join(role.forbidden)}")
    console.print(f"escalation: {role.escalation}")
    console.print(f"output_contract: {role.output_contract}")


@roles_app.command("validate")
def validate_role_manifest() -> None:
    """Validate role manifest consistency."""
    problems = validate_roles()
    if not problems:
        console.print("[green]Role manifest valid[/]")
        return
    for problem in problems:
        console.print(f"[red]{problem}[/]")
    raise typer.Exit(1)
