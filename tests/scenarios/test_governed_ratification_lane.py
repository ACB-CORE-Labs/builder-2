"""End-to-end: a standing grant satisfies a real `builder-setup apply`, and revoking it stops.

This is the scenario the whole ratification lane exists to make true, driven through the shipped
CLI rather than through the library functions: mint a grant, watch apply stop asking, confirm the
receipt says a grant satisfied it (not that a human typed anything), revoke, and watch apply ask
again. Testing the pieces separately would leave the wiring -- the part that actually decides
whether a confirmation appears -- unproven.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from builder_ii.setup_cli import setup_app
from test_setup_apply import _artifacts, _write
from typer.testing import CliRunner

from builder_ii.cli.govern_cli import govern_app
from builder_ii.governance.ledger.ratification_ledger import (
    EVENT_AUTO_ACCEPTED,
    EVENT_GRANT_CREATED,
    EVENT_GRANT_REVOKED,
    EVENT_MANUAL_RATIFIED,
    read_ratification_events,
    validate_ratification_ledger,
)
from builder_ii.governance.ratification_grants import (
    APPROVAL_MODE_STANDING_GRANT,
    RATIFICATION_ROOT_ENV,
)

runner = CliRunner()

POINT_ID = "setup.apply.overlay_digest"


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated ratification store, so a test can never read the developer's real grants."""
    root = tmp_path / "ratification"
    root.mkdir(parents=True)
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(root))
    return root


def _grant(store: Path) -> str:
    result = runner.invoke(
        govern_app,
        ["grant-auto", POINT_ID, "--granted-by", "operator@example", "--yes"],
    )
    assert result.exit_code == 0, result.output
    grants = list((store / "grants").glob("*.json"))
    assert len(grants) == 1
    return str(json.loads(grants[0].read_text(encoding="utf-8"))["grant_digest"])


def _run_dir(tmp_path: Path, name: str) -> Path:
    """`_artifacts` mkdirs its children but not its parent, so each run needs its own dir made."""
    path = tmp_path / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _apply(tmp_path: Path, *, stdin: str | None = None) -> tuple[int, str, Path]:
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = tmp_path / "receipt.json"
    result = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(receipt_path)],
        input=stdin,
    )
    return result.exit_code, result.output, receipt_path


def test_a_standing_grant_satisfies_apply_and_the_receipt_says_so(tmp_path: Path, store: Path) -> None:
    """The receipt must never claim a human typed a prefix that a grant satisfied."""
    grant_digest = _grant(store)

    # No stdin at all: if apply still prompted, it would fail rather than silently pass.
    exit_code, output, receipt_path = _apply(_run_dir(tmp_path, "run"), stdin=None)
    assert exit_code == 0, output
    assert "Auto-accepted under standing grant" in output
    assert grant_digest[:12] in output, "the satisfying grant must be named in stdout, not silently applied"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["approval_mode"] == APPROVAL_MODE_STANDING_GRANT
    assert receipt["approval_mode"] != "interactive_digest_prefix_confirmation"


def test_revoking_the_grant_makes_apply_ask_again(tmp_path: Path, store: Path) -> None:
    """Revocation is the whole reason a grant is not a config flag: it has to actually stop."""
    grant_digest = _grant(store)
    revoked = runner.invoke(
        govern_app,
        ["revoke", grant_digest, "--revoked-by", "operator@example", "--reason", "rotating delegations"],
    )
    assert revoked.exit_code == 0, revoked.output

    # Without stdin the prompt now has nothing to read, so a still-granted apply would succeed here.
    exit_code, output, _receipt = _apply(_run_dir(tmp_path, "denied"), stdin=None)
    assert exit_code != 0, output
    assert "Auto-accepted" not in output

    overlay, snap = _artifacts(_run_dir(tmp_path, "typed"))
    op, sp = _write(tmp_path / "typed", overlay, snap)
    receipt_path = tmp_path / "typed" / "receipt.json"
    typed = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(receipt_path)],
        input=overlay["overlay_plan_digest"][:4] + "\n",
    )
    assert typed.exit_code == 0, typed.output
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["approval_mode"] == "interactive_digest_prefix_confirmation"


def test_the_ledger_records_the_whole_delegation_history_in_one_intact_chain(tmp_path: Path, store: Path) -> None:
    """Grant, auto-accept, revoke, manual ratify -- all four, chained and verifiable."""
    grant_digest = _grant(store)
    _apply(_run_dir(tmp_path, "auto"), stdin=None)
    runner.invoke(govern_app, ["revoke", grant_digest, "--revoked-by", "op", "--reason", "done"])

    overlay, snap = _artifacts(_run_dir(tmp_path, "manual"))
    op, sp = _write(tmp_path / "manual", overlay, snap)
    runner.invoke(
        setup_app,
        [
            "apply",
            str(op),
            "--rollback-snapshot",
            str(sp),
            "--output",
            str(tmp_path / "manual" / "receipt.json"),
        ],
        input=overlay["overlay_plan_digest"][:4] + "\n",
    )

    events = read_ratification_events(store)
    assert [event["event"] for event in events] == [
        EVENT_GRANT_CREATED,
        EVENT_AUTO_ACCEPTED,
        EVENT_GRANT_REVOKED,
        EVENT_MANUAL_RATIFIED,
    ]
    assert validate_ratification_ledger(store) == [], "the recorded chain must verify"

    auto = events[1]
    assert auto["grant_digest"] == grant_digest, "an auto-acceptance must name the grant that caused it"
    assert events[3]["grant_digest"] is None, "a typed confirmation must not be attributed to a grant"


def test_apply_writes_no_ratification_store_where_none_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply must not conjure a governance store inside every repository it touches."""
    absent = tmp_path / "absent-store"
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(absent))

    overlay, snap = _artifacts(_run_dir(tmp_path, "run"))
    op, sp = _write(tmp_path / "run", overlay, snap)
    result = runner.invoke(
        setup_app,
        [
            "apply",
            str(op),
            "--rollback-snapshot",
            str(sp),
            "--output",
            str(tmp_path / "run" / "receipt.json"),
        ],
        input=overlay["overlay_plan_digest"][:4] + "\n",
    )
    assert result.exit_code == 0, result.output
    assert not absent.exists(), "no ratification store existed, so none may be created"
