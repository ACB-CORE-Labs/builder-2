"""Pins for `builder chain` -- the governed patch-loop walkthrough.

This file is new because the old `tests/test_chain_cli.py` tested `chain_summary_cli`, a different
module (it is now `tests/test_chain_summary_cli.py`). `chain_cli` itself had no coverage at all,
which is how it shipped in a state where it could not run: it enforced `builder chain` while no
record declared that name, so every invocation ended in an unhandled traceback.

The regression tests here pin the four defects the rewrite removed:

1. it must actually run (authority record exists),
2. it must run nothing (no subprocess),
3. it must not claim success it did not verify,
4. it must not transcribe its commands' options, which were wrong and unverifiable.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.chain_cli import CHAIN_STAGES, chain_app
from builder_ii.governance.authority import get_command_record
from builder_ii.governance.ratification_points import get_ratification_point

runner = CliRunner()


def _source() -> str:
    return (Path(__file__).resolve().parent.parent / "builder_ii" / "cli" / "chain_cli.py").read_text(
        encoding="utf-8"
    )


def test_the_walkthrough_runs_at_all() -> None:
    """The regression. `builder chain` enforces its own name and previously had no record."""
    assert get_command_record("builder chain") is not None
    result = runner.invoke(chain_app, [])
    assert result.exit_code == 0, result.output


def test_every_stage_is_rendered_in_order() -> None:
    result = runner.invoke(chain_app, [])
    positions = [result.output.index(f"{stage.number}. {stage.title}") for stage in CHAIN_STAGES]
    assert positions == sorted(positions), "stages must render in loop order"


def test_each_stage_names_its_command_and_its_live_authority() -> None:
    result = runner.invoke(chain_app, [])
    for stage in CHAIN_STAGES:
        assert stage.command in result.output
        record = get_command_record(stage.command)
        if record is not None:
            assert record.promotion_state in result.output
        else:
            assert "NO REGISTERED RECORD" in result.output


def test_an_unregistered_stage_command_is_reported_not_hidden() -> None:
    """Silence is what let `builder chain` itself stay unrunnable; absence must be visible."""
    unregistered = [stage for stage in CHAIN_STAGES if get_command_record(stage.command) is None]
    result = runner.invoke(chain_app, [])
    if unregistered:
        assert "NO REGISTERED RECORD" in result.output


def test_the_approve_stage_shows_its_non_delegable_ratification_point() -> None:
    stage = next(stage for stage in CHAIN_STAGES if stage.ratification_point)
    point = get_ratification_point(str(stage.ratification_point))
    assert point is not None
    result = runner.invoke(chain_app, [])
    assert point.id in result.output
    assert "can never be delegated" in result.output


def test_the_task_option_is_echoed_and_optional() -> None:
    assert runner.invoke(chain_app, []).exit_code == 0, "task must not be required"
    assert "fix the parser" in runner.invoke(chain_app, ["--task", "fix the parser"]).output


def test_it_never_claims_success_it_did_not_verify() -> None:
    """The old module printed 'completed successfully!' after swallowing every failure."""
    output = runner.invoke(chain_app, []).output.lower()
    assert "completed successfully" not in output
    assert "runs nothing" in output


def test_it_spawns_no_subprocess() -> None:
    """The rewrite removed a `subprocess.run` path that reached `builder-hitl apply-patch`."""
    tree = ast.parse(_source())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    # Checked against imports rather than raw text: the module docstring names `subprocess` when
    # describing the path that was removed, and a substring check would fail on the explanation.
    assert "subprocess" not in imported
    assert "os" not in imported


def test_no_stage_transcribes_its_commands_options() -> None:
    """The invariant: a stage names its command, never its flags.

    The old module hardcoded `--from-last` on `builder-hitl propose-patch`, which has no such
    option and requires four others. Transcribed flags are wrong silently; a `--help` pointer
    cannot be.
    """
    result = runner.invoke(chain_app, [])
    # Matches an actual flag token (`--diff-file`), not a prose dash.
    flag = re.compile(r"--[a-z][a-z0-9-]+")
    for line in result.output.splitlines():
        if "--help" in line:
            continue
        found = flag.findall(line)
        assert not found, f"stage output transcribes option(s) {found}: {line!r}"


def test_the_stage_table_has_no_duplicate_numbers_or_commands() -> None:
    numbers = [stage.number for stage in CHAIN_STAGES]
    assert numbers == sorted(set(numbers))
    assert len({stage.command for stage in CHAIN_STAGES}) == len(CHAIN_STAGES)
