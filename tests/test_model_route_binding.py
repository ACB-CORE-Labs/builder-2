import json
import time
from pathlib import Path

import httpx
import pytest

from builder_ii.core.config import load_settings
from builder_ii.routing.gateway_invocation import CancellationToken, GatewayInvocationEngine
from builder_ii.routing.model_budget import create_model_budget
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
from builder_ii.routing.model_route_binding import (
    assert_route_runtime_request,
    build_model_route_binding,
    canonical_digest,
)
from builder_ii.routing.model_routing_policy import create_model_execution_policy


def _route():
    fixture = Path("tests/fixtures/artifacts")
    recommendation = json.loads((fixture / "model-recommendation.json").read_text())
    assignment = json.loads((fixture / "agent-assignment-plan.json").read_text())
    registry = create_model_client_registry()
    policy = create_model_execution_policy(recommendation, max_tokens=64)
    budget = create_model_budget(session_id="route-session", task_id="route-task",
                                 max_output_tokens=64, max_total_tokens=100_000, max_usd=1)
    route = build_model_route_binding(
        recommendation=recommendation, assignment=assignment, execution_policy=policy,
        registry=registry, budget=budget, session_id="route-session", run_id="run-1",
        obligation_id="obl-1", role="code_reviewer", max_tokens=64,
    )
    return route, recommendation, assignment, registry, policy, budget


def test_route_reconstructs_exact_wrp_order_and_primary() -> None:
    route, recommendation, _assignment, _registry, _policy, _budget = _route()
    assert route.selected_candidate.model_id == recommendation["recommended_candidates"][0]["model_id"]
    assert [c.model_id for c in route.ordered_candidates] == [
        c["model_id"] for c in recommendation["recommended_candidates"]
    ]
    assert len(route.route_digest) == 64
    assert route.cloud_allowed is False


def test_model_substitution_refuses_before_runtime() -> None:
    route, _recommendation, _assignment, _registry, policy, budget = _route()
    with pytest.raises(ValueError, match="WRP-selected"):
        assert_route_runtime_request(route, model_id="foreign", budget=budget, execution_policy=policy)


def test_budget_substitution_refuses_before_runtime() -> None:
    route, _recommendation, _assignment, _registry, policy, _budget = _route()
    other = create_model_budget(session_id="foreign")
    with pytest.raises(ValueError, match="WRP-bound budget"):
        assert_route_runtime_request(route, model_id=None, budget=other, execution_policy=policy)


def test_policy_widening_is_detected_as_substitution() -> None:
    route, _recommendation, _assignment, _registry, policy, budget = _route()
    policy["allowed_models"] = [*policy["allowed_models"], "gpt-4o-stub"]
    with pytest.raises(ValueError, match="WRP-bound policy"):
        assert_route_runtime_request(route, model_id=None, budget=budget, execution_policy=policy)


def test_assignment_primary_substitution_refuses() -> None:
    _route_value, recommendation, assignment, registry, policy, budget = _route()
    assignment["bindings"]["model"]["selected_candidate"] = recommendation["recommended_candidates"][1]
    with pytest.raises(ValueError, match="selected candidate"):
        build_model_route_binding(recommendation=recommendation, assignment=assignment,
                                  execution_policy=policy, registry=registry, budget=budget,
                                  session_id="route-session", run_id="r", obligation_id="o", role="x")


def test_retry_refuses_when_cumulative_worst_case_exceeds_route_budget(tmp_path: Path) -> None:
    route, _recommendation, _assignment, registry, policy, budget = _route()
    calls = 0

    class TransientTransport:
        def stream(self, _request, _cancellation):
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("transient")
            yield

    gateway = ModelExecutionGateway(
        load_settings(), registry, policy,
        invocation_engine=GatewayInvocationEngine(lambda _candidate: TransientTransport()),
    )
    with pytest.raises(ValueError, match="projected output_tokens"):
        gateway.run_routed_model_call(
            route=route, prompt="budget bound retry", budget=budget,
            envelope_path=tmp_path / "envelope.json", receipt_path=tmp_path / "receipt.json",
        )
    assert calls == 1


