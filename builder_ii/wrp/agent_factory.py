"""AgentFactory (MoIRA reference) — lifecycle records + optional earned seam binding.

W.5 extends P2.5 plan-only with explicit spawn/retire *records*: role binding,
task binding, ExperienceStore digest linkage, and deterministic lifecycle proofs.

Honesty pins ≠ non-implementation (see ``docs/HONESTY_PINS_VS_IMPLEMENTATION.md``):
- **Default** records claim no execution: ``spawn_executed=false``,
  ``runtime_binding=UNBOUND`` — because no seam work was performed.
- **Earned** records may set ``spawn_executed=true`` / ``SEAM_BOUND`` when
  digest-bound evidence from the governed subagent seam is supplied.
- Pins still reject *false* claims (executed=true without evidence).
- ``process_spawn`` stays false (no OS process fork); ``grants_authority`` false;
  global S3 enablement is a separate ceremony surface (``s3_enablement.py``).
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from builder_ii.config_schema import attach_digest
from builder_ii.wrp.artifacts import (
    AGENT_FACTORY_PLAN_KIND,
    AGENT_LIFECYCLE_PROOF_KIND,
    AGENT_LIFECYCLE_RECORD_KIND,
    base_envelope,
    finalize_wrp_artifact,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.experience_store import append_exemplar, create_experience_store
from builder_ii.wrp.spaces import AgentPoint

_SEAM_GATEWAY_MODES = frozenset({"invoke_local", "invoke_cloud"})
_ALLOWED_PLAN_ACTIONS = frozenset({"register_plan", "retire_plan"})
_ALLOWED_LIFECYCLE_ACTIONS = frozenset({"spawn", "retire"})
_ALLOWED_ROLES = frozenset(
    {
        "code_reviewer",
        "patch_planner",
        "verification_planner",
        "repo_mapper",
        "maker_structural",
        "maker_unit",
        "governor_architecture",
        "governor_security",
    }
)

# Fixed proof fixtures (deterministic; no wall-clock, no host entropy).
_PROOF_CASES: tuple[tuple[str, str], ...] = (
    ("code_reviewer", "review agent_factory lifecycle honesty bounds"),
    ("governor_architecture", "architecture gate for modular expert binding"),
)


def _deterministic_agent_id(*, role: str, task: str, action: str = "spawn") -> str:
    payload = f"wrp.agent_factory.v1|{action}|{role}|{task}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _role_to_agent_point(role: str, *, model_family: str = "validation-only") -> AgentPoint:
    platform = "governor" if role.startswith("governor") else "maker"
    if role in {"code_reviewer", "verification_planner"}:
        platform = "governor"
    return AgentPoint(
        role=role,
        reasoning_coverage=0.7,
        tool_coverage=0.5,
        model_family=model_family,
        platform=platform,
    )


def _experience_binding(
    *,
    store: dict[str, Any] | None,
    agent_id: str,
    action: str,
    success: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Link optional ExperienceStore; never grants live routing.

    Returns (binding_meta, updated_store_or_none).
    """
    if store is None:
        return (
            {
                "bound": False,
                "store_id": None,
                "parent_store_digest": None,
                "updated_store_digest": None,
                "exemplar_appended": False,
                "updates_live_routing": False,
                "grants_authority": False,
            },
            None,
        )
    parent = store.get("digest")
    if not isinstance(parent, str) or len(parent) != 64:
        # Finalize a copy so digest linkage is always available for proofs.
        store = finalize_wrp_artifact(dict(store))
        parent = store["digest"]
    updated = append_exemplar(
        store,
        trajectory_id=f"lifecycle:{action}:{agent_id}",
        success=success,
        error_signal=0.0 if success else 1.0,
        features={"lifecycle": 1.0, "action_spawn": 1.0 if action == "spawn" else 0.0},
        notes=f"AgentFactory {action} record (validation_only; not runtime spawn)",
    )
    return (
        {
            "bound": True,
            "store_id": store.get("store_id"),
            "parent_store_digest": parent,
            "updated_store_digest": updated.get("digest"),
            "exemplar_appended": True,
            "updates_live_routing": False,
            "grants_authority": False,
        },
        updated,
    )


