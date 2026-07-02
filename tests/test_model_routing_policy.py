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
        "max_risk_classification": "local_network",
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
        "max_risk_classification": "local_network",
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
        "max_risk_classification": "local_network",
        "requires_tool_use": True,
        "required_model_id": "gpt-5.5",
    }
    with pytest.raises(ValueError, match="No candidate model client satisfies"):
        create_model_routing_recommendation(policy=policy, registry=registry, request=request)


def test_routing_recommendation_forbidden_execution():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    request = {
        "task_intent": "coding",
        "max_risk_classification": "local_network",
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
        "max_risk_classification": "local_network",
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


def test_routing_policy_risk_cap_enforcement():
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    
    # 1. Enable gpt-4o-stub (cloud_external risk)
    found_gpt4o = False
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
            found_gpt4o = True
            break
    assert found_gpt4o, "Could not find gpt-4o-stub in default registry"
    
    # 2. Match a rule (coding) that caps risk to local_network
    for rule in policy["rules"]:
        if rule["task_intent"] == "coding":
            rule["max_risk_classification"] = "local_network"
            break
            
    # 3. Request with cloud_external max_risk
    request = {
        "task_intent": "coding",
        "max_risk_classification": "cloud_external",
        "requires_tool_use": True,
    }
    
    # Recommend
    rec = create_model_routing_recommendation(policy=policy, registry=registry, request=request)
    errors = validate_model_routing_recommendation(rec)
    assert errors == []
    
    # Cloud candidate should NOT be recommended because coding rule caps at local_network
    recommended_model_ids = [c["model_id"] for c in rec["recommended_candidates"]]
    assert "gpt-4o-stub" not in recommended_model_ids
    
    # 4. Now relax coding rule cap to cloud_external
    for rule in policy["rules"]:
        if rule["task_intent"] == "coding":
            rule["max_risk_classification"] = "cloud_external"
            break
            
    rec_relaxed = create_model_routing_recommendation(policy=policy, registry=registry, request=request)
    assert any(c["model_id"] == "gpt-4o-stub" for c in rec_relaxed["recommended_candidates"])

