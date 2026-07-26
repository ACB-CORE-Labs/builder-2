"""STRATUM projection layer — pure view-models over governed modules.

Observers only: no writes, no subprocess, no authority origin.
Missing data is absence (None / "—" / unevaluated), never synthesis.
"""

from __future__ import annotations

from builder_ii.tui.projections.agents import project_agent_roster
from builder_ii.tui.projections.authority import (
    COMPOSE_ONLY,
    INVOKE_DIRECT,
    INVOKE_WITH_CONFIRM,
    REFUSE,
    UNWIRED,
    ActionAffordance,
    project_action_affordance,
)
from builder_ii.tui.projections.chain import PIPELINE_STAGES, project_chain
from builder_ii.tui.projections.codevault import project_code_vault
from builder_ii.tui.projections.gates import (
    THIRD_DOOR_INCOMPLETE,
    THIRD_DOOR_LOCKED,
    THIRD_DOOR_UNASSESSED,
    THIRD_DOOR_UNLOCKED,
    project_hitl_surface,
    project_third_door,
    third_door_state,
)
from builder_ii.tui.projections.models import project_model_matrix
from builder_ii.tui.projections.operator import project_operator_dashboard
from builder_ii.tui.projections.orchestration import project_orchestration
from builder_ii.tui.projections.render import (
    kv,
    rule,
    section_title,
    status_glyph,
    themed,
)
from builder_ii.tui.projections.workflow import project_workflow

__all__ = [
    "COMPOSE_ONLY",
    "INVOKE_DIRECT",
    "INVOKE_WITH_CONFIRM",
    "PIPELINE_STAGES",
    "REFUSE",
    "THIRD_DOOR_INCOMPLETE",
    "THIRD_DOOR_LOCKED",
    "THIRD_DOOR_UNASSESSED",
    "THIRD_DOOR_UNLOCKED",
    "UNWIRED",
    "ActionAffordance",
    "kv",
    "project_action_affordance",
    "project_agent_roster",
    "project_chain",
    "project_code_vault",
    "project_hitl_surface",
    "project_model_matrix",
    "project_operator_dashboard",
    "project_orchestration",
    "project_third_door",
    "project_workflow",
    "rule",
    "section_title",
    "status_glyph",
    "themed",
    "third_door_state",
]
