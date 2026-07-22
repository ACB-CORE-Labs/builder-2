from pathlib import Path

from builder_ii.adapters.goose.goose_command_proposal import create_goose_command_proposal
from builder_ii.adapters.goose.goose_session import create_goose_session_manifest
from builder_ii.core.config import load_settings
from builder_ii.lifecycle.candidate.approval_records import create_approval_record


def _record(tmp_path: Path) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="approval record governance",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(
        manifest,
        manifest_path=tmp_path / "goose-session.json",
        command="verify",
        reason="record a proposed operator action",
        risk_level="low",
    )
    return create_approval_record(
        proposal,
        proposal_path=tmp_path / "proposal.json",
        decision="approved",
        decided_by="operator",
    )


def test_approval_record_is_not_authority(tmp_path: Path) -> None:
    record = _record(tmp_path)
    governance = record["governance"]

    assert governance["artifact_is_authority"] is False
    assert governance["core_workbench_coupling"] == "NONE"
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False


def test_approval_record_keeps_runtime_authority_disabled(tmp_path: Path) -> None:
    governance = _record(tmp_path)["governance"]

    for key in (
        "runtime_execution",
        "goose_runtime_start",
        "model_execution",
        "agent_construction",
        "deepagents_construction",
        "shell_execution",
        "command_execution",
        "source_writes",
        "memory_mutation",
        "commit_push",
        "pull_request_creation",
        "source_collection",
        "web_search",
        "mcp_execution",
    ):
        assert governance[key] == "DISABLED", key


def test_approval_record_has_empty_performed_result(tmp_path: Path) -> None:
    record = _record(tmp_path)

    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_runtime_state"] == "DISABLED"
    assert record["performed_actions"] == []
    assert record["result"] == {"status": None, "stdout": "", "stderr": ""}
