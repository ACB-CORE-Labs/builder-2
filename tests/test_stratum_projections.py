"""Projection-layer honesty tests — no Textual, no writes, no synthesis."""

from __future__ import annotations

import json
import re
from pathlib import Path

from builder_ii.tui.projections.agents import compose_assign_command, project_agent_roster
from builder_ii.tui.projections.chain import epistemic_from_chain, project_chain
from builder_ii.tui.projections.gates import (
    THIRD_DOOR_CONSTRAINTS,
    THIRD_DOOR_INCOMPLETE,
    THIRD_DOOR_LOCKED,
    THIRD_DOOR_UNASSESSED,
    THIRD_DOOR_UNLOCKED,
    ThirdDoorView,
    project_hitl_surface,
    project_third_door,
    scan_pending_hitl,
    unassessed_third_door,
)
from builder_ii.tui.projections.models import project_model_matrix
from builder_ii.tui.projections.operator import project_operator_dashboard
from builder_ii.tui.projections.workflow import project_workflow
from builder_ii.tui.widgets.masterpiece import EpistemicMatrix, ThirdDoorGate

#: Rich markup tags carry theme colours, which are not the claim under test. Asserting on raw
#: `render()` output would couple every verdict lane to the palette and go red on a re-theme.
_MARKUP = re.compile(r"\[/?[^\]]*\]")


def _strip_markup(text: str) -> str:
    return _MARKUP.sub("", text)


def test_project_chain_empty_dir(tmp_path: Path) -> None:
    view = project_chain(tmp_path)
    assert view.file_count == 0
    assert view.chain_valid is None
    assert all(s.status == "pending" for s in view.stages)
    assert all(s.artifact is None for s in view.stages)


def test_project_chain_marks_present_artifact(tmp_path: Path) -> None:
    artifact = {"kind": "builder_ii.repo_map", "files": []}
    (tmp_path / "repo_map.json").write_text(json.dumps(artifact), encoding="utf-8")
    view = project_chain(tmp_path)
    repo = next(s for s in view.stages if s.stage_id == "repo-map")
    assert repo.status == "verified"
    assert repo.artifact is not None
    pending = next(s for s in view.stages if s.stage_id == "ctx-pack")
    assert pending.status == "pending"


def test_project_chain_failed_on_errors(tmp_path: Path) -> None:
    artifact = {"kind": "builder_ii.repo_map", "errors": ["broken"]}
    (tmp_path / "repo_map.json").write_text(json.dumps(artifact), encoding="utf-8")
    view = project_chain(tmp_path)
    repo = next(s for s in view.stages if s.stage_id == "repo-map")
    assert repo.status == "failed"


