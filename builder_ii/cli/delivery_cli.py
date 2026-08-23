"""Operator-facing guided delivery surface.

The command never mints approval.  It displays the next bounded action or
executes one action only when the operator supplies matching artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.delivery import (
    DELIVERY_ACTIONS,
    DeliveryError,
    DeliveryService,
    validate_delivery_action_request,
    validate_delivery_approval,
    validate_delivery_plan,
)
from builder_ii.governance.authority import enforce_command_authority

delivery_app = typer.Typer(name="builder deliver", help="Guided, digest-bound Git/GitHub delivery.")


def _load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise typer.BadParameter(f"artifact {path} must contain a JSON object")
    return value


@delivery_app.callback(invoke_without_command=True)
def deliver(
    plan: Path = typer.Option(..., "--plan", help="Exact delivery_plan artifact."),
    action: Optional[str] = typer.Option(None, "--action", help="Current action: commit, push, pr_create, or pr_update."),
    request: Optional[Path] = typer.Option(None, "--request", help="Exact delivery_action_request artifact."),
    approval: Optional[Path] = typer.Option(None, "--approval", help="Exact human delivery_approval artifact."),
    verification_receipt: Optional[Path] = typer.Option(None, "--verification-receipt", help="Exact successful receipt required before push."),
    push_receipt: Optional[Path] = typer.Option(None, "--push-receipt", help="Exact successful push receipt required before PR."),
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Target repository path."),
    execute: bool = typer.Option(False, "--execute", help="Execute exactly the supplied approved current action."),
) -> None:
    """Show the next delivery boundary, or execute one approved current effect."""
    enforce_command_authority("builder deliver")
    plan_data = _load(plan)
    plan_errors = validate_delivery_plan(plan_data)
    if plan_errors:
        echo_stdout(json.dumps({"status": "REFUSED", "kind": "builder_ii.delivery_boundary", "errors": plan_errors}, indent=2) + "\n")
        raise typer.Exit(1)
    if not execute:
        echo_stdout(json.dumps({
            "kind": "builder_ii.delivery_projection",
            "status": "READY",
            "plan_digest": plan_data["plan_digest"],
            "current_stage": "PLAN" if request is None else "APPROVE",
            "next_admissible_action": "materialize a digest-bound action request, then obtain its separate human approval",
            "actions": list(DELIVERY_ACTIONS),
            "artifact_is_authority": False,
        }, indent=2) + "\n")
        return
    if request is None or approval is None or not action:
        raise typer.BadParameter("--execute requires --action, --request, and --approval")
    if action not in DELIVERY_ACTIONS:
        raise typer.BadParameter(f"unsupported action {action}")
    request_data = _load(request)
    approval_data = _load(approval)
    request_errors = validate_delivery_action_request(request_data, plan_data)
    approval_errors = validate_delivery_approval(approval_data, request_data)
    if request_errors or approval_errors:
        echo_stdout(json.dumps({"status": "REFUSED", "request_errors": request_errors, "approval_errors": approval_errors}, indent=2) + "\n")
        raise typer.Exit(1)
    service = DeliveryService(repo)
    try:
        if action == "commit":
            receipt = service.execute_commit(plan_data, request_data, approval_data)
        elif action == "push":
            if verification_receipt is None:
                raise typer.BadParameter("push requires --verification-receipt")
            receipt = service.execute_push(plan_data, request_data, approval_data, verified_receipt=_load(verification_receipt))
        else:
            if push_receipt is None:
                raise typer.BadParameter("PR action requires --push-receipt")
            receipt = service.execute_pr(plan_data, request_data, approval_data, push_receipt=_load(push_receipt))
    except DeliveryError as exc:
        echo_stdout(json.dumps({"kind": "builder_ii.delivery_boundary", "status": "REFUSED", "error": str(exc), "artifact_is_authority": False}, indent=2) + "\n")
        raise typer.Exit(1) from exc
    echo_stdout(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if receipt.get("status") != "SUCCEEDED":
        raise typer.Exit(1)


if __name__ == "__main__":
    delivery_app()
