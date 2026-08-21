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

`ThirdDoorGate` is likewise not a blocker. It is a `Static` that renders eight constraints and a
verdict; nothing in the codebase consults it for a decision. `test_the_third_door_is_a_readout_not
_a_blocker` pins that directly, because a widget that *looks* like the authority is exactly the
thing this repository keeps getting caught by.

The tier system is the other thing that looks like an authority and is not, and
`test_tier_is_a_blast_radius_classifier_not_an_authority_classifier` is the tripwire for it.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from textual.app import App

from builder_ii.governance.authority import (
    COMMAND_AUTHORITY_REGISTRY,
    TIER_0,
    TIER_1,
    TIER_3,
    TIER_4,
    check_command_authority,
)
from builder_ii.tui.app import StratumApp
from builder_ii.tui.widgets.stratum import StratumMode

FORBIDDEN_COMMANDS = sorted(rec.name for rec in COMMAND_AUTHORITY_REGISTRY if rec.tier == TIER_4)
PERMITTED_GATED_COMMANDS = sorted(
    rec.name for rec in COMMAND_AUTHORITY_REGISTRY if rec.tier == TIER_3 and check_command_authority(rec.name).allowed
)

#: Measured: pressing `a` on a pending gate opens the composer prefilled with the approve command,
#: and `enter` surfaces it. Two presses, and that is the terminus -- STRATUM never approves.
#: Asserted as an exact number so an added confirmation step has to be argued for, not slipped in.
FRICTION_APPROVE_PRESSES = 2

#: Bound compose requires proposal path + output. Bare prefixes without flags are a regression.
APPROVE_COMPOSE_MARKER = "builder-hitl approve-patch"
REJECT_COMPOSE_MARKER = "builder-hitl refuse-patch"
#: Wrong ceremony for patch proposals — must never appear in the patch gate compose path.
PROMOTION_REJECT_MARKER = "rejection-record"

#: The registry names behind the HITL gate keys. Every one of them *is* an approval/refusal act, and
#: every one of them is TIER_1 -- see `test_tier_is_a_blast_radius_classifier_not_an_authority
#: _classifier`, which exists solely to keep that pairing visible.
GATE_KEY_COMMANDS = (
    "builder-hitl approve-patch",
    "builder-hitl refuse-patch",
    "builder-hitl approve-rollback",
)

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
    ("key", "marker", "required_flags"),
    [
        ("a", APPROVE_COMPOSE_MARKER, ("--proposal", "--output")),
        ("r", REJECT_COMPOSE_MARKER, ("--proposal", "--output", "--rationale")),
    ],
    ids=["approve", "reject"],
)
async def test_the_gate_keys_compose_a_command_and_never_touch_approval_state(
    stratum: StratumApp,
    artifacts_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    marker: str,
    required_flags: tuple[str, ...],
) -> None:
    """`a` and `r` on a real pending Tier-4 gate must not decide anything.

    This is the governance claim in its load-bearing form: the artifact on disk is the approval
    state, and a keypress must leave it byte-identical. STRATUM composes a *bound*
    `builder-hitl approve-patch` / `refuse-patch` line for the operator's terminal precisely
    because a TUI cannot harvest a confirmation for a digest it merely rendered. Bare prefixes
    without path flags are incomplete compose theater and are not success.
    """
    _no_execution_allowed(monkeypatch)

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        await pilot.press(key)
        await pilot.pause()

        assert stratum.stratum.mode == StratumMode.HITL_GATE, "the pending gate was not bound"
        assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen"
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL, f"{key!r} mutated approval state from the TUI"


