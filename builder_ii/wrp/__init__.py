"""Workload–Router–Pool (WRP) control plane — passive, digest-bound foundation.

This package implements the geometry-first orchestration & routing control plane
described by ADR-0007 and the dual-platform Maker/Governor master plan.

Promotion honesty:
- All operators emit recommendation / plan / validation artifacts only.
- Nothing here grants model, shell, MCP, Goose, or deepagents execution authority.
- Adjoint corrections update *experience artifacts*; φ apply requires HITL
  ``apply-rstar-approved`` and still never mutates DEFAULT_PHI / live defaults.
"""

from __future__ import annotations

from builder_ii.wrp.artifacts import (
    WRP_ARTIFACT_KINDS,
    finalize_wrp_artifact,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.spaces import (
    AgentPoint,
    ToolPolicyPoint,
    TrajectoryEdge,
    TrajectoryGraph,
    WorkloadPoint,
    workload_distance,
)

__all__ = [
    "WRP_ARTIFACT_KINDS",
    "AgentPoint",
    "ToolPolicyPoint",
    "TrajectoryEdge",
    "TrajectoryGraph",
    "WorkloadPoint",
    "finalize_wrp_artifact",
    "validate_wrp_artifact_envelope",
    "workload_distance",
]
