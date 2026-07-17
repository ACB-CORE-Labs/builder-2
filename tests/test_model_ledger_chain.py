"""Tests for model call ledger event chaining.

Verifies:
1. When a model call is the first event in a session, previous_event_ref is None.
2. When a model call is appended to an existing session, previous_event_ref.sha256
   matches the last recorded event's payload_sha256.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from unittest.mock import patch

from builder_ii.model_cli import model_app
from typer.testing import CliRunner

from builder_ii.config import Settings
from builder_ii.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
    write_event_record,
)
from builder_ii.model_routing_policy import create_model_execution_policy


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        target_repo=Path("/tmp/core"),
        backend="mlx-lm",
        model_tier="primary",
        model_alias="qwen-coder",
        model_primary="gemma-4-12b-4bit",
        model_fast="gemma-4-e4b-4bit",
        mlx_model_primary="mlx-community/gemma-4-12B-it-4bit",
        mlx_model_fast="mlx-community/gemma-4-e4b-it-4bit",
        mlx_model_phi="mlx-community/Phi-4-mini-reasoning-4bit",
        mlx_model_qwen="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        mlx_model_deepseek="mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        mlx_model_llama="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        mlx_model_codegeex="mlx-community/codegeex4-all-9b-4bit",
        mlx_model_qwen14="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        mlx_model_qwen3_coder="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.7,
        project_root=tmp_path,
        allow_cloud_models=False,
    )


def _policy_path(tmp_path: Path) -> Path:
    dummy_rec = {
        "kind": "builder_ii.model_routing_recommendation",
        "recommended_candidates": [
            {"model_id": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"},
        ],
    }
    policy = create_model_execution_policy(dummy_rec, max_tokens=1024)
    pol_path = tmp_path / "policy.json"
    pol_path.write_text(json_lib.dumps(policy), encoding="utf-8")
    return pol_path


def _run_call_cmd(tmp_path: Path, session_id: str, pol_path: Path, settings: Settings, monkeypatch) -> dict:
    """Invoke builder-model call in-process via CliRunner and return the last written ledger event."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    env_path = tmp_path / f"envelope_{session_id}.json"
    rec_path = tmp_path / f"receipt_{session_id}.json"

    from builder_ii.direct_chat import DirectChatResult

    stub = DirectChatResult(ok=True, content="Paris", endpoint="http://x", model_id="m")

    with (
        patch("builder_ii.model_cli.load_settings", return_value=settings),
        patch("builder_ii.model_execution_gateway.run_direct_chat", return_value=stub),
    ):
        result = runner.invoke(
            model_app,
            [
                "call",
                "--model",
                "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
                "--prompt",
                "What is 2+2?",
                "--execution-policy",
                str(pol_path),
                "--output-envelope",
                str(env_path),
                "--output-receipt",
                str(rec_path),
                "--session-id",
                session_id,
            ],
        )

    assert result.exit_code == 0, f"call_cmd failed: {result.output}"

    events_dir = tmp_path / ".builder/sessions" / session_id / "events"
    records = load_event_records(events_dir)
    assert records, "No event was written to ledger"
    return records[-1][0]  # (event_dict, path) -> event_dict


def test_model_event_as_first_in_session(tmp_path: Path, monkeypatch) -> None:
    """Event #1 in a fresh session must have previous_event_ref=None."""
    settings = _settings(tmp_path)
    pol_path = _policy_path(tmp_path)
    event = _run_call_cmd(tmp_path, "session-first", pol_path, settings, monkeypatch)

    assert event["sequence"] == 1
    assert event["previous_event_ref"] is None, (
        f"First event must not have previous_event_ref, got: {event['previous_event_ref']}"
    )
    assert event["previous_event_sha256"] is None


def test_model_event_chains_to_prior_event(tmp_path: Path, monkeypatch) -> None:
    """Event #2 must have previous_event_ref.sha256 == prior event's payload_sha256."""
    settings = _settings(tmp_path)
    pol_path = _policy_path(tmp_path)
    session_id = "session-chain"

    # Write a synthetic prior event manually
    events_dir = tmp_path / ".builder/sessions" / session_id / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

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

    # Now run the model call -- it should chain to the prior event
    event = _run_call_cmd(tmp_path, session_id, pol_path, settings, monkeypatch)

    from builder_ii.event_ledger import validate_event_record
    from builder_ii.workflow_records import canonical_digest

    assert event["sequence"] == 2, f"Expected sequence 2, got {event['sequence']}"
    prev_ref = event.get("previous_event_ref")
    assert prev_ref is not None, "Event #2 must have previous_event_ref"

    expected_digest = canonical_digest(prior_event)
    assert prev_ref["sha256"] == expected_digest, (
        f"previous_event_ref.sha256 {prev_ref['sha256']!r} != expected digest {expected_digest!r}"
    )
    assert event["previous_event_sha256"] == expected_digest

    # Load all records and perform direct validation and replay validation
    records = load_event_records(events_dir)
    assert validate_event_record(records[-1][0]) == []
    report = replay_events(records, session_id=session_id)
    assert report["valid"], report["errors"]
