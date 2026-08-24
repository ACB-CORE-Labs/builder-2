"""
DeepSeek Harness / Goose ACP Compatibility Matrix and Threat Model.

This module defines the pinned constraints and authority ownership bounds
required for the DSH-0 read-only integration spike.
"""

from typing import Dict, List, Literal

class ThreatModelError(Exception):
    """Raised when a fail-closed constraint is violated."""
    pass

# Pinned dependencies for safe integration
# These bytes/digests must match before a governed run starts.
PINNED_MANIFEST: Dict[str, str] = {
    "goose_version": "v1.2.0",  # Example version, should be strictly enforced
    "acp_protocol_version": "0.1.0",
    "dsh_version": "developer-preview-0.1.0"
}

# The Authority Ownership Matrix enforces the boundaries of what DSH can and cannot do.
AUTHORITY_OWNERSHIP = {
    "target_profiles": "builder-II",
    "command_authority": "builder-II",
    "approvals": "builder-II",
    "agent_loop": "goose",
    "effectful_tools": "builder-II",
    "ui_projection": "deepseek-harness",
    "session_log": "observational",  # Non-authoritative
    "effect_history": "builder-II",
}

def verify_compatibility(env_info: Dict[str, str]) -> bool:
    """
    Verifies that the current environment matches the pinned manifest exactly.
    """
    for key, expected in PINNED_MANIFEST.items():
        actual = env_info.get(key)
        if actual != expected:
            raise ThreatModelError(f"Compatibility mismatch on {key}: expected {expected}, got {actual}")
    return True

def assert_authority(claimant: str, capability: str) -> None:
    """
    Asserts that the claimant is allowed to exercise the requested capability.
    """
    owner = AUTHORITY_OWNERSHIP.get(capability)
    if owner != claimant:
        raise ThreatModelError(f"Authority violation: {claimant} attempted to exercise {capability}. Owner is {owner}.")

