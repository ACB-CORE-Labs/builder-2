from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.deepagents_cli import deepagents_app
from builder_ii.deepagents_forge_schema import DeepAgentSpec
from builder_ii.deepagents_forge_tui import run_forge_tui


runner = CliRunner()


def test_builder_deepagents_forge_help_is_registered() -> None:
    result = runner.invoke(deepagents_app, ["forge", "--help"])

    assert result.exit_code == 0
    assert "--non-interactive" in result.output
    assert "--dry-run" in result.output


def test_builder_deepagents_forge_dry_run_has_no_side_effects(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        deepagents_app,
        [
            "forge",
            "--non-interactive",
            "--dry-run",
            "--name",
            "Safe Agent",
            "--persona",
            "You are an agent that prepares governed test artifacts.",
            "--description",
            "A governed Forge test agent.",
            "--capabilities",
            "read_files",
            "--output-artifact",
            "artifacts/safe_agent",
            "--rollback-path",
            "rollback/safe_agent",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "[DRY-RUN]" in result.output
    assert not Path("profiles").exists()


def test_builder_deepagents_forge_invalid_spec_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        deepagents_app,
        [
            "forge",
            "--non-interactive",
            "--dry-run",
            "--name",
            "Shell Agent",
            "--persona",
            "You are an agent that would run commands.",
            "--description",
            "A governed Forge test agent.",
            "--capabilities",
            "run_shell",
            "--output-artifact",
            "artifacts/shell_agent",
            "--rollback-path",
            "rollback/shell_agent",
        ],
    )

    assert result.exit_code == 1
    assert "before_shell" in result.output
    assert not Path("profiles").exists()


def test_run_forge_tui_returns_none_when_app_aborts(monkeypatch) -> None:
    class FakeApp:
        def __init__(self, wizard, dry_run: bool = False) -> None:
            self.wizard = wizard
            self.dry_run = dry_run

        def run(self):
            self.wizard.spec = DeepAgentSpec(
                name="ready",
                slug="ready",
                description="Ready but aborted.",
                persona="You are an agent that is ready but aborted.",
                output_artifact="artifacts/ready",
                rollback_path="rollback/ready",
            )
            return None

    monkeypatch.setattr("builder_ii.deepagents_forge_tui.ForgeApp", FakeApp)

    assert run_forge_tui(seed_name="ready", dry_run=True) is None


def test_run_forge_tui_returns_app_result(monkeypatch) -> None:
    expected = DeepAgentSpec(
        name="ready",
        slug="ready",
        description="Ready and emitted.",
        persona="You are an agent that returns from the app.",
        output_artifact="artifacts/ready",
        rollback_path="rollback/ready",
    )

    class FakeApp:
        def __init__(self, wizard, dry_run: bool = False) -> None:
            self.wizard = wizard
            self.dry_run = dry_run

        def run(self):
            return expected

    monkeypatch.setattr("builder_ii.deepagents_forge_tui.ForgeApp", FakeApp)

    assert run_forge_tui(seed_name="ready", dry_run=True) is expected
