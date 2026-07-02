from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.event_ledger import load_event_records, replay_events
from builder_ii.readonly_founder_demo import (
    TARGET_INSPECTION_PLAN_KIND,
    TARGET_PATCH_PROPOSAL_KIND,
    TARGET_VERIFICATION_PLAN_KIND,
    generate_readonly_founder_demo,
    get_forbidden_authority_boundaries,
    validate_target_inspection_plan,
    validate_target_patch_proposal,
    validate_target_verification_plan,
)


def test_forbidden_authority_boundaries() -> None:
    bounds = get_forbidden_authority_boundaries()
    assert bounds["runtime_authority"] == "DISABLED"
    assert bounds["model_execution"] == "DISABLED"
    assert bounds["shell_execution"] == "DISABLED"
    assert bounds["mcp"] == "DISABLED"
    assert bounds["goose_runtime"] == "DISABLED"
    assert bounds["deepagents_runtime"] == "DISABLED"
    assert bounds["source_writes"] == "DISABLED"
    assert bounds["commit_push_automation"] == "DISABLED"
    assert bounds["core_workbench_coupling"] == "NONE"


@pytest.mark.parametrize("target", ["core", "generic", "builder"])
def test_generate_readonly_founder_demo(tmp_path: Path, target: str) -> None:
    out = tmp_path / f"{target}-demo"
    res = generate_readonly_founder_demo(target=target, output_dir=out)  # type: ignore[arg-type]

    assert res["inspection_plan"].exists()
    assert res["patch_proposal"].exists()
    assert res["verification_plan"].exists()
    assert res["event_ledger"].exists()
    assert res["workflow_session"].exists()
    assert res["workflow_status"].exists()
    assert res["replay_report"].exists()

    insp_data = json.loads(res["inspection_plan"].read_text("utf-8"))
    assert validate_target_inspection_plan(insp_data) == []
    assert insp_data["kind"] == TARGET_INSPECTION_PLAN_KIND
    assert insp_data["governance"] == get_forbidden_authority_boundaries()

    prop_data = json.loads(res["patch_proposal"].read_text("utf-8"))
    assert validate_target_patch_proposal(prop_data) == []
    assert prop_data["kind"] == TARGET_PATCH_PROPOSAL_KIND
    assert prop_data["governance"] == get_forbidden_authority_boundaries()
    assert prop_data["inspection_plan_ref"]["path"] == str(res["inspection_plan"])

    verif_data = json.loads(res["verification_plan"].read_text("utf-8"))
    assert validate_target_verification_plan(verif_data) == []
    assert verif_data["kind"] == TARGET_VERIFICATION_PLAN_KIND
    assert verif_data["governance"] == get_forbidden_authority_boundaries()
    assert verif_data["patch_proposal_ref"]["path"] == str(res["patch_proposal"])

    # Test chain verification
    artifacts_dir = out / "artifacts"
    events_dir = out / "events"
    all_json = list(artifacts_dir.glob("*.json")) + list(events_dir.glob("*.json"))
    report = verify_artifact_chain(all_json)
    assert report["valid"] is True, f"Chain verification failed: {report['errors']}"
    assert report["errors"] == []

    # Test event replay
    events = load_event_records(events_dir)
    assert len(events) == 4
    replay = replay_events(events, session_id=f"wf-{target}-readonly-founder-demo")
    assert replay["valid"] is True
    assert replay["current_stage"] == "candidate"
    assert replay["completed_stages"] == ["initialized", "planned", "promoted", "candidate"]


