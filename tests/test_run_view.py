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

def test_lesion_malformed_event_refs_returns_corrupt(tmp_path: Path) -> None:
    from tests.test_run_lifecycle_scenarios import _setup_deepagents_fixture
    from builder_ii.adapters.deepagents.deepagents_session_custody import persist_deepagents_start
    import json
    
    session_id = "malformed-event-refs"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)
    
    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )
    
    ledger_path = artifact_root / "sessions" / session_id / "deepagents" / "event_ledger.json"
    data = json.loads(ledger_path.read_text())
    data["event_refs"] = 7
    ledger_path.write_text(json.dumps(data))
    
    view = project_run_view(artifact_root, session_id=session_id)
    assert view.evidence_health == "CORRUPT"

def test_lesion_malformed_sequence_returns_corrupt(tmp_path: Path) -> None:
    from tests.test_run_lifecycle_scenarios import _setup_deepagents_fixture
    from builder_ii.adapters.deepagents.deepagents_session_custody import persist_deepagents_start
    import json
    
    session_id = "malformed-seq"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)
    
    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )
    
    event_path = artifact_root / "sessions" / session_id / "deepagents" / "events" / "event-000001.json"
    data = json.loads(event_path.read_text())
    data["sequence"] = "two"
    event_path.write_text(json.dumps(data))
    
    view = project_run_view(artifact_root, session_id=session_id)
    assert view.evidence_health == "CORRUPT"

def test_lesion_malformed_previous_event_ref_returns_corrupt(tmp_path: Path) -> None:
    from tests.test_run_lifecycle_scenarios import _setup_deepagents_fixture
    from builder_ii.adapters.deepagents.deepagents_session_custody import persist_deepagents_start
    import json
    
    session_id = "malformed-prev-ref"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)
    
    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )
    
    event_path = artifact_root / "sessions" / session_id / "deepagents" / "events" / "event-000002.json"
    if event_path.exists():
        data = json.loads(event_path.read_text())
        data["previous_event_ref"] = 7
        event_path.write_text(json.dumps(data))
    
    view = project_run_view(artifact_root, session_id=session_id)
    assert view.evidence_health == "CORRUPT"

