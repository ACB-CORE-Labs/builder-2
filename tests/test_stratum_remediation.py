"""Gating tests for STRATUM TUI remediation (C1–C4 + greenglow labels).

Pure projection + Pilot. No digest harvest, no execution, no incomplete bare compose.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.governance.hitl.hitl_patch_refusal import (
    HITL_PATCH_REFUSAL_KIND,
    create_hitl_patch_refusal,
    validate_hitl_patch_refusal,
    write_hitl_patch_refusal,
)
from builder_ii.routing.model_budget import create_model_budget, write_model_budget
from builder_ii.tui.app import STRATUM_UNIMPLEMENTED_SURFACES, StratumApp
from builder_ii.tui.projections.gates import scan_pending_hitl
from builder_ii.tui.projections.hitl_compose import compose_hitl_approve, compose_hitl_reject
from builder_ii.tui.projections.last_mile import format_last_mile_hud_lines, project_last_mile_hud
from builder_ii.tui.widgets.palette import CommandPaletteScreen
from builder_ii.tui.widgets.signals import HITLGateIndicator, LastMileHud
from builder_ii.tui.widgets.stratum import StratumMode

# ── HITL compose (pure) ───────────────────────────────────────────────────


def test_compose_approve_refuses_unbound() -> None:
    result = compose_hitl_approve(None)
    assert result.refused is True
    assert result.command is None
    assert "refused" in result.reason.lower()


def test_compose_approve_bound_includes_required_flags(tmp_path: Path) -> None:
    prop = tmp_path / "proposal.json"
    prop.write_text("{}", encoding="utf-8")
    result = compose_hitl_approve(
        {"path": str(prop), "artifact": {"kind": "builder_ii.hitl_patch_proposal"}},
        artifacts_dir=tmp_path,
    )
    assert result.refused is False
    assert result.command is not None
    assert "builder-hitl approve-patch" in result.command
    assert "--proposal" in result.command
    assert "--output" in result.command
    assert str(prop) in result.command


def test_compose_reject_patch_is_refuse_patch_not_promotion(tmp_path: Path) -> None:
    prop = tmp_path / "proposal.json"
    prop.write_text("{}", encoding="utf-8")
    result = compose_hitl_reject(
        {"path": str(prop), "artifact": {"kind": "builder_ii.hitl_patch_proposal"}},
        artifacts_dir=tmp_path,
    )
    assert result.refused is False
    assert result.command is not None
    assert "refuse-patch" in result.command
    assert "rejection-record" not in result.command
    assert "--proposal" in result.command
    assert "--output" in result.command
    assert "--rationale" in result.command


def test_compose_reject_refuses_unbound() -> None:
    result = compose_hitl_reject({})
    assert result.refused is True
    assert result.command is None


def test_refuse_patch_artifact_is_passive(tmp_path: Path) -> None:
    proposal = {
        "kind": "builder_ii.hitl_patch_proposal",
        "patch_digest": "a" * 64,
        "state": "PENDING",
    }
    record = create_hitl_patch_refusal(
        proposal,
        proposal_path=tmp_path / "p.json",
        rationale="no thanks",
    )
    assert validate_hitl_patch_refusal(record) == []
    assert record["kind"] == HITL_PATCH_REFUSAL_KIND
    assert record["grants_authority"] is False
    assert record["executes_patch"] is False
    out = tmp_path / "refusal.json"
    write_hitl_patch_refusal(record, out)
    assert out.is_file()


# ── Last-mile HUD ─────────────────────────────────────────────────────────


def test_last_mile_hud_absent_when_empty(tmp_path: Path) -> None:
    view = project_last_mile_hud(tmp_path)
    assert view.budget == "—"
    assert view.seam == "none"
    assert view.ledger_tail == "—"
    assert view.cost == "—"
    lines = format_last_mile_hud_lines(view)
    assert any("budget" in line for line in lines)
    assert any("seam" in line for line in lines)


def test_last_mile_hud_projects_budget(tmp_path: Path) -> None:
    artifacts = tmp_path / ".builder" / "artifacts"
    artifacts.mkdir(parents=True)
    budget = create_model_budget(
        session_id="stratum-test",
        max_input_tokens=1000,
        max_output_tokens=1000,
        max_total_tokens=2000,
        max_usd=1.0,
        spent_input_tokens=100,
        spent_output_tokens=50,
        spent_total_tokens=150,
        spent_usd=0.1,
    )
    write_model_budget(budget, artifacts / "budget.json")
    view = project_last_mile_hud(artifacts)
    assert view.budget != "—"
    assert "tok" in view.budget
    assert "$" in view.budget


def test_last_mile_hud_widget_renders_labels() -> None:
    hud = LastMileHud(artifacts_dir=None)
    hud.budget = "ACTIVE · 10 tok · $0.01 rem"
    hud.seam = "none"
    hud.ledger_tail = "—"
    hud.cost = "—"
    rendered = hud.render()
    assert "LAST-MILE" in rendered
    assert "budget" in rendered
    assert "seam" in rendered


# ── Greenglow labels ──────────────────────────────────────────────────────


def test_hitl_gate_indicator_says_no_pending_hitl_not_all_gates_clear() -> None:
    ind = HITLGateIndicator()
    ind.gate_open = False
    text = ind.render()
    assert "NO PENDING HITL" in text
    assert "ALL GATES CLEAR" not in text


def test_scan_pending_hitl_closed_label(tmp_path: Path) -> None:
    open_, label = scan_pending_hitl(tmp_path)
    assert open_ is False
    assert "NO PENDING HITL" in label.upper()


# ── Dead modes reachable ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dead_modes_enter_via_bindings() -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.project_root = Path(".")

        app = StratumApp(show_splash=False, skip_guide=True)
        async with app.run_test(headless=True) as pilot:
            await pilot.press("f")
            await pilot.pause()
            assert app.stratum is not None
            assert app.stratum.mode == StratumMode.POSTFLIGHT

            await pilot.press("s")
            await pilot.pause()
            assert app.stratum.mode == StratumMode.PROMOTION

            await pilot.press("l")
            await pilot.pause()
            assert app.stratum.mode == StratumMode.GOOSE_LIVE

            await pilot.press("p")
            await pilot.pause()
            # Prepare wizard may stack a screen; mode must be PREPARE under it.
            assert app.stratum.mode == StratumMode.PREPARE


# ── Palette keyboard ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_palette_keyboard_select_without_click() -> None:
    commands = [
        {
            "name": "builder-alpha",
            "tier": "Tier 0 — read-only inspection",
            "promotion_state": "x",
            "allowed": True,
            "reason": "",
            "requires_authority": False,
        },
        {
            "name": "builder-beta",
            "tier": "Tier 0 — read-only inspection",
            "promotion_state": "x",
            "allowed": True,
            "reason": "",
            "requires_authority": False,
        },
        {
            "name": "builder-gamma-forbidden",
            "tier": "Tier 4 — forbidden",
            "promotion_state": "x",
            "allowed": False,
            "reason": "forbidden",
            "requires_authority": True,
        },
    ]

    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.project_root = Path(".")

        app = StratumApp(show_splash=False, skip_guide=True)
        selected: list[str | None] = []

        async with app.run_test(headless=True) as pilot:
            app.push_screen(CommandPaletteScreen(commands=commands), lambda v: selected.append(v))
            await pilot.pause()
            assert app.screen.__class__.__name__ == "CommandPaletteScreen"
            # Move down to second entry and confirm with Enter (no click).
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert selected, "Enter did not dismiss palette with a selection"
            assert selected[-1] == "builder-beta"


@pytest.mark.asyncio
async def test_palette_escape_dismisses_without_selection() -> None:
    commands = [
        {
            "name": "builder-only",
            "tier": "Tier 0 — read-only inspection",
            "promotion_state": "x",
            "allowed": True,
            "reason": "",
            "requires_authority": False,
        },
    ]
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.project_root = Path(".")

        app = StratumApp(show_splash=False, skip_guide=True)
        selected: list[str | None] = []
        async with app.run_test(headless=True) as pilot:
            app.push_screen(CommandPaletteScreen(commands=commands), lambda v: selected.append(v))
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert selected == [None]


def test_unimplemented_surfaces_still_list_diff_viewer() -> None:
    assert "HITL diff viewer" in STRATUM_UNIMPLEMENTED_SURFACES