def test_validation_errors() -> None:
    # Baseline empty failures
    assert validate_target_inspection_plan({}) != []
    assert validate_target_patch_proposal({}) != []
    assert validate_target_verification_plan({}) != []

    invalid_gov = {
        "kind": TARGET_INSPECTION_PLAN_KIND,
        "schema_version": 1,
        "title": "Title",
        "target_profile": "core",
        "target_repo": "/repo",
        "agent_profile": "agent",
        "inspection_scope": ["README.md"],
        "target_profile_ref": {"path": "t.json", "sha256": "h"},
        "workflow_session_ref": {"path": "s.json", "sha256": "h"},
        "governance": {"runtime_authority": "ENABLED"},
    }
    errors = validate_target_inspection_plan(invalid_gov)
    assert any("Forbidden authority violation" in e for e in errors)

    # Negative tests for missing references
    valid_insp = {
        "kind": TARGET_INSPECTION_PLAN_KIND,
        "schema_version": 1,
        "title": "Title",
        "target_profile": "core",
        "target_repo": "/repo",
        "agent_profile": "agent",
        "inspection_scope": ["README.md"],
        "target_profile_ref": {"path": "t.json", "sha256": "h"},
        "workflow_session_ref": {"path": "s.json", "sha256": "h"},
        "governance": get_forbidden_authority_boundaries(),
    }
    assert validate_target_inspection_plan(valid_insp) == []

    # Missing target_profile_ref
    bad_insp = dict(valid_insp)
    del bad_insp["target_profile_ref"]
    assert validate_target_inspection_plan(bad_insp) != []

    # Missing workflow_session_ref
    bad_insp2 = dict(valid_insp)
    del bad_insp2["workflow_session_ref"]
    assert validate_target_inspection_plan(bad_insp2) != []

    valid_proposal = {
        "kind": TARGET_PATCH_PROPOSAL_KIND,
        "schema_version": 1,
        "title": "Title",
        "target_profile": "core",
        "target_repo": "/repo",
        "agent_profile": "agent",
        "proposed_changes": ["change"],
        "invariant_impact": "impact",
        "target_profile_ref": {"path": "t.json", "sha256": "h"},
        "workflow_session_ref": {"path": "s.json", "sha256": "h"},
        "inspection_plan_ref": {"path": "i.json", "sha256": "h"},
        "governance": get_forbidden_authority_boundaries(),
    }
    assert validate_target_patch_proposal(valid_proposal) == []

    # Missing inspection_plan_ref
    bad_proposal = dict(valid_proposal)
    del bad_proposal["inspection_plan_ref"]
    assert validate_target_patch_proposal(bad_proposal) != []

    valid_verif = {
        "kind": TARGET_VERIFICATION_PLAN_KIND,
        "schema_version": 1,
        "title": "Title",
        "target_profile": "core",
        "target_repo": "/repo",
        "agent_profile": "agent",
        "proposed_commands": ["cmd"],
        "pass_criteria": "pass",
        "target_profile_ref": {"path": "t.json", "sha256": "h"},
        "workflow_session_ref": {"path": "s.json", "sha256": "h"},
        "patch_proposal_ref": {"path": "p.json", "sha256": "h"},
        "governance": get_forbidden_authority_boundaries(),
    }
    assert validate_target_verification_plan(valid_verif) == []

    # Missing patch_proposal_ref
    bad_verif = dict(valid_verif)
    del bad_verif["patch_proposal_ref"]
    assert validate_target_verification_plan(bad_verif) != []


def test_promoted_stage_authority_invariants(tmp_path: Path) -> None:
    # Generate the demo to inspect replay report governance details
    out = tmp_path / "core-demo"
    generate_readonly_founder_demo(target="core", output_dir=out)

    events_dir = out / "events"
    events = load_event_records(events_dir)

    # Verify events sequence
    # 0003-workflow_promoted.json represents the 'promoted' transition
    promoted_event_file = events_dir / "0003-workflow_promoted.json"
    assert promoted_event_file.exists()

    # Replay events to get replay report
    replay = replay_events(events, session_id="wf-core-readonly-founder-demo")
    assert replay["valid"] is True

    # Assert that no authority promotion or active runtime execution is authorized at the 'promoted' stage
    # In particular, all command-surface / runtime execution flags must remain disabled/false.
    gov = replay["governance"]
    assert gov["grants_runtime_authority"] is False
    assert gov["grants_action_authority"] is False
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["mcp_execution"] == "DISABLED"
    assert gov["goose_runtime_start"] == "DISABLED"
    assert gov["deepagents_runtime"] == "DISABLED"
    assert gov["target_repo_writes"] == "DISABLED"

