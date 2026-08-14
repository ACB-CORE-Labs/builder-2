"""Policy evaluation: check/enforce command authority against the registry."""
from __future__ import annotations

from dataclasses import dataclass

from builder_ii.governance.authority.assurance import (
    BLOCKED_BY_EVIDENCE,
    SAFETY_CRITICAL_PROHIBITED,
    AssuranceState,
)
from builder_ii.governance.authority.authority_registry import get_command_record
from builder_ii.governance.authority.signet_verifier import assurance_state_for_record
from builder_ii.governance.authority.tier_definitions import (
    MODE_FORBIDDEN_UNPROMOTED,
    MODE_HITL_ARTIFACT_REQUIRED,
    STATE_FORBIDDEN_UNPROMOTED,
    TIER_4,
)


class CommandAuthorityError(PermissionError):
    """Raised when a command attempts an unregistered or under-classified effect."""


@dataclass(frozen=True)
class CommandAuthorityDecision:
    command_name: str
    allowed: bool
    tier: str
    promotion_state: str
    approval_mode: str
    assurance_state: AssuranceState
    requested_effects: tuple[str, ...]
    reasons: tuple[str, ...]
    capability_ref: str = ""

    @property
    def command(self) -> str:
        return self.command_name

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ""

    @property
    def allowed_effects(self) -> tuple[str, ...]:
        record = get_command_record(self.command_name)
        if record is None:
            return ()
        return tuple(
            effect for effect, flags in _EFFECT_FLAGS.items() if any(bool(getattr(record, flag)) for flag in flags)
        )

    @property
    def denied_effects(self) -> tuple[str, ...]:
        allowed = self.allowed_effects
        return tuple(eff for eff in self.requested_effects if eff not in allowed)

    def to_evidence(self) -> dict[str, object]:
        return {
            "kind": "builder_ii.command_authority_decision",
            "command": self.command,
            "allowed": self.allowed,
            "reason": self.reason,
            "tier": self.tier,
            "promotion_state": self.promotion_state,
            "approval_mode": self.approval_mode,
            "allowed_effects": list(self.allowed_effects),
            "denied_effects": list(self.denied_effects),
            "capability_ref": self.capability_ref,
            "fail_closed": not self.allowed,
        }


_EFFECT_FLAGS: dict[str, tuple[str, ...]] = {
    "runtime_start": ("allows_runtime_start",),
    "process_control": ("allows_process_control",),
    "model_execution": ("allows_model_execution",),
    "shell_execution": ("allows_shell_execution",),
    "source_write": ("allows_source_writes",),
    "source_writes": ("allows_source_writes",),
    "patch_application": ("allows_source_writes",),
    "git_mutation": ("allows_git_mutation",),
    "memory_mutation": ("allows_memory_mutation",),
    "artifact_write": ("allows_artifact_writes",),
    "artifact_writes": ("allows_artifact_writes",),
    "state_write": ("allows_state_writes",),
    "state_writes": ("allows_state_writes",),
    "readonly_subprocess": ("allows_readonly_subprocess",),
    "external_tool": ("allows_external_tool_invocation",),
    "external_tool_invocation": ("allows_external_tool_invocation",),
}


