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


def test_wrp_cli_replay_w5_null_git_and_bound(tmp_path: Path) -> None:
    import json

    plan_path = tmp_path / "plan.json"
    obs_path = tmp_path / "obs.json"
    out_path = tmp_path / "replay.json"
    r = runner.invoke(wrp_app, ["graph", "--task", "w5", "--nodes", "a,b", "-o", str(plan_path)])
    assert r.exit_code == 0, r.output
    dig_a = "a" * 64
    dig_b = "b" * 64
    obs_path.write_text(
        json.dumps([{"node_id": "a", "digest": dig_a}, {"node_id": "b", "digest": dig_b}]),
        encoding="utf-8",
    )
    # null-git agreement → perfect_match
    r = runner.invoke(
        wrp_app,
        ["replay", "--plan", str(plan_path), "--observed", str(obs_path), "-o", str(out_path)],
    )
    assert r.exit_code == 0, r.output
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["perfect_match"] is True
    assert report["repo_state_mode"] == "null_git"

    # bound match
    out2 = tmp_path / "replay2.json"
    r = runner.invoke(
        wrp_app,
        [
            "replay",
            "--plan",
            str(plan_path),
            "--observed",
            str(obs_path),
            "--planned-commit",
            "abc",
            "--planned-tree",
            "def",
            "--observed-commit",
            "abc",
            "--observed-tree",
            "def",
            "-o",
            str(out2),
        ],
    )
    assert r.exit_code == 0, r.output
    report2 = json.loads(out2.read_text(encoding="utf-8"))
    assert report2["perfect_match"] is True
    assert report2["repo_state_mode"] == "bound"

    # mismatch fails closed
    r = runner.invoke(
        wrp_app,
        [
            "replay",
            "--plan",
            str(plan_path),
            "--observed",
            str(obs_path),
            "--planned-commit",
            "abc",
            "--planned-tree",
            "def",
            "--observed-commit",
            "abc",
            "--observed-tree",
            "NOPE",
        ],
    )
    assert r.exit_code == 1, r.output


def test_wrp_cli_p6_surfaces(tmp_path: Path) -> None:
    import json

    # langgraph project (pure)
    out = tmp_path / "lg.json"
    r = runner.invoke(wrp_app, ["langgraph-project", "--nodes", "x,y", "-o", str(out)])
    assert r.exit_code == 0, r.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["backend"] == "pure_projection"
    assert data["grants_authority"] is False

    # compile without env → fail-closed
    r = runner.invoke(wrp_app, ["langgraph-project", "--nodes", "x,y", "--compile"])
    assert r.exit_code == 1, r.output

    # vllm profile
    vp = tmp_path / "vllm.json"
    r = runner.invoke(wrp_app, ["vllm-profile", "-o", str(vp)])
    assert r.exit_code == 0, r.output
    vdata = json.loads(vp.read_text(encoding="utf-8"))
    assert vdata["default_runtime"] is False
    assert vdata["engine_started"] is False

    # opa-eval python
    oe = tmp_path / "opa.json"
    r = runner.invoke(
        wrp_app,
        ["opa-eval", "--tool", "repo_map", "--domain", "local_workspace", "-o", str(oe)],
    )
    assert r.exit_code == 0, r.output
    odata = json.loads(oe.read_text(encoding="utf-8"))
    assert odata["backend"] == "python_msda"
    assert odata["effect"] == "allow"

    # opa backend absent → fail-closed
    r = runner.invoke(
        wrp_app,
        ["opa-eval", "--tool", "repo_map", "--domain", "local_workspace", "--backend", "opa"],
    )
    # may be 0 if opa installed, or 1 if not — structure: never crash without message
    assert r.exit_code in (0, 1)
    if r.exit_code == 1:
        assert "fail-closed" in r.output.lower() or "opa" in r.output.lower()

    # embed-status default hashing
    es = tmp_path / "embed.json"
    r = runner.invoke(wrp_app, ["embed-status", "-o", str(es)])
    assert r.exit_code == 0, r.output
    edata = json.loads(es.read_text(encoding="utf-8"))
    assert edata["is_default_hashing"] is True
    assert edata["backend_name"] == "hashing"

    # repo-state
    rs = tmp_path / "rs.json"
    r = runner.invoke(wrp_app, ["repo-state", "-o", str(rs)])
    assert r.exit_code == 0, r.output
    rdata = json.loads(rs.read_text(encoding="utf-8"))
    assert "commit_id" in rdata and "tree_hash" in rdata
    assert rdata["grants_authority"] is False
