import json as json_lib
import shutil
import pytest
from pathlib import Path
from typer.testing import CliRunner

from builder_ii.readonly_authority import (
    create_read_policy,
    validate_read_policy,
    execute_governed_read,
    validate_read_receipt,
    READ_POLICY_KIND,
    READ_RECEIPT_KIND,
    DENIED_READ_KIND,
)
from builder_ii.readonly_inspection_cli import readonly_app
from builder_ii.event_ledger import load_event_records


def test_create_and_validate_read_policy(tmp_path: Path):
    policy = create_read_policy(
        target_name="builder",
        target_repo=tmp_path,
        allowed_paths=["src/*", "tests/*"],
        denied_paths=["*.key"],
        max_bytes_budget=5000,
        content_capture_allowed=True,
    )
    assert policy["kind"] == READ_POLICY_KIND
    assert policy["max_bytes_budget"] == 5000
    assert policy["content_capture_allowed"] is True
    
    errors = validate_read_policy(policy)
    assert not errors


def test_execute_governed_read_success(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    allowed_file = repo / "allowed.txt"
    allowed_file.write_text("Hello World", encoding="utf-8")
    
    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["allowed.txt"],
        content_capture_allowed=True,
    )
    
    # Read allowed file with content capture
    receipt = execute_governed_read(policy, allowed_file)
    assert receipt["kind"] == READ_RECEIPT_KIND
    assert receipt["bytes_read"] == len("Hello World")
    assert receipt["content"] == "Hello World"
    assert not validate_read_receipt(receipt)


def test_execute_governed_read_metadata_only(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    allowed_file = repo / "allowed.txt"
    allowed_file.write_text("Hello World", encoding="utf-8")
    
    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["allowed.txt"],
        content_capture_allowed=False,
    )
    
    # Read allowed file without content capture
    receipt = execute_governed_read(policy, allowed_file)
    assert receipt["kind"] == READ_RECEIPT_KIND
    assert receipt["bytes_read"] == len("Hello World")
    assert receipt["content"] is None
    assert not validate_read_receipt(receipt)


def test_execute_governed_read_denies_path_traversal(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside repo", encoding="utf-8")
    
    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["*"],
    )
    
    receipt = execute_governed_read(policy, outside_file)
    assert receipt["kind"] == DENIED_READ_KIND
    assert "Path not allowed" in receipt["reason"]


def test_execute_governed_read_denies_secrets_suffix(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    secret_file = repo / "private.key"
    secret_file.write_text("my-private-key", encoding="utf-8")
    
    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["private.key"],
    )
    
    receipt = execute_governed_read(policy, secret_file)
    assert receipt["kind"] == DENIED_READ_KIND
    assert "Path not allowed" in receipt["reason"]


def test_execute_governed_read_denies_secrets_content(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    content_secret = repo / "config.txt"
    content_secret.write_text("my_api_key = 'abcdef12345'", encoding="utf-8")
    
    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["config.txt"],
        content_capture_allowed=True,
    )
    
    receipt = execute_governed_read(policy, content_secret)
    assert receipt["kind"] == DENIED_READ_KIND
    assert "detected potential secrets" in receipt["reason"]


def test_execute_governed_read_exceeds_budget(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    
    large_file = repo / "large.txt"
    large_file.write_text("a" * 100, encoding="utf-8")
    
    policy = create_read_policy(
        target_name="generic",
        target_repo=repo,
        allowed_paths=["large.txt"],
        max_bytes_budget=50,
    )
    
    receipt = execute_governed_read(policy, large_file)
    assert receipt["kind"] == DENIED_READ_KIND
    assert "Read budget exceeded" in receipt["reason"]


def test_cli_policy_and_read_governance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('BUILDER_TARGET_REPO', str(tmp_path))
    runner = CliRunner()
    
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test.txt").write_text("hello test", encoding="utf-8")
    
    policy_json = tmp_path / "policy.json"
    
    # 1. Create Policy via CLI
    res = runner.invoke(readonly_app, [
        "policy",
        "--target", "generic",
        "--allowed-path", "repo/*",
        "--budget", "200",
        "--content-capture",
        "--output", str(policy_json)
    ])
    assert res.exit_code == 0, res.output
    assert policy_json.exists()
    
    # 2. Read File via CLI
    out_dir = tmp_path / "receipts"
    res = runner.invoke(readonly_app, [
        "read",
        "--policy", str(policy_json),
        "--file", str(repo / "test.txt"),
        "--output-dir", str(out_dir)
    ])
    assert res.exit_code == 0, res.output
    
    # Check that a receipt JSON was written
    receipts = list(out_dir.glob("read_receipt_*.json"))
    assert len(receipts) == 1
    receipt = json_lib.loads(receipts[0].read_text(encoding="utf-8"))
    assert receipt["kind"] == READ_RECEIPT_KIND
    assert receipt["bytes_read"] == 10
    assert receipt["content"] == "hello test"
    
    # 3. Validate Receipt via CLI
    res = runner.invoke(readonly_app, ["validate", str(receipts[0])])
    assert res.exit_code == 0, res.output
    assert "is valid" in res.stdout


def test_cli_read_logs_to_event_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('BUILDER_TARGET_REPO', str(tmp_path))
    runner = CliRunner()
    
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test.txt").write_text("hello test", encoding="utf-8")
    
    policy_json = tmp_path / "policy.json"
    res = runner.invoke(readonly_app, [
        "policy",
        "--target", "generic",
        "--allowed-path", "repo/*",
        "--output", str(policy_json)
    ])
    assert res.exit_code == 0, res.output
    
    # Set up dummy workflow session directory
    session_id = "test_sess_123"
    sess_dir = Path(".builder/sessions") / session_id
    events_dir = sess_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    
    # Run CLI read with session ID
    out_dir = tmp_path / "receipts"
    res = runner.invoke(readonly_app, [
        "read",
        "--policy", str(policy_json),
        "--file", str(repo / "test.txt"),
        "--output-dir", str(out_dir),
        "--session-id", session_id
    ])
    assert res.exit_code == 0, res.output
    
    # Verify event record was written
    events = load_event_records(events_dir)
    assert len(events) == 1
    assert events[0][0]["event_type"] == "read_executed"
    assert events[0][0]["sequence"] == 1
    assert events[0][0]["stage"] == "initialized"
    
    # Clean up dummy workflow session directory
    if Path(".builder/sessions").exists():
        shutil.rmtree(".builder/sessions")