def check_command_authority(
    command_name: str,
    *,
    requested_effects: tuple[str, ...] = (),
    approval_ref: str | None = None,
    safety_critical_claim: bool = False,
    hitl_bound: bool | None = None,
    capability_ref: str = "",
    subject_digest: str | None = None,
) -> CommandAuthorityDecision:
    record = get_command_record(command_name)
    if record is None:
        return CommandAuthorityDecision(
            command_name=command_name,
            allowed=False,
            tier=TIER_4,
            promotion_state=STATE_FORBIDDEN_UNPROMOTED,
            approval_mode=MODE_FORBIDDEN_UNPROMOTED,
            assurance_state=BLOCKED_BY_EVIDENCE,
            requested_effects=tuple(requested_effects),
            reasons=(f"command is not registered in COMMAND_AUTHORITY_REGISTRY: {command_name}",),
            capability_ref=capability_ref,
        )

    reasons: list[str] = []
    if safety_critical_claim:
        reasons.append("life-safety or safety-critical authority is prohibited by builder-II")
    if record.tier == TIER_4 or record.promotion_state == STATE_FORBIDDEN_UNPROMOTED:
        reasons.append("command is forbidden or unpromoted")

    # A record nobody declared cannot certify an effect. `_generate_extra_records` copied this
    # record's capability flags from whichever declared command is a word-prefix of its name; that
    # is a naming coincidence, and a coincidence is not evidence. Deny-only: an inherited record can
    # lose a permission it never earned, never gain one.
    if requested_effects and record.authority_is_inherited:
        reasons.append(
            f"command's authority is inherited from `{record.inherited_from}`, not declared; "
            f"an undeclared command cannot certify a requested effect"
        )

    for effect in requested_effects:
        flags = _EFFECT_FLAGS.get(effect)
        if flags is None:
            reasons.append(f"unknown requested effect: {effect}")
            continue
        if not any(bool(getattr(record, flag)) for flag in flags):
            reasons.append(f"command is not classified for requested effect: {effect}")

    if record.approval_mode == MODE_HITL_ARTIFACT_REQUIRED:
        if not approval_ref:
            reasons.append("command requires a HITL approval artifact reference")
        else:
            try:
                import json
                import time
                from pathlib import Path
                approval_path = Path(approval_ref)
                if not approval_path.exists():
                    reasons.append("Approval file does not exist")
                else:
                    approval = json.loads(approval_path.read_text(encoding="utf-8"))
                    kind = approval.get("kind")

                    if not kind:
                        reasons.append("Invalid patch approval: unknown kind None")

                    # Verify expiry
                    expires_at = approval.get("expires_at")
                    if expires_at:
                        # Some approvals use ISO strings (verification), some use timestamps (model call)
                        if isinstance(expires_at, str):
                            from datetime import datetime, timezone
                            if expires_at.endswith("Z"):
                                expires_at = expires_at[:-1] + "+00:00"
                            dt = datetime.fromisoformat(expires_at)
                            now_utc = datetime.now(timezone.utc)
                            if now_utc > dt:
                                reasons.append("Patch approval has expired")
                        elif isinstance(expires_at, (int, float)):
                            if expires_at < int(time.time()):
                                reasons.append("Patch approval has expired")

                    # Generic binding check
                    if subject_digest:
                        bound = False
                        for key in ["patch_digest", "proposal_digest", "plan_digest", "prompt_digest", "candidate_digest", "manifest_digest", "approved_model_id", "subject_digest"]:
                            val = approval.get(key)
                            if val and val == subject_digest:
                                bound = True
                                break
                        if not bound:
                            reasons.append("Approval is not bound to this proposal: digest mismatch")
            except Exception as e:
                reasons.append(f"Invalid patch approval: {e}")

    assurance = SAFETY_CRITICAL_PROHIBITED if safety_critical_claim else assurance_state_for_record(record)
    return CommandAuthorityDecision(
        command_name=command_name,
        allowed=not reasons,
        tier=record.tier,
        promotion_state=record.promotion_state,
        approval_mode=record.approval_mode,
        assurance_state=assurance,
        requested_effects=tuple(requested_effects),
        reasons=tuple(reasons),
        capability_ref=capability_ref,
    )


def enforce_command_authority(
    command_name: str,
    *,
    requested_effects: tuple[str, ...] = (),
    approval_ref: str | None = None,
    safety_critical_claim: bool = False,
    hitl_bound: bool | None = None,
    capability_ref: str = "",
    subject_digest: str | None = None,
) -> CommandAuthorityDecision:
    decision = check_command_authority(
        command_name,
        requested_effects=requested_effects,
        approval_ref=approval_ref,
        safety_critical_claim=safety_critical_claim,
        hitl_bound=hitl_bound,
        capability_ref=capability_ref,
        subject_digest=subject_digest,
    )
    if not decision.allowed:
        raise CommandAuthorityError("; ".join(decision.reasons))
    return decision

