"""Core ownership and compatibility tests for the governed run read model."""

from pathlib import Path

from builder_ii.core.run_view import RunView, project_run_view
from builder_ii.tui.projections.run_projection import RunProjection, project_run


def test_empty_run_view_is_frontend_neutral_and_explicit(tmp_path: Path) -> None:
    view = project_run_view(tmp_path)

    assert isinstance(view, RunView)
    assert view.canonical_stage == "PREPARE"
    assert view.activity_label == "orienting the run"
    assert view.recommended_action == "prepare-package"
    assert view.admissible_actions == ("prepare-package",)
    assert view.attention_items == ()
    assert view.validated_evidence == ()
    assert view.projection_errors == ()


def test_tui_projection_names_are_one_release_compatibility_aliases(tmp_path: Path) -> None:
    assert RunProjection is RunView
    assert project_run is project_run_view
    assert project_run(tmp_path) == project_run_view(tmp_path)


def test_corrupt_json_requires_recovery_without_becoming_evidence(tmp_path: Path) -> None:
    (tmp_path / "corrupt.json").write_text("{", encoding="utf-8")

    view = project_run_view(tmp_path)

    assert view.evidence_health == "CORRUPT"
    assert view.canonical_stage == "PREPARE"
    assert view.attention_items
    assert view.recovery == "repair or retire corrupt/foreign evidence before continuing"
    assert view.validated_evidence == ()
