from pathlib import Path

import pytest

from builder_ii.tui.projections.run_projection import project_run
from builder_ii.tui.stratum_commands import build_command, command_inventory


def test_registry_is_closed_and_uses_real_module_entrypoints(tmp_path: Path) -> None:
    assert command_inventory() == (
        "builder-session prepare-package",
        "builder-session validate-prepare-package",
        "builder-deepagents assign-subagent",
        "builder-hitl approve-patch",
        "builder-hitl refuse-patch",
    )
    command = build_command("builder-deepagents assign-subagent", output_root=tmp_path,
                            target="builder", task="inspect", profile="builder_reviewer")
    assert command.entrypoint == "builder_ii.cli.deepagents_cli"
    assert "builder_full" not in command.argv
    assert command.output.parent.name != "current"
    with pytest.raises(ValueError, match="invalid governed agent profile"):
        build_command("builder-deepagents assign-subagent", output_root=tmp_path, profile="builder_full")


def test_registry_rejects_malformed_canonical_output(tmp_path: Path) -> None:
    command = build_command("builder-hitl refuse-patch", output_root=tmp_path)
    command.output.parent.mkdir(parents=True)
    command.output.write_text("[]", encoding="utf-8")
    assert command.validator(command.output)


def test_projection_has_exact_lifecycle_and_fail_closed_next_action(tmp_path: Path) -> None:
    projection = project_run(tmp_path, task="demo")
    assert projection.stage == "PREPARE"
    assert projection.next_action == "prepare-package"
    assert projection.evidence_health == "healthy"
