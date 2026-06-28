import pytest
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
    validate_model_routing_policy,
    validate_model_routing_recommendation,
)


def test_valid_routing_policy():
    policy = create_model_routing_policy()
    errors = validate_model_routing_policy(policy)
    assert errors == []


def test_routing_policy_forbidden_authority():
    policy = create_model_routing_policy()
    policy["governance"]["model_execution"] = "ENABLED"
    errors = validate_model_routing_policy(policy)
    assert any("model_execution" in err for err in errors)


def test_routing_recommendation_valid_and_passive():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    request = {
        "task_intent": "coding",
        "max_risk_classification": "local_offline",
        "requires_tool_use": True,
    }
    rec = create_model_routing_recommendation(policy=policy, registry=registry, request=request)
    errors = validate_model_routing_recommendation(rec)
    assert errors == []
    assert rec["recommendation_state"] == "RECOMMENDATION_ONLY"
    assert rec["governance"]["model_execution"] == "DISABLED"
    assert rec["recommended_candidates"][0]["model_alias"] == "qwen-coder"


def test_routing_recommendation_unknown_lane():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    request = {
        "task_intent": "coding",
        "max_risk_classification": "local_offline",
        "requires_tool_use": True,
        "required_lane": "non_existent_lane",
    }
    with pytest.raises(ValueError, match="Unknown required_lane"):
        create_model_routing_recommendation(policy=policy, registry=registry, request=request)


def test_routing_recommendation_no_candidate():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    request = {
        "task_intent": "coding",
        "max_risk_classification": "local_offline",
        "requires_tool_use": True,
        "required_model_id": "claude-3-5-sonnet-stub",
    }
    with pytest.raises(ValueError, match="No candidate model client satisfies"):
        create_model_routing_recommendation(policy=policy, registry=registry, request=request)


def test_routing_recommendation_forbidden_execution():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    request = {
        "task_intent": "coding",
        "max_risk_classification": "local_offline",
        "requires_tool_use": True,
    }
    rec = create_model_routing_recommendation(policy=policy, registry=registry, request=request)
    rec["governance"]["model_execution"] = "ENABLED"
    errors = validate_model_routing_recommendation(rec)
    assert any("model_execution" in err for err in errors)

def test_routing_recommendation_invalid_source_ref():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    request = {
        "task_intent": "coding",
        "max_risk_classification": "local_offline",
        "requires_tool_use": True,
    }
    rec = create_model_routing_recommendation(policy=policy, registry=registry, request=request)
    rec["source_policy_ref"]["sha256"] = "invalid_hash"
    errors = validate_model_routing_recommendation(rec)
    assert any("valid SHA-256 digest" in err for err in errors)

def test_routing_policy_nested_execution():
    policy = create_model_routing_policy()
    policy["rules"][0]["rationale"] = "EXECUTED"
    errors = validate_model_routing_policy(policy)
    assert any("claims active authority state 'EXECUTED'" in err for err in errors)
