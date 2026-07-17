"""Audit STRATUM's HITL boundary by driving it, not by reading it.

What these lanes actually pin, and why it is not what an audit brief tends to assume: STRATUM has
**no execution authority to gate**. It is not an engine with guards in front of it. The palette is a
tier inspector, `approve`/`reject` are constitutive refusals that compose a CLI command for the
operator's own terminal, and the compose modal says so in its own header ("STRATUM runs nothing").

That distinction decides what is worth asserting. A gate that can be satisfied has a bypass worth
testing; an absent capability has none. So these lanes do not try to sneak past a check -- they pin
that no key sequence reaches execution or mutates approval state at all, which is the stronger and
simpler property, and the one that would actually regress if someone wired a keypress to a
subprocess "for convenience".

`ThirdDoorGate` is likewise not a blocker. It is a `Static` that renders eight constraints and the
words VAULT LOCKED; nothing in the codebase consults it for a decision. `test_the_third_door_is_a
_readout_not_a_blocker` pins that directly, because a widget that *looks* like the authority is
exactly the thing this repository keeps getting caught by.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from textual.app import App

from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    TIER_3,
    TIER_4,
    check_command_authority,
)
from builder_ii.tui.app import StratumApp
from builder_ii.tui.widgets.stratum import StratumMode

FORBIDDEN_COMMANDS = sorted(rec.name for rec in COMMAND_AUTHORITY_REGISTRY if rec.tier == TIER_4)
PERMITTED_GATED_COMMANDS = sorted(
    rec.name
    for rec in COMMAND_AUTHORITY_REGISTRY
    if rec.tier == TIER_3 and check_command_authority(rec.name).allowed
)

#: Measured: pressing `a` on a pending gate opens the composer prefilled with the approve command,
#: and `enter` surfaces it. Two presses, and that is the terminus -- STRATUM never approves.
#: Asserted as an exact number so an added confirmation step has to be argued for, not slipped in.
FRICTION_APPROVE_PRESSES = 2

APPROVE_COMPOSES = "uv run builder-hitl approve-patch"
REJECT_COMPOSES = "uv run builder-hitl rejection-record"

#: A pending Tier-4 patch proposal -- the highest-authority gate STRATUM can be shown.
#: `project_hitl_surface` selects on a `kind` containing "hitl" and a state that is not already
#: APPROVED/REJECTED/APPLIED/CLOSED, so this is the real discovery path, not an injected mode.
PENDING_PROPOSAL: dict[str, Any] = {
    "kind": "builder_ii.hitl_patch_proposal",
    "state": "PENDING",
    "command": "builder-hitl apply-patch",
    "tier": TIER_4,
    "authority": "HITL required",
    "effects": "mutates target repository source files",
    "digest": "a" * 64,
}


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    """An artifacts dir holding one pending Tier-4 HITL proposal."""
    directory = tmp_path / ".builder" / "artifacts"
    directory.mkdir(parents=True)
    (directory / "proposal.json").write_text(json.dumps(PENDING_PROPOSAL), encoding="utf-8")
    return directory


@pytest.fixture
def stratum(artifacts_dir: Path) -> StratumApp:
    """STRATUM pointed at the pending gate. `artifacts_dir` is read at compose time."""
    app = StratumApp(show_splash=False, skip_guide=True)
    app.artifacts_dir = artifacts_dir
    return app


def _proposal_on_disk(artifacts_dir: Path) -> dict[str, Any]:
    return json.loads((artifacts_dir / "proposal.json").read_text(encoding="utf-8"))


def _no_execution_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trip-wire: make any real process launch fail loudly rather than silently succeed."""

    def explode(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"STRATUM attempted to execute a process: {args!r}")

    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)


def _census(app: App[Any]) -> Counter[str]:
    return Counter(widget.__class__.__name__ for widget in app.screen.walk_children())