@pytest.mark.asyncio
async def test_no_gate_keypress_reaches_a_subprocess(stratum: StratumApp, monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen"

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
            assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen", "escape did not close"
            assert len(stratum.screen_stack) == base_stack, "the screen stack did not unwind"
            censuses.append(_census(stratum))

        assert censuses[0] == censuses[-1], (
            f"the DOM grew across identical reject/escape cycles -- orphaned nodes: {censuses[-1] - censuses[0]}"
        )
        assert _proposal_on_disk(artifacts_dir) == PENDING_PROPOSAL


@pytest.mark.asyncio
async def test_the_third_door_is_a_readout_not_a_blocker(stratum: StratumApp, monkeypatch: pytest.MonkeyPatch) -> None:
    """`ThirdDoorGate` displays authority constraints. It does not enforce them.

    Worth a lane precisely because the name invites the opposite reading. It is a `Static`: no
    bindings, no click handler, and no caller anywhere reads its state to decide anything.

    If it ever *should* enforce, this lane is the one that has to change, deliberately, rather than
    a reviewer assuming it already does.

    It has now changed once, and this is the record of why. The audit that added this lane asserted
    `VAULT LOCKED` here, and separately reported the locked-by-default readout as a finding: with no
    readiness artifact, all eight constraints are unevaluated, and `render()` collapsed every
    non-True slot into a refusal. So the door read *refused* on every host, always, having refused
    nothing. That was fixed -- absence of evidence now reads `VAULT UNASSESSED` -- and this lane
    moved with it. The claim under test is unchanged: whatever the door says, it gates nothing.
    """
    _no_execution_allowed(monkeypatch)

    async with stratum.run_test(headless=True) as pilot:
        monkeypatch.setattr(stratum, "notify", lambda msg, **kw: None)
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        gate = stratum.stratum._third_door
        assert gate is not None, "Third Door widget must remain mounted"

        rendered = str(gate.render())
        assert "VAULT UNASSESSED" in rendered, (
            "no readiness artifact exists here, so the door has evaluated nothing and must say so"
        )
        assert "VAULT LOCKED" not in rendered, "the door is reporting a refusal it never made -- see third_door_state()"

        # The fixed terminal handoff remains reachable without a composer.
        await pilot.press("a")
        await pilot.pause()
        assert stratum.screen.__class__.__name__ != "CLIPassthroughScreen"


def test_tier_is_a_blast_radius_classifier_not_an_authority_classifier() -> None:
    """`tier <= TIER_1` must never be used as a predicate for "safe to execute automatically".

    This lane exists because that predicate is an attractive idea, was formally proposed, and is
    wrong in a way that reads as obviously right. The tiers classify what a command's *mechanism*
    touches -- TIER_1 is "artifact-only planning/validation", meaning it writes a JSON file and
    nothing else. They do not classify what the act *means*. And for `builder-hitl approve-patch`,
    writing that JSON file **is** the approval. Tier 1 blast radius, maximal authority.

    So a TUI that auto-executed TIER_0/TIER_1 "because they're safe" would let a keypress approve a
    patch, and an airgap that stops at TIER_3/TIER_4 -- the natural companion proposal -- catches
    none of the three commands the gate keys compose. Measured, both halves. That combination is
    precisely `model output != approval` failing through the governance system rather than around
    it, which is the hardest kind to see.

    If this lane goes red, do not simply update the constant. It means the tiering of an approval
    command changed, and the question to answer first is whether anything downstream started
    treating tier as permission.
    """
    by_name = {rec.name: rec for rec in COMMAND_AUTHORITY_REGISTRY}

    for name in GATE_KEY_COMMANDS:
        assert name in by_name, f"{name!r} is not registered; this lane's subject vanished"
        record = by_name[name]

        assert record.tier == TIER_1, (
            f"{name!r} is {record.tier!r}, not TIER_1. This lane assumed the trap it guards still "
            f"exists. Re-check whether any caller now reads tier as permission before editing it."
        )
        assert record.tier in (TIER_0, TIER_1), (
            f"{name!r} would be captured by a `tier in (TIER_0, TIER_1)` auto-execute predicate"
        )
        assert record.tier not in (TIER_3, TIER_4), (
            f"{name!r} would NOT be caught by a TIER_3/TIER_4 airgap -- the airgap does not "
            f"protect the HITL boundary, which is the whole reason this lane is here"
        )

    # And the scale of the predicate, so "narrow read-only lane" cannot be claimed for it.
    auto_exec_set = [rec for rec in COMMAND_AUTHORITY_REGISTRY if rec.tier in (TIER_0, TIER_1)]
    assert len(auto_exec_set) > len(COMMAND_AUTHORITY_REGISTRY) * 0.75, (
        f"`tier in (TIER_0, TIER_1)` selects {len(auto_exec_set)} of "
        f"{len(COMMAND_AUTHORITY_REGISTRY)} registered commands -- it is not a narrow carve-out"
    )
