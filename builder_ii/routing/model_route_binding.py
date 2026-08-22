"""Immutable in-memory WRP model route projection.

The projection is reconstructed from existing governed artifacts.  It is not a
persistent authority artifact and cannot create models, budgets, providers, or
cloud approval at execution time.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from builder_ii.core.orchestration_assignment import validate_agent_assignment_plan
from builder_ii.routing.model_budget import validate_model_budget
from builder_ii.routing.model_client_registry import validate_model_client_registry
from builder_ii.routing.model_routing_policy import (
    validate_model_execution_policy,
    validate_model_routing_recommendation,
)


def canonical_digest(value: Mapping[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k != "digest"}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RouteCandidate:
    model_id: str
    model_alias: str
    provider_id: str
    client_id: str
    risk_classification: str


@dataclass(frozen=True)
class ModelRouteBinding:
    session_id: str
    run_id: str
    obligation_id: str
    role: str
    routing_recommendation_digest: str
    assignment_digest: str
    policy_digest: str
    registry_digest: str
    budget_digest: str
    ordered_candidates: tuple[RouteCandidate, ...]
    selected_candidate: RouteCandidate
    max_risk: str
    cloud_allowed: bool
    allowed_providers: tuple[str, ...]
    approval_ref: str | None
    max_input_tokens: int
    max_output_tokens: int
    max_total_tokens: int
    max_usd: float
    temperature: float | None
    max_tokens: int
    secret_token_refs: tuple[str, ...]
    route_digest: str

    def candidate(self, index: int) -> RouteCandidate:
        return self.ordered_candidates[index]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_RISK_ORDER = {"local_offline": 0, "local_network": 1, "cloud_external": 2}


def _fail(label: str, errors: list[str]) -> None:
    if errors:
        raise ValueError(f"invalid {label}: {'; '.join(errors)}")


def build_model_route_binding(
    *,
    recommendation: dict[str, Any],
    assignment: dict[str, Any],
    execution_policy: dict[str, Any],
    registry: dict[str, Any],
    budget: dict[str, Any],
    session_id: str,
    run_id: str,
    obligation_id: str,
    role: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    cloud_approval: Mapping[str, Any] | None = None,
) -> ModelRouteBinding:
    """Validate governed sources and construct their immutable runtime projection."""
    for name, value in (("session_id", session_id), ("run_id", run_id), ("obligation_id", obligation_id), ("role", role)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    _fail("routing recommendation", validate_model_routing_recommendation(recommendation))
    _fail("assignment", validate_agent_assignment_plan(assignment))
    _fail("execution policy", validate_model_execution_policy(execution_policy))
    _fail("client registry", validate_model_client_registry(registry))
    _fail("model budget", validate_model_budget(budget))
    if budget.get("session_id") != session_id:
        raise ValueError("model budget session_id does not equal route session_id")

    candidates = tuple(
        RouteCandidate(
            model_id=str(c["model_id"]),
            model_alias=str(c.get("model_alias") or ""),
            provider_id=str(c["provider_id"]),
            client_id=str(c["client_id"]),
            risk_classification=str(c["risk_classification"]),
        )
        for c in recommendation["recommended_candidates"]
    )
    if not candidates:
        raise ValueError("WRP route has no candidates")
    selected_raw = (((assignment.get("bindings") or {}).get("model") or {}).get("selected_candidate"))
    if not isinstance(selected_raw, dict) or selected_raw != recommendation["recommended_candidates"][0]:
        raise ValueError("assignment selected candidate does not equal WRP primary candidate")

    rec_digest = canonical_digest(recommendation)
    policy_ref = execution_policy.get("source_recommendation_ref") or {}
    if policy_ref.get("sha256") != rec_digest:
        raise ValueError("execution policy is not bound to the WRP recommendation")
    allowed = execution_policy.get("allowed_models") or []
    if list(allowed) != [c.model_id for c in candidates]:
        raise ValueError("execution policy candidate order/set does not equal WRP route")

    clients = {(str(c.get("client_id")), str(c.get("model_id"))): c for c in registry.get("clients", []) if isinstance(c, dict)}
    for candidate in candidates:
        client = clients.get((candidate.client_id, candidate.model_id))
        if not client or any(
            client.get(field) != getattr(candidate, field)
            for field in ("model_id", "provider_id", "risk_classification")
        ):
            raise ValueError(f"route candidate {candidate.client_id!r} does not match registry")
        if client.get("enabled") is not True:
            raise ValueError(f"route candidate {candidate.client_id!r} is disabled")

    cloud_candidates = [c for c in candidates if c.risk_classification == "cloud_external"]
    cloud_allowed = bool(cloud_candidates)
    approval_ref: str | None = None
    secret_refs: tuple[str, ...] = ()
    if cloud_allowed:
        if not isinstance(cloud_approval, Mapping) or cloud_approval.get("valid") is not True:
            raise ValueError("cloud route requires an explicit valid cloud approval")
        approval_ref = str(cloud_approval.get("digest") or "")
        if len(approval_ref) != 64 or approval_ref != canonical_digest(cloud_approval):
            raise ValueError("cloud approval requires its canonical digest")
        expires_at = cloud_approval.get("expires_at")
        if (not isinstance(expires_at, (int, float)) or isinstance(expires_at, bool)
                or float(expires_at) <= time.time()):
            raise ValueError("cloud approval is missing expiry or has expired")
        approved_providers = set(cloud_approval.get("allowed_providers") or [])
        if not {c.provider_id for c in cloud_candidates}.issubset(approved_providers):
            raise ValueError("cloud approval does not cover every cloud route provider")
        if float(cloud_approval.get("max_usd") or -1) < float(budget["max_usd"]):
            raise ValueError("cloud approval cost ceiling is below the WRP budget")
        refs: list[str] = []
        for candidate in cloud_candidates:
            refs.extend(str(x) for x in clients[(candidate.client_id, candidate.model_id)].get("secret_ref_names", []))
        secret_refs = tuple(dict.fromkeys(refs))

    resolved_max_tokens = int(max_tokens if max_tokens is not None else execution_policy["max_tokens"])
    if resolved_max_tokens > int(execution_policy["max_tokens"]):
        raise ValueError("route max_tokens exceeds execution policy")
    if resolved_max_tokens > int(budget["max_output_tokens"]):
        raise ValueError("route max_tokens exceeds WRP budget")

    body: dict[str, Any] = {
        "session_id": session_id,
        "run_id": run_id,
        "obligation_id": obligation_id,
        "role": role,
        "routing_recommendation_digest": rec_digest,
        "assignment_digest": canonical_digest(assignment),
        "policy_digest": canonical_digest(execution_policy),
        "registry_digest": canonical_digest(registry),
        "budget_digest": str(budget["digest"]),
        "ordered_candidates": [asdict(c) for c in candidates],
        "selected_candidate": asdict(candidates[0]),
        "max_risk": max(candidates, key=lambda c: _RISK_ORDER[c.risk_classification]).risk_classification,
        "cloud_allowed": cloud_allowed,
        "allowed_providers": list(dict.fromkeys(c.provider_id for c in candidates)),
        "approval_ref": approval_ref,
        "max_input_tokens": int(budget["max_input_tokens"]),
        "max_output_tokens": int(budget["max_output_tokens"]),
        "max_total_tokens": int(budget["max_total_tokens"]),
        "max_usd": float(budget["max_usd"]),
        "temperature": temperature,
        "max_tokens": resolved_max_tokens,
        "secret_token_refs": list(secret_refs),
    }
    return ModelRouteBinding(
        **{**body, "ordered_candidates": candidates, "selected_candidate": candidates[0],
           "allowed_providers": tuple(body["allowed_providers"]), "secret_token_refs": secret_refs,
           "route_digest": canonical_digest(body)}
    )


def assert_route_runtime_request(
    route: ModelRouteBinding,
    *,
    model_id: str | None,
    budget: Mapping[str, Any],
    execution_policy: Mapping[str, Any],
) -> None:
    """Refuse substitutions before any provider call."""
    if model_id is not None and model_id != route.selected_candidate.model_id:
        raise ValueError("runtime model does not equal WRP-selected model")
    if str(budget.get("digest")) != route.budget_digest:
        raise ValueError("runtime budget does not equal WRP-bound budget")
    if canonical_digest(execution_policy) != route.policy_digest:
        raise ValueError("runtime execution policy does not equal WRP-bound policy")


def advance_route_budget(route: ModelRouteBinding, budget: Mapping[str, Any]) -> ModelRouteBinding:
    """Rebind only the immutable debit successor; every authority ceiling stays fixed."""
    _fail("model budget", validate_model_budget(dict(budget)))
    for field in ("max_input_tokens", "max_output_tokens", "max_total_tokens"):
        if int(budget[field]) != int(getattr(route, field)):
            raise ValueError(f"debit successor changed route {field}")
    if float(budget["max_usd"]) != route.max_usd:
        raise ValueError("debit successor changed route max_usd")
    body = route.as_dict()
    body.pop("route_digest", None)
    body["budget_digest"] = str(budget["digest"])
    return ModelRouteBinding(**{**body, "ordered_candidates": route.ordered_candidates,
                                "selected_candidate": route.selected_candidate,
                                "allowed_providers": route.allowed_providers,
                                "secret_token_refs": route.secret_token_refs,
                                "route_digest": canonical_digest(body)})
