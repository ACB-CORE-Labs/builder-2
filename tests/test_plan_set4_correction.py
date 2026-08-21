from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from builder_ii.adapters.deepagents.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.adapters.deepagents.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    create_deepagents_work_plan,
    write_deepagents_work_plan,
)
from builder_ii.cli.deepagents_cli import deepagents_app
from builder_ii.cli.hitl_execution_cli import hitl_app
from builder_ii.cli.main import app as builder_app
from builder_ii.cli.session_cli import session_app
from builder_ii.core.canonical_json import canonical_digest
from builder_ii.core.config import load_settings
from builder_ii.core.handoff_artifacts import create_handoff_artifact
from builder_ii.governance.hitl.hitl_patch_apply import create_patch_apply_receipt
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.lifecycle.setup.presets import PRESETS, preset_artifact, validate_preset_artifact
from builder_ii.lifecycle.setup.readiness import (
    Readiness,
    check_deepagents,
    check_gh,
    check_goose,
    check_model_backend,
    check_repository,
    validate_readiness_evidence,
)
from builder_ii.routing.agent_profiles import profiles_for_target
from builder_ii.tui.app import StratumApp
from builder_ii.tui.projections.run_projection import LIFECYCLE, project_run
from builder_ii.tui.stratum_commands import (
    AssignSubagentInputs,
    HitlPatchInputs,
    PreparePackageInputs,
    ValidatePackageInputs,
    build_command,
    command_inventory,
)
from tests.hitl_patch_test_helpers import write_executed_verification_receipt
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture

runner = CliRunner()
SESSION = "plan-set-4-e2e"


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _work_plan(tmp_path: Path, *, task: str = "Plan Set 4 primary path") -> Path:
    fixture = build_goal2_assignment_fixture(tmp_path / "goal2", task=task)
    policy = create_deepagents_policy_artifact(load_settings(), target_name="generic")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")
    policy_path = tmp_path / "policy.json"
    readiness_path = tmp_path / "readiness.json"
    _write(policy_path, policy)
    _write(readiness_path, readiness)
    plan = create_deepagents_work_plan(
        target="generic",
        task=task,
        orchestration_assignment_plan=fixture["artifacts"]["orchestration"],
        orchestration_assignment_dry_run=fixture["artifacts"]["dry_run"],
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        orchestration_assignment_plan_path=fixture["paths"]["orchestration"],
        orchestration_assignment_dry_run_path=fixture["paths"]["dry_run"],
        deepagents_policy_path=policy_path,
        deepagents_readiness_path=readiness_path,
        proposed_subagents=["repo_mapper", "code_reviewer"],
        expected_outputs=["subagent_assignment"],
        review_gates=["operator_review"],
    )
    path = tmp_path / "work-plan.json"
    write_deepagents_work_plan(plan, path)
    return path


def _prepare(root: Path, *, session: str = SESSION):
    command = build_command(
        "builder-session prepare-package",
        PreparePackageInputs("generic", "Plan Set 4 primary path", root, session),
    )
    result = runner.invoke(session_app, list(command.argv))
    assert result.exit_code == 0, result.output
    assert command.validator(command.output).errors == ()
    return command


def _proposal(tmp_path: Path) -> Path:
    proposal = create_hitl_patch_proposal(
        target_name="generic",
        patch_digest="a7f2deadbeef",
        unified_diff="diff-body",
        target_head_sha="a" * 40,
        verification_receipt_file_sha256="b" * 64,
    )
    path = tmp_path / "proposal.json"
    write_hitl_patch_proposal(proposal, path)
    return path


def test_closed_inventory_uses_real_modules_and_real_profiles(tmp_path: Path) -> None:
    assert command_inventory() == (
        "builder-session prepare-package",
        "builder-session validate-prepare-package",
        "builder-deepagents assign-subagent",
        "builder-hitl approve-patch",
        "builder-hitl refuse-patch",
    )
    plan = _work_plan(tmp_path)
    for profile in ("repo_mapper", "code_reviewer"):
        assert profile in {item.name for item in profiles_for_target("generic")}
        command = build_command(
            "builder-deepagents assign-subagent",
            AssignSubagentInputs("generic", "Plan Set 4 primary path", profile, plan, tmp_path, SESSION),
        )
        assert command.entrypoint == "builder_ii.cli.deepagents_cli"
        assert profile in command.argv


