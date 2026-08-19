"""Plan Set 3B1 identity bindings on the canonical ``builder start`` -> Goose -> MCP path."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import builder_ii.cli.main as main_cli
from builder_ii.adapters.goose.goose_compatibility import GooseCompatibility
from builder_ii.adapters.goose.goose_receipts import create_goose_launch_receipt
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.cli.main import app


def test_governed_goose_launch_uses_one_admitted_target_profile_for_receipt_and_mcp_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "builder-platform"
    target_root = tmp_path / "target-repo"
    project_root.mkdir()
    target_root.mkdir()
    settings = SimpleNamespace(project_root=project_root)
    session = SimpleNamespace(target_name="core", agent_profile="code_reviewer")
    process = MagicMock()
    process.pid = 4242

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

    harness = GooseRuntimeHarness(settings, session, target_root)
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
    settings = SimpleNamespace(project_root=project_root)
    session = SimpleNamespace(target_name="generic", agent_profile="repo_mapper")

    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.find_goose_binary",
        lambda: "/mock/goose",
    )
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.validate_governed_recipe",
        lambda _path: "b" * 64,
    )
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.probe_goose",
        lambda *_args: GooseCompatibility("/mock/goose", "1.46.0", ">=1.45.0,<1.47.0"),
    )
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.goose_env",
        lambda *_args, **_kwargs: {},
    )
    popen = MagicMock()
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.subprocess.Popen", popen)

    harness = GooseRuntimeHarness(settings, session, target_root)
    harness.session_id = "drift-test"
    harness.admit_governed()
    session.target_name = "core"

    with pytest.raises(ValueError, match="changed after admission"):
        harness.launch_governed()
    popen.assert_not_called()


def test_primary_builder_start_passes_resolved_target_identity_into_canonical_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "builder-platform"
    target_root = tmp_path / "target-repo"
    project_root.mkdir()
    target_root.mkdir()
    session = SimpleNamespace(
        mode="orchestrator",
        model_alias="alias",
        model_tier="3",
        target_name="core",
        agent_profile="code_reviewer",
    )
    settings = SimpleNamespace(
        project_root=project_root,
        target_repo=target_root,
        model_alias="alias",
        backend="openai",
        active_model_id="model",
    )
    launch = create_goose_launch_receipt(
        "primary-identity",
        "core",
        "code_reviewer",
        42,
        "2026-01-01T00:00:00+00:00",
        {"runtime": "goose_governed"},
    )
    close = {"kind": "builder_ii.goose_close_receipt", "digest": "close"}
    postflight = {"kind": "builder_ii.no_mutation_postflight", "valid": True, "digest": "postflight"}
    seen: dict[str, object] = {}

    class FakeHarness:
        def __init__(self, actual_settings, actual_session, actual_target):
            seen["project_root"] = actual_settings.project_root
            seen["target_profile"] = actual_session.target_name
            seen["target_root"] = actual_target
            self.session_id = "primary-identity"

        def admit_governed(self):
            return GooseCompatibility("/mock/goose", "1.46.0", ">=1.45.0,<1.47.0"), "c" * 64

        def launch_governed(self):
            return launch

        def wait_for_exit(self):
            return 0

        def close(self, _digest):
            return close, postflight

    monkeypatch.setattr(main_cli, "enforce_command_authority", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("builder_ii.core.config.load_settings", lambda: settings)
    monkeypatch.setattr("builder_ii.core.config.normalize_model_alias", lambda alias, tier_fallback: alias)
    monkeypatch.setattr("builder_ii.routing.model_router.plan_session", lambda _mode, _task: session)
    monkeypatch.setattr("builder_ii.routing.model_router.explain_plan", lambda _session: "plan")
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: None)
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.GooseRuntimeHarness",
        FakeHarness,
    )

    result = CliRunner().invoke(app, ["start", "--task", "identity", "--name", "primary-identity"])

    assert result.exit_code == 0, result.output
    assert seen == {
        "project_root": project_root,
        "target_profile": "core",
        "target_root": target_root,
    }