def test_the_registry_still_has_forbidden_and_gated_commands_to_audit() -> None:
    """Vacuity guard. Every parametrized lane below is empty-and-green if these lists empty out."""
    assert FORBIDDEN_COMMANDS, "no TIER_4 commands -- the breach lanes are vacuous"
    assert PERMITTED_GATED_COMMANDS, "no permitted TIER_3 commands -- the compose lane is vacuous"


@pytest.mark.asyncio
@pytest.mark.parametrize("command", FORBIDDEN_COMMANDS)
async def test_selecting_a_forbidden_command_refuses_and_composes_nothing(
    stratum: StratumApp, artifacts_dir: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    """A TIER_4 command selected in the palette is refused, and no composer opens for it.

    `dismiss(cmd_name)` is exactly what `PaletteEntry.on_click` does. It is driven directly rather
    than clicked because the palette holds every registered command and `pilot.click` raises
    `OutOfBounds` on an entry scrolled out of the viewport -- a property of Textual's hit-testing,
    not of the governance logic under test, which is `on_selected`.
    """
    _no_execution_allowed(monkeypatch)
    notified: list[str] = []

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: notified.append(str(msg)))
        await pilot.press("question_mark")
        await pilot.pause()
        assert stratum.screen.__class__.__name__ == "CommandPaletteScreen"

        stratum.screen.dismiss(command)
        await pilot.pause()

        assert notified, f"selecting {command!r} said nothing at all"
        assert "refused" in notified[-1], f"{command} is TIER_4 but was reported: {notified[-1]!r}"
        assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen", (
            f"a composer opened for forbidden command {command!r}"
        )
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL


@pytest.mark.asyncio
async def test_selecting_a_permitted_command_composes_it_but_still_executes_nothing(
    stratum: StratumApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: a permitted TIER_3 command reaches the composer and stops there.

    Without this, a change that refused *everything* would satisfy the forbidden lanes above while
    making the palette useless -- fail-closed is not the same as correct.
    """
    _no_execution_allowed(monkeypatch)
    command = PERMITTED_GATED_COMMANDS[0]

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        await pilot.press("question_mark")
        await pilot.pause()
        stratum.screen.dismiss(command)
        await pilot.pause()

        assert stratum.screen.__class__.__name__ == "CLIPassthroughScreen"
        # Composed for the operator to run -- never run here.
        assert stratum.screen.prefix_context == command


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "composes"),
    [("a", APPROVE_COMPOSES), ("r", REJECT_COMPOSES)],
    ids=["approve", "reject"],
)
async def test_the_gate_keys_compose_a_command_and_never_touch_approval_state(
    stratum: StratumApp, artifacts_dir: Path, monkeypatch: pytest.MonkeyPatch, key: str, composes: str
) -> None:
    """`a` and `r` on a real pending Tier-4 gate must not decide anything.

    This is the governance claim in its load-bearing form: the artifact on disk is the approval
    state, and a keypress must leave it byte-identical. STRATUM composes `builder-hitl approve-patch`
    for the operator's terminal precisely because a TUI cannot harvest a confirmation for a digest
    it merely rendered.
    """
    _no_execution_allowed(monkeypatch)

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        await pilot.press(key)
        await pilot.pause()

        assert stratum.stratum.mode == StratumMode.HITL_GATE, "the pending gate was not bound"
        assert stratum.screen.__class__.__name__ == "CLIPassthroughScreen"
        assert stratum.screen.prefix_context == composes, (
            f"{key!r} composed {stratum.screen.prefix_context!r}, not the governed CLI command"
        )
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL, (
            f"{key!r} mutated approval state from the TUI"
        )


@pytest.mark.asyncio
async def test_no_gate_keypress_reaches_a_subprocess(
    stratum: StratumApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sweep the authority-adjacent keys with execution trip-wired.

    STRATUM owns exactly one process launch -- `_hand_off_goose_readonly`, a fixed-argv `shell=False`
    read-only Goose handoff reached only through an explicit confirm. Nothing on the HITL or palette
    path may acquire a second one. This lane is what fails if someone wires a key straight to a
    command "for convenience".
    """
    _no_execution_allowed(monkeypatch)

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        for key in ("a", "escape", "r", "escape", "i", "escape", "question_mark", "escape"):
            await pilot.press(key)
            await pilot.pause()


@pytest.mark.asyncio
async def test_friction_two_presses_compose_an_approval_and_that_is_the_terminus(
    stratum: StratumApp, artifacts_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Friction Score, as a lane rather than a paragraph.

    Intent to composed approval is `a`, `enter` -- two presses, nothing redundant. What the number
    must not be read as is "two presses to approve": there is no third press that approves, and no
    number of presses that would. The flow terminates at a command the operator runs elsewhere, and
    the artifact below proves it did not settle anything on the way out.
    """
    _no_execution_allowed(monkeypatch)
    presses = ["a", "enter"]
    assert len(presses) == FRICTION_APPROVE_PRESSES

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)

        await pilot.press("a")
        await pilot.pause()
        composer = stratum.screen
        assert composer.__class__.__name__ == "CLIPassthroughScreen"
        # Prefilled, so the second press is a confirmation and not typing.
        assert composer.query_one("#cli-input").value == APPROVE_COMPOSES

        await pilot.press("enter")
        await pilot.pause()

        assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen", "the composer never closed"
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL, "the flow approved something"


@pytest.mark.asyncio
async def test_rejecting_the_composer_restores_the_screen_without_orphaning_nodes(
    stratum: StratumApp, artifacts_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Escape out of the composer: stack restored, no node accumulation, nothing decided.

    Deliberately compares cycle-to-cycle rather than against boot. The DOM legitimately grows once
    on first interaction -- Textual's `Footer` lazily mounts one `FooterKey` per binding (measured:
    39 -> 65 nodes, 26 of them `FooterKey`) -- and a lane that compared against the boot census would
    report that as an orphan leak. It is Textual's furniture arriving, not STRATUM's litter. What a
    real leak would look like is monotonic growth across repeats, which is what this measures.
    """
    _no_execution_allowed(monkeypatch)

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        base_stack = len(stratum.screen_stack)

        censuses: list[Counter[str]] = []
        for _ in range(3):
            await pilot.press("r")
            await pilot.pause()
            assert stratum.screen.__class__.__name__ == "CLIPassthroughScreen"

            await pilot.press("escape")
            await pilot.pause()
            assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen", "escape did not close"
            assert len(stratum.screen_stack) == base_stack, "the screen stack did not unwind"
            censuses.append(_census(stratum))

        assert censuses[0] == censuses[-1], (
            f"the DOM grew across identical reject/escape cycles -- orphaned nodes: "
            f"{censuses[-1] - censuses[0]}"
        )
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL


@pytest.mark.asyncio
async def test_the_third_door_is_a_readout_not_a_blocker(
    stratum: StratumApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ThirdDoorGate` displays authority constraints. It does not enforce them.

    Worth a lane precisely because the name invites the opposite reading. With no promotion
    readiness artifact present all eight constraints are unevaluated and it renders VAULT LOCKED --
    and the composer is still reachable, because nothing consults it. It is a `Static`: no bindings,
    no click handler, and no caller anywhere reads its state to decide anything.

    If it ever *should* enforce, this lane is the one that has to change, deliberately, rather than
    a reviewer assuming it already does.
    """
    _no_execution_allowed(monkeypatch)

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        gate = stratum.stratum._third_door
        assert gate is not None and gate.display is True, "HITL_GATE mode must surface the Third Door"

        rendered = str(gate.render())
        assert "VAULT LOCKED" in rendered, "no readiness artifact: the door must read locked"

        # Locked, and the authority path is open anyway -- which is the whole point.
        await pilot.press("a")
        await pilot.pause()
        assert stratum.screen.__class__.__name__ == "CLIPassthroughScreen", (
            "the composer became unreachable -- if the Third Door now gates it, this lane is the "
            "record that it did not before, and the change needs saying out loud"
        )