def test_pre_cancel_writes_truthful_receipt_with_no_actual_provider(tmp_path: Path) -> None:
    route, _recommendation, _assignment, registry, policy, budget = _route()

    def forbidden(_candidate):
        raise AssertionError("provider must not be selected after pre-cancellation")

    token = CancellationToken()
    token.cancel()
    gateway = ModelExecutionGateway(
        load_settings(), registry, policy,
        invocation_engine=GatewayInvocationEngine(forbidden),
    )
    _envelope, receipt, debited = gateway.run_routed_model_call(
        route=route, prompt="cancel", budget=budget, cancellation=token,
        envelope_path=tmp_path / "envelope.json", receipt_path=tmp_path / "receipt.json",
    )
    assert receipt["status"] == "cancelled"
    assert receipt["complete"] is False
    assert receipt["actual_model"] is None
    assert receipt["actual_provider"] is None
    assert receipt["attempt_count"] == 0
    assert debited is None


def test_cloud_route_refuses_expired_or_substituted_approval(cloud_route_sources_factory) -> None:
    sources = cloud_route_sources_factory("cloud-route-binding")
    expired = dict(sources["cloud_approval"])
    expired["expires_at"] = time.time() - 1
    expired["digest"] = canonical_digest(expired)
    with pytest.raises(ValueError, match="expired"):
        build_model_route_binding(**{**sources, "cloud_approval": expired})

    substituted = dict(sources["cloud_approval"])
    substituted["max_usd"] = 100
    with pytest.raises(ValueError, match="canonical digest"):
        build_model_route_binding(**{**sources, "cloud_approval": substituted})


def test_validate_model_call_receipt_enforces_wrp_reconstruction(tmp_path: Path) -> None:
    from builder_ii.routing.gateway_invocation import StreamChunk
    from builder_ii.routing.model_execution_gateway import (
        reconstruct_and_validate_routed_receipt,
        validate_model_call_receipt,
    )

    route, recommendation, assignment, registry, policy, budget = _route()

    def transport_factory(_c):
        class _T:
            def stream(self, _req, _cancel):
                yield StreamChunk("test output")
        return _T()

    gateway = ModelExecutionGateway(
        load_settings(), registry, policy,
        invocation_engine=GatewayInvocationEngine(transport_factory),
    )
    _env, receipt, _debited = gateway.run_routed_model_call(
        route=route, prompt="test prompt", budget=budget,
        envelope_path=tmp_path / "env.json", receipt_path=tmp_path / "rec.json",
    )

    sources = {
        "recommendation": recommendation,
        "assignment": assignment,
        "execution_policy": policy,
        "registry": registry,
        "budget": budget,
        "session_id": route.session_id,
        "run_id": route.run_id,
        "obligation_id": route.obligation_id,
        "role": route.role,
        "max_tokens": route.max_tokens,
    }

    # Valid receipt matches route and can be reconstructed from source artifacts
    assert validate_model_call_receipt(receipt, route=route) == []
    assert reconstruct_and_validate_routed_receipt(receipt, route=route) == []
    assert reconstruct_and_validate_routed_receipt(receipt, sources=sources) == []

    # Substituted route_digest is rejected
    tampered_route_digest = dict(receipt, route_digest="0" * 64)
    errors = validate_model_call_receipt(tampered_route_digest, route=route)
    assert any("does not equal bound route_digest" in e for e in errors)

    # Substituted planned_primary is rejected
    tampered_primary = dict(receipt, planned_primary="unauthorized-model")
    errors = validate_model_call_receipt(tampered_primary, route=route)
    assert any("does not equal route selected model" in e for e in errors)

    # Substituted candidate sequence is rejected
    tampered_seq = dict(receipt, candidate_sequence=["foreign-model-1", "foreign-model-2"])
    errors = validate_model_call_receipt(tampered_seq, route=route)
    assert any("does not equal route candidates" in e for e in errors)

    # Invalid attempt history (e.g. attempt count mismatch or negative tokens)
    tampered_history = dict(receipt, attempt_count=99)
    errors = validate_model_call_receipt(tampered_history, route=route)
    assert any("does not equal length of attempt_history" in e for e in errors)

    tampered_tokens = dict(receipt, attempt_history=[
        dict(receipt["attempt_history"][0], input_tokens=-5)
    ])
    errors = validate_model_call_receipt(tampered_tokens, route=route)
    assert any("input_tokens must be a non-negative integer" in e for e in errors)
