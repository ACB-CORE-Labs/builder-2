"""Target-profile isolation packages.

builder-II is a generic platform. Target-specific doctrine (e.g. CORE) lives under
this package only — never as generic platform identity or Workbench coupling.
"""

from __future__ import annotations

from builder_ii.targets.core import (
    CORE_TARGET_NAME,
    core_profile_block,
    doctor_core_profile,
    validate_core_profile_block,
)

__all__ = [
    "CORE_TARGET_NAME",
    "core_profile_block",
    "doctor_core_profile",
    "validate_core_profile_block",
]
