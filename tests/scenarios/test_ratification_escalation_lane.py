"""End-to-end: policy escalation actually changes what `builder-setup apply` will accept.

#199 proved a grant can *relax* a confirmation. This proves the other direction is real: at
``always_prompt`` a grant stops working, and at ``require_approval_artifact`` even a typed
confirmation stops working. Both are driven through the shipped CLIs, because the wiring -- not the
library -- is what decides whether a command refuses.

The sharpest test in this file is
:func:`test_approve_digest_cannot_bypass_an_escalated_policy`. ``--approve-digest`` exists for
scripted flows, and a script can compute a digest; if the policy gate only covered the interactive
path, every level above 0 would be bypassable by passing the flag, and the whole escalation feature
would be decorative.
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
    EVENT_APPROVAL_ACCEPTED,
    read_ratification_events,
    validate_ratification_ledger,
)
from builder_ii.governance.ratification_approvals import build_ratification_approval, write_ratification_approval
from builder_ii.governance.ratification_grants import (
    APPROVAL_MODE_RATIFICATION_APPROVAL,
    APPROVAL_MODE_STANDING_GRANT,
    RATIFICATION_ROOT_ENV,
)
from builder_ii.governance.ratification_points import get_ratification_point
from builder_ii.governance.ratification_policy import (
    LEVEL_ALWAYS_PROMPT,
    LEVEL_REQUIRE_APPROVAL_ARTIFACT,
    build_ratification_policy,
    write_policy,
)

runner = CliRunner()

POINT_ID = "setup.apply.overlay_digest"


@pytest.fixture()
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "ratification"
    root.mkdir(parents=True)
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(root))
    return root


def _run_dir(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _grant(store: Path) -> str:
    result = runner.invoke(govern_app, ["grant-auto", POINT_ID, "--granted-by", "op", "--yes"])
    assert result.exit_code == 0, result.output
    path = next(iter((store / "grants").glob("*.json")))
    return str(json.loads(path.read_text(encoding="utf-8"))["grant_digest"])


def _apply(run_dir: Path, *, stdin: str | None = None, extra: list[str] | None = None):
    overlay, snap = _artifacts(run_dir)
    op, sp = _write(run_dir, overlay, snap)
    receipt = run_dir / "receipt.json"
    args = ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(receipt)]
    args.extend(extra or [])
    result = runner.invoke(setup_app, args, input=stdin)
    return result, overlay, receipt


def test_escalating_to_always_prompt_disarms_a_live_grant(tmp_path: Path, store: Path) -> None:
    """The grant is untouched and still valid; policy simply outranks it."""
    _grant(store)
    result, overlay, receipt = _apply(_run_dir(tmp_path, "granted"), stdin=None)
    assert result.exit_code == 0, result.output
    assert json.loads(receipt.read_text(encoding="utf-8"))["approval_mode"] == APPROVAL_MODE_STANDING_GRANT

    write_policy(build_ratification_policy({POINT_ID: LEVEL_ALWAYS_PROMPT}, set_by="op"), root=store)

    # No stdin: with the grant disarmed there is nothing to satisfy the prompt, so this must fail.
    denied, _overlay, _receipt = _apply(_run_dir(tmp_path, "denied"), stdin=None)
    assert denied.exit_code != 0
    assert "Auto-accepted" not in denied.output

    # Typing still works. Each run dir gets its own overlay, so type *this* run's prefix.
    typed_dir = _run_dir(tmp_path, "typed")
    typed_overlay, typed_snap = _artifacts(typed_dir)
    op, sp = _write(typed_dir, typed_overlay, typed_snap)
    typed_receipt = typed_dir / "receipt.json"
    typed = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(typed_receipt)],
        input=typed_overlay["overlay_plan_digest"][:4] + "\n",
    )
    assert typed.exit_code == 0, typed.output
    payload = json.loads(typed_receipt.read_text(encoding="utf-8"))
    assert payload["approval_mode"] == "interactive_digest_prefix_confirmation"
    assert payload["approval_grant_digest"] is None, "a typed confirmation is never attributed to a grant"

    # And the grant itself was never revoked -- policy outranked it, rather than destroying it.
    assert len(list((store / "grants").glob("*.json"))) == 1
    assert not (store / "revocations").exists()


def test_approve_digest_cannot_bypass_an_escalated_policy(tmp_path: Path, store: Path) -> None:
    """A script can compute a digest, so the flag must be refused above level 0."""
    write_policy(build_ratification_policy({POINT_ID: LEVEL_ALWAYS_PROMPT}, set_by="op"), root=store)

    run_dir = _run_dir(tmp_path, "scripted")
    overlay, snap = _artifacts(run_dir)
    op, sp = _write(run_dir, overlay, snap)
    result = runner.invoke(
        setup_app,
        [
            "apply",
            str(op),
            "--rollback-snapshot",
            str(sp),
            "--approve-digest",
            overlay["overlay_plan_digest"],
            "--output",
            str(run_dir / "receipt.json"),
        ],
    )
    assert result.exit_code != 0, result.output
    assert "--approve-digest is not accepted" in result.output
    assert not (run_dir / "receipt.json").exists(), "a refused apply must write no receipt"


def test_require_approval_artifact_refuses_a_typed_confirmation(tmp_path: Path, store: Path) -> None:
    write_policy(build_ratification_policy({POINT_ID: LEVEL_REQUIRE_APPROVAL_ARTIFACT}, set_by="op"), root=store)
    run_dir = _run_dir(tmp_path, "typed-refused")
    overlay, snap = _artifacts(run_dir)
    op, sp = _write(run_dir, overlay, snap)
    result = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(run_dir / "receipt.json")],
        input=overlay["overlay_plan_digest"][:4] + "\n",
    )
    assert result.exit_code != 0
    assert "none was supplied" in result.output
    assert "builder-govern approve" in result.output, "the refusal must say how to comply"


def test_a_bound_approval_satisfies_level_two_and_the_receipt_names_it(tmp_path: Path, store: Path) -> None:
    write_policy(build_ratification_policy({POINT_ID: LEVEL_REQUIRE_APPROVAL_ARTIFACT}, set_by="op"), root=store)
    run_dir = _run_dir(tmp_path, "approved")
    overlay, snap = _artifacts(run_dir)
    op, sp = _write(run_dir, overlay, snap)

    point = get_ratification_point(POINT_ID)
    assert point is not None
    approval = build_ratification_approval(
        point,
        subject_digest=overlay["overlay_plan_digest"],
        approved_by="approver@example",
        confirmed_digest_prefix=overlay["overlay_plan_digest"][:4],
    )
    approval_path = write_ratification_approval(approval, run_dir / "approval.json")

    result = runner.invoke(
        setup_app,
        [
            "apply",
            str(op),
            "--rollback-snapshot",
            str(sp),
            "--approval-ref",
            str(approval_path),
            "--output",
            str(run_dir / "receipt.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["approval_mode"] == APPROVAL_MODE_RATIFICATION_APPROVAL
    assert receipt["approval_ref_digest"] == approval["approval_digest"]
    assert receipt["approval_grant_digest"] is None

    events = read_ratification_events(store)
    assert events[-1]["event"] == EVENT_APPROVAL_ACCEPTED
    assert validate_ratification_ledger(store) == []


def test_an_approval_for_a_different_overlay_is_refused(tmp_path: Path, store: Path) -> None:
    """The subject binding, proven through the CLI rather than the library."""
    write_policy(build_ratification_policy({POINT_ID: LEVEL_REQUIRE_APPROVAL_ARTIFACT}, set_by="op"), root=store)
    point = get_ratification_point(POINT_ID)
    assert point is not None

    other = _run_dir(tmp_path, "other")
    other_overlay, _snap = _artifacts(other)
    approval = build_ratification_approval(
        point,
        subject_digest=other_overlay["overlay_plan_digest"],
        approved_by="approver@example",
        confirmed_digest_prefix=other_overlay["overlay_plan_digest"][:4],
    )
    approval_path = write_ratification_approval(approval, other / "approval.json")

    run_dir = _run_dir(tmp_path, "target")
    overlay, snap = _artifacts(run_dir)
    op, sp = _write(run_dir, overlay, snap)
    result = runner.invoke(
        setup_app,
        [
            "apply",
            str(op),
            "--rollback-snapshot",
            str(sp),
            "--approval-ref",
            str(approval_path),
            "--output",
            str(run_dir / "receipt.json"),
        ],
    )
    assert result.exit_code != 0
    assert "binds subject digest" in result.output
    assert not (run_dir / "receipt.json").exists()


def test_the_receipt_names_the_grant_that_satisfied_it(tmp_path: Path, store: Path) -> None:
    """Receipt-first forensics: `standing_ratification_grant` alone never said *which* grant."""
    grant_digest = _grant(store)
    result, _overlay, receipt = _apply(_run_dir(tmp_path, "named"), stdin=None)
    assert result.exit_code == 0, result.output
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["approval_grant_digest"] == grant_digest
    assert payload["approval_ref_digest"] is None
