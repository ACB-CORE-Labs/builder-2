from __future__ import annotations

import json as json_lib
from pathlib import Path

import pytest

pytest.importorskip("deepagents")

from builder_ii.deepagents_cli import deepagents_app
from typer.testing import CliRunner

from builder_ii.adapters.deepagents.deepagents_execution import (
    DEEPAGENTS_BACKEND_READINESS_GATE_KIND,
    OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION,
    create_deepagents_backend_readiness_gate,
    create_deepagents_execution_candidate,
    validate_deepagents_backend_readiness_gate,
    validate_deepagents_execution_candidate,
)
from builder_ii.adapters.deepagents.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.adapters.deepagents.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.adapters.deepagents.deepagents_work_artifacts import create_deepagents_work_plan
from builder_ii.core.config import load_settings
from builder_ii.governance.ledger.artifact_index_records import (
    create_artifact_index_record,
    validate_artifact_index_record,
)
from builder_ii.routing.model_budget import create_model_budget
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_routing_policy import create_model_execution_policy
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _install_fake_deepagents(_monkeypatch):
    """Compatibility helper for Ladder 4 tests; returns the installed official package."""

    import deepagents

    return deepagents


def _native_model_config() -> dict:
    registry = create_model_client_registry()
    root = Path("tests/fixtures/artifacts")
    recommendation = json_lib.loads((root / "model-recommendation.json").read_text())
    assignment = json_lib.loads((root / "agent-assignment-plan.json").read_text())
    policy = create_model_execution_policy(recommendation, max_tokens=1024)
    budget = create_model_budget(session_id="native-route", max_output_tokens=4096,
                                 max_total_tokens=100_000, max_usd=5)
    return {"registry": registry, "policy": policy, "recommendation": recommendation,
            "assignment": assignment, "budget": budget}


def _work_plan_fixture(tmp_path: Path) -> tuple[dict, Path]:
    goal2 = build_goal2_assignment_fixture(tmp_path, task="Official Deep Agents readiness lane")
    policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")
    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Run the official native Deep Agents lane",
        orchestration_assignment_plan=goal2["artifacts"]["orchestration"],
        orchestration_assignment_dry_run=goal2["artifacts"]["dry_run"],
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        proposed_subagents=["native-alpha", "native-beta"],
        expected_outputs=["native evidence bundle"],
        review_gates=["operator_review"],
    )
    return work_plan, _write(tmp_path / "deepagents-work-plan.json", work_plan)


def test_backend_readiness_gate_uses_official_factory_without_construction() -> None:
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)

    assert gate["kind"] == DEEPAGENTS_BACKEND_READINESS_GATE_KIND
    assert gate["gate_state"] == "PASS"
    assert gate["protocol_compatibility"] == {
        "required_version": OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION,
        "observed_version": "0.6.12",
        "version_compatible": True,
        "factory_export": "create_deep_agent",
        "factory_export_present": True,
        "factory_constructed": False,
    }
    assert all(gate["contract_tests"].values())
    assert all(probe["state"] == "DENIED" for probe in gate["denial_probes"])
    assert all(probe["evidence_mode"] == "static_adapter_contract" for probe in gate["denial_probes"])
    assert all(probe["probe_executed"] is False for probe in gate["denial_probes"])
    assert gate["model_gateway_routing"]["native_deepagents_model_invocation"] == (
        "ROUTED_THROUGH_BUILDER_II"
    )
    assert gate["model_gateway_routing"]["model_call_receipt_refs"] == []
    assert validate_deepagents_backend_readiness_gate(gate) == []


def test_backend_readiness_gate_fails_without_promotion_gates() -> None:
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=False)

    assert gate["gate_state"] == "FAIL"
    assert any("capability promotion gates" in error for error in gate["summary"]["errors"])
    assert validate_deepagents_backend_readiness_gate(gate) == []


def test_backend_readiness_cli_writes_official_gate(tmp_path: Path) -> None:
    output = tmp_path / "gate.json"
    result = CliRunner().invoke(
        deepagents_app,
        ["backend-readiness", "--capability-gates-passed", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    gate = json_lib.loads(output.read_text(encoding="utf-8"))
    assert gate["gate_state"] == "PASS"
    assert gate["protocol_compatibility"]["factory_export"] == "create_deep_agent"
    assert validate_deepagents_backend_readiness_gate(gate) == []


def test_optional_candidate_binds_single_gateway_model_and_worker_cap(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)
    gate_path = _write(tmp_path / "gate.json", gate)
    route = _native_model_config()
    registry, model_policy = route["registry"], route["policy"]
    registry_path = _write(tmp_path / "model-registry.json", registry)
    model_policy_path = _write(tmp_path / "model-policy.json", model_policy)
    recommendation_path = _write(tmp_path / "model-recommendation.json", route["recommendation"])
    assignment_path = _write(tmp_path / "model-assignment.json", route["assignment"])
    budget_path = _write(tmp_path / "model-budget.json", route["budget"])

    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        backend_mode="optional_deepagents",
        backend_readiness_gate=gate,
        backend_readiness_gate_path=gate_path,
        allowed_subagents=["native-alpha", "native-beta"],
        model_registry=registry,
        model_registry_path=registry_path,
        model_execution_policy=model_policy,
        model_execution_policy_path=model_policy_path,
        model_routing_recommendation=route["recommendation"],
        model_routing_recommendation_path=recommendation_path,
        model_assignment=route["assignment"], model_assignment_path=assignment_path,
        model_budget=route["budget"], model_budget_path=budget_path,
        model_id=route["recommendation"]["recommended_candidates"][0]["model_id"],
        active_workers=2,
    )

    assert candidate["native_runtime"]["model_id"] == route["recommendation"]["recommended_candidates"][0]["model_id"]
    assert candidate["native_runtime"]["active_workers"] == 2
    assert candidate["native_runtime"]["worker_cap"] == 4
    assert candidate["native_runtime"]["single_model_instance"] is True
    assert candidate["model_boundary"]["native_deepagents_model_invocation"] == (
        "ROUTED_THROUGH_BUILDER_II"
    )
    assert validate_deepagents_execution_candidate(candidate) == []


def test_optional_candidate_requires_model_gateway_configuration(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)

    try:
        create_deepagents_execution_candidate(
            work_plan=work_plan,
            work_plan_path=work_plan_path,
            output_root=tmp_path / "runs",
            backend_mode="optional_deepagents",
            backend_readiness_gate=gate,
            backend_readiness_gate_path=tmp_path / "gate.json",
            allowed_subagents=["native-alpha", "native-beta"],
        )
        raise AssertionError("missing native model configuration must fail")
    except ValueError as exc:
        assert "requires WRP recommendation" in str(exc)


def test_backend_readiness_gate_is_indexable(tmp_path: Path) -> None:
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)
    _write(tmp_path / "gate.json", gate)

    index = create_artifact_index_record(tmp_path, recursive=True)

    assert index["counts"]["unknown"] == 0
    assert index["counts"]["invalid"] == 0
    assert validate_artifact_index_record(index) == []
