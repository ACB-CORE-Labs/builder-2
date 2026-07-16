#!/usr/bin/env python3
"""Capture operational-coherence hardening verification evidence per goal/plan.md."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

GATING_SUITES: tuple[tuple[str, str], ...] = (
    ("command_authority", "tests/test_command_authority.py"),
    ("platform_truth", "tests/test_platform_completion_truth.py tests/test_docs_truth_enforcement.py"),
    ("setup", "tests/test_setup_apply.py tests/test_setup_rollback_execute.py"),
    ("verification", "tests/test_verification_execution_runner.py tests/test_verification_execution_ledger.py"),
    ("hitl_patch", "tests/test_hitl_patch_proposal.py tests/test_hitl_patch_apply.py tests/test_hitl_patch_rollback.py"),
    ("model", "tests/test_model_execution_gateway.py tests/test_model_policy_cli.py"),
    ("tool_mcp", "tests/test_tool_invocation_gateway.py tests/test_mcp_policy.py tests/test_mcp_cli.py"),
    ("readonly", "tests/test_readonly_authority.py tests/test_readonly_demo.py tests/test_content_read_receipts.py"),
    ("operator_lane", "tests/test_operator_lane.py tests/test_hitl_run_command_fail_closed.py"),
)


def _run(
    cmd: list[str],
    log_path: Path,
    *,
    env: dict[str, str],
    cwd: Path,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = f"$ {' '.join(cmd)}\n"
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    body = proc.stdout or ""
    log_path.write_text(header + body + f"\nEXIT_CODE={proc.returncode}\n", encoding="utf-8")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Evidence root directory (goal SCRATCH / implementer path)",
    )
    parser.add_argument("--skip-full-suite", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("CORE_REPO_PATH", ".")
    failures: list[str] = []

    prereq = out / "prereq.log"
    prereq_lines = ["=== Verification plan step 1: prerequisites ==="]
    for gh_cmd in (
        ["gh", "issue", "view", "211", "--repo", "AssetOverflow/builder-II"],
        ["gh", "pr", "view", "212", "--repo", "AssetOverflow/builder-II"],
        ["gh", "repo", "view", "AssetOverflow/builder-II", "--json", "description,name"],
    ):
        prereq_lines.append(f"$ {' '.join(gh_cmd)}")
        proc = subprocess.run(gh_cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        prereq_lines.append(proc.stdout or "")
        if proc.returncode != 0:
            prereq_lines.append(f"EXIT_CODE={proc.returncode}")
    prereq.write_text("\n".join(prereq_lines) + "\n", encoding="utf-8")

    gating_summary: list[str] = ["=== Verification plan step 2: gating pytest suites ==="]
    tests_dir = out / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    for name, targets in GATING_SUITES:
        cmd = ["uv", "run", "pytest", "-v", *targets.split()]
        log_path = tests_dir / f"{name}.log"
        code = _run(cmd, log_path, env=env, cwd=root)
        log_text = log_path.read_text(encoding="utf-8")
        gating_summary.append(log_text.rstrip())
        if code != 0:
            failures.append(f"gating suite {name} failed (exit {code})")

    (tests_dir / "gating.log").write_text("\n".join(gating_summary) + "\n", encoding="utf-8")

    run_lines = ["=== Verification plan step 3: builder-hitl run-command ==="]
    req = out / "run-command-req.json"
    prop = out / "run-command-prop.json"
    app = out / "run-command-app.json"
    for path in (req, prop, app):
        path.write_text("{}", encoding="utf-8")
    cli_cmd = [
        "uv",
        "run",
        "builder-hitl",
        "run-command",
        "--request",
        str(req),
        "--proposal",
        str(prop),
        "--approval",
        str(app),
        "--output-dir",
        str(out / "run-command-out"),
    ]
    cli_log = out / "run-command-cli.log"
    code = _run(cli_cmd, cli_log, env=env, cwd=root)
    run_lines.append(cli_log.read_text(encoding="utf-8").rstrip())
    (out / "run-command.log").write_text("\n".join(run_lines) + "\n", encoding="utf-8")
    if code not in (0, 2):
        failures.append(f"run-command unexpected exit {code}")

    lane_log = out / "lane-launch.log"
    lane_lines = ["=== Verification plan step 4: operator-lane dry-run ==="]
    for target, lane_dir in (("generic", out / "lane-run-1"), ("builder", out / "lane-run-2")):
        cmd = [
            "uv",
            "run",
            "builder-platform",
            "operator-lane",
            "--target",
            target,
            "--dry-run",
            "--output-dir",
            str(lane_dir),
        ]
        lane_lines.append(f"$ {' '.join(cmd)}")
        log_path = lane_dir / "run.log"
        code = _run(cmd, log_path, env=env, cwd=root)
        lane_lines.append(log_path.read_text(encoding="utf-8").rstrip())
        if code != 0:
            failures.append(f"operator-lane {target} failed (exit {code})")
        elif not (lane_dir / "operator-lane-report.json").is_file():
            failures.append(f"operator-lane {target} missing operator-lane-report.json")
        elif not (lane_dir / "readonly-inspection-report.json").is_file():
            failures.append(f"operator-lane {target} missing readonly-inspection-report.json")
    lane_log.write_text("\n".join(lane_lines) + "\n", encoding="utf-8")

    v0_dir = out / "builder-ii-v0-proof"
    v0_cmd = ["uv", "run", "python", "scripts/verify_v0_release.py", "--output-dir", str(v0_dir)]
    code = _run(v0_cmd, v0_dir / "run.log", env=env, cwd=root)
    if code != 0:
        failures.append(f"verify_v0_release failed (exit {code})")

    if not args.skip_full_suite:
        full_cmd = ["uv", "run", "pytest", "-q"]
        code = _run(full_cmd, tests_dir / "full-suite.log", env=env, cwd=root)
        full_note = tests_dir / "full-suite.log"
        note = full_note.read_text(encoding="utf-8")
        if code != 0:
            full_note.write_text(
                note + f"\nNOTE: full suite exit {code}; gating steps 2-5 are authoritative per verification plan step 6.\n",
                encoding="utf-8",
            )

    pr_log = out / "pr-evidence.log"
    pr_lines = ["=== Verification plan step 7: PR evidence ==="]
    for cmd in (
        ["git", "log", "-3", "--oneline"],
        ["gh", "pr", "view", "213", "--repo", "AssetOverflow/builder-II"],
    ):
        pr_lines.append(f"$ {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        pr_lines.append(proc.stdout or "")
    pr_log.write_text("\n".join(pr_lines) + "\n", encoding="utf-8")

    summary = out / "capture-summary.log"
    if failures:
        summary.write_text("FAILURES:\n" + "\n".join(f"- {item}" for item in failures) + "\n", encoding="utf-8")
        print("\n".join(failures), file=sys.stderr)
        return 1

    summary.write_text("ALL_VERIFICATION_STEPS_PASSED\n", encoding="utf-8")
    print(f"Evidence captured under {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
