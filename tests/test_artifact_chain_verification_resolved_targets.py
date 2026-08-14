from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.goose_command_proposal import create_goose_command_proposal
from builder_ii.core.artifact_chain_verification import verify_artifact_chain
from builder_ii.lifecycle.candidate.approval_records import create_approval_record

_MANIFEST: dict[str, Any] = {
    "kind": "builder_ii.goose_session_manifest",
    "schema_version": 1,
    "target": {"name": "test-target", "repo": "/tmp/repo", "description": "test"},
    "agent_profile": {"name": "test-agent", "description": "test", "authority": "user"},
    "task": "resolved target native validation",
    "requested_runtime_mode": "disabled",
}


def test_resolved_referenced_file_must_pass_native_validation(tmp_path: Path) -> None:
    proposal = create_goose_command_proposal(
        _MANIFEST,
        manifest_path="manifest.json",
        command="echo test",
        risk_level="low",
    )
    proposal["governance"]["model_execution"] = "ENABLED"
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json_lib.dumps(proposal), encoding="utf-8")

    approval = create_approval_record(
        proposal,
        proposal_path="proposal.json",
        decision="approved",
        decided_by="operator",
    )
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json_lib.dumps(approval), encoding="utf-8")

    report = verify_artifact_chain([approval_path])

    assert report["valid"] is False
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 1
    assert any("Resolved target native validation failed" in error for error in report["errors"])
    assert any("governance.model_execution must be DISABLED or NOT_AUTHORIZED" in error for error in report["errors"])
