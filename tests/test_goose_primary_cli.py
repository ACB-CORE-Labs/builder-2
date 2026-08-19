from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import builder_ii.cli.main as main_cli
from builder_ii.adapters.goose.goose_receipts import create_goose_launch_receipt
from builder_ii.cli.main import app
from builder_ii.governance.authority import CommandAuthorityError


def test_primary_builder_start_uses_governed_lifecycle_and_persists_receipts(
    monkeypatch, tmp_path: Path
) -> None:
    session = SimpleNamespace(mode="orchestrator", model_alias="alias", model_tier="3", target_name="builder", agent_profile="patch_planner")
    settings = SimpleNamespace(
        project_root=tmp_path,
        target_repo=tmp_path,
        model_alias="alias",
        backend="openai",
        active_model_id="model",
    )
    launch = create_goose_launch_receipt(
        "primary-test", "builder", "patch_planner", 42, "2026-01-01T00:00:00+00:00", {"runtime": "goose_governed"}
    )
    close = {"kind": "builder_ii.goose_close_receipt", "digest": "close-digest"}
    postflight = {"kind": "builder_ii.no_mutation_postflight", "valid": True, "digest": "postflight-digest"}
    calls: list[str] = []

    monkeypatch.setattr(main_cli, "enforce_command_authority", lambda *_args, **_kwargs: calls.append("authority"))

    class FakeHarness:
        def __init__(self, *_args):
            self.session_id = "primary-test"

        def admit_governed(self):
            calls.append("admit")
            return SimpleNamespace(binary="/mock/goose", version="1.46.0", policy=">=1.45.0,<1.47.0"), "r" * 64

        def launch_governed(self):
            calls.append("launch")
            return launch

        def wait_for_exit(self):
            calls.append("wait")
            return 0

        def close(self, digest):
            calls.append(f"close:{digest}")
            return close, postflight

    monkeypatch.setattr("builder_ii.core.config.load_settings", lambda: settings)
    monkeypatch.setattr("builder_ii.core.config.normalize_model_alias", lambda alias, tier_fallback: alias)
    monkeypatch.setattr("builder_ii.routing.model_router.plan_session", lambda mode, task: session)
    monkeypatch.setattr("builder_ii.routing.model_router.explain_plan", lambda session: "plan")
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: calls.append("backend"))
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.GooseRuntimeHarness", FakeHarness)

    result = CliRunner().invoke(app, ["start", "--task", "test", "--name", "primary-test"])

    assert result.exit_code == 0, result.output
    assert calls == ["authority", "admit", "backend", "launch", "wait", f"close:{launch['digest']}"]
    receipts = tmp_path / ".builder" / "receipts"
    assert json.loads((receipts / "primary-test_launch.json").read_text())["schema_version"] == 2
    assert json.loads((receipts / "primary-test_postflight.json").read_text()) == postflight


def test_primary_builder_start_denied_authority_has_no_side_effects(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def deny(*_args, **_kwargs):
        calls.append("authority")
        raise CommandAuthorityError("builder start denied")

    monkeypatch.setattr(main_cli, "enforce_command_authority", deny)
    monkeypatch.setattr(main_cli, "_ensure_backend", lambda *_args: calls.append("backend"))
    monkeypatch.setattr("builder_ii.adapters.goose.goose_runtime_harness.GooseRuntimeHarness", lambda *_args: calls.append("goose"))

    result = CliRunner().invoke(app, ["start", "--task", "test", "--name", "denied-test"])

    assert result.exit_code != 0
    assert calls == ["authority"]
    assert not (tmp_path / ".builder" / "receipts").exists()