def test_profile_target_compatibility_is_enforced(tmp_path: Path) -> None:
    plan = _work_plan(tmp_path)
    try:
        build_command(
            "builder-deepagents assign-subagent",
            AssignSubagentInputs("generic", "Plan Set 4 primary path", "core.invariant_auditor", plan, tmp_path, SESSION),
        )
    except ValueError as exc:
        assert "not compatible" in str(exc)
    else:
        raise AssertionError("foreign target/profile pair was admitted")


def test_prepare_validate_retain_exact_invocation_path(tmp_path: Path) -> None:
    prepared = _prepare(tmp_path)
    validate = build_command(
        "builder-session validate-prepare-package",
        ValidatePackageInputs(prepared.output, tmp_path, SESSION),
    )
    assert validate.output == prepared.output
    assert "current" not in validate.output.parts
    result = runner.invoke(session_app, list(validate.argv))
    assert result.exit_code == 0, result.output
    assert validate.validator(validate.output).errors == ()


def test_real_canonical_assignment_and_wrong_kind_rejection(tmp_path: Path) -> None:
    plan = _work_plan(tmp_path)
    command = build_command(
        "builder-deepagents assign-subagent",
        AssignSubagentInputs("generic", "Plan Set 4 primary path", "repo_mapper", plan, tmp_path, SESSION),
    )
    result = runner.invoke(deepagents_app, list(command.argv))
    assert result.exit_code == 0, result.output
    assert command.validator(command.output).errors == ()
    _write(command.output, {"kind": "wrong.kind", "anything": "at all"})
    errors = command.validator(command.output).errors
    assert any("kind must be builder_ii.deepagents_subagent_assignment" in error for error in errors)


def test_stale_output_and_work_plan_substitution_are_rejected(tmp_path: Path) -> None:
    plan = _work_plan(tmp_path)
    command = build_command(
        "builder-deepagents assign-subagent",
        AssignSubagentInputs("generic", "Plan Set 4 primary path", "repo_mapper", plan, tmp_path, SESSION),
    )
    command.output.parent.mkdir(parents=True)
    _write(command.output, {"kind": "wrong.kind"})
    assert command.creates_output and command.output.exists()
    result = runner.invoke(deepagents_app, list(command.argv))
    assert result.exit_code == 0
    plan_data = json.loads(plan.read_text(encoding="utf-8"))
    plan_data["task"] = "substituted"
    _write(plan, plan_data)
    assert any("work plan" in error or "task" in error for error in command.validator(command.output).errors)


def test_hitl_real_cli_binding_and_wrong_kind_substitution(tmp_path: Path) -> None:
    proposal_path = _proposal(tmp_path)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    approve = build_command("builder-hitl approve-patch", HitlPatchInputs(proposal_path, tmp_path, SESSION))
    result = runner.invoke(hitl_app, list(approve.argv), input=proposal["patch_digest"][:4] + "\n")
    assert result.exit_code == 0, result.output
    assert approve.validator(approve.output).errors == ()
    approval = json.loads(approve.output.read_text(encoding="utf-8"))
    approval["kind"] = "wrong.kind"
    _write(approve.output, approval)
    assert approve.validator(approve.output).errors

    refuse = build_command("builder-hitl refuse-patch", HitlPatchInputs(proposal_path, tmp_path, SESSION))
    result = runner.invoke(hitl_app, list(refuse.argv), input="bounded rationale\n")
    assert result.exit_code == 0, result.output
    assert refuse.validator(refuse.output).errors == ()
    proposal["target"] = {"name": "core", "repo": "/foreign"}
    _write(proposal_path, proposal)
    assert any("proposal" in error for error in refuse.validator(refuse.output).errors)


