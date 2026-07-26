"""Pins for `builder-govern`: the surface where a delegation is made, audited, and withdrawn.

Every write path here is checked for the same property in both directions: a refused command must
leave nothing behind, and an accepted one must say exactly what it wrote.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.cli.govern_cli import govern_app
from builder_ii.governance.ratification_grants import RATIFICATION_ROOT_ENV

runner = CliRunner()

GRANTABLE = "setup.apply.overlay_digest"
UNGRANTABLE = "hitl.approve_patch.patch_digest"


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "ratification"
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(root))
    return root


def test_list_points_names_both_the_delegable_and_the_undelegable(store: Path) -> None:
    result = runner.invoke(govern_app, ["list-points"])
    assert result.exit_code == 0, result.output
    assert GRANTABLE in result.output
    assert "GRANTABLE" in result.output
    assert "NOT GRANTABLE" in result.output
    assert "human_approval_mint" in result.output, "the reason a point is refused must be visible, not implied"


def test_grant_auto_refuses_an_ungrantable_point_and_writes_nothing(store: Path) -> None:
    result = runner.invoke(govern_app, ["grant-auto", UNGRANTABLE, "--granted-by", "op", "--yes"])
    assert result.exit_code == 1
    assert "cannot be delegated" in result.output
    assert not (store / "grants").exists()


def test_grant_auto_refuses_an_unregistered_point(store: Path) -> None:
    result = runner.invoke(govern_app, ["grant-auto", "nope.not.a.point", "--granted-by", "op", "--yes"])
    assert result.exit_code == 1
    assert "no ratification point is registered" in result.output
    assert not (store / "grants").exists()


def test_grant_auto_requires_the_point_id_typed_back(store: Path) -> None:
    """Delegating authority is itself an exercise of it, so the interactive path confirms."""
    wrong = runner.invoke(govern_app, ["grant-auto", GRANTABLE, "--granted-by", "op"], input="not-the-id\n")
    assert wrong.exit_code == 1
    assert "No grant was written" in wrong.output
    assert not (store / "grants").exists()

    right = runner.invoke(govern_app, ["grant-auto", GRANTABLE, "--granted-by", "op"], input=GRANTABLE + "\n")
    assert right.exit_code == 0, right.output
    assert len(list((store / "grants").glob("*.json"))) == 1


def test_grant_auto_states_the_consequence_before_asking(store: Path) -> None:
    result = runner.invoke(govern_app, ["grant-auto", GRANTABLE, "--granted-by", "op"], input="no\n")
    assert "if granted:" in result.output
    assert "revocable" in result.output


def _grant(store: Path) -> str:
    result = runner.invoke(govern_app, ["grant-auto", GRANTABLE, "--granted-by", "op", "--yes"])
    assert result.exit_code == 0, result.output
    path = next(iter((store / "grants").glob("*.json")))
    return str(json.loads(path.read_text(encoding="utf-8"))["grant_digest"])


def test_list_grants_reports_active_then_revoked(store: Path) -> None:
    digest = _grant(store)
    assert "ACTIVE" in runner.invoke(govern_app, ["list-grants"]).output

    runner.invoke(govern_app, ["revoke", digest, "--revoked-by", "op", "--reason", "done"])
    assert "REVOKED" in runner.invoke(govern_app, ["list-grants"]).output


def test_list_grants_shows_an_invalid_grant_rather_than_hiding_it(store: Path) -> None:
    """Silently filtering a corrupted grant would look identical to having none."""
    _grant(store)
    path = next(iter((store / "grants").glob("*.json")))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["granted_by"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    output = runner.invoke(govern_app, ["list-grants"]).output
    assert "IGNORED" in output
    assert "grant_digest does not match" in output


def test_revoke_refuses_an_unknown_digest(store: Path) -> None:
    _grant(store)
    result = runner.invoke(govern_app, ["revoke", "f" * 64, "--revoked-by", "op", "--reason", "x"])
    assert result.exit_code == 1
    assert "no grant on file" in result.output
    assert not (store / "revocations").exists()


def test_consult_reports_both_directions_as_json(store: Path) -> None:
    before = json.loads(runner.invoke(govern_app, ["consult", GRANTABLE]).output)
    assert before["satisfied"] is False
    assert before["because"]

    _grant(store)
    after = json.loads(runner.invoke(govern_app, ["consult", GRANTABLE]).output)
    assert after["satisfied"] is True
    assert after["granted_by"] == "op"


def test_trace_shows_the_history_and_the_current_state(store: Path) -> None:
    digest = _grant(store)
    runner.invoke(govern_app, ["revoke", digest, "--revoked-by", "op", "--reason", "done"])

    result = runner.invoke(govern_app, ["trace", GRANTABLE])
    assert result.exit_code == 0, result.output
    assert "grant_created" in result.output
    assert "grant_revoked" in result.output
    assert "prompts" in result.output, "after revocation the point must report that it asks again"


def test_trace_refuses_an_unregistered_point(store: Path) -> None:
    assert runner.invoke(govern_app, ["trace", "nope.not.a.point"]).exit_code == 1


def test_validate_ledger_passes_on_a_real_chain_and_fails_on_a_broken_one(store: Path) -> None:
    _grant(store)
    assert runner.invoke(govern_app, ["validate-ledger"]).exit_code == 0

    path = store / "ratification_ledger.jsonl"
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    entry["actor"] = "someone-else"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    broken = runner.invoke(govern_app, ["validate-ledger"])
    assert broken.exit_code == 1
    assert "entry_digest does not match" in broken.output


def test_validate_grant_checks_a_file(store: Path, tmp_path: Path) -> None:
    _grant(store)
    path = next(iter((store / "grants").glob("*.json")))
    assert runner.invoke(govern_app, ["validate-grant", str(path)]).exit_code == 0

    missing = runner.invoke(govern_app, ["validate-grant", str(tmp_path / "absent.json")])
    assert missing.exit_code == 1
    assert "unreadable" in missing.output
