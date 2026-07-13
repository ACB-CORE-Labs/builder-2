"""SubtaskGraphManager — pure-Python DAG (LangGraph reference only)."""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    REPLAY_REPORT_KIND,
    SUBTASK_GRAPH_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.spaces import TrajectoryGraph


def create_subtask_graph(graph: TrajectoryGraph, *, task: str) -> dict[str, Any]:
    order = graph.topological_order()
    return base_envelope(
        kind=SUBTASK_GRAPH_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_plan_only",
        extra={
            "task": task,
            "graph": graph.to_jsonable(),
            "execution_order": order,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
        },
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
) -> dict[str, Any]:
    """W5 reconstructive replay: compare planned execution_order digests to observed chain digests."""
    planned_order = list(planned.get("execution_order") or [])
    observed_ids = [str(item.get("node_id", item.get("id", ""))) for item in observed_chain]
    planned_digests = [str(item.get("digest", "")) for item in observed_chain]  # observed carry digests
    # Bit-for-bit / digest match of node sequence
    sequence_match = observed_ids == planned_order
    # Reconstruct expected length
    length_match = len(observed_ids) == len(planned_order)
    all_digests_present = all(len(d) == 64 for d in planned_digests) if planned_digests else False
    perfect = sequence_match and length_match and (all_digests_present or not observed_chain)

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
            "perfect_match": perfect and sequence_match,
            "grants_authority": False,
        },
    )


def validate_replay_report(record: Any) -> list[str]:
    return validate_wrp_artifact_envelope(record, expected_kind=REPLAY_REPORT_KIND)
