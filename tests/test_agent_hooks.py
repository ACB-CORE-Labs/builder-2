from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from builder_ii.governance.ledger.gate_battery_receipt import (
    build_gate_battery_receipt,
    gate_record_for_run,
    write_gate_battery_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "hooks@example.invalid")
    _git(repo, "config", "user.name", "Hook Tests")
    (repo / "tracked.txt").write_text("settled\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".builder/\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt", ".gitignore")
    _git(repo, "commit", "-m", "settled")
    return repo


def _run(script: str, repo: Path, payload: dict) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        ["bash", str(ROOT / ".agents" / "scripts" / script)],
        cwd=repo,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def test_qualification_gate_allows_nonqualification_and_refuses_dirty_qualification(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    harmless = {"workspacePaths": [str(repo)], "toolCall": {"args": {"CommandLine": "git status"}}}
    assert _run("qualification_gate.sh", repo, harmless)["decision"] == "allow"
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    qualifying = {
        "workspacePaths": [str(repo)],
        "toolCall": {"args": {"CommandLine": "builder-model benchmark --profile m1-v1"}},
    }
    assert _run("qualification_gate.sh", repo, qualifying)["decision"] == "force_ask"


def test_closure_gate_requires_digest_valid_passed_receipt_on_current_clean_head(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    payload = {"workspacePaths": [str(repo)]}
    assert _run("closure_stop_gate.sh", repo, payload)["decision"] == "continue"

    head = _git(repo, "rev-parse", "HEAD")
    receipt = build_gate_battery_receipt(
        gates=[gate_record_for_run("focused", ["pytest", "-q"], 0, 1.0)],
        head_sha_before=head,
        head_sha_after=head,
        working_tree_clean=True,
    )
    path = repo / ".builder" / "artifacts" / "gate-battery-receipt.json"
    write_gate_battery_receipt(receipt, path)
    assert _run("closure_stop_gate.sh", repo, payload)["decision"] == "allow"

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["head_sha_after"] = "0" * 40
    path.write_text(json.dumps(tampered), encoding="utf-8")
    assert _run("closure_stop_gate.sh", repo, payload)["decision"] == "continue"


def test_rust_cli_rejects_unknown_kind_instead_of_kind_only_acceptance() -> None:
    source = (ROOT / "builder_ii_validation_rs" / "src" / "main.rs").read_text(encoding="utf-8")
    validation = (ROOT / "builder_ii_validation_rs" / "src" / "validation.rs").read_text(encoding="utf-8")
    assert "validation::validate_artifact_core" in source
    assert "unsupported artifact kind" in validation
