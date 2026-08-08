from __future__ import annotations

from pathlib import Path

import pytest

from builder_ii.adapters.goose.governed_invocation import (
    GovernedInvocationError,
    GooseCliCapabilities,
    plan_governed_headless_invocation,
)


FULL_HELP = """Usage: goose run [OPTIONS]
  --recipe <PATH>
  --name <NAME>
  --with-builtin <B>
  --text <TEXT>
"""


def _recipe(tmp_path: Path) -> Path:
    path = tmp_path / "governed-readonly.yaml"
    path.write_text("version: '1.0.0'\nextensions: []\n", encoding="utf-8")
    return path


def test_capability_snapshot_requires_all_authority_bearing_flags() -> None:
    caps = GooseCliCapabilities.from_run_help(FULL_HELP)
    assert caps.supports_governed_headless
    assert caps.missing_governed_headless_flags() == ()
    assert len(caps.help_sha256) == 64


@pytest.mark.parametrize(
    ("removed", "expected"),
    [
        ("--text <TEXT>\n", "--text"),
        ("--recipe <PATH>\n", "--recipe"),
        ("--with-builtin <B>\n", "--with-builtin"),
    ],
)
def test_missing_governance_flag_refuses_before_argv_exists(
    tmp_path: Path, removed: str, expected: str
) -> None:
    help_text = FULL_HELP.replace(removed, "")
    with pytest.raises(GovernedInvocationError, match=expected):
        plan_governed_headless_invocation(
            goose_binary="/fake/goose",
            recipe_path=_recipe(tmp_path),
            task="inspect the repository",
            session_id="run-1",
            help_text=help_text,
        )


def test_missing_help_refuses_instead_of_guessing(tmp_path: Path) -> None:
    with pytest.raises(GovernedInvocationError, match="refusing to guess"):
        plan_governed_headless_invocation(
            goose_binary="/fake/goose",
            recipe_path=_recipe(tmp_path),
            task="inspect",
            session_id="run-1",
            help_text="",
        )


def test_missing_recipe_refuses_instead_of_silently_dropping_interposition(tmp_path: Path) -> None:
    with pytest.raises(GovernedInvocationError, match="refusing to start without MCP interposition"):
        plan_governed_headless_invocation(
            goose_binary="/fake/goose",
            recipe_path=tmp_path / "missing.yaml",
            task="inspect",
            session_id="run-1",
            help_text=FULL_HELP,
        )


def test_empty_task_refuses(tmp_path: Path) -> None:
    with pytest.raises(GovernedInvocationError, match="non-empty task"):
        plan_governed_headless_invocation(
            goose_binary="/fake/goose",
            recipe_path=_recipe(tmp_path),
            task="   ",
            session_id="run-1",
            help_text=FULL_HELP,
        )


def test_plan_is_fixed_and_digest_bound(tmp_path: Path) -> None:
    recipe = _recipe(tmp_path)
    plan = plan_governed_headless_invocation(
        goose_binary="/fake/goose",
        recipe_path=recipe,
        task="inspect the repository",
        session_id="run-1",
        help_text=FULL_HELP,
    )

    assert plan.argv == (
        "/fake/goose",
        "run",
        "--recipe",
        str(recipe),
        "--name",
        "run-1",
        "--with-builtin",
        "",
        "--text",
        "inspect the repository",
    )
    assert len(plan.recipe_sha256) == 64
    assert len(plan.task_sha256) == 64


def test_name_is_optional_because_it_is_not_an_authority_boundary(tmp_path: Path) -> None:
    recipe = _recipe(tmp_path)
    plan = plan_governed_headless_invocation(
        goose_binary="/fake/goose",
        recipe_path=recipe,
        task="inspect",
        session_id="run-1",
        help_text=FULL_HELP.replace("  --name <NAME>\n", ""),
    )
    assert "--name" not in plan.argv
    assert plan.capabilities.supports_governed_headless
