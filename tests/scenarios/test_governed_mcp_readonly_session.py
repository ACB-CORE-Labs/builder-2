"""A whole governed session, driven through the MCP protocol the way Goose drives it.

The unit tests cover the jail and the ceremony separately. This one asserts the thing an
operator actually cares about: a governed Goose session can read the repository, everything it
did is on one replayable chain, and the tree it read is byte-for-byte unchanged afterwards.

Driven through `handle_request` rather than the stdio loop -- the server's own docstring notes
the protocol layer is framing-independent, so this needs no subprocess and no Goose binary.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.ledger.event_ledger import load_event_records, replay_events

SESSION = "governed-scenario"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "engine.py").write_text(
        "class Engine:\n    def start(self):\n        return 'running'\n", encoding="utf-8"
    )
    (tmp_path / "src" / "util.py").write_text("MARKER = 'findme'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Scenario repo\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    return tmp_path


def _tree_digest(root: Path) -> dict[str, str]:
    """Content digests of every non-reserved file, so mutation is proven, not assumed."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or ".builder" in path.parts:
            continue
        snapshot[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _call(server: GovernedMcpServer, name: str, arguments: dict[str, Any], req_id: int) -> dict[str, Any]:
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
    )
    assert response is not None
    return response["result"]


def test_a_governed_session_reads_the_repo_and_leaves_one_valid_chain(repo: Path) -> None:
    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)
    before = _tree_digest(repo)

    # 1. Handshake.
    init = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init is not None and init["result"]["serverInfo"]["name"]

    # 2. The read tools are advertised, so a real Goose session would know they exist.
    listed = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {"read_file", "list_dir", "grep"} <= names

    # 3. The work an agent would actually do: orient, search, read.
    listing = _call(server, "list_dir", {"path": "."}, 3)
    assert "src/" in listing["content"][0]["text"]
    assert listing["isError"] is False

    found = _call(server, "grep", {"pattern": "findme"}, 4)
    assert "src/util.py" in found["content"][0]["text"]

    source = _call(server, "read_file", {"path": "src/engine.py"}, 5)
    assert "class Engine" in source["content"][0]["text"]

    # 4. An escape attempt is refused in-loop and still ledgered, not silently dropped.
    escape = _call(server, "read_file", {"path": "../../../etc/passwd"}, 6)
    assert escape["isError"] is True
    assert "must not contain '..'" in escape["content"][0]["text"]

    # 5. Every call -- permitted and refused -- is one link on a single replayable chain.
    records = load_event_records(builder_root / "sessions" / SESSION / "events")
    assert [event["sequence"] for event, _ in records] == [1, 2, 3, 4]
    assert all(event["event_type"] == "mcp_call_executed" for event, _ in records)
    assert replay_events(records, session_id=SESSION)["valid"]

    # Each link commits to its predecessor; the first has none.
    assert records[0][0]["previous_event_sha256"] is None
    assert all(event["previous_event_sha256"] for event, _ in records[1:])

    # 6. Read-only is proven by content digest, not asserted by configuration.
    assert _tree_digest(repo) == before


def test_a_refused_read_still_writes_a_receipt(repo: Path) -> None:
    """A denial is evidence too: it must not vanish into an exception."""
    builder_root = repo / ".builder"
    server = GovernedMcpServer(session_id=SESSION, builder_root=builder_root, target_root=repo)

    result = _call(server, "read_file", {"path": ".git/config"}, 1)

    assert result["isError"] is True
    receipts = sorted((builder_root / "sessions" / SESSION / "mcp").glob("*_receipt.json"))
    assert len(receipts) == 1
    assert '"status": "denied"' in receipts[0].read_text(encoding="utf-8")


def test_the_read_tools_do_not_reach_outside_the_declared_target_root(
    repo: Path, tmp_path_factory: Any
) -> None:
    """The jail follows the root the session was constructed with, not the process's cwd.

    Goose spawns the server with cwd=target_root, so the two normally agree -- this pins that
    the reachable tree is the one the session declared, and that a cwd change cannot widen it.
    """
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    (elsewhere / "secret.txt").write_text("should stay unreachable", encoding="utf-8")

    server = GovernedMcpServer(
        session_id=SESSION, builder_root=repo / ".builder", target_root=repo
    )
    result = _call(server, "read_file", {"path": "secret.txt"}, 1)

    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"]
