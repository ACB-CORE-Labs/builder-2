from __future__ import annotations

import copy
import json as json_lib
from pathlib import Path

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.config import load_settings
from builder_ii.goose_projection import create_goose_projection
from builder_ii.goose_wrapper_plan import create_goose_wrapper_plan
from builder_ii.orchestration_plan import create_orchestration_plan
from builder_ii.session_config import create_session_configuration


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_artifact_chain_accepts_session_projection_wrapper_and_orchestration_artifacts(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    session_config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task="verify new chain artifact registrations",
        model_alias="qwen-coder",
        generic_repo=repo,
    )
    projection = create_goose_projection(settings, session_config)
    wrapper_plan = create_goose_wrapper_plan(projection)
    orchestration_plan = create_orchestration_plan(
        target="generic",
        task="verify orchestration chain registration",
    )

    artifacts = {
        "session-config.json": session_config,
        "goose-projection.json": projection,
        "goose-wrapper-plan.json": wrapper_plan,
        "orchestration-plan.json": orchestration_plan,
    }
    paths: list[Path] = []
    for name, artifact in artifacts.items():
        path = tmp_path / "artifacts" / name
        _write_json(path, artifact)
        paths.append(path)

    report = verify_artifact_chain(paths)

    assert report["valid"] is True
    assert report["status"] == "valid"
    assert report["counts"]["files"] == 4
    assert report["counts"]["native_valid"] == 4
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0
    assert {item["kind"] for item in report["files"]} == {
        "builder_ii.session_configuration",
        "builder_ii.goose_projection",
        "builder_ii.goose_wrapper_plan",
        "builder_ii.orchestration_plan",
    }
    assert report["governance"]["runtime_execution"] == "DISABLED"
    assert report["governance"]["model_execution"] == "DISABLED"
    assert report["governance"]["artifact_is_authority"] is False


def test_artifact_chain_rejects_registered_artifact_authority_escalation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    session_config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)
    projection = create_goose_projection(settings, session_config)
    bad_projection = copy.deepcopy(projection)
    bad_projection["projection_state"] = "EXECUTED"
    bad_projection["governance"]["model_execution"] = "ENABLED"

    path = tmp_path / "artifacts" / "bad-goose-projection.json"
    _write_json(path, bad_projection)

    report = verify_artifact_chain([path])

    assert report["valid"] is False
    assert report["status"] == "invalid"
    assert report["counts"]["native_valid"] == 0
    assert report["counts"]["native_invalid"] == 1
    assert any("projection_state must be PLANNED_ONLY" in error for error in report["errors"])
    assert any("governance.model_execution must be DISABLED" in error for error in report["errors"])
