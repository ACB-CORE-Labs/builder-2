"""Compatibility facade for the frontend-neutral run registry projection."""

from builder_ii.core.run_registry import (
    RunRegistryEntry,
    RunRegistryView,
    RunRosterView,
    RunRow,
    project_run_registry,
    project_run_roster,
)

__all__ = [
    "RunRegistryEntry",
    "RunRegistryView",
    "RunRosterView",
    "RunRow",
    "project_run_registry",
    "project_run_roster",
]
