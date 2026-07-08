"""Interactive digest-prefix approvals for `builder-setup apply`/`rollback` (plan item 2.2).

When --approve-digest is omitted, apply/rollback print the governing digest and require
the operator to type its first 4 characters back — the same confirmation grammar as the
HITL patch approvals (plan item 1.1). A wrong prefix refuses with no writes and no
receipt. Receipts record which approval path was used in `approval_mode`
(`interactive_digest_prefix_confirmation` vs `explicit_digest_bound_cli_flag`).
"""

from __future__ import annotations

import json
from pathlib import Path

from builder_ii.setup_cli import setup_app
from test_setup_apply import _artifacts, _write
from typer.testing import CliRunner

runner = CliRunner()


def _apply_scripted(tmp_path: Path, op: Path, sp: Path, overlay: dict) -> Path:
    receipt_path = tmp_path / "receipt.json"
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
            str(receipt_path),
        ],
    )
    assert result.exit_code == 0, result.output
    return receipt_path


def test_interactive_apply_correct_prefix_applies_and_records_mode(tmp_path: Path):
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = tmp_path / "receipt.json"
    prefix = overlay["overlay_plan_digest"][:4]
    result = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(receipt_path)],
        input=prefix + "\n",
    )
    assert result.exit_code == 0, result.output
    assert overlay["overlay_plan_digest"] in result.output, "full digest must be rendered for operator review"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["approval_mode"] == "interactive_digest_prefix_confirmation"
    assert receipt["approval_digest"] == overlay["overlay_plan_digest"]
    assert receipt["operation_result"] == "applied"
    assert (tmp_path / "artifacts" / "setup" / "created.txt").exists()


def test_interactive_apply_wrong_prefix_refuses_without_writes(tmp_path: Path):
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = tmp_path / "receipt.json"
    result = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(receipt_path)],
        input="zzzz\n",
    )
    assert result.exit_code == 1
    assert "Prefix did not match" in result.output
    assert not receipt_path.exists(), "refused approval must not write a receipt"
    assert not (tmp_path / "artifacts" / "setup" / "created.txt").exists(), "refused approval must not mutate"


def test_interactive_apply_no_input_refuses_without_writes(tmp_path: Path):
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = tmp_path / "receipt.json"
    result = runner.invoke(
        setup_app,
        ["apply", str(op), "--rollback-snapshot", str(sp), "--output", str(receipt_path)],
    )
    assert result.exit_code != 0
    assert not receipt_path.exists()
    assert not (tmp_path / "artifacts" / "setup" / "created.txt").exists()


def test_scripted_apply_records_explicit_flag_mode(tmp_path: Path):
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = _apply_scripted(tmp_path, op, sp, overlay)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["approval_mode"] == "explicit_digest_bound_cli_flag"


def test_interactive_rollback_correct_prefix_rolls_back_and_records_mode(tmp_path: Path):
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = _apply_scripted(tmp_path, op, sp, overlay)
    created = tmp_path / "artifacts" / "setup" / "created.txt"
    assert created.exists()

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rollback_receipt_path = tmp_path / "rollback-receipt.json"
    result = runner.invoke(
        setup_app,
        ["rollback", str(receipt_path), "--rollback-snapshot", str(sp), "--output", str(rollback_receipt_path)],
        input=receipt["receipt_digest"][:4] + "\n",
    )
    assert result.exit_code == 0, result.output
    assert receipt["receipt_digest"] in result.output, "full receipt digest must be rendered for operator review"
    assert not created.exists(), "rollback must delete the future-created path"
    rollback_receipt = json.loads(rollback_receipt_path.read_text(encoding="utf-8"))
    assert rollback_receipt["approval_mode"] == "interactive_digest_prefix_confirmation"
    assert rollback_receipt["rollback_result"] == "rolled_back"


def test_interactive_rollback_wrong_prefix_refuses_without_writes(tmp_path: Path):
    overlay, snap = _artifacts(tmp_path)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = _apply_scripted(tmp_path, op, sp, overlay)
    created = tmp_path / "artifacts" / "setup" / "created.txt"

    rollback_receipt_path = tmp_path / "rollback-receipt.json"
    result = runner.invoke(
        setup_app,
        ["rollback", str(receipt_path), "--rollback-snapshot", str(sp), "--output", str(rollback_receipt_path)],
        input="zzzz\n",
    )
    assert result.exit_code == 1
    assert "Prefix did not match" in result.output
    assert not rollback_receipt_path.exists(), "refused approval must not write a rollback receipt"
    assert created.exists(), "refused approval must not roll anything back"