def test_epistemic_from_chain_never_invents_digests(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(json.dumps({"kind": "builder_ii.repo_map"}), encoding="utf-8")
    chain = project_chain(tmp_path)
    epi = epistemic_from_chain(chain)
    for key in ("digest_planned", "digest_executed", "digest_verified", "digest_promoted"):
        assert epi[key] == "—"


def test_epistemic_matrix_defaults_are_absent() -> None:
    matrix = EpistemicMatrix()
    assert matrix.digest_planned == "—"
    assert matrix.digest_executed == "—"
    assert matrix.digest_verified == "—"
    assert matrix.digest_promoted == "—"
    assert matrix.state_planned == "pending"
    assert matrix.state_executed == "pending"
    assert matrix.state_verified == "pending"
    assert matrix.state_promoted == "pending"
    rendered = matrix.render()
    assert "a8b2" not in rendered
    assert "SHA256" not in rendered


def test_third_door_unevaluated_without_artifacts(tmp_path: Path) -> None:
    view = project_third_door(tmp_path)
    assert view.source == "unevaluated"
    assert all(v is None for v in view.constraints.values())


# ── Third Door: four states, because two could not tell absence from refusal ──────────────
#
# `render()` used to derive its verdict as `all True -> UNLOCKED else LOCKED`. Measured against
# this repository's own populated `.builder/artifacts`, and against a fresh clone: `VAULT LOCKED`,
# every time, on every host -- because no promotion readiness artifact exists to read, not because
# anything was refused. These lanes exist so a mechanical lock can one day bind to a state that
# knows the difference; a lock bound to the old binary would have refused every operator forever.


def _door(**overrides: bool | None) -> ThirdDoorView:
    """A view over the canonical eight, unassessed except where named."""
    constraints: dict[str, bool | None] = {name: None for name in THIRD_DOOR_CONSTRAINTS}
    constraints.update(overrides)
    return ThirdDoorView(constraints=constraints, source="readiness")


def test_an_unassessed_third_door_is_not_reported_as_refused(tmp_path: Path) -> None:
    """The defect, pinned at the level that matters: what an operator sees on a real checkout.

    Deliberately routed through `project_third_door` on a real directory rather than a hand-built
    view -- the bug was never in the constraint mapping, it was in what the absence of a readiness
    artifact was then *called*. A unit test over a synthetic all-None dict would have passed both
    before and after this change.
    """
    view = project_third_door(tmp_path)

    assert view.state == THIRD_DOOR_UNASSESSED
    assert view.state != THIRD_DOOR_LOCKED, (
        "an unassessed door is reporting as refused again -- absence of evidence is being "
        "rendered as denial, which is what made a Third Door lock unbuildable"
    )

    rendered = _strip_markup(str(ThirdDoorGate(view).render()))
    assert "VAULT UNASSESSED" in rendered
    assert "VAULT LOCKED" not in rendered


def test_third_door_locks_only_on_an_explicit_refusal() -> None:
    """LOCKED must mean something was evaluated and came back False. Nothing weaker."""
    assert _door(Documentation=False).state == THIRD_DOOR_LOCKED
    # One refusal shuts the door regardless of how much else is satisfied.
    assert _door(**{name: True for name in THIRD_DOOR_CONSTRAINTS[:7]}, **{THIRD_DOOR_CONSTRAINTS[7]: False}).state == (
        THIRD_DOOR_LOCKED
    )
    # ...and regardless of how much else is merely unassessed. An open slot cannot un-refuse.
    assert _door(Tests=False).state == THIRD_DOOR_LOCKED


def test_partial_evidence_with_no_refusal_is_incomplete_not_locked() -> None:
    """The state that had nowhere to live before: real evidence, nothing refusing, not yet done."""
    view = _door(Documentation=True, Tests=True)

    assert view.state == THIRD_DOOR_INCOMPLETE
    rendered = _strip_markup(str(ThirdDoorGate(view).render()))
    assert "VAULT INCOMPLETE" in rendered
    assert "2/8 satisfied" in rendered
    assert "none refused" in rendered


def test_third_door_unlocks_only_when_all_eight_are_satisfied() -> None:
    """The claim the header makes ('authority requires all 8') must be the claim the code makes."""
    assert _door(**{name: True for name in THIRD_DOOR_CONSTRAINTS}).state == THIRD_DOOR_UNLOCKED
    # Seven of eight is not eight. Nothing refused, and the door still does not open.
    seven = _door(**{name: True for name in THIRD_DOOR_CONSTRAINTS[:7]})
    assert seven.state == THIRD_DOOR_INCOMPLETE
    assert seven.state != THIRD_DOOR_UNLOCKED


def test_the_widget_and_the_projection_cannot_disagree_about_the_verdict() -> None:
    """The drift that caused the bug: two readers deriving one verdict by two different rules.

    `ThirdDoorGate.render()` had its own inline copy, which is how it came to contradict the
    docstring three lines above it. Both now read `third_door_state`, so this asserts they agree
    across every state rather than trusting that they were written to.
    """
    expectations = {
        THIRD_DOOR_UNASSESSED: "VAULT UNASSESSED",
        THIRD_DOOR_INCOMPLETE: "VAULT INCOMPLETE",
        THIRD_DOOR_LOCKED: "VAULT LOCKED",
        THIRD_DOOR_UNLOCKED: "VAULT UNLOCKED",
    }
    views = [
        _door(),
        _door(Documentation=True),
        _door(Documentation=False),
        _door(**{name: True for name in THIRD_DOOR_CONSTRAINTS}),
    ]
    seen = set()
    for view in views:
        rendered = _strip_markup(str(ThirdDoorGate(view).render()))
        assert expectations[view.state] in rendered, f"state {view.state!r} did not render as itself"
        seen.add(view.state)

    assert seen == set(expectations), f"a state went unexercised: {set(expectations) - seen}"


def test_an_unassessed_door_says_which_kind_of_unassessed_it_is() -> None:
    """'Mint a readiness artifact' and 'yours is unreadable' are different jobs.

    `set_constraints(door.constraints)` dropped `source` at both call sites, so the widget could
    not tell them apart and an operator staring at eight open slots had no way to know which one
    they were in.
    """
    no_artifact = _strip_markup(str(ThirdDoorGate(unassessed_third_door()).render()))
    assert "no promotion readiness artifact found" in no_artifact

    constraints: dict[str, bool | None] = {name: None for name in THIRD_DOOR_CONSTRAINTS}
    unreadable = ThirdDoorView(constraints=constraints, source="readiness")
    rendered = _strip_markup(str(ThirdDoorGate(unreadable).render()))
    assert "readiness artifact was found" in rendered
    assert "no recognised constraint evidence" in rendered


def test_scan_pending_hitl_clear_when_empty(tmp_path: Path) -> None:
    open_, label = scan_pending_hitl(tmp_path)
    assert open_ is False
    assert "NO PENDING" in label.upper() or "PENDING" in label.upper()


def test_hitl_surface_finds_pending_proposal(tmp_path: Path) -> None:
    data = {
        "kind": "builder_ii.hitl_patch_proposal",
        "command": "apply-patch",
        "state": "PENDING",
        "digest": "abc123real",
    }
    (tmp_path / "proposal.json").write_text(json.dumps(data), encoding="utf-8")
    view = project_hitl_surface(tmp_path)
    assert view is not None
    assert view.pending is True
    assert view.digest == "abc123real"
    assert view.command == "apply-patch"


def test_model_matrix_loads_registry() -> None:
    view = project_model_matrix()
    assert view.error is None or view.rows  # registry should load in test env
    assert isinstance(view.rows, tuple)


def test_agent_roster_loads_profiles() -> None:
    view = project_agent_roster(target="generic")
    assert len(view.profiles) > 0
    assert view.readiness_verdict != ""


def test_compose_assign_command_names_governed_cli() -> None:
    cmd = compose_assign_command("repo_mapper", target="builder")
    assert "builder-deepagents assign-subagent" in cmd
    assert "repo_mapper" in cmd
    assert "Dispatch" not in cmd


def test_teaming_widget_ids_reject_dots_in_profile_names() -> None:
    """Textual DOM ids cannot contain '.' — profile names like core.invariant_auditor must be sanitized."""
    from builder_ii.tui.widgets.teaming import _widget_id_for_profile

    assert _widget_id_for_profile("core.invariant_auditor") == "agent-core-invariant_auditor"
    assert "." not in _widget_id_for_profile("core.patch_planner")
    assert _widget_id_for_profile("repo_mapper") == "agent-repo_mapper"


def test_operator_dashboard_empty_chain(tmp_path: Path) -> None:
    dash = project_operator_dashboard(artifacts_dir=tmp_path, target="generic")
    assert dash.platform == "builder-II"
    assert dash.chain_length == 0
    assert dash.chain_valid is None
    assert dash.epistemic["digest_planned"] == "—"


# ── STRATUM idle report: memory_atoms / chain_length must be read, not fabricated ─────────────
#
# The idle HUD shipped `"memory_atoms": "0"  # Would read from memory browser` and a matching
# `"chain_length": "0"`. Both were fabricated: the memory zero never looked at an index, and the
# chain zero was overwritten by the async verifier moments later (and reset again on any refresh,
# because set_platform_info replaces the whole dict). An operator cannot distinguish a fabricated
# zero from a genuine empty state — so these pin the honest read, and the "—" for absent evidence.


def test_idle_report_memory_atoms_reads_the_real_index(tmp_path: Path) -> None:
    """An index of N atoms shows N — the number is read from `memory-index.json`, not hardcoded."""
    from builder_ii.tui.projections.operator import memory_atom_display

    index = {"kind": "builder_ii.memory_index", "atom_count": 3, "entries": [1, 2, 3]}
    (tmp_path / "memory-index.json").write_text(json.dumps(index), encoding="utf-8")
    assert memory_atom_display(tmp_path) == "3"


def test_idle_report_memory_atoms_is_dash_when_no_index(tmp_path: Path) -> None:
    """No index (or no dir) is unknown — "—", never a fabricated "0". Absence ≠ zero atoms."""
    from builder_ii.tui.projections.operator import memory_atom_display

    assert memory_atom_display(tmp_path) == "—"
    assert memory_atom_display(None) == "—"


def test_idle_report_memory_atoms_honours_a_truthful_zero(tmp_path: Path) -> None:
    """A real index holding zero atoms shows "0" — because it was read, not guessed."""
    from builder_ii.tui.projections.operator import memory_atom_display

    index = {"kind": "builder_ii.memory_index", "atom_count": 0, "entries": []}
    (tmp_path / "memory-index.json").write_text(json.dumps(index), encoding="utf-8")
    assert memory_atom_display(tmp_path) == "0"


def test_idle_report_memory_atoms_dash_on_unreadable_index(tmp_path: Path) -> None:
    """A malformed index is "—" (unknown), not a fabricated zero and not a crash."""
    from builder_ii.tui.projections.operator import memory_atom_display

    (tmp_path / "memory-index.json").write_text("{not json", encoding="utf-8")
    assert memory_atom_display(tmp_path) == "—"


def test_idle_report_chain_length_counts_real_artifacts(tmp_path: Path) -> None:
    """chain_length is the real *.json count (matching the async verifier), not a hardcoded 0."""
    from builder_ii.tui.projections.operator import count_artifact_files

    assert count_artifact_files(tmp_path) == 0
    assert count_artifact_files(None) == 0
    (tmp_path / "repo_map.json").write_text(json.dumps({"kind": "builder_ii.repo_map"}), encoding="utf-8")
    (tmp_path / "ctx.json").write_text(json.dumps({"kind": "builder_ii.context_pack"}), encoding="utf-8")
    assert count_artifact_files(tmp_path) == 2


def test_idle_report_source_carries_no_fabricated_zero() -> None:
    """Pin the wiring, not just the helpers: a revert to `"memory_atoms": "0"` must fail here.

    The honest helpers can exist and be correct while `_update_idle_report` still hardcodes "0";
    this asserts the fabrication is gone from the source and the real readers are the ones wired in.
    """
    app_src = (Path(__file__).resolve().parents[1] / "builder_ii" / "tui" / "app.py").read_text(encoding="utf-8")
    assert '"memory_atoms": "0"' not in app_src, "idle report is fabricating a memory-atom zero again"
    assert '"chain_length": "0"' not in app_src, "idle report is fabricating a chain-length zero again"
    assert "idle_report_stats(" in app_src, "idle report must read real stats via idle_report_stats"


def test_idle_report_stats_is_best_effort_and_never_raises() -> None:
    """The two mount-path FS reads must degrade to "—", never crash the TUI at mount.

    idle_report_stats is the only synchronous filesystem read on the mount path. A MagicMock
    artifacts_dir is exactly what a TUI test that patches load_settings without a real project_root
    produces (its `.read_text()` returns a mock that `json.loads` rejects with TypeError) — that
    regression is what motivated this wrapper, so it is pinned here with the same object.
    """
    from unittest.mock import MagicMock

    from builder_ii.tui.projections.operator import idle_report_stats

    memory_atoms, chain_length = idle_report_stats(MagicMock())
    assert memory_atoms == "—"
    assert chain_length == "—"


def test_idle_report_stats_reads_real_values(tmp_path: Path) -> None:
    """On a real dir, the wrapper returns the honest (memory_atoms, chain_length) pair."""
    from builder_ii.tui.projections.operator import idle_report_stats

    index = {"kind": "builder_ii.memory_index", "atom_count": 2, "entries": [1, 2]}
    (tmp_path / "memory-index.json").write_text(json.dumps(index), encoding="utf-8")
    (tmp_path / "repo_map.json").write_text(json.dumps({"kind": "builder_ii.repo_map"}), encoding="utf-8")

    memory_atoms, chain_length = idle_report_stats(tmp_path)
    assert memory_atoms == "2"
    # 2 files: memory-index.json + repo_map.json (chain_length counts all *.json).
    assert chain_length == "2"


def test_workflow_lists_stages() -> None:

    view = project_workflow(artifacts_dir=None)
    assert len(view.stages) >= 1
    assert view.current_stage is None
    assert "builder-goose manifest" in view.compose_manifest


def test_orchestration_empty(tmp_path: Path) -> None:
    from builder_ii.tui.projections.orchestration import project_orchestration

    view = project_orchestration(artifacts_dir=tmp_path)
    assert view.plans == ()
    assert "builder-orchestration plan" in view.compose_plan


def test_code_vault_empty(tmp_path: Path) -> None:
    from builder_ii.tui.projections.codevault import project_code_vault

    view = project_code_vault(artifacts_dir=tmp_path, project_root=tmp_path)
    # Frame count is always 0 for an empty directory
    assert view.frame_count == 0
    # The projection must have a coherent note regardless of install state
    if view.is_installed:
        assert "CodeVault" in view.note
        assert view.compose_demo  # populated when installed
    else:
        assert "not installed" in view.note.lower()
        assert not view.compose_demo  # empty when not installed


def test_model_matrix_includes_local_config() -> None:
    from builder_ii.tui.projections.models import project_model_matrix

    view = project_model_matrix()
    assert view.local is not None
    assert view.compose_policy_render
    assert "builder-model-policy" in view.compose_policy_render
