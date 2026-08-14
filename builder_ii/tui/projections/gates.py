"""HITL gate ceremony + Third Door projection."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Canonical 8 constraints (Builder's Signet / Third Door)
THIRD_DOOR_CONSTRAINTS: tuple[str, ...] = (
    "Documentation",
    "Tests",
    "CLI Surface",
    "Failure Mode",
    "Approval Boundary",
    "Output Artifact",
    "Rollback Path",
    "Verification Path",
)

#: All eight satisfied. The only state in which the door is not shut.
THIRD_DOOR_UNLOCKED = "unlocked"
#: At least one constraint was evaluated and came back False. Assessed, and refused.
THIRD_DOOR_LOCKED = "locked"
#: Some evidence, none of it refusing, not yet all eight. Shut, but nothing said no.
THIRD_DOOR_INCOMPLETE = "incomplete"
#: No constraint has any evidence either way. Shut because nobody has looked.
THIRD_DOOR_UNASSESSED = "unassessed"


def third_door_state(constraints: Mapping[str, bool | None]) -> str:
    """Classify the eight constraints into one of the four states above.

    The one place this is computed. It previously was not computed anywhere: `ThirdDoorGate.render`
    derived a verdict inline as `all(v is True) -> UNLOCKED else LOCKED`, and that binary is the
    defect. It collapses "assessed and refused" into "nobody has looked yet", which is precisely
    the distinction the widget's own docstring promises to keep ("Unevaluated (None) is not pass
    and not fail -- open slot"). Measured before this change: a checkout with a fully populated
    `.builder/artifacts` -- and every fresh clone -- rendered `VAULT LOCKED`, because no promotion
    readiness artifact exists to read. Locked on every machine, always, and never once because
    anything failed.

    That mattered beyond cosmetics. A mechanical lock bound to that verdict would have refused
    every operator on every host forever, and it would have been enforcing *absence of evidence* as
    *denial*. Any future lock binds here, to a state that distinguishes the two.

    `LOCKED` takes precedence over everything except nothing: one explicit refusal shuts the door
    regardless of how many other slots are still open. An unevaluated slot cannot un-refuse a
    refused one.
    """
    values = [constraints.get(name) for name in THIRD_DOOR_CONSTRAINTS]
    if any(v is False for v in values):
        return THIRD_DOOR_LOCKED
    if all(v is True for v in values):
        return THIRD_DOOR_UNLOCKED
    if all(v is None for v in values):
        return THIRD_DOOR_UNASSESSED
    return THIRD_DOOR_INCOMPLETE


@dataclass(frozen=True)
class ThirdDoorView:
    constraints: dict[str, bool | None]  # None = unevaluated
    source: str  # "readiness" | "unevaluated"

    @property
    def state(self) -> str:
        """One of the four `THIRD_DOOR_*` states, derived -- never stored.

        A property rather than a field so a view cannot be constructed whose recorded state
        disagrees with its own constraints. The drift this file just fixed was two places deriving
        the same verdict from different rules; a fifth copy stored in a field would be the same
        trap with a longer fuse.
        """
        return third_door_state(self.constraints)


def unassessed_third_door() -> ThirdDoorView:
    """The honest default: nothing looked at, nothing refused, nothing claimed."""
    constraints: dict[str, bool | None] = {name: None for name in THIRD_DOOR_CONSTRAINTS}
    return ThirdDoorView(constraints=constraints, source="unevaluated")


@dataclass(frozen=True)
class HitlProposalView:
    command: str
    tier: str
    authority: str
    effects: str
    digest: str  # real field or "—" — never synthesized
    artifact: dict[str, Any]
    path: str | None
    pending: bool


def project_third_door(artifacts_dir: Path | None = None) -> ThirdDoorView:
    """Project Third Door slots from promotion readiness if present; else all unevaluated."""
    unevaluated = {name: None for name in THIRD_DOOR_CONSTRAINTS}

    if artifacts_dir is None or not artifacts_dir.exists():
        return unassessed_third_door()

    readiness: dict[str, Any] | None = None
    for path in sorted(artifacts_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        kind = str(data.get("kind", ""))
        if "promotion_readiness" in kind:
            readiness = data
            break

    if readiness is None:
        return unassessed_third_door()

    # Map known fields conservatively — only mark True when explicitly satisfied.
    constraints: dict[str, bool | None] = dict(unevaluated)
    evidence = readiness.get("evidence") or readiness.get("gates") or readiness.get("required_gates")
    if isinstance(evidence, dict):
        mapping = {
            "Documentation": ("docs", "documentation"),
            "Tests": ("tests", "test"),
            "CLI Surface": ("cli", "command_surface", "command surface"),
            "Failure Mode": ("failure_mode", "failure mode"),
            "Approval Boundary": ("approval", "hitl", "approval_boundary"),
            "Output Artifact": ("output", "artifact", "output_artifact"),
            "Rollback Path": ("rollback", "rollback_path"),
            "Verification Path": ("verification", "verify", "verification_path"),
        }
        for label, keys in mapping.items():
            for key, val in evidence.items():
                key_l = str(key).lower().replace("-", "_")
                if any(k.replace(" ", "_") in key_l or k in key_l for k in keys):
                    if val is True or val == "satisfied" or val == "pass":
                        constraints[label] = True
                    elif val is False or val == "missing" or val == "fail":
                        constraints[label] = False
                    # else leave None (unevaluated)
    elif isinstance(evidence, list):
        # List of named gates with status objects — only mark when explicit
        for item in evidence:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("gate") or "").lower()
            status = item.get("status") or item.get("satisfied")
            for label in THIRD_DOOR_CONSTRAINTS:
                if label.lower().split()[0] in name or name in label.lower():
                    if status is True or status == "satisfied" or status == "pass":
                        constraints[label] = True
                    elif status is False or status == "missing" or status == "fail":
                        constraints[label] = False

    return ThirdDoorView(constraints=constraints, source="readiness")


def project_hitl_surface(artifacts_dir: Path | None) -> HitlProposalView | None:
    """Find a pending HITL-related artifact for ceremony display, if any."""
    if artifacts_dir is None or not artifacts_dir.exists():
        return None

    pending_kinds = (
        "hitl",
        "approval",
        "patch_proposal",
        "execution_candidate",
        "command_proposal",
    )
    candidates: list[tuple[float, Path, dict[str, Any]]] = []
    search_dirs = [artifacts_dir]
    hitl_dir = artifacts_dir.parent / "hitl"
    if hitl_dir.is_dir():
        search_dirs.append(hitl_dir)

    for directory in search_dirs:
        for path in directory.rglob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            kind = str(data.get("kind", "")).lower()
            if not any(frag in kind for frag in pending_kinds):
                continue
            state = str(data.get("state") or data.get("status") or "").upper()
            if state in ("REJECTED", "APPROVED", "APPLIED", "CLOSED"):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append((mtime, path, data))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    _mtime, path, data = candidates[0]

    # Digest: only show if the artifact itself carries one — never invent.
    digest = "—"
    for key in ("digest", "content_digest", "sha256", "artifact_digest"):
        val = data.get(key)
        if isinstance(val, str) and val and val != "—":
            digest = val
            break

    return HitlProposalView(
        command=str(data.get("command") or data.get("proposed_command") or "—"),
        tier=str(data.get("tier") or data.get("authority_tier") or "—"),
        authority=str(data.get("authority") or "HITL required"),
        effects=str(data.get("effects") or data.get("summary") or data.get("kind") or "—"),
        digest=digest,
        artifact=data,
        path=str(path),
        pending=True,
    )


def scan_pending_hitl(artifacts_dir: Path | None) -> tuple[bool, str]:
    """Return (gate_open, label) for the signal rail indicator.

    Closed state means no pending HITL JSON was found — not that governance is cleared.
    """
    view = project_hitl_surface(artifacts_dir)
    if view is None:
        return False, "NO PENDING HITL"
    label = view.command if view.command != "—" else (view.path or "pending HITL")
    return True, label[:48]
