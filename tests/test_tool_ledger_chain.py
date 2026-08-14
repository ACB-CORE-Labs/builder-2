import json as json_lib
from pathlib import Path

from builder_ii.tools_cli import tools_app
from typer.testing import CliRunner

from builder_ii.core.config import Settings
from builder_ii.core.mcp_policy import (
    ENVELOPE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
)
from builder_ii.governance.ledger.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        target_repo=Path("/tmp/core"),
        backend="mlx-lm",
        model_tier="primary",
        model_alias="qwen-coder",
        model_primary="gemma-4-12b-4bit",
        model_fast="gemma-4-e4b-4bit",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.7,
        project_root=tmp_path,
        allow_cloud_models=False,
    )


def _policy_path(tmp_path: Path) -> Path:
    policy = {
        "kind": TOOL_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "denied_by_default": True,
        "artifact_is_authority": False,
        "grants_authority": False,
        "allowed_operations": ["invoke"],
        "allowed_risk_classes": ["low", "low_risk"],
        "allowed_tools": ["builtin.echo"],
        "max_input_bytes": 1024,
        "max_output_bytes": 1024,
        "timeout_seconds": 30,
        "network_allowed": False,
        "mutation_allowed": False,
        "credential_access_allowed": False,
        "cost_allowed": False,
        "requires_approval_for_mutation": True,
        "requires_approval_for_external_network": True,
        "requires_approval_for_credentials": True,
        "governance": {"artifact_is_authority": False},
    }
    pol_path = tmp_path / "policy.json"
    pol_path.write_text(json_lib.dumps(policy), encoding="utf-8")
    return pol_path


def _envelope_path(tmp_path: Path, pol_path: Path) -> Path:
    import json as json_lib

    policy = json_lib.loads(pol_path.read_text())
    envelope = {
        "kind": TOOL_ENVELOPE_KIND,
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "operation_name": "invoke",
        "tool_id": "builtin.echo",
        "executes_tool": True,
        "input_digest": "0" * 64,
        "policy_ref": {"role": "policy", "kind": "policy", "path": str(pol_path), "sha256": canonical_digest(policy)},
        "effect_classification": "pure",
        "risk_classification": "low",
        "rollback_requirement": "none",
        "timeout": 30,
        "output_cap": 1024,
        "credential_redaction_declaration": True,
        "requires_human_promotion_for_execution": True,
        "executes_shell": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "arguments": {"text": "hello test"},
    }
    env_path = tmp_path / "envelope.json"
    env_path.write_text(json_lib.dumps(envelope), encoding="utf-8")
    return env_path


def test_tool_event_as_first_in_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    pol_path = _policy_path(tmp_path)
    env_path = _envelope_path(tmp_path, pol_path)
    rec_path = tmp_path / "receipt.json"
    session_id = "session-first"

    result = runner.invoke(
        tools_app,
        [
            "invoke",
            str(env_path),
            str(pol_path),
            "--receipt-output",
            str(rec_path),
            "--session-id",
            session_id,
        ],
    )

    assert result.exit_code == 0, result.output
    events_dir = tmp_path / ".builder/sessions" / session_id / "events"
    records = load_event_records(events_dir)
    assert records

    event = records[-1][0]
    assert event["sequence"] == 1
    assert event["previous_event_ref"] is None
    assert event["previous_event_sha256"] is None
    assert event["event_type"] == "tool_call_executed"

    assert validate_event_record(event) == []
    report = replay_events(records, session_id=session_id)
    assert report["valid"]


def test_tool_event_chains_to_prior_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    pol_path = _policy_path(tmp_path)
    env_path = _envelope_path(tmp_path, pol_path)
    rec_path = tmp_path / "receipt.json"
    session_id = "session-chain"

    events_dir = tmp_path / ".builder/sessions" / session_id / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    # Write synthetic prior event
    prior_event = create_event_record(
        event_id="evt_prior_001",
        session_id=session_id,
        sequence=1,
        event_type="workflow_planned",
        stage="planned",
        subject_refs=[],
        command_surface="builder workflow plan",
        policy_snapshot_ref={
            "kind": "command_authority",
            "sha256": "a" * 64,
            "role": "policy_snapshot",
            "required": True,
            "path": "docs/COMMAND_AUTHORITY.md",
        },
        previous_event_ref=None,
        message="Prior synthetic event",
    )
    prior_path = events_dir / "001_workflow_planned.json"
    write_event_record(prior_event, prior_path)

    result = runner.invoke(
        tools_app,
        [
            "invoke",
            str(env_path),
            str(pol_path),
            "--receipt-output",
            str(rec_path),
            "--session-id",
            session_id,
        ],
    )

    assert result.exit_code == 0, result.output
    records = load_event_records(events_dir)
    assert len(records) == 2

    event = records[-1][0]
    assert event["sequence"] == 2

    expected_digest = canonical_digest(prior_event)
    assert event["previous_event_ref"]["sha256"] == expected_digest
    assert event["previous_event_sha256"] == expected_digest
    assert event["event_type"] == "tool_call_executed"

    assert validate_event_record(event) == []
    report = replay_events(records, session_id=session_id)
    assert report["valid"]


def test_tool_event_failure_logs_failed_event(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    pol_path = _policy_path(tmp_path)
    env_path = _envelope_path(tmp_path, pol_path)
    rec_path = tmp_path / "receipt.json"
    session_id = "session-fail"

    # Mismatch policy digest in envelope to trigger failure
    import json as json_lib

    envelope = json_lib.loads(env_path.read_text())
    envelope["policy_ref"]["sha256"] = "wrong" * 16
    env_path.write_text(json_lib.dumps(envelope))

    result = runner.invoke(
        tools_app,
        [
            "invoke",
            str(env_path),
            str(pol_path),
            "--receipt-output",
            str(rec_path),
            "--session-id",
            session_id,
        ],
    )

    assert result.exit_code != 0
    events_dir = tmp_path / ".builder/sessions" / session_id / "events"
    records = load_event_records(events_dir)
    assert records

    event = records[-1][0]
    assert event["event_type"] == "tool_call_failed"
    assert validate_event_record(event) == []
