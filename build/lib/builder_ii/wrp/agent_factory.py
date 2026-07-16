"""AgentFactory (MoIRA reference) — lifecycle records only, no free spawn.

W.5 extends P2.5 plan-only with explicit spawn/retire *records*: role binding,
task binding, ExperienceStore digest linkage, and deterministic lifecycle proofs.

Honesty boundaries (pinned):
- spawn_permitted=false, spawn_executed=false always
- runtime_binding=UNBOUND always
- grants_authority=false; no process/agent runtime; not S3 multi-agent enablement
- ExperienceStore integration is digest-bound record linkage / immutable append only
"""

from __future__ import annotations

import hashlib
from typing import Any

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


def spawn_agent(
    *,
    role: str,
    task: str,
    model_family: str = "validation-only",
    experience_store: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """W.5: emit a lifecycle *spawn record* (not a process spawn).

    spawn_executed is always false. ExperienceStore may be bound by digest only.
    """
    role = role.strip()
    task = task.strip()
    if not role:
        raise ValueError("role must be non-empty")
    if not task:
        raise ValueError("task must be non-empty")
    if role not in _ALLOWED_ROLES:
        raise ValueError(f"role must be one of {sorted(_ALLOWED_ROLES)}")

    agent = _role_to_agent_point(role, model_family=model_family)
    aid = agent_id or _deterministic_agent_id(role=role, task=task, action="spawn")
    binding, _updated = _experience_binding(
        store=experience_store, agent_id=aid, action="spawn", success=True
    )
    return base_envelope(
        kind=AGENT_LIFECYCLE_RECORD_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
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
            "spawn_permitted": False,
            "spawn_executed": False,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
            "s3_enabled": False,
            "process_spawn": False,
            "notes": (
                "Lifecycle spawn *record* only. Does not start an agent process, "
                "bind a runtime session, or enable S3 multi-agent."
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
    return base_envelope(
        kind=AGENT_LIFECYCLE_RECORD_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
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
            "spawn_permitted": False,
            "spawn_executed": False,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
            "s3_enabled": False,
            "process_spawn": False,
            "notes": (
                "Lifecycle retire *record* only. Does not kill processes; "
                "pairs with spawn digest for replay proofs."
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
    """MoIRA-shaped factory surface for lifecycle records (validation_only)."""

    def __init__(self, *, experience_store: dict[str, Any] | None = None) -> None:
        self._store = experience_store

    def spawn(
        self,
        *,
        role: str,
        task: str,
        model_family: str = "validation-only",
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        return spawn_agent(
            role=role,
            task=task,
            model_family=model_family,
            experience_store=self._store,
            agent_id=agent_id,
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
