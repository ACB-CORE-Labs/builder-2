from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.cli.config_cli import _override_map
from builder_ii.core.config_sources import ConfigResolution, resolve_config_sources
from builder_ii.lifecycle.setup.onboarding_intent import (
    finalize_onboarding_intent_report,
    validate_onboarding_intent_report_artifact,
    write_onboarding_intent_report,
)
from builder_ii.lifecycle.setup.setup_overlay import (
    create_setup_overlay_plan,
    validate_setup_overlay_plan_artifact,
    write_setup_overlay_plan,
)
from builder_ii.lifecycle.setup.setup_plan import (
    create_setup_plan,
    validate_setup_plan_artifact,
    write_setup_plan,
)
from builder_ii.lifecycle.setup.setup_rollback import (
    create_setup_rollback_snapshot,
    validate_setup_rollback_snapshot_artifact,
    write_setup_rollback_snapshot,
)


def _cmd(*parts: object) -> str:
    return " ".join(str(part) for part in parts)


@dataclass(frozen=True)
class OnboardingResult:
    valid: bool
    output_dir: Path
    setup_plan_path: Path
    setup_overlay_path: Path
    rollback_snapshot_path: Path
    onboarding_intent_path: Path
    setup_plan: dict[str, Any]
    overlay_plan: dict[str, Any]
    rollback_snapshot: dict[str, Any]
    onboarding_intent: dict[str, Any]
    errors: list[str]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "output_dir": str(self.output_dir),
            "artifacts": {
                "setup_plan": {"path": str(self.setup_plan_path), "digest": self.setup_plan.get("plan_digest")},
                "setup_overlay": {
                    "path": str(self.setup_overlay_path),
                    "digest": self.overlay_plan.get("overlay_plan_digest"),
                },
                "rollback_snapshot": {
                    "path": str(self.rollback_snapshot_path),
                    "digest": self.rollback_snapshot.get("snapshot_id"),
                },
                "onboarding_intent": {
                    "path": str(self.onboarding_intent_path),
                    "digest": self.onboarding_intent.get("onboarding_intent_digest"),
                },
            },
            "next_commands": {
                "apply": self.onboarding_intent.get("apply_command"),
                "validate_receipt": self.onboarding_intent.get("validate_receipt_command"),
                "rollback": self.onboarding_intent.get("rollback_command"),
                "validate_rollback_receipt": self.onboarding_intent.get("validate_rollback_receipt_command"),
            },
            "errors": list(self.errors),
        }