def test_primary_surface_reaches_plan_set_6_boundary_from_canonical_evidence(monkeypatch, tmp_path: Path) -> None:
    readiness = tuple(
        Readiness(name, "ready", "qualified", "none")
        for name in (
            "goose-compatibility",
            "native-deepagents",
            "selected-model-backend",
            "github-cli",
            "repository-identity",
        )
    )
    monkeypatch.setattr("builder_ii.lifecycle.setup.readiness.passive_readiness", lambda **_kwargs: readiness)
    onboarding = tmp_path / "onboarding"
    initialized = runner.invoke(
        builder_app,
        [
            "init",
            "--root",
            str(tmp_path),
            "--output-dir",
            str(onboarding),
            "--non-interactive",
            "--target-profile",
            "generic",
            "--model-backend",
            "mlx-lm",
            "--model-alias",
            "qwen-coder",
            "--preset",
            "solo-fast",
        ],
    )
    assert initialized.exit_code == 0, initialized.output
    intent = json.loads((onboarding / "onboarding-intent.json").read_text(encoding="utf-8"))
    assert intent["preset_configuration"]["name"] == "solo-fast"

    root = tmp_path / "artifacts"
    session_root = root / "stratum" / "sessions" / SESSION
    assert LIFECYCLE == ("PREPARE", "PLAN", "APPROVE", "EXECUTE", "VERIFY", "DELIVER/PROMOTE")
    assert project_run(root, session_id=SESSION, target="generic").stage == "PREPARE"

    prepared = _prepare(root)
    assert project_run(root, session_id=SESSION, target="generic").stage == "PLAN"
    validation = build_command(
        "builder-session validate-prepare-package",
        ValidatePackageInputs(prepared.output, root, SESSION),
    )
    validated = runner.invoke(session_app, list(validation.argv))
    assert validated.exit_code == 0, validated.output
    assert validation.validator(validation.output).errors == ()

    plan = _work_plan(tmp_path)
    session_plan = session_root / "work-plan.json"
    session_plan.parent.mkdir(parents=True, exist_ok=True)
    session_plan.write_bytes(plan.read_bytes())
    plan_projection = project_run(root, session_id=SESSION, target="generic")
    assert plan_projection.stage == "APPROVE", plan_projection.errors
    assignment = build_command(
        "builder-deepagents assign-subagent",
        AssignSubagentInputs("generic", "Plan Set 4 primary path", "repo_mapper", session_plan, root, SESSION),
    )
    assigned = runner.invoke(deepagents_app, list(assignment.argv))
    assert assigned.exit_code == 0, assigned.output
    assert assignment.validator(assignment.output).errors == ()

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    verification = session_root / "verification-receipt.json"
    write_executed_verification_receipt(verification, repo, target_profile="generic")

    proposal_path = session_root / "proposal.json"
    source_proposal = _proposal(tmp_path)
    proposal_data = json.loads(source_proposal.read_text(encoding="utf-8"))
    proposal_data["verification_receipt_file_sha256"] = hashlib.sha256(verification.read_bytes()).hexdigest()
    _write(proposal_path, proposal_data)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    pending = project_run(root, session_id=SESSION, target="generic")
    assert pending.approvals == "PENDING" and pending.stage == "APPROVE"
    approval = build_command("builder-hitl approve-patch", HitlPatchInputs(proposal_path, root, SESSION))
    approved = runner.invoke(hitl_app, list(approval.argv), input=proposal["patch_digest"][:4] + "\n")
    assert approved.exit_code == 0, approved.output
    assert approval.validator(approval.output).errors == ()
    _write(
        session_root / "unrelated-execution.json",
        {
            "kind": "builder_ii.governed_run_receipt",
            "status": "succeeded",
            "successful": True,
            "session_id": SESSION,
            "task": "unrelated governed run",
        },
    )
    bare_apply = create_patch_apply_receipt(
        target_name="generic",
        generic_repo=tmp_path,
        proposal_digest="a" * 64,
        pre_apply_head="b" * 40,
    )
    bare_apply["status"] = "succeeded"
    bare_apply["successful"] = True
    _write(session_root / "bare-apply-receipt.json", bare_apply)
    projected = project_run(root, session_id=SESSION, target="generic")
    assert projected.stage == "EXECUTE", projected.errors
    assert projected.next_action == "execute only through existing governed authority"

    projected = project_run(root, session_id=SESSION, target="generic")
    assert projected.stage == "EXECUTE", projected.errors
    assert projected.next_action == "execute only through existing governed authority"

    handoff = create_handoff_artifact(
        target="generic",
        agent_profile="repo_mapper",
        task="Plan Set 4 primary path",
        summary="Verified evidence reaches the existing delivery boundary.",
    )
    _write(session_root / "handoff.json", handoff)
    projected = project_run(root, session_id=SESSION, target="generic")
    assert projected.delivery == "PENDING"
    assert any(item.path == prepared.output / "prepare-package.json" for item in projected.evidence)

    # A generic handoff and synthetic promotion event are deliberately not
    # delivery evidence. Plan Set 3D's MCP delivery services own that boundary.
    assert project_run(root, session_id=SESSION, target="generic").delivery == "PENDING"


