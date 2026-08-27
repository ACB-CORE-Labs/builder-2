"""Compatibility facade for the frontend-neutral governed run view.

New code imports :mod:`builder_ii.core.run_view`. The old names remain for one
compatibility release so existing STRATUM extensions and tests do not acquire a
flag-day migration. This module contains no projection logic.
"""

from builder_ii.core.run_view import (
    LIFECYCLE,
    Evidence,
    EvidenceState,
    RunView,
    project_run_view,
)

RunProjection = RunView
project_run = project_run_view

__all__ = [
    "LIFECYCLE",
    "Evidence",
    "EvidenceState",
    "RunProjection",
    "RunView",
    "project_run",
    "project_run_view",
]