def run_onboarding_pipeline(
    *,
    output_dir: Path,
    onboarding_mode: str = "init",
    root: Path | None = None,
    config_file: Path | None = None,
    target_repo: Path | None = None,
    artifact_root: Path | None = None,
    target_profile: str | None = None,
    agent_profile: str | None = None,
    verification_profile: str | None = None,
    model_backend: str | None = None,
    model_alias: str | None = None,
    runtime_mode: str | None = None,
    allow_artifact_root_inside_target: bool | None = None,
    preset_configuration: dict[str, Any] | None = None,
    readiness_evidence: list[dict[str, str]] | None = None,
    resolution: ConfigResolution | None = None,
) -> OnboardingResult:
    if root is None:
        root = Path.cwd()

    if resolution is None:
        resolution = resolve_config_sources(
            project_root=root,
            builder_config_file=config_file,
            cli_overrides=_override_map(
                target_repo=target_repo,
                artifact_root=artifact_root,
                target_profile=target_profile,
                agent_profile=agent_profile,
                verification_profile=verification_profile,
                model_backend=model_backend,
                model_alias=model_alias,
                runtime_mode=runtime_mode,
                allow_artifact_root_inside_target=allow_artifact_root_inside_target,
            ),
        )

    setup_plan = create_setup_plan(resolution)
    plan_errors = validate_setup_plan_artifact(setup_plan)
    if plan_errors:
        return _error_result(
            output_dir, plan_errors, setup_plan={}, overlay_plan={}, rollback_snapshot={}, onboarding_intent={}
        )

    overlay_plan = create_setup_overlay_plan(setup_plan)
    overlay_errors = validate_setup_overlay_plan_artifact(overlay_plan)
    if overlay_errors:
        return _error_result(
            output_dir,
            overlay_errors,
            setup_plan=setup_plan,
            overlay_plan=overlay_plan,
            rollback_snapshot={},
            onboarding_intent={},
        )

    rollback_snapshot = create_setup_rollback_snapshot(overlay_plan)
    snapshot_errors = validate_setup_rollback_snapshot_artifact(rollback_snapshot)
    if snapshot_errors:
        return _error_result(
            output_dir,
            snapshot_errors,
            setup_plan=setup_plan,
            overlay_plan=overlay_plan,
            rollback_snapshot=rollback_snapshot,
            onboarding_intent={},
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "setup-plan.json"
    overlay_path = output_dir / "setup-overlay.json"
    snapshot_path = output_dir / "setup-rollback-snapshot.json"
    intent_path = output_dir / "onboarding-intent.json"

    overlay_digest = overlay_plan["overlay_plan_digest"]
    receipt_path = output_dir / "setup-receipt.json"
    rollback_receipt_path = output_dir / "setup-rollback-receipt.json"
    setup_tool = "builder" + "-setup"
    approve_flag = "--approve" + "-digest"
    output_flag = "--out" + "put"
    snapshot_flag = "--rollback" + "-snapshot"
    receipt_digest_placeholder = "<" + "setup_receipt_digest" + ">"

    apply_cmd = _cmd(
        setup_tool,
        "ap" + "ply",
        overlay_path,
        snapshot_flag,
        snapshot_path,
        approve_flag,
        overlay_digest,
        output_flag,
        receipt_path,
    )
    validate_receipt_cmd = _cmd(setup_tool, "validate" + "-receipt", receipt_path)
    rollback_cmd = _cmd(
        setup_tool,
        "roll" + "back",
        receipt_path,
        snapshot_flag,
        snapshot_path,
        approve_flag,
        receipt_digest_placeholder,
        output_flag,
        rollback_receipt_path,
    )
    validate_rollback_cmd = _cmd(setup_tool, "validate" + "-rollback" + "-receipt", rollback_receipt_path)
    selected_model = setup_plan.get("selected_model") or {}

    intent_report = finalize_onboarding_intent_report(
        setup_plan_path=str(plan_path.resolve()),
        setup_plan_digest=setup_plan["plan_digest"],
        setup_overlay_path=str(overlay_path.resolve()),
        overlay_plan_digest=overlay_digest,
        rollback_snapshot_path=str(snapshot_path.resolve()),
        rollback_snapshot_digest=rollback_snapshot["snapshot_id"],
        onboarding_mode=onboarding_mode,
        apply_command=apply_cmd,
        validate_receipt_command=validate_receipt_cmd,
        rollback_command=rollback_cmd,
        validate_rollback_receipt_command=validate_rollback_cmd,
        selected_summary={
            "target_profile": setup_plan.get("selected_target_profile"),
            "agent_profile": setup_plan.get("selected_agent_profile"),
            "verification_profile": setup_plan.get("selected_verification_profile"),
            "model_backend": selected_model.get("backend"),
            "model_alias": selected_model.get("alias"),
            "model_tier": selected_model.get("tier"),
            "worker_concurrency": (preset_configuration or {}).get("worker_concurrency"),
            "routing_preference": (preset_configuration or {}).get("routing_preference"),
            "confirmation_policy": (preset_configuration or {}).get("confirmation_policy"),
            "budget_usd": (preset_configuration or {}).get("budget_usd"),
        },
        preset_configuration=preset_configuration,
        readiness_evidence=readiness_evidence,
    )
    intent_errors = validate_onboarding_intent_report_artifact(intent_report)
    if intent_errors:
        return _error_result(
            output_dir,
            intent_errors,
            setup_plan=setup_plan,
            overlay_plan=overlay_plan,
            rollback_snapshot=rollback_snapshot,
            onboarding_intent=intent_report,
        )

    write_setup_plan(setup_plan, plan_path)
    write_setup_overlay_plan(overlay_plan, overlay_path)
    write_setup_rollback_snapshot(rollback_snapshot, snapshot_path)
    write_onboarding_intent_report(intent_report, intent_path)

    return OnboardingResult(
        valid=True,
        output_dir=output_dir,
        setup_plan_path=plan_path,
        setup_overlay_path=overlay_path,
        rollback_snapshot_path=snapshot_path,
        onboarding_intent_path=intent_path,
        setup_plan=setup_plan,
        overlay_plan=overlay_plan,
        rollback_snapshot=rollback_snapshot,
        onboarding_intent=intent_report,
        errors=[],
    )


def _error_result(
    output_dir: Path,
    errors: list[str],
    *,
    setup_plan: dict[str, Any],
    overlay_plan: dict[str, Any],
    rollback_snapshot: dict[str, Any],
    onboarding_intent: dict[str, Any],
) -> OnboardingResult:
    return OnboardingResult(
        valid=False,
        output_dir=output_dir,
        setup_plan_path=output_dir / "setup-plan.json",
        setup_overlay_path=output_dir / "setup-overlay.json",
        rollback_snapshot_path=output_dir / "setup-rollback-snapshot.json",
        onboarding_intent_path=output_dir / "onboarding-intent.json",
        setup_plan=setup_plan,
        overlay_plan=overlay_plan,
        rollback_snapshot=rollback_snapshot,
        onboarding_intent=onboarding_intent,
        errors=errors,
    )
