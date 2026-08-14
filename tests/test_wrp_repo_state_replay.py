"""W5 reconstructive replay: digests + commit_id/tree_hash binding."""

from __future__ import annotations

from pathlib import Path

from builder_ii.wrp.patterns import sequential_chain
from builder_ii.wrp.repo_state import capture_repo_state, normalize_repo_state, repo_states_match
from builder_ii.wrp.subtask_graph import (
    create_subtask_graph,
    replay_graph_digests,
    validate_replay_report,
    validate_subtask_graph,
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64


def test_capture_repo_state_on_this_repo() -> None:
    state = capture_repo_state(Path.cwd())
    # This workspace is a git tree; values must be non-null hex-ish strings.
    assert state["grants_authority"] is False
    if state["is_git_tree"] and state["capture_error"] is None:
        assert isinstance(state["commit_id"], str) and len(state["commit_id"]) >= 7
        assert isinstance(state["tree_hash"], str) and len(state["tree_hash"]) >= 7
    else:
        # Honest null path still structured.
        assert state["commit_id"] is None or state["capture_error"]


def test_capture_repo_state_null_for_non_git(tmp_path: Path) -> None:
    state = capture_repo_state(tmp_path)
    assert state["is_git_tree"] is False
    assert state["commit_id"] is None
    assert state["tree_hash"] is None
    assert state["grants_authority"] is False


def test_repo_states_match_null_git() -> None:
    result = repo_states_match(None, None)
    assert result["repo_state_match"] is True
    assert result["mode"] == "null_git"


def test_repo_states_match_bound() -> None:
    planned = {"commit_id": "abc123", "tree_hash": "def456"}
    observed = {"commit_id": "abc123", "tree_hash": "def456"}
    result = repo_states_match(planned, observed)
    assert result["repo_state_match"] is True
    assert result["mode"] == "bound"


def test_repo_states_match_mismatch() -> None:
    planned = {"commit_id": "abc123", "tree_hash": "def456"}
    observed = {"commit_id": "abc123", "tree_hash": "zzzzzz"}
    result = repo_states_match(planned, observed)
    assert result["repo_state_match"] is False
    assert result["mode"] == "mismatch"
    assert any("tree_hash" in r for r in result["reasons"])


def test_replay_perfect_match_null_git_digest_ok() -> None:
    planned = create_subtask_graph(sequential_chain(["a", "b"]), task="t")
    observed = [
        {"node_id": "a", "digest": _DIGEST_A},
        {"node_id": "b", "digest": _DIGEST_B},
    ]
    report = replay_graph_digests(planned=planned, observed_chain=observed)
    assert report["sequence_match"] is True
    assert report["digest_sequence_ok"] is True
    assert report["repo_state_match"] is True
    assert report["repo_state_mode"] == "null_git"
    assert report["perfect_match"] is True
    assert report["grants_authority"] is False
    assert validate_replay_report(report) == []


def test_replay_perfect_match_with_bound_repo() -> None:
    rs = {"commit_id": "c0ffee", "tree_hash": "t0ad", "is_git_tree": True, "source": "test"}
    planned = create_subtask_graph(sequential_chain(["a", "b"]), task="t", repo_state=rs)
    assert planned["repo_state"]["commit_id"] == "c0ffee"
    assert validate_subtask_graph(planned) == []
    observed = [
        {"node_id": "a", "digest": _DIGEST_A},
        {"node_id": "b", "digest": _DIGEST_B},
    ]
    report = replay_graph_digests(
        planned=planned,
        observed_chain=observed,
        observed_repo_state=rs,
    )
    assert report["perfect_match"] is True
    assert report["repo_state_mode"] == "bound"


def test_replay_fails_on_repo_mismatch_even_if_digests_ok() -> None:
    planned_rs = {"commit_id": "aaa", "tree_hash": "bbb"}
    planned = create_subtask_graph(sequential_chain(["a"]), task="t", repo_state=planned_rs)
    observed = [{"node_id": "a", "digest": _DIGEST_A}]
    report = replay_graph_digests(
        planned=planned,
        observed_chain=observed,
        observed_repo_state={"commit_id": "aaa", "tree_hash": "DIFFERENT"},
    )
    assert report["digest_sequence_ok"] is True
    assert report["repo_state_match"] is False
    assert report["perfect_match"] is False


def test_replay_fails_on_sequence_mismatch() -> None:
    planned = create_subtask_graph(sequential_chain(["a", "b"]), task="t")
    observed = [
        {"node_id": "b", "digest": _DIGEST_B},
        {"node_id": "a", "digest": _DIGEST_A},
    ]
    report = replay_graph_digests(planned=planned, observed_chain=observed)
    assert report["sequence_match"] is False
    assert report["perfect_match"] is False


def test_replay_fails_when_digests_missing() -> None:
    planned = create_subtask_graph(sequential_chain(["a"]), task="t")
    observed = [{"node_id": "a", "digest": "short"}]
    report = replay_graph_digests(planned=planned, observed_chain=observed)
    assert report["digests_present"] is False
    assert report["perfect_match"] is False


def test_replay_cli_kwargs_override_planned_repo() -> None:
    planned = create_subtask_graph(sequential_chain(["a"]), task="t")
    observed = [{"node_id": "a", "digest": _DIGEST_A}]
    report = replay_graph_digests(
        planned=planned,
        observed_chain=observed,
        planned_repo_state={"commit_id": "x", "tree_hash": "y"},
        observed_repo_state={"commit_id": "x", "tree_hash": "y"},
    )
    assert report["perfect_match"] is True
    assert report["planned_repo_state"]["commit_id"] == "x"


def test_normalize_repo_state_empty_strings_as_null() -> None:
    n = normalize_repo_state({"commit_id": "", "tree_hash": ""})
    assert n["commit_id"] is None
    assert n["tree_hash"] is None
