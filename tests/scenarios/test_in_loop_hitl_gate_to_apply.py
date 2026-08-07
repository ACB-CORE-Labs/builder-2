"""The in-loop write gate, end to end: agent proposes, human sees it, human decides.

This is the loop the whole lane was built for. A governed Goose session cannot write, so when it
concludes a change is warranted it calls `propose_patch` -- and what happens next is the thing
that used to be missing. The gate refused, wrote a ledger line, and returned a sentence; the
operator watching the run never saw *what* was proposed, and the work evaporated at the boundary.

Now the refusal produces a reviewable artifact in the directory the operator console's gate
scanner already watches. The gate lights, the diff renders, and the decision is a governed one.

What must stay true no matter what: proposing is never applying. Every lane below asserts the
target file is byte-identical afterwards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.ledger.event_ledger import load_event_records, replay_events
from builder_ii.tui.projections.gates import scan_pending_hitl

SESSION = "in-loop-session"

DIFF = """--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,2 @@
 def main():
-    return 'hello'
+    return 'hello, world'
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 'hello'\n", encoding="utf-8")
    return tmp_path


def _propose(server: GovernedMcpServer, arguments: dict[str, Any], req_id: int = 1) -> dict[str, Any]:
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
         "params": {"name": "propose_patch", "arguments": arguments}}
    )
    assert response is not None
    return response["result"]


def test_a_proposed_patch_becomes_a_reviewable_gate_and_changes_nothing(repo: Path) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)
    before = (repo / "src" / "app.py").read_bytes()

    result = _propose(server, {"path": "src/app.py", "unified_diff": DIFF, "reason": "clearer greeting"})

    # Refused as an application, and it says what to do next rather than just "no".
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "Not applied" in text
    assert "approve" in text.lower()

    # The target is untouched. This is the claim that must survive every future change here.
    assert (repo / "src" / "app.py").read_bytes() == before

    # A real, schema-valid proposal landed where the console's gate scanner looks.
    artifacts = builder_root / "artifacts"
    proposals = list(artifacts.glob("hitl-patch-proposal-*.json"))
    assert len(proposals) == 1
    artifact = json.loads(proposals[0].read_text(encoding="utf-8"))
    assert artifact["kind"] == "builder_ii.hitl_patch_proposal"
    assert artifact["unified_diff"] == DIFF

    # ...and the operator console lights its gate from exactly that directory.
    gate_open, label = scan_pending_hitl(artifacts)
    assert gate_open, "the gate stayed dark on a real pending proposal"
    assert label

    # The refusal is still ledgered: recording the proposal did not replace the denial.
    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert [event["event_type"] for event, _ in records] == ["mcp_call_denied"]
    assert replay_events(records, session_id=SESSION)["valid"]


def test_the_recorded_diff_is_what_the_operator_reviews(repo: Path) -> None:
    """The console renders the proposal's own diff, so what is shown is what was proposed."""
    from builder_ii.tui.projections.gates import project_hitl_surface

    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)
    _propose(server, {"path": "src/app.py", "unified_diff": DIFF})

    view = project_hitl_surface(builder_root / "artifacts")
    assert view is not None
    artifact = json.loads(Path(view.path).read_text(encoding="utf-8"))
    assert artifact["unified_diff"] == DIFF


def test_a_proposal_with_no_diff_is_refused_without_writing_an_artifact(repo: Path) -> None:
    """An empty proposal is not a gate; it would light the console for nothing to review."""
    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)

    result = _propose(server, {"path": "src/app.py", "unified_diff": "   "})

    assert result["isError"] is True
    assert not list((builder_root / "artifacts").glob("hitl-patch-proposal-*.json"))
    gate_open, _ = scan_pending_hitl(builder_root / "artifacts")
    assert not gate_open


def test_run_shell_is_still_refused_outright(repo: Path) -> None:
    """`propose_patch` gained a governed destination; `run_shell` has none and gets none."""
    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)

    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "run_shell", "arguments": {"cmd": "echo pwned"}}}
    )
    assert response is not None
    result = response["result"]

    assert result["isError"] is True
    assert not list((builder_root / "artifacts").glob("hitl-patch-proposal-*.json"))


def test_applying_still_requires_the_flag_and_a_real_approval(repo: Path, monkeypatch: Any) -> None:
    """The proposal path did not become a way in: applying is unchanged and still fails closed."""
    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)
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

    # Even with the flag, a non-existent approval is refused rather than assumed.
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
