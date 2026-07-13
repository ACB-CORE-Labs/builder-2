from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app

runner = CliRunner()


def test_wrp_cli_classify_and_validate(tmp_path: Path) -> None:
    out = tmp_path / "clf.json"
    result = runner.invoke(wrp_app, ["classify", "--text", "implement a validator", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    result = runner.invoke(wrp_app, ["validate", str(out)])
    assert result.exit_code == 0, result.output


def test_wrp_cli_score_classifier() -> None:
    result = runner.invoke(wrp_app, ["score-classifier"])
    assert result.exit_code == 0, result.output


def test_wrp_cli_p4_rstar_apply_lane(tmp_path: Path) -> None:
    """plan-rstar-apply → approve → apply-rstar-approved CLI surface."""
    import json

    store_path = tmp_path / "store.json"
    receipts_path = tmp_path / "receipts.json"
    corr_path = tmp_path / "corr.json"
    base_path = tmp_path / "phi0.json"
    plan_path = tmp_path / "plan.json"
    approval_path = tmp_path / "approval.json"
    policy_out = tmp_path / "phi1.json"
    receipt_path = tmp_path / "receipt.json"

    assert runner.invoke(wrp_app, ["experience-init", "-o", str(store_path)]).exit_code == 0
    assert runner.invoke(wrp_app, ["phi-policy-init", "-o", str(base_path)]).exit_code == 0
    receipts_path.write_text(
        json.dumps(
            [
                {
                    "kind": "verification",
                    "success": False,
                    "trajectory_id": "cli-fail",
                    "workload_features": {"difficulty": 0.8},
                }
            ]
        ),
        encoding="utf-8",
    )
    r = runner.invoke(
        wrp_app,
        [
            "corrections-from-receipts",
            "--store",
            str(store_path),
            "--receipts",
            str(receipts_path),
            "--store-out",
            str(tmp_path / "store2.json"),
            "-o",
            str(corr_path),
        ],
    )
    assert r.exit_code == 0, r.output
    r = runner.invoke(
        wrp_app,
        [
            "plan-rstar-apply",
            "--base-policy",
            str(base_path),
            "--corrections",
            str(corr_path),
            "--store",
            str(tmp_path / "store2.json"),
            "-o",
            str(plan_path),
        ],
    )
    assert r.exit_code == 0, r.output
    r = runner.invoke(
        wrp_app,
        ["approve-rstar-apply", "--plan", str(plan_path), "--approved-by", "cli-human", "-o", str(approval_path)],
    )
    assert r.exit_code == 0, r.output
    r = runner.invoke(
        wrp_app,
        [
            "apply-rstar-approved",
            "--plan",
            str(plan_path),
            "--approval",
            str(approval_path),
            "--policy-out",
            str(policy_out),
            "-o",
            str(receipt_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert policy_out.is_file() and receipt_path.is_file()
    assert runner.invoke(wrp_app, ["validate", str(policy_out)]).exit_code == 0
    assert runner.invoke(wrp_app, ["validate", str(receipt_path)]).exit_code == 0


def test_wrp_cli_gate_and_route(tmp_path: Path) -> None:
    result = runner.invoke(
        wrp_app,
        ["gate", "--tool", "shell", "--domain", "local_workspace", "-o", str(tmp_path / "gate.json")],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(wrp_app, ["route", "--text", "fix the digest mismatch", "-o", str(tmp_path / "r.json")])
    assert result.exit_code == 0, result.output
