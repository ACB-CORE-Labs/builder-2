"""SubtaskGraphManager — pure-Python DAG (LangGraph reference only)."""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    REPLAY_REPORT_KIND,
    SUBTASK_GRAPH_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.repo_state import repo_states_match
from builder_ii.wrp.spaces import TrajectoryGraph


def create_subtask_graph(
    graph: TrajectoryGraph,
    *,
    task: str,
    repo_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order = graph.topological_order()
    extra: dict[str, Any] = {
        "task": task,
        "graph": graph.to_jsonable(),
        "execution_order": order,
        "runtime_binding": "UNBOUND",
        "grants_authority": False,
    }
    if repo_state is not None:
        # Planned repo identity for W5 reconstructive match (optional bind).
        extra["repo_state"] = {
            "commit_id": repo_state.get("commit_id"),
            "tree_hash": repo_state.get("tree_hash"),
            "is_git_tree": bool(repo_state.get("is_git_tree")),
            "source": str(repo_state.get("source") or "planned"),
        }
    return base_envelope(
        kind=SUBTASK_GRAPH_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_plan_only",
        extra=extra,
    )


def validate_subtask_graph(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=SUBTASK_GRAPH_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("runtime_binding") != "UNBOUND":
        errors.append("runtime_binding must be UNBOUND")
    graph = record.get("graph")
    if not isinstance(graph, dict):
        errors.append("graph must be an object")
    return errors


def replay_graph_digests(
    *,
    planned: dict[str, Any],
    observed_chain: list[dict[str, Any]],
    planned_repo_state: dict[str, Any] | None = None,
    observed_repo_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """W5 reconstructive replay: planned digests/order **and** repo state vs observed.

    ``perfect_match`` is True only when:
    - observed node id sequence equals planned ``execution_order``
    - lengths match
    - observed digests present (64-hex) when chain non-empty
    - repo-state fields agree per ``repo_states_match`` (both null = honest null_git)

    Does not grant authority.
    """
    planned_order = list(planned.get("execution_order") or [])
    observed_ids = [str(item.get("node_id", item.get("id", ""))) for item in observed_chain]
    observed_digests = [str(item.get("digest", "")) for item in observed_chain]
    sequence_match = observed_ids == planned_order
    length_match = len(observed_ids) == len(planned_order)
    all_digests_present = all(len(d) == 64 for d in observed_digests) if observed_digests else False
    digest_ok = sequence_match and length_match and (all_digests_present or not observed_chain)

    # Prefer explicit kwargs; fall back to planned artifact's embedded repo_state.
    planned_rs = planned_repo_state
    if planned_rs is None and isinstance(planned.get("repo_state"), dict):
        planned_rs = planned["repo_state"]
    # Observed chain may carry repo_state on first item or as sibling field via kwargs only.
    observed_rs = observed_repo_state

    rs = repo_states_match(planned_rs, observed_rs)
    perfect = bool(digest_ok and rs["repo_state_match"])

    return base_envelope(
        kind=REPLAY_REPORT_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
        extra={
            "planned_order": planned_order,
            "observed_order": observed_ids,
            "sequence_match": sequence_match,
            "length_match": length_match,
            "digests_present": all_digests_present,
            "digest_sequence_ok": digest_ok,
            "repo_state_match": rs["repo_state_match"],
            "repo_state_mode": rs["mode"],
            "repo_state_reasons": list(rs["reasons"]),
            "planned_repo_state": rs["planned"],
            "observed_repo_state": rs["observed"],
            "perfect_match": perfect,
            "grants_authority": False,
        },
    )


def validate_replay_report(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=REPLAY_REPORT_KIND)
    if not isinstance(record, dict):
        return errors
    if "perfect_match" not in record:
        errors.append("perfect_match missing")
    if "repo_state_match" not in record:
        errors.append("repo_state_match missing (W5 requires repo-state field)")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    return errors
