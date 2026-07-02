from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.agent_profiles import create_agent_profile_record, get_agent_profile
from builder_ii.config import load_settings
from builder_ii.context_packs import create_context_pack
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
)
from builder_ii.orchestration_assignment import (
    create_agent_assignment_plan,
    create_orchestration_assignment_dry_run,
    create_orchestration_assignment_plan,
    create_orchestration_assignment_validation_report,
)
from builder_ii.profile_pack import create_profile_pack
from builder_ii.profile_pack_dry_run import create_profile_pack_dry_run
from builder_ii.profile_pack_manifest import create_profile_pack_manifest
from builder_ii.profile_pack_render_plan import create_profile_pack_render_plan
from builder_ii.profile_pack_validation_report import (
    create_profile_pack_validation_report,
)
from builder_ii.repo_map import create_repo_map
from builder_ii.target_profiles import target_profile
from builder_ii.verification_profiles import get_verification_profile

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_goal2_assignment_fixture(
    tmp_path: Path, *, task: str = "test passive assignment"
) -> dict[str, Any]:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'generic-repo'\n", encoding="utf-8"
    )

    artifact_dir = tmp_path / "artifacts"
    paths = {
        "target_profile": artifact_dir / "target-profile.json",
        "agent_profile": artifact_dir / "agent-profile.json",
        "context_pack": artifact_dir / "context-pack.json",
        "verification_profile": artifact_dir / "verification-profile.json",
        "model_registry": artifact_dir / "model-registry.json",
        "model_policy": artifact_dir / "model-policy.json",
        "model_recommendation": artifact_dir / "model-recommendation.json",
        "profile_pack_manifest": artifact_dir / "profile-pack-manifest.json",
        "profile_pack_render_plan": artifact_dir / "profile-pack-render-plan.json",
        "profile_pack_dry_run": artifact_dir / "profile-pack-dry-run.json",
        "profile_pack_validation_report": artifact_dir
        / "profile-pack-validation-report.json",
        "profile_pack": artifact_dir / "profile-pack.json",
        "assignment": artifact_dir / "agent-assignment-plan.json",
        "orchestration": artifact_dir / "orchestration-assignment-plan.json",
        "dry_run": artifact_dir / "orchestration-assignment-dry-run.json",
        "validation_report": artifact_dir
        / "orchestration-assignment-validation-report.json",
    }

    settings = load_settings(project_root=ROOT)
    target = target_profile(settings, "generic", generic_repo=repo).to_artifact_dict()
    agent = create_agent_profile_record(
        get_agent_profile("patch_planner"),
        target_profile(settings, "generic", generic_repo=repo),
        task=task,
    )
    repo_map = create_repo_map(repo, target_name="generic")
    context_pack = create_context_pack(repo_map, target_name="generic", task=task)
    verification = get_verification_profile("generic_basic").to_artifact_dict(
        target="generic", task=task
    )
    model_registry = create_model_client_registry()
    model_policy = create_model_routing_policy()
    model_recommendation = create_model_routing_recommendation(
        policy=model_policy,
        registry=model_registry,
        request={
            "task_intent": "coding",
            "max_risk_classification": "local_network",
            "requires_tool_use": True,
        },
        policy_path=paths["model_policy"],
        registry_path=paths["model_registry"],
    )

    manifest = create_profile_pack_manifest(
        pack_id="goal2-test-profile-pack",
        target_profile="generic",
        task=task,
        project_root=ROOT,
    )
    render_plan = create_profile_pack_render_plan(
        manifest, manifest_path=paths["profile_pack_manifest"]
    )
    profile_pack_dry_run = create_profile_pack_dry_run(
        manifest,
        render_plan,
        manifest_path=paths["profile_pack_manifest"],
        render_plan_path=paths["profile_pack_render_plan"],
    )
    profile_pack_validation_report = create_profile_pack_validation_report(
        manifest,
        subject_path=paths["profile_pack_manifest"],
    )
    profile_pack = create_profile_pack(
        manifest=manifest,
        render_plan=render_plan,
        dry_run=profile_pack_dry_run,
        validation_report=profile_pack_validation_report,
        manifest_path=paths["profile_pack_manifest"],
        render_plan_path=paths["profile_pack_render_plan"],
        dry_run_path=paths["profile_pack_dry_run"],
        validation_report_path=paths["profile_pack_validation_report"],
    )

    artifacts = {
        "target_profile": target,
        "agent_profile": agent,
        "context_pack": context_pack,
        "verification_profile": verification,
        "model_registry": model_registry,
        "model_policy": model_policy,
        "model_recommendation": model_recommendation,
        "profile_pack_manifest": manifest,
        "profile_pack_render_plan": render_plan,
        "profile_pack_dry_run": profile_pack_dry_run,
        "profile_pack_validation_report": profile_pack_validation_report,
        "profile_pack": profile_pack,
    }

    assignment = create_agent_assignment_plan(
        target_profile=target,
        agent_profile=agent,
        task=task,
        context_pack=context_pack,
        verification_profile=verification,
        model_registry=model_registry,
        model_policy=model_policy,
        model_recommendation=model_recommendation,
        profile_pack_manifest=manifest,
        profile_pack_render_plan=render_plan,
        profile_pack_dry_run=profile_pack_dry_run,
        profile_pack_validation_report=profile_pack_validation_report,
        profile_pack=profile_pack,
        target_profile_path=paths["target_profile"],
        agent_profile_path=paths["agent_profile"],
        context_pack_path=paths["context_pack"],
        verification_profile_path=paths["verification_profile"],
        model_registry_path=paths["model_registry"],
        model_policy_path=paths["model_policy"],
        model_recommendation_path=paths["model_recommendation"],
        profile_pack_manifest_path=paths["profile_pack_manifest"],
        profile_pack_render_plan_path=paths["profile_pack_render_plan"],
        profile_pack_dry_run_path=paths["profile_pack_dry_run"],
        profile_pack_validation_report_path=paths["profile_pack_validation_report"],
        profile_pack_path=paths["profile_pack"],
    )
    orchestration = create_orchestration_assignment_plan(
        assignment, assignment_plan_path=paths["assignment"]
    )
    dry_run = create_orchestration_assignment_dry_run(
        orchestration, orchestration_assignment_plan_path=paths["orchestration"]
    )
    validation_report = create_orchestration_assignment_validation_report(
        orchestration, subject_path=paths["orchestration"]
    )

    artifacts.update(
        {
            "assignment": assignment,
            "orchestration": orchestration,
            "dry_run": dry_run,
            "validation_report": validation_report,
        }
    )

    for name, artifact in artifacts.items():
        write_json(paths[name], artifact)

    return {
        "repo": repo,
        "artifact_dir": artifact_dir,
        "paths": paths,
        "artifacts": artifacts,
    }