def plan_agent_lifecycle(
    *,
    agents: list[AgentPoint],
    action: str = "register_plan",
) -> dict[str, Any]:
    """P2.5 plan-only surface (retained)."""
    if action not in _ALLOWED_PLAN_ACTIONS:
        raise ValueError("action must be register_plan or retire_plan")
    return base_envelope(
        kind=AGENT_FACTORY_PLAN_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_plan_only",
        extra={
            "action": action,
            "agents": [a.to_jsonable() for a in agents],
            "spawn_permitted": False,
            "spawn_executed": False,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
        },
    )


def _normalize_seam_execution(seam_execution: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Validate earned-execution evidence; return normalized dict or None."""
    if seam_execution is None:
        return None
    if not isinstance(seam_execution, Mapping):
        raise ValueError("seam_execution must be a mapping when provided")
    loop_digest = seam_execution.get("subagent_loop_digest") or seam_execution.get("loop_digest")
    plan_digest = seam_execution.get("plan_digest")
    approved_by = str(seam_execution.get("approved_by") or "").strip()
    gateway_mode = str(seam_execution.get("gateway_mode") or "").strip()
    steps = seam_execution.get("steps_executed")
    if not isinstance(loop_digest, str) or len(loop_digest) != 64:
        raise ValueError("seam_execution.subagent_loop_digest must be a 64-char hex digest")
    if not isinstance(plan_digest, str) or len(plan_digest) != 64:
        raise ValueError("seam_execution.plan_digest must be a 64-char hex digest")
    if not approved_by:
        raise ValueError("seam_execution.approved_by is required for earned spawn_executed")
    if gateway_mode not in _SEAM_GATEWAY_MODES:
        raise ValueError(
            f"seam_execution.gateway_mode must be one of {sorted(_SEAM_GATEWAY_MODES)}"
        )
    if not isinstance(steps, int) or steps < 1:
        raise ValueError("seam_execution.steps_executed must be an int >= 1")
    return {
        "subagent_loop_digest": loop_digest,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "gateway_mode": gateway_mode,
        "steps_executed": steps,
        "kill_switch_armed": bool(seam_execution.get("kill_switch_armed")),
        "uses_seam": True,
        "grants_authority": False,
    }


def spawn_agent(
    *,
    role: str,
    task: str,
    model_family: str = "validation-only",
    experience_store: dict[str, Any] | None = None,
    agent_id: str | None = None,
    seam_execution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit a lifecycle spawn record.

    Default (no ``seam_execution``): honesty-default — ``spawn_executed=false``,
    validation-only claim. This is not a ban on implementing execution; it is
    the correct claim when no seam work happened.

    With ``seam_execution`` evidence from the governed subagent loop: earned
    ``spawn_executed=true`` and ``runtime_binding=SEAM_BOUND``. Still not an OS
    process spawn and not global S3 enablement.
    """
    role = role.strip()
    task = task.strip()
    if not role:
        raise ValueError("role must be non-empty")
    if not task:
        raise ValueError("task must be non-empty")
    if role not in _ALLOWED_ROLES:
        raise ValueError(f"role must be one of {sorted(_ALLOWED_ROLES)}")

    seam = _normalize_seam_execution(seam_execution)
    earned = seam is not None

    agent = _role_to_agent_point(role, model_family=model_family)
    aid = agent_id or _deterministic_agent_id(role=role, task=task, action="spawn")
    binding, _updated = _experience_binding(
        store=experience_store, agent_id=aid, action="spawn", success=True
    )
    return base_envelope(
        kind=AGENT_LIFECYCLE_RECORD_KIND,
        artifact_state="HITL_SEAM_BOUND" if earned else "VALIDATION_ONLY",
        # Earned path reuses wrp_hitl_live_lane (HITL-bounded seam work), not a new authority tier.
        capability_state="wrp_hitl_live_lane" if earned else "wrp_validation_only",
        extra={
            "action": "spawn",
            "agent_id": aid,
            "role": role,
            "task": task,
            "agent": agent.to_jsonable(),
            "role_binding": {
                "role": role,
                "platform": agent.platform,
                "model_family": agent.model_family,
                "bound": True,
            },
            "experience_binding": binding,
            "seam_execution": seam,
            "spawn_permitted": earned,
            "spawn_executed": earned,
            "runtime_binding": "SEAM_BOUND" if earned else "UNBOUND",
            "grants_authority": False,
            "s3_enabled": False,
            "process_spawn": False,
            "notes": (
                "Earned seam-bound lifecycle spawn: subagent loop evidence attached. "
                "Not an OS process fork; not global S3 enablement; not authority grant."
                if earned
                else (
                    "Default lifecycle spawn *record* (no seam evidence). "
                    "Honesty-default spawn_executed=false does not forbid implementing "
                    "or later binding a governed seam execution path."
                )
            ),
        },
    )
def retire_agent(
    *,
    spawn_record: dict[str, Any],
    reason: str = "task_complete",
    experience_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """W.5: emit a lifecycle *retire record* bound to a prior spawn digest."""
    errors = validate_agent_lifecycle_record(spawn_record)
    if errors:
        raise ValueError(f"invalid spawn record: {'; '.join(errors)}")
    if spawn_record.get("action") != "spawn":
        raise ValueError("retire requires a spawn lifecycle record")
    agent_id = spawn_record["agent_id"]
    role = spawn_record["role"]
    task = str(spawn_record.get("task") or "")
    binding, _updated = _experience_binding(
        store=experience_store, agent_id=str(agent_id), action="retire", success=True
    )
    earned = spawn_record.get("spawn_executed") is True
    return base_envelope(
        kind=AGENT_LIFECYCLE_RECORD_KIND,
        artifact_state=str(spawn_record.get("artifact_state") or "VALIDATION_ONLY"),
        capability_state=str(spawn_record.get("capability_state") or "wrp_validation_only"),
        extra={
            "action": "retire",
            "agent_id": agent_id,
            "role": role,
            "task": task,
            "reason": reason,
            "spawn_digest": spawn_record.get("digest"),
            "agent": spawn_record.get("agent"),
            "role_binding": spawn_record.get("role_binding"),
            "experience_binding": binding,
            "seam_execution": spawn_record.get("seam_execution"),
            "spawn_permitted": bool(spawn_record.get("spawn_permitted")),
            "spawn_executed": bool(spawn_record.get("spawn_executed")),
            "runtime_binding": str(spawn_record.get("runtime_binding") or "UNBOUND"),
            "grants_authority": False,
            "s3_enabled": False,
            "process_spawn": False,
            "notes": (
                "Lifecycle retire for seam-bound spawn; does not kill OS processes."
                if earned
                else (
                    "Lifecycle retire *record* only. Does not kill processes; "
                    "pairs with spawn digest for replay proofs."
                )
            ),
        },
    )

def prove_agent_lifecycle() -> dict[str, Any]:
    """Deterministic spawn→retire proof for fixed roles; emits lifecycle proof report."""
    rows: list[dict[str, Any]] = []
    for role, task in _PROOF_CASES:
        # Unbound store path: digests must replay bit-identically.
        spawn = spawn_agent(role=role, task=task)
        retire = retire_agent(spawn_record=spawn, reason="proof_complete")
        ok = (
            spawn.get("action") == "spawn"
            and retire.get("action") == "retire"
            and spawn.get("spawn_executed") is False
            and retire.get("spawn_executed") is False
            and spawn.get("spawn_permitted") is False
            and retire.get("spawn_permitted") is False
            and spawn.get("runtime_binding") == "UNBOUND"
            and retire.get("runtime_binding") == "UNBOUND"
            and spawn.get("grants_authority") is False
            and retire.get("grants_authority") is False
            and retire.get("spawn_digest") == spawn.get("digest")
            and isinstance(spawn.get("digest"), str)
            and len(spawn["digest"]) == 64
            and isinstance(retire.get("digest"), str)
            and len(retire["digest"]) == 64
            and validate_agent_lifecycle_record(spawn) == []
            and validate_agent_lifecycle_record(retire) == []
        )
        replay = spawn_agent(role=role, task=task)
        replay_ok = (
            replay.get("agent_id") == spawn.get("agent_id")
            and replay.get("digest") == spawn.get("digest")
        )
        rows.append(
            {
                "role": role,
                "task": task,
                "agent_id": spawn.get("agent_id"),
                "spawn_digest": spawn.get("digest"),
                "retire_digest": retire.get("digest"),
                "ok": ok and replay_ok,
                "replay_ok": replay_ok,
                "spawn_executed": False,
                "runtime_binding": "UNBOUND",
            }
        )

    # Separate ExperienceStore integration proof (immutable append + digest bind).
    store = create_experience_store(store_id="agent_lifecycle_proof")
    role0, task0 = _PROOF_CASES[0]
    bound_spawn = spawn_agent(role=role0, task=task0, experience_store=store)
    exp_ok = (
        bound_spawn.get("experience_binding", {}).get("bound") is True
        and bound_spawn.get("experience_binding", {}).get("exemplar_appended") is True
        and bound_spawn.get("experience_binding", {}).get("updates_live_routing") is False
        and bound_spawn.get("spawn_executed") is False
        and validate_agent_lifecycle_record(bound_spawn) == []
    )
    # Thread store via the binding's parent digest path for retire.
    store_after = append_exemplar(
        finalize_wrp_artifact(dict(store)),
        trajectory_id=f"lifecycle:spawn:{bound_spawn['agent_id']}",
        success=True,
        error_signal=0.0,
        features={"lifecycle": 1.0, "action_spawn": 1.0},
        notes="AgentFactory spawn record (validation_only; not runtime spawn)",
    )
    bound_retire = retire_agent(
        spawn_record=bound_spawn, reason="proof_complete", experience_store=store_after
    )
    exp_ok = exp_ok and bound_retire.get("experience_binding", {}).get("bound") is True
    store_final = append_exemplar(
        store_after,
        trajectory_id=f"lifecycle:retire:{bound_spawn['agent_id']}",
        success=True,
        error_signal=0.0,
        features={"lifecycle": 1.0, "action_spawn": 0.0},
        notes="AgentFactory retire record (validation_only; not runtime spawn)",
    )

    all_ok = bool(rows) and all(r["ok"] for r in rows) and exp_ok
    return attach_digest(
        {
            "kind": AGENT_LIFECYCLE_PROOF_KIND,
            "schema_version": 1,
            "artifact_state": "VALIDATION_ONLY",
            "ok": all_ok,
            "cases": rows,
            "case_count": len(rows),
            "experience_store_bound": exp_ok,
            "experience_store_id": store_final.get("store_id"),
            "experience_store_digest": store_final.get("digest"),
            "experience_exemplar_count": len(store_final.get("exemplars") or []),
            "spawn_permitted": False,
            "spawn_executed": False,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
            "s3_enabled": False,
            "process_spawn": False,
            "notes": (
                "W.5 AgentFactory lifecycle proof: deterministic spawn/retire records "
                "with ExperienceStore exemplar linkage. Not S3 enablement; not process spawn."
            ),
        }
    )


class AgentFactory:
    """MoIRA-shaped factory: default validation records + optional earned seam binding."""

    def __init__(self, *, experience_store: dict[str, Any] | None = None) -> None:
        self._store = experience_store

    def spawn(
        self,
        *,
        role: str,
        task: str,
        model_family: str = "validation-only",
        agent_id: str | None = None,
        seam_execution: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return spawn_agent(
            role=role,
            task=task,
            model_family=model_family,
            experience_store=self._store,
            agent_id=agent_id,
            seam_execution=seam_execution,
        )

    def retire(
        self,
        *,
        spawn_record: dict[str, Any],
        reason: str = "task_complete",
    ) -> dict[str, Any]:
        return retire_agent(
            spawn_record=spawn_record,
            reason=reason,
            experience_store=self._store,
        )


def validate_agent_factory_plan(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=AGENT_FACTORY_PLAN_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("spawn_permitted") is not False:
        errors.append("spawn_permitted must be false")
    if record.get("runtime_binding") != "UNBOUND":
        errors.append("runtime_binding must be UNBOUND")
    return errors


def validate_agent_lifecycle_record(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=AGENT_LIFECYCLE_RECORD_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("action") not in _ALLOWED_LIFECYCLE_ACTIONS:
        errors.append("action must be spawn or retire")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("s3_enabled") is not False:
        errors.append("s3_enabled must be false")
    if record.get("process_spawn") is not False:
        errors.append("process_spawn must be false")

    executed = record.get("spawn_executed")
    permitted = record.get("spawn_permitted")
    binding_rt = record.get("runtime_binding")
    if executed is True:
        # Earned path: evidence required; pins reject *false* claims only.
        if permitted is not True:
            errors.append("spawn_permitted must be true when spawn_executed is true")
        if binding_rt != "SEAM_BOUND":
            errors.append("runtime_binding must be SEAM_BOUND when spawn_executed is true")
        seam = record.get("seam_execution")
        if not isinstance(seam, dict):
            errors.append("seam_execution is required when spawn_executed is true")
        else:
            if not isinstance(seam.get("subagent_loop_digest"), str) or len(seam["subagent_loop_digest"]) != 64:
                errors.append("seam_execution.subagent_loop_digest must be a 64-char digest")
            if not isinstance(seam.get("plan_digest"), str) or len(seam["plan_digest"]) != 64:
                errors.append("seam_execution.plan_digest must be a 64-char digest")
            if not str(seam.get("approved_by") or "").strip():
                errors.append("seam_execution.approved_by is required when spawn_executed is true")
            if seam.get("gateway_mode") not in _SEAM_GATEWAY_MODES:
                errors.append(
                    f"seam_execution.gateway_mode must be one of {sorted(_SEAM_GATEWAY_MODES)}"
                )
            if not isinstance(seam.get("steps_executed"), int) or seam["steps_executed"] < 1:
                errors.append("seam_execution.steps_executed must be int >= 1")
    elif executed is False:
        if permitted is not False:
            errors.append("spawn_permitted must be false when spawn_executed is false")
        if binding_rt != "UNBOUND":
            errors.append("runtime_binding must be UNBOUND when spawn_executed is false")
    else:
        errors.append("spawn_executed must be a bool")

    if not isinstance(record.get("agent_id"), str) or not record.get("agent_id"):
        errors.append("agent_id must be a non-empty string")
    if not isinstance(record.get("role"), str) or not record.get("role"):
        errors.append("role must be a non-empty string")
    if record.get("action") == "retire":
        dig = record.get("spawn_digest")
        if not isinstance(dig, str) or len(dig) != 64:
            errors.append("retire record requires 64-char spawn_digest")
    binding = record.get("experience_binding")
    if not isinstance(binding, dict):
        errors.append("experience_binding must be an object")
    elif binding.get("updates_live_routing") is not False:
        errors.append("experience_binding.updates_live_routing must be false")
    elif binding.get("grants_authority") is not False:
        errors.append("experience_binding.grants_authority must be false")
    return errors


def validate_agent_lifecycle_proof(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["agent lifecycle proof must be a JSON object"]
    if record.get("kind") != AGENT_LIFECYCLE_PROOF_KIND:
        errors.append(f"kind must be {AGENT_LIFECYCLE_PROOF_KIND}")
    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if record.get("spawn_permitted") is not False:
        errors.append("spawn_permitted must be false")
    if record.get("spawn_executed") is not False:
        errors.append("spawn_executed must be false")
    if record.get("runtime_binding") != "UNBOUND":
        errors.append("runtime_binding must be UNBOUND")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("s3_enabled") is not False:
        errors.append("s3_enabled must be false")
    if record.get("process_spawn") is not False:
        errors.append("process_spawn must be false")
    if not isinstance(record.get("cases"), list):
        errors.append("cases must be a list")
    digest = record.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("digest must be a 64-char hex sha256")
    else:
        from builder_ii.config_schema import digest_jsonable

        if digest != digest_jsonable(record):
            errors.append("digest mismatch")
    return errors
