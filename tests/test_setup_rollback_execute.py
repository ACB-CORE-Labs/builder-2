from __future__ import annotations

import json
from pathlib import Path

from builder_ii.setup_cli import setup_app
from typer.testing import CliRunner

from builder_ii.governance.authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.lifecycle.setup.setup_rollback_receipt import validate_setup_rollback_receipt_artifact
from tests.test_setup_apply import _artifacts, _change, _write

runner = CliRunner()


def _apply(tmp_path: Path, changes: list[dict]) -> tuple[dict, dict, Path]:
    overlay, snap = _artifacts(tmp_path, changes)
    op, sp = _write(tmp_path, overlay, snap)
    receipt_path = tmp_path / "setup-receipt.json"
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
    return json.loads(receipt_path.read_text(encoding="utf-8")), snap, sp


def test_rollback_deletes_future_created_file_and_validates_receipt(tmp_path: Path) -> None:
    target = tmp_path / "artifacts" / "setup" / "created.txt"
    setup_receipt, snap, sp = _apply(tmp_path, [_change(target, content="A=created\n")])
    assert target.exists()
    setup_receipt_path = tmp_path / "setup-receipt.json"
    rollback_receipt_path = tmp_path / "rollback-receipt.json"

    result = runner.invoke(
        setup_app,
        [
            "rollback",
            str(setup_receipt_path),
            "--rollback-snapshot",
            str(sp),
            "--approve-digest",
            setup_receipt["receipt_digest"],
            "--output",
            str(rollback_receipt_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert not target.exists()
    receipt = json.loads(rollback_receipt_path.read_text(encoding="utf-8"))
    assert validate_setup_rollback_receipt_artifact(receipt) == []
    assert receipt["rollback_result"] == "rolled_back"
    assert receipt["deleted_paths"] == [str(target)]
    assert runner.invoke(setup_app, ["validate-rollback-receipt", str(rollback_receipt_path)]).exit_code == 0


def test_rollback_preflight_denial_does_not_mutate_eligible_prior_path(tmp_path: Path) -> None:
    path_a = tmp_path / "artifacts" / "setup" / "delete-me.txt"
    path_b = tmp_path / "artifacts" / "setup" / "nonempty-dir"
    setup_receipt, snap, sp = _apply(
        tmp_path, [_change(path_a, content="A=created\n"), _change(path_b, content="B=created\n")]
    )
    path_a_before = path_a.read_text(encoding="utf-8")
    if path_b.is_file():
        path_b.unlink()
    path_b.mkdir(parents=True)
    (path_b / "child.txt").write_text("keep\n", encoding="utf-8")
    rollback_receipt_path = tmp_path / "rollback-denied.json"

    result = runner.invoke(
        setup_app,
        [
            "rollback",
            str(tmp_path / "setup-receipt.json"),
            "--rollback-snapshot",
            str(sp),
            "--approve-digest",
            setup_receipt["receipt_digest"],
            "--output",
            str(rollback_receipt_path),
        ],
    )

    assert result.exit_code != 0
    receipt = json.loads(rollback_receipt_path.read_text(encoding="utf-8"))
    assert receipt["rollback_result"] == "denied"
    assert receipt["deleted_paths"] == []
    assert receipt["restored_paths"] == []
    assert str(path_b) in receipt["denied_paths"]
    assert path_a.exists()
    assert path_a.read_text(encoding="utf-8") == path_a_before
    assert path_b.is_dir()
    assert (path_b / "child.txt").read_text(encoding="utf-8") == "keep\n"


def test_denied_or_failed_apply_receipts_are_not_eligible_for_rollback(tmp_path: Path) -> None:
    path = tmp_path / "artifacts" / "setup" / "created.txt"
    setup_receipt, snap, sp = _apply(tmp_path, [_change(path)])
    setup_receipt["operation_result"] = "denied"
    bad_receipt = tmp_path / "bad-receipt.json"
    bad_receipt.write_text(json.dumps(setup_receipt), encoding="utf-8")
    out = tmp_path / "rollback.json"

    result = runner.invoke(
        setup_app,
        [
            "rollback",
            str(bad_receipt),
            "--rollback-snapshot",
            str(sp),
            "--approve-digest",
            setup_receipt["receipt_digest"],
            "--output",
            str(out),
        ],
    )

    assert result.exit_code != 0
    assert path.exists()


def test_command_authority_setup_rollback_only_no_runtime_model_tool_patch_git() -> None:
    records = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}
    rollback = records["builder-setup rollback"]
    validate = records["builder-setup validate-rollback-receipt"]
    assert rollback.allows_source_writes
    assert rollback.allows_artifact_writes
    for record in (rollback, validate):
        assert not record.allows_runtime_start
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_external_tool_invocation
        assert not record.allows_git_mutation
        assert "B2 patch rollback" in rollback.runtime_boundary
