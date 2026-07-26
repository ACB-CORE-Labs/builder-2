"""Logic for evaluating user project state and returning an ordered list of onboarding commands."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from builder_ii.lifecycle.setup.operator_next import create_operator_next_action_report


def get_onboarding_state() -> dict[str, Any]:
    """Evaluate the user's project setup state and return the next recommended command."""

    # 1. Check if .env exists
    if not os.path.exists(".env"):
        return {
            "title": "Initialize Configuration",
            "description": "The first step is to configure your environment variables.",
            "safe_command": "cp .env.example .env",
            "state": "NO_ENV"
        }

    # 2. Check if setup plan exists (builder init generates this)
    artifact_root = Path(".builder/artifacts")
    if not (artifact_root / "setup-plan.json").exists():
        return {
            "title": "Create Initialization Plan",
            "description": "Generate the initial setup plan for your project.",
            "safe_command": "builder init",
            "state": "NO_PLAN"
        }

    # 3. Check if setup receipt exists (builder-setup apply generates this)
    if not (artifact_root / "setup-receipt.json").exists():
        return {
            "title": "Apply Initialization Plan",
            "description": "Apply the setup plan to initialize your artifact directories.",
            "safe_command": "builder-setup apply",
            "state": "NO_RECEIPT"
        }

    # 4. Check if session exists
    session_root = Path(".builder/session")
    if not session_root.exists() or not list(session_root.iterdir()):
        return {
            "title": "Prepare First Session Package",
            "description": "Create your first governed session package to fill the artifact chain.",
            "safe_command": 'builder-session prepare-package generic -o .builder/session --task "first governed session"',
            "state": "NO_SESSION"
        }

    # 5. If everything is done, recommend normal platform operations
    return {
        "title": "Open Stratum",
        "description": "Your project is initialized. Open Stratum to inspect the artifact chain and compose commands.",
        "safe_command": "builder stratum",
        "state": "READY"
    }


def create_user_next_action_report() -> dict[str, Any]:
    """Generates the next action report prioritizing user onboarding over platform matrix."""
    onboarding = get_onboarding_state()

    if onboarding["state"] != "READY":
        return {
            "ordered_next_actions": [
                {
                    "capability": "Project Setup: " + onboarding["title"],
                    "state": onboarding["state"],
                    "safe_commands": [onboarding["safe_command"]],
                    "description": onboarding["description"]
                }
            ]
        }

    # If the user is fully onboarded, we check if they are missing core platform development steps.
    try:
        report = create_operator_next_action_report()
        actions = report.get("ordered_next_actions", [])
        if actions:
            # If the only recommendation is to look at the matrix, the user is likely not a core developer
            # or they have finished their core work. Suppress this for normal operators.
            if actions[0].get("safe_commands") == ["builder-platform matrix"]:
                return {"ordered_next_actions": []}
            return report
    except Exception:
        pass

    return {"ordered_next_actions": []}