def test_canonical_refusal_projects_denied_without_authority(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    _prepare(root)
    session_root = root / "stratum" / "sessions" / SESSION
    plan = _work_plan(tmp_path)
    session_plan = session_root / "work-plan.json"
    session_plan.parent.mkdir(parents=True, exist_ok=True)
    session_plan.write_bytes(plan.read_bytes())
    proposal_path = session_root / "proposal.json"
    proposal_path.write_bytes(_proposal(tmp_path).read_bytes())
    refusal = build_command("builder-hitl refuse-patch", HitlPatchInputs(proposal_path, root, SESSION))
    refused = runner.invoke(hitl_app, list(refusal.argv), input="canonical refusal rationale\n")
    assert refused.exit_code == 0, refused.output
    assert refusal.validator(refusal.output).errors == ()
    projected = project_run(root, session_id=SESSION, target="generic")
    assert projected.approvals == "DENIED", projected.errors
    assert projected.stage == "APPROVE"
    assert projected.next_action == "revise or retire refused proposal"


def test_corrupt_and_foreign_session_evidence_blocks_progress(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    _prepare(root)
    bad = root / "stratum" / "sessions" / SESSION / "bad-event.json"
    _write(bad, {"kind": "builder_ii.event_record", "session_id": "foreign"})
    projection = project_run(root, session_id=SESSION, target="generic")
    assert projection.evidence_health == "CORRUPT"
    assert projection.next_action.startswith("BLOCKED")


def test_valid_failed_execution_evidence_is_distinct_from_corruption(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    _prepare(root)
    session_root = root / "stratum" / "sessions" / SESSION
    failure = create_patch_apply_receipt(target_name="generic", generic_repo=tmp_path)
    failure["status"] = "failed"
    failure["error_summary"] = "governed executor refused before mutation"
    _write(session_root / "failed-execution.json", failure)
    projection = project_run(root, session_id=SESSION, target="generic")
    assert projection.evidence_health == "FAILED", projection.errors
    assert projection.verification == "FAILED"


def test_presets_are_persistable_bounded_configuration_only(tmp_path: Path) -> None:
    assert set(PRESETS) == {"solo-fast", "solo-strict", "team"}
    fast = preset_artifact("solo-fast", root=tmp_path, model_backend="mlx-lm", model_alias="qwen-coder")
    strict = preset_artifact("solo-strict", root=tmp_path, model_backend="mlx-lm", model_alias="qwen-coder")
    team = preset_artifact("team", root=tmp_path, model_backend="mlx-lm", model_alias="qwen-coder", budget_usd=10)
    for preset in (fast, strict, team):
        assert validate_preset_artifact(preset) == []
        assert 1 <= preset["worker_concurrency"] <= 2
        assert preset["grants_authority"] is preset["promotes"] is preset["enables_forbidden_tools"] is False
    assert strict["standing_grant_suggestions"] == []
    assert team["budget_usd"] == 10


def test_team_requires_explicit_model_and_budget(tmp_path: Path) -> None:
    for kwargs in ({}, {"model_backend": "mlx-lm", "model_alias": "qwen-coder"}):
        try:
            preset_artifact("team", root=tmp_path, **kwargs)
        except ValueError as exc:
            assert "team preset requires" in str(exc)
        else:
            raise AssertionError("team preset admitted implicit model or budget")


def test_readiness_inventory_has_independent_truth() -> None:
    values = [
        Readiness("goose-compatibility", "ready", "ok", "none"),
        Readiness("native-deepagents", "failed", "bad", "repair"),
        Readiness("selected-model-backend", "unavailable", "missing", "start separately"),
        Readiness("github-cli", "ready", "ok", "none"),
        Readiness("repository-identity", "failed", "foreign", "configure origin"),
    ]
    assert validate_readiness_evidence([item.as_dict() for item in values]) == []


def test_each_readiness_detector_reports_independent_truth(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("builder_ii.lifecycle.setup.readiness.shutil.which", lambda _name: None)
    assert check_gh().status == "unavailable"

    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_compatibility.probe_goose",
        lambda **_kwargs: SimpleNamespace(version="1.45.0", policy=">=1.45.0,<1.47.0"),
    )
    assert check_goose(state_root=tmp_path / "goose").status == "ready"

    monkeypatch.setattr(
        "builder_ii.adapters.deepagents.deepagents_bridge.deepagents_availability",
        lambda: SimpleNamespace(
            available=False,
            create_deep_agent_present=False,
            import_status="MISS",
            detail="deepagents absent",
        ),
    )
    assert check_deepagents().status == "unavailable"

    monkeypatch.setattr("builder_ii.routing.backends.ensure_backend_supports_model", lambda _settings: (True, "ok"))
    monkeypatch.setattr("builder_ii.routing.backends.check_health", lambda _settings, timeout: (False, "offline"))
    assert check_model_backend(model_backend="mlx-lm", model_alias="qwen-coder").status == "unavailable"

    monkeypatch.setattr(
        "builder_ii.core.repository_identity.check_repository_identity",
        lambda **_kwargs: SimpleNamespace(
            matches=False,
            configured_url="foreign",
            canonical_repository="canonical",
            error="mismatch",
        ),
    )
    assert check_repository(repository_path=tmp_path).status == "unavailable"


def test_builder_init_persists_preset_and_five_readiness_results(monkeypatch, tmp_path: Path) -> None:
    readiness = (
        Readiness("goose-compatibility", "ready", "ok", "none"),
        Readiness("native-deepagents", "ready", "ok", "none"),
        Readiness("selected-model-backend", "ready", "ok", "none"),
        Readiness("github-cli", "ready", "ok", "none"),
        Readiness("repository-identity", "ready", "ok", "none"),
    )
    monkeypatch.setattr("builder_ii.lifecycle.setup.readiness.passive_readiness", lambda **_kwargs: readiness)
    output = tmp_path / "onboarding"
    result = runner.invoke(
        builder_app,
        [
            "init",
            "--root",
            str(tmp_path),
            "--output-dir",
            str(output),
            "--non-interactive",
            "--target-profile",
            "generic",
            "--model-backend",
            "mlx-lm",
            "--model-alias",
            "qwen-coder",
            "--preset",
            "solo-fast",
        ],
    )
    assert result.exit_code == 0, result.output
    intent = json.loads((output / "onboarding-intent.json").read_text(encoding="utf-8"))
    assert intent["preset_configuration"]["name"] == "solo-fast"
    assert intent["selected_summary"]["worker_concurrency"] == 2
    assert len(intent["readiness_evidence"]) == 5
    assert intent["disabled_authority"]["patch_authority"] == "disabled"


def test_stale_command_object_can_be_detected_without_spawn(tmp_path: Path) -> None:
    command = _prepare(tmp_path)
    stale = replace(command, output=command.output)
    assert stale.creates_output and stale.output.exists()
    observation = StratumApp(show_splash=False, skip_guide=True).invoke_stratum_command(stale)
    assert not observation.successful
    assert "stale output substitution refused" in observation.validation_errors[0]
    assert canonical_digest(json.loads((stale.output / "prepare-package.json").read_text(encoding="utf-8")))


def test_authority_denial_prevents_subprocess(monkeypatch, tmp_path: Path) -> None:
    app = StratumApp(show_splash=False, skip_guide=True)
    command = build_command(
        "builder-session prepare-package",
        PreparePackageInputs("generic", "denied", tmp_path, SESSION),
    )
    monkeypatch.setattr(
        "builder_ii.tui.stratum_commands.check_command_authority",
        lambda _name: SimpleNamespace(allowed=False, reasons=("test denial",)),
    )
    monkeypatch.setattr(app, "_run_governed_subprocess_observed", lambda _argv: (_ for _ in ()).throw(AssertionError("spawned")))
    observation = app.invoke_stratum_command(command)
    assert observation.returncode is None
    assert "authority denied" in observation.validation_errors[0]


def test_nonzero_and_interrupts_never_fabricate_success(monkeypatch, tmp_path: Path) -> None:
    app = StratumApp(show_splash=False, skip_guide=True)
    command = build_command(
        "builder-session prepare-package",
        PreparePackageInputs("generic", "failure", tmp_path, SESSION),
    )
    monkeypatch.setattr(app, "_run_governed_subprocess_observed", lambda _argv: (7, "bounded failure detail"))
    observation = app.invoke_stratum_command(command)
    assert observation.returncode == 7 and not observation.successful
    assert observation.stderr == "bounded failure detail"

    for exception in (KeyboardInterrupt(), EOFError()):
        next_command = build_command(
            "builder-session prepare-package",
            PreparePackageInputs("generic", "cancel", tmp_path, SESSION),
        )

        def cancelled(_argv, exc=exception):
            raise exc

        monkeypatch.setattr(app, "_run_governed_subprocess_observed", cancelled)
        cancelled_observation = app.invoke_stratum_command(next_command)
        assert cancelled_observation.cancelled and not cancelled_observation.successful
