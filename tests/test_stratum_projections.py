"""Projection-layer honesty tests — no Textual, no writes, no synthesis."""

from __future__ import annotations

import json
from pathlib import Path

from builder_ii.tui.projections.agents import compose_assign_command, project_agent_roster
from builder_ii.tui.projections.chain import epistemic_from_chain, project_chain
from builder_ii.tui.projections.gates import project_hitl_surface, project_third_door, scan_pending_hitl
from builder_ii.tui.projections.models import project_model_matrix
from builder_ii.tui.projections.operator import project_operator_dashboard
from builder_ii.tui.projections.workflow import project_workflow
from builder_ii.tui.widgets.masterpiece import EpistemicMatrix


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
    assert view.frame_count == 0
    assert "builder-code-vault" in view.compose_demo


def test_model_matrix_includes_local_config() -> None:
    from builder_ii.tui.projections.models import project_model_matrix

    view = project_model_matrix()
    assert view.local is not None
    assert view.compose_policy_render
    assert "builder-model-policy" in view.compose_policy_render
