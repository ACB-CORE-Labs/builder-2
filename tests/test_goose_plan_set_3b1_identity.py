"""Plan Set 3B1 identity bindings on the canonical ``builder start`` -> Goose -> MCP path."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import builder_ii.cli.main as main_cli
from builder_ii.adapters.goose.goose_compatibility import GooseCompatibility
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.cli.main import app
from builder_ii.routing.model_router import SessionPlan


def _write_target_profile(project_root: Path, target_profile: str) -> None:
    (project_root / "builder.config.json").write_text(
        json.dumps({"active_target_profile": target_profile}) + "\n",
        encoding="utf-8",
    )


def _session() -> SessionPlan:
    # Production SessionPlan intentionally owns only model/session routing. Target repository
    # identity comes from governed config and must never be invented on this object.
    return SessionPlan(
        mode="orchestrator",
        model_tier="primary",
        model_alias="qwen-coder",
        recipe_name="core-platform.yaml",
        planner_same_as_execution=True,
        confidence="high",
        rationale="3B1 identity test",
    )


def _patch_goose_boundary(monkeypatch: pytest.MonkeyPatch, process: MagicMock) -> MagicMock:
    # Environment overrides outrank project config. Remove operator-machine target-profile
    # state so these tests exercise the intended project-config and drift paths deterministically.
    monkeypatch.delenv("BUILDER_TARGET_PROFILE", raising=False)
    monkeypatch.delenv("CORE_TARGET_PROFILE", raising=False)
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary",
        lambda: "/mock/goose",
    )
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe",
        lambda _path: "a" * 64,
    )
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.probe_goose",
        lambda *_args: GooseCompatibility("/mock/goose", "1.46.0", ">=1.45.0,<1.47.0"),
    )
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.goose_env",
        lambda *_args, **_kwargs: {},
    )
    popen = MagicMock(return_value=process)
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen", popen)
    return popen


def test_governed_goose_launch_uses_one_admitted_target_profile_for_receipt_and_mcp_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "builder-platform"
    target_root = tmp_path / "target-repo"
    project_root.mkdir()
    target_root.mkdir()
    _write_target_profile(project_root, "core")
    settings = SimpleNamespace(project_root=project_root)
    process = MagicMock()
    process.pid = 4242
    popen = _patch_goose_boundary(monkeypatch, process)

    harness = GooseRuntimeHarness(settings, _session(), target_root)
    harness.session_id = "identity-test"
    harness.admit_governed()
    receipt = harness.launch_governed()

    assert receipt["target_profile"] == "core"
    _, kwargs = popen.call_args
    assert kwargs["cwd"] == target_root
    assert kwargs["env"]["BUILDER_MCP_SESSION_ID"] == "identity-test"
    assert kwargs["env"]["BUILDER_MCP_TARGET_PROFILE"] == receipt["target_profile"]
    assert kwargs["env"]["BUILDER_MCP_PROJECT_ROOT"] == str(project_root.resolve())


def test_governed_goose_launch_refuses_target_profile_drift_after_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "builder-platform"
    target_root = tmp_path / "target-repo"
    project_root.mkdir()
    target_root.mkdir()
    _write_target_profile(project_root, "generic")
    settings = SimpleNamespace(project_root=project_root)
    process = MagicMock()
    process.pid = 4242
    popen = _patch_goose_boundary(monkeypatch, process)

    harness = GooseRuntimeHarness(settings, _session(), target_root)
    harness.session_id = "drift-test"
    harness.admit_governed()
    _write_target_profile(project_root, "core")

    with pytest.raises(ValueError, match="changed after admission"):
        harness.launch_governed()
    popen.assert_not_called()


def test_primary_builder_start_propagates_resolved_profile_to_real_governed_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "builder-platform"
    target_root = tmp_path / "target-repo"
    project_root.mkdir()
    target_root.mkdir()
    _write_target_profile(project_root, "core")
    session = _session()
    settings = SimpleNamespace(
        project_root=project_root,
        target_repo=target_root,
        model_alias="qwen-coder",
        backend="openai",
        active_model_id="model",
    )
    process = MagicMock()
    process.pid = 42
    process.wait.return_value = 0
    popen = _patch_goose_boundary(monkeypatch, process)
    close = {"kind": "builder_ii.goose_close_receipt", "digest": "close"}
    postflight = {"kind": "builder_ii.no_mutation_postflight", "valid": True, "digest": "postflight"}

    monkeypatch.setattr(main_cli, "enforce_command_authority", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("builder_ii.core.config.load_settings", lambda: settings)
    monkeypatch.setattr("builder_ii.core.config.normalize_model_alias", lambda alias, tier_fallback: alias)
    monkeypatch.setattr("builder_ii.routing.model_router.plan_session", lambda _mode, _task: session)
    monkeypatch.setattr("builder_ii.routing.model_router.explain_plan", lambda _session: "plan")
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: None)
    monkeypatch.setattr(GooseRuntimeHarness, "wait_for_exit", lambda _self: 0)
    monkeypatch.setattr(GooseRuntimeHarness, "close", lambda _self, _digest: (close, postflight))

    result = CliRunner().invoke(app, ["start", "--task", "identity", "--name", "primary-identity"])

    assert result.exit_code == 0, result.output
    _, kwargs = popen.call_args
    assert kwargs["cwd"] == target_root
    assert kwargs["env"]["BUILDER_MCP_TARGET_PROFILE"] == "core"
    assert kwargs["env"]["BUILDER_MCP_PROJECT_ROOT"] == str(project_root.resolve())
    persisted = json.loads(
        (project_root / ".builder" / "receipts" / "primary-identity_launch.json").read_text(encoding="utf-8")
    )
    assert persisted["target_profile"] == "core"
