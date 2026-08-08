"""In-loop write gate: proposal becomes reviewable evidence, never an implicit write.

These scenarios prove the passive half of the governed edit loop.  A proposal is
content-addressed, bound to its source preimage and origin session, referenced by the
denial event, visible to STRATUM, and incapable of mutating the target.  The later
approval/apply ceremony remains independently governed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from builder_ii.adapters.mcp.governed_apply import run_gated_patch_apply
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.ledger.event_ledger import load_event_records, replay_events
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.tui.projections.gates import scan_pending_hitl

SESSION = "in-loop-session"

DIFF = """--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
 def main():
-    return 'hello'
+    return 'hello, world'
"""

DIFF_TWO = """--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
 def main():
-    return 'hello'
+    return 'hello again'
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def main():\n    return 'hello'\n", encoding="utf-8"
    )
    return tmp_path


def _propose(
    server: GovernedMcpServer, arguments: dict[str, Any], req_id: int = 1
) -> dict[str, Any]:
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": "propose_patch", "arguments": arguments},
        }
    )
    assert response is not None
    return response["result"]


def _proposal_paths(builder_root: Path) -> list[Path]:
    return sorted((builder_root / "artifacts" / "hitl" / "proposals").glob("*.json"))


def test_a_proposed_patch_becomes_a_digest_bound_reviewable_gate_and_changes_nothing(
    repo: Path,
) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )
    target = repo / "src" / "app.py"
    before = target.read_bytes()

    result = _propose(
        server,
        {"path": "src/app.py", "unified_diff": DIFF, "reason": "clearer greeting"},
    )

    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "Not applied" in text
    assert "approve" in text.lower()
    assert target.read_bytes() == before

    proposals = _proposal_paths(builder_root)
    assert len(proposals) == 1
    artifact = json.loads(proposals[0].read_text(encoding="utf-8"))
    assert artifact["kind"] == "builder_ii.hitl_patch_proposal"
    assert artifact["unified_diff"] == DIFF
    assert proposals[0].stem == canonical_digest(artifact)

    origin = artifact["in_loop_origin"]
    assert origin["session_id"] == SESSION
    assert origin["target_path"] == "src/app.py"
    assert origin["target_preimage_state"] == "present"
    assert len(origin["target_preimage_sha256"]) == 64
    assert origin["artifact_is_authority"] is False

    gate_open, label = scan_pending_hitl(builder_root / "artifacts")
    assert gate_open, "the gate stayed dark on a real pending proposal"
    assert label

    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert [event["event_type"] for event, _ in records] == ["mcp_call_denied"]
    event = records[0][0]
    assert len(event["subject_refs"]) == 1
    ref = event["subject_refs"][0]
    assert ref["kind"] == "builder_ii.hitl_patch_proposal"
    assert ref["path"] == str(proposals[0])
    assert ref["sha256"] == canonical_digest(artifact)
    assert replay_events(records, session_id=SESSION)["valid"]


def test_two_proposals_in_one_session_cannot_overwrite_each_other(repo: Path) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )

    _propose(server, {"path": "src/app.py", "unified_diff": DIFF}, req_id=1)
    _propose(server, {"path": "src/app.py", "unified_diff": DIFF_TWO}, req_id=2)

    proposals = _proposal_paths(builder_root)
    assert len(proposals) == 2
    assert proposals[0].name != proposals[1].name
    diffs = {json.loads(path.read_text(encoding="utf-8"))["unified_diff"] for path in proposals}
    assert diffs == {DIFF, DIFF_TWO}

    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert len(records) == 2
    assert all(event["subject_refs"] for event, _ in records)
    assert replay_events(records, session_id=SESSION)["valid"]


def test_the_recorded_diff_is_exactly_what_the_operator_reviews(repo: Path) -> None:
    from builder_ii.tui.projections.gates import project_hitl_surface

    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )
    _propose(server, {"path": "src/app.py", "unified_diff": DIFF})

    view = project_hitl_surface(builder_root / "artifacts")
    assert view is not None
    artifact = json.loads(Path(view.path).read_text(encoding="utf-8"))
    assert artifact["unified_diff"] == DIFF


def test_a_proposal_with_no_diff_is_refused_without_writing_an_artifact(
    repo: Path,
) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )

    result = _propose(server, {"path": "src/app.py", "unified_diff": "   "})

    assert result["isError"] is True
    assert not _proposal_paths(builder_root)
    gate_open, _ = scan_pending_hitl(builder_root / "artifacts")
    assert not gate_open


def test_proposal_path_uses_the_same_target_jail_as_repo_reads(repo: Path) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )
    result = _propose(server, {"path": "../outside.py", "unified_diff": DIFF})
    assert result["isError"] is True
    assert "path jail" in result["content"][0]["text"].lower()
    assert not _proposal_paths(builder_root)


def test_run_shell_is_still_refused_outright(repo: Path) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )

    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "run_shell", "arguments": {"cmd": "echo pwned"}},
        }
    )
    assert response is not None
    assert response["result"]["isError"] is True
    assert not _proposal_paths(builder_root)


def test_source_drift_refuses_before_the_governed_apply_lane_is_called(
    repo: Path, monkeypatch: Any
) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )
    _propose(server, {"path": "src/app.py", "unified_diff": DIFF})
    proposal_path = _proposal_paths(builder_root)[0]

    approval = repo / "approval.json"
    verification = repo / "verification.json"
    approval.write_text("{}", encoding="utf-8")
    verification.write_text("{}", encoding="utf-8")

    # Drift after proposal/review subject was minted.
    (repo / "src" / "app.py").write_text("changed after review\n", encoding="utf-8")
    monkeypatch.setenv("BUILDER_MCP_GOVERNED_APPLY", "1")

    with (
        patch(
            "builder_ii.adapters.mcp.governed_apply.validate_hitl_patch_approval_file",
            return_value=[],
        ),
        patch("builder_ii.adapters.mcp.governed_apply.apply_hitl_patch") as mock_apply,
    ):
        outcome = run_gated_patch_apply(
            arguments={
                "proposal_path": str(proposal_path),
                "approval_path": str(approval),
                "verification_receipt_path": str(verification),
            },
            session_id=SESSION,
            builder_root=builder_root,
            target_root=repo,
        )

    assert outcome.status == "refused"
    assert "preimage digest" in outcome.reason
    mock_apply.assert_not_called()


def test_applying_still_requires_the_flag_and_real_artifacts(
    repo: Path, monkeypatch: Any
) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(
        session_id=SESSION, builder_root=builder_root, target_root=repo
    )
    before = (repo / "src" / "app.py").read_bytes()

    monkeypatch.delenv("BUILDER_MCP_GOVERNED_APPLY", raising=False)
    result = _propose(
        server,
        {
            "proposal_path": str(repo / "nope.json"),
            "approval_path": str(repo / "nope.json"),
            "verification_receipt_path": str(repo / "nope.json"),
        },
    )
    assert result["isError"] is True
    assert "not enabled" in result["content"][0]["text"]

    monkeypatch.setenv("BUILDER_MCP_GOVERNED_APPLY", "1")
    result = _propose(
        server,
        {
            "proposal_path": str(repo / "nope.json"),
            "approval_path": str(repo / "nope.json"),
            "verification_receipt_path": str(repo / "nope.json"),
        },
        req_id=2,
    )
    assert result["isError"] is True
    assert (repo / "src" / "app.py").read_bytes() == before
