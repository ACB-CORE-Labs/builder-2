"""STRATUM first-run guide and operator walkthrough content.

All commands here are real console scripts or documented entry points.
Opt-out is explicit: --no-guide, STRATUM_SKIP_GUIDE=1, or dismiss file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GUIDE_DISMISS_FILENAME = "stratum_guide_dismissed"
ENV_SKIP_GUIDE = "STRATUM_SKIP_GUIDE"


@dataclass(frozen=True)
class WalkthroughStep:
    """One operator step: what to do, the exact command, what STRATUM shows after."""

    number: int
    title: str
    why: str
    command: str | None  # None = in-TUI only
    stratum_after: str
    optional: bool = False


# Verified against `uv run <cmd> --help` for this repo revision.
WALKTHROUGH_STEPS: tuple[WalkthroughStep, ...] = (
    WalkthroughStep(
        number=1,
        title="Install dependencies",
        why="STRATUM needs Textual + the builder-II package env.",
        command="uv sync",
        stratum_after="App launches; spine empty until artifacts exist.",
    ),
    WalkthroughStep(
        number=2,
        title="Sanity-check the platform",
        why="Confirm install and see capability truth before any agent work.",
        command="uv run builder-platform matrix",
        stratum_after="Press C for audit matrix (read-only projection of the same truth).",
    ),
    WalkthroughStep(
        number=3,
        title="See recommended next actions",
        why="Operator-next lists incomplete capabilities with safe compose commands.",
        command="uv run builder-platform next",
        stratum_after="Press N to compose the top safe command into the Command Composer.",
    ),
    WalkthroughStep(
        number=4,
        title="Emit a governed prepare package",
        why="First real spine fill: session prep writes digest-bound artifacts (CLI writes; STRATUM does not).",
        command="uv run builder-session prepare-package generic -o .builder/artifacts --task \"first stratum session\"",
        stratum_after="Restart or wait for spine poll; stages appear as kinds land under .builder/.",
    ),
    WalkthroughStep(
        number=5,
        title="Validate the prepare package",
        why="Integrity check — planned ≠ verified until this (or chain verify) says so.",
        command="uv run builder-session validate-prepare-package .builder/artifacts",
        stratum_after="Press V to re-check on-disk chain validity in the center bar stats.",
    ),
    WalkthroughStep(
        number=6,
        title="(Optional) Mint a read-only Goose manifest",
        why=(
            "A read_only manifest is required for the hand-off. Pre-minting it via CLI is optional "
            "— G asks to mint a passive one if none exists."
        ),
        command=(
            "uv run builder-goose manifest --target generic --mode read_only "
            "--task \"readonly inspect\" --output .builder/goose/session.json"
        ),
        stratum_after=(
            "Press G to hand off to read-only Goose. If no read_only manifest exists, STRATUM asks "
            "before minting a passive one (confirm required); it then runs the fixed "
            "`builder-goose start-readonly` — never raw Goose, never write authority."
        ),
        optional=True,
    ),
    WalkthroughStep(
        number=7,
        title="Launch STRATUM and inspect",
        why="Observe-only console: spine, instruments, compose — never authority origin.",
        command="uv run builder stratum",
        stratum_after="j/k spine · SPC pin · O models · U agents · W workflow · H help · ~ compose.",
    ),
)


def guide_dismiss_path(project_root: Path) -> Path:
    return project_root / ".builder" / GUIDE_DISMISS_FILENAME


def is_guide_skipped(*, project_root: Path, force_show: bool = False, force_skip: bool = False) -> bool:
    """Return True when first-run guide should not auto-open."""
    if force_show:
        return False
    if force_skip:
        return True
    env = os.environ.get(ENV_SKIP_GUIDE, "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    return guide_dismiss_path(project_root).is_file()


def dismiss_guide(project_root: Path) -> Path:
    """Persist opt-out so guide does not auto-open next launch. Returns path written."""
    path = guide_dismiss_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "STRATUM first-run guide dismissed by operator.\n"
        "Delete this file or run with --guide to show again.\n",
        encoding="utf-8",
    )
    return path


def clear_guide_dismiss(project_root: Path) -> bool:
    path = guide_dismiss_path(project_root)
    if path.is_file():
        path.unlink()
        return True
    return False


def artifacts_look_empty(artifacts_dir: Path | None) -> bool:
    if artifacts_dir is None or not artifacts_dir.exists():
        return True
    return not any(artifacts_dir.glob("*.json"))


def should_auto_open_guide(
    *,
    project_root: Path,
    artifacts_dir: Path | None,
    force_show: bool = False,
    force_skip: bool = False,
) -> bool:
    """Auto-open when not opted out and the artifact root looks like a first session."""
    if is_guide_skipped(project_root=project_root, force_show=force_show, force_skip=force_skip):
        return False
    if force_show:
        return True
    return artifacts_look_empty(artifacts_dir)


def normalize_composed_command(cmd: str) -> str:
    """Normalize composed CLI text for display (avoid 'builder builder-platform …')."""
    text = cmd.strip()
    if not text:
        return text
    # Already a full builder-* console script
    if text.startswith("builder-") or text.startswith("uv run "):
        return text
    if text.startswith("builder "):
        return text
    # Bare subcommand fragments like "platform matrix" or "session prepare-package"
    return f"builder {text}"


def walkthrough_lines(*, include_opt_out_hint: bool = True) -> list[str]:
    """Plain markup-ready lines for the center-panel walkthrough."""
    lines = [
        "FIRST SESSION WALKTHROUGH",
        "STRATUM observes and composes. It never writes artifacts or harvests HITL approval.",
        "Run each command in your terminal (outside or after composing with ~).",
        "",
    ]
    for step in WALKTHROUGH_STEPS:
        opt = " (optional)" if step.optional else ""
        lines.append(f"{step.number}. {step.title}{opt}")
        lines.append(f"   why: {step.why}")
        if step.command:
            lines.append(f"   cmd: {step.command}")
        lines.append(f"   then in STRATUM: {step.stratum_after}")
        lines.append("")
    lines.extend(
        [
            "BOUNDARIES",
            "  · planned ≠ executed ≠ verified ≠ promoted",
            "  · artifact ≠ authority · model output ≠ approval",
            "  · Chain digest is — until verification exposes one (never synthesized)",
            "  · A/R only compose builder-hitl … — they do not approve",
            "",
            "KEYMAP (essentials)",
            "  TAB cycle · ESC idle · H help · 0 walkthrough · X dismiss auto-guide",
            "  j/k spine · SPC pin · O models · U agents · W workflow · C audit",
            "  P prepare compose · V chain check · G goose hand-off · N next · ~ composer",
            "",
        ]
    )
    if include_opt_out_hint:
        lines.extend(
            [
                "OPT OUT OF AUTO GUIDE",
                "  · Press X while walkthrough is open (writes .builder/stratum_guide_dismissed)",
                "  · Or: uv run builder stratum --no-guide",
                "  · Or: export STRATUM_SKIP_GUIDE=1",
                "  · Show again: uv run builder stratum --guide",
            ]
        )
    return lines


def help_keymap_lines() -> list[str]:
    return [
        "OPERATOR KEYMAP",
        "",
        "NAVIGATION",
        "  TAB       Cycle focus: Spine · Center · Signals",
        "  ESC       Back to Operator (or close search)",
        "  CTRL+Q    Quit (confirms if HITL gate open)",
        "  j/k ↑↓    Move spine selection",
        "  SPC/Enter Pin selected stage → inspect",
        "  /         Filter spine",
        "",
        "INSTRUMENTS",
        "  H / F1    Help (this manual)",
        "  0         First-session walkthrough",
        "  M         Memory atoms",
        "  O         Models: .env config + registry + routing",
        "  U         Deepagents roster / readiness / forge compose",
        "  C         Platform capability audit",
        "  W         Workflow · Goose recipes · manifest status",
        "  Y         Orchestration plans / obligations",
        "  E         Quality gate evidence template",
        "  T         External tooling health",
        "  L         Run cockpit: runs roster + live ledger transcript ( , / . select run)",
        "",
        "COMPOSE / GOVERN",
        "  ?         Command palette (tier inspector → compose if permitted)",
        "  ~         Command Composer (injects context; runs nothing)",
        "  P         Prepare-package configurator → compose only",
        "  V         Re-verify artifact chain on disk",
        "  G         Hand terminal to builder-goose start-readonly (fail-closed)",
        "  N         Operator-next → compose top safe command",
        "  A / R     HITL: hand off approve-patch / refuse-patch to the canonical CLI; reload the result",
        "  I         HITL: bind pending proposal or inspect payload",
        "  D         HITL diff: render bound proposal's unified diff (read-only)",
        "",
        "WHERE ARTIFACTS LIVE",
        "  STRATUM reads:  <project_root>/.builder/artifacts",
        "  That is the cwd/project you launched from — not another clone.",
        "  Empty spine = no JSON kinds yet in THIS tree's .builder/artifacts.",
    ]


def help_boundary_lines() -> list[str]:
    return [
        "GOVERNANCE BOUNDARIES",
        "",
        "STRATUM IS",
        "  · A read-only instrument panel over real registries and on-disk artifacts",
        "  · A Command Composer that surfaces exact CLI for you to run",
        "  · A launcher OF builder-goose start-readonly (suspend + fixed argv only)",
        "",
        "STRATUM IS NOT",
        "  · An authority origin (no approvals, no artifact writes, no dispatch)",
        "  · A place that invents digests or paints gates green without evidence",
        "  · A substitute for docs/GETTING_STARTED.md or FIRST_SESSION.md",
        "",
        "LOAD-BEARING DISTINCTIONS",
        "  · planned ≠ executed ≠ verified ≠ promoted",
        "  · artifact ≠ authority · model output ≠ approval",
        "",
        "NEW BUILDER MAP",
        "  · docs/GETTING_STARTED.md  — setup order + STRATUM × full platform",
        "  · docs/STRATUM.md          — keys, flags, empty-spine troubleshooting",
        "  · FIRST_SESSION.md         — smoked propose→approve→verify→apply loop",
        "",
        "FULL PLATFORM FIRST LOOP (outside STRATUM)",
        "  uv run builder-platform golden-path --target builder --output-dir .builder/artifacts/golden-path",
    ]
