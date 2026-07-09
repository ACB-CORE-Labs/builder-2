"""Ladder 4 PR-3: builder-orchestration obligation / lane-policy CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.orchestration_cli import orchestration_app
from builder_ii.orchestration_lane_policy import validate_orchestration_lane_policy_artifact
from builder_ii.orchestration_obligation import validate_orchestration_obligation

runner = CliRunner()

_SEAL = "a" * 64
_SHA = "c" * 64


def _write_lane_policy(tmp_path: Path) -> Path:
    out = tmp_path / "lane-policy.json"
    result = runner.invoke(orchestration_app, ["lane-policy", "--output", str(out)])
    assert result.exit_code == 0, result.output
    return out


def _mint_args(policy: Path, **overrides: str) -> list[str]:
    args = {
        "--obligation-kind": "planning_step",
        "--task": "draft the plan",
        "--expected-kind": "builder_ii.deepagents_execution_receipt",
        "--subagent-profile": "planner",
        "--lane-policy": str(policy),
        "--seal-digest": _SEAL,
    }
    args.update(overrides)
    flat: list[str] = ["mint-obligation"]
    for key, value in args.items():
        flat.extend([key, value])
    return flat


def test_lane_policy_roundtrip_and_validate(tmp_path: Path) -> None:
    out = _write_lane_policy(tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.orchestration_lane_policy"
    assert validate_orchestration_lane_policy_artifact(data) == []

    valid = runner.invoke(orchestration_app, ["validate-lane-policy", str(out)])
    assert valid.exit_code == 0, valid.output


def test_mint_obligation_derives_lane_and_validates(tmp_path: Path) -> None:
    policy = _write_lane_policy(tmp_path)
    out = tmp_path / "obligation.json"
    result = runner.invoke(
        orchestration_app,
        _mint_args(
            policy,
            **{
                "--required-evidence": "builder_ii.verification_execution_receipt",
                "--file-ref": f"builder_ii/x.py={_SHA}",
                "--max-output-bytes": "4096",
                "--briefing-bytes": "64",
                "--output": str(out),
            },
        ),
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.orchestration_obligation"
    assert data["lane"] == "deepagents"  # derived from the policy for planning_step
    assert data["lane_policy_digest"] == json.loads(policy.read_text(encoding="utf-8"))["lane_policy_digest"]
    assert validate_orchestration_obligation(data) == []

    valid = runner.invoke(orchestration_app, ["validate-obligation", str(out)])
    assert valid.exit_code == 0, valid.output


def test_mint_obligation_rejects_lane_collision(tmp_path: Path) -> None:
    policy = _write_lane_policy(tmp_path)
    # interactive_ops belongs to lane "goose"; forcing "deepagents" is a policy collision.
    result = runner.invoke(
        orchestration_app,
        _mint_args(policy, **{"--obligation-kind": "interactive_ops", "--lane": "deepagents"}),
    )
    assert result.exit_code == 1
    assert "collision" in result.output


def test_mint_obligation_requires_exactly_one_parent(tmp_path: Path) -> None:
    policy = _write_lane_policy(tmp_path)
    both = runner.invoke(
        orchestration_app,
        _mint_args(policy, **{"--parent-obligation-digest": "b" * 64}),
    )
    assert both.exit_code == 1
    assert "mutually exclusive" in both.output

    neither = runner.invoke(
        orchestration_app,
        [
            "mint-obligation",
            "--obligation-kind", "planning_step",
            "--task", "t",
            "--expected-kind", "k",
            "--subagent-profile", "p",
            "--lane-policy", str(policy),
        ],
    )
    assert neither.exit_code == 1
    assert "exactly one" in neither.output


def test_validate_obligation_detects_tamper(tmp_path: Path) -> None:
    policy = _write_lane_policy(tmp_path)
    out = tmp_path / "obligation.json"
    minted = runner.invoke(orchestration_app, _mint_args(policy, **{"--output": str(out)}))
    assert minted.exit_code == 0, minted.output

    data = json.loads(out.read_text(encoding="utf-8"))
    data["task"] = "a different task entirely"  # obligation_id no longer matches
    out.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(orchestration_app, ["validate-obligation", str(out)])
    assert result.exit_code == 1
    assert "canonical digest" in result.output


def test_mint_obligation_rejects_malformed_file_ref(tmp_path: Path) -> None:
    policy = _write_lane_policy(tmp_path)
    result = runner.invoke(orchestration_app, _mint_args(policy, **{"--file-ref": "no-equals-sign"}))
    assert result.exit_code == 1
    assert "path=sha256" in result.output


def test_mint_obligation_rejects_briefing_over_output_budget(tmp_path: Path) -> None:
    policy = _write_lane_policy(tmp_path)
    result = runner.invoke(
        orchestration_app,
        _mint_args(policy, **{"--briefing-bytes": "5000", "--max-output-bytes": "1000"}),
    )
    assert result.exit_code == 1
    assert "briefing_bytes" in result.output
