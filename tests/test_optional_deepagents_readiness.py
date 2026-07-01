from __future__ import annotations

import json as json_lib
import sys
from types import ModuleType
from pathlib import Path

from typer.testing import CliRunner

from builder_ii import deepagents_execution as execution_module
from builder_ii.artifact_index_records import (
    create_artifact_index_record,
    validate_artifact_index_record,
)
from builder_ii.config import load_settings
from builder_ii.deepagents_cli import deepagents_app
from builder_ii.deepagents_execution import (
    DEEPAGENTS_BACKEND_READINESS_GATE_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION,
    create_deepagents_backend_readiness_gate,
    create_deepagents_execution_approval,
    create_deepagents_execution_candidate,
    replay_deepagents_run,
    run_deepagents_approved_candidate,
    validate_deepagents_backend_readiness_gate,
    validate_deepagents_execution_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_replay_report,
)
from builder_ii.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.deepagents_work_artifacts import create_deepagents_work_plan
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _event_by_type(events_dir: Path, event_type: str) -> dict:
    for path in sorted(events_dir.glob("event-*.json")):
        event = json_lib.loads(path.read_text(encoding="utf-8"))
        if event.get("event_type") == event_type:
            return event
    raise AssertionError(f"missing {event_type} event in {events_dir}")


def _proposal_payload(subagent_profile: str, task: str) -> dict:
    payload = {
        "subagent_profile": subagent_profile,
        "result_mode": "PROPOSAL_ONLY",
        "summary": f"{subagent_profile} optional protocol proposal for: {task}",
        "writes_source": False,
        "executes_shell": False,
        "calls_models": False,
        "calls_tools": False,
        "calls_mcp": False,
        "mutates_memory": False,
        "constructs_deepagents": False,
    }
    payload["result_digest"] = execution_module._digest_jsonable(payload)
    return payload


def _install_fake_deepagents(monkeypatch, *, model_work_expected: bool = False) -> ModuleType:
    module = ModuleType("deepagents")
    module.__version__ = "1.0.0-test"
    module.BUILDER_II_DEEPAGENTS_PROTOCOL_VERSION = OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION
    module.BUILDER_II_MODEL_WORK_EXPECTED = model_work_expected
    module.BUILDER_II_DENIAL_PROBES = {
        "tool calls": "DENIED",
        "model calls": "DENIED",
        "shell execution": "DENIED",
        "mcp calls": "DENIED",
        "memory mutation": "DENIED",
        "source writes": "DENIED",
    }

    def create_governed_deep_agent(*args, **kwargs):
        raise AssertionError("readiness must not construct native deepagents")

    def builder_ii_run_protocol_subagent(*, subagent_profile: str, task: str) -> dict:
        return _proposal_payload(subagent_profile, task)

    module.create_governed_deep_agent = create_governed_deep_agent
    module.builder_ii_run_protocol_subagent = builder_ii_run_protocol_subagent
    monkeypatch.setitem(sys.modules, "deepagents", module)
    return module


def _work_plan_fixture(tmp_path: Path) -> tuple[dict, Path]:
    goal2 = build_goal2_assignment_fixture(tmp_path, task="Optional backend readiness lane")
    policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")
    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Map the optional backend readiness lane",
        orchestration_assignment_plan=goal2["artifacts"]["orchestration"],
        orchestration_assignment_dry_run=goal2["artifacts"]["dry_run"],
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        proposed_subagents=["repo_mapper"],
        expected_outputs=["proposal-only results"],
        review_gates=["operator_review"],
    )
    return work_plan, _write(tmp_path / "deepagents-work-plan.json", work_plan)


def _gate_candidate_approval(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    _install_fake_deepagents(monkeypatch)
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)
    gate_path = _write(tmp_path / "backend-readiness-gate.json", gate)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        backend_mode="optional_deepagents",
        backend_readiness_gate=gate,
        backend_readiness_gate_path=gate_path,
        allowed_subagents=["repo_mapper"],
    )
    candidate_path = _write(tmp_path / "candidate.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="Joshua Shay",
        approval_reason="Approve optional backend readiness gate test.",
    )
    approval_path = _write(tmp_path / "approval.json", approval)
    return gate_path, candidate_path, approval_path


def test_backend_readiness_gate_passes_with_protocol_adapter(monkeypatch) -> None:
    _install_fake_deepagents(monkeypatch)

    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)

    assert gate["kind"] == DEEPAGENTS_BACKEND_READINESS_GATE_KIND
    assert gate["gate_state"] == "PASS"
    assert gate["protocol_compatibility"]["factory_constructed"] is False
    assert gate["contract_tests"]["deterministic_shape"] is True
    assert gate["schema_drift_detection"]["stable"] is True
    assert all(probe["state"] == "DENIED" for probe in gate["denial_probes"])
    assert validate_deepagents_backend_readiness_gate(gate) == []


def test_backend_readiness_cli_writes_gate(monkeypatch, tmp_path: Path) -> None:
    _install_fake_deepagents(monkeypatch)
    output = tmp_path / "gate.json"

    result = CliRunner().invoke(
        deepagents_app,
        [
            "backend-readiness",
            "--capability-gates-passed",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    gate = json_lib.loads(output.read_text(encoding="utf-8"))
    assert gate["gate_state"] == "PASS"
    assert validate_deepagents_backend_readiness_gate(gate) == []


def test_backend_readiness_detects_schema_drift(monkeypatch) -> None:
    module = _install_fake_deepagents(monkeypatch)

    def drifted(*, subagent_profile: str, task: str) -> dict:
        payload = _proposal_payload(subagent_profile, task)
        payload["unexpected"] = "drift"
        payload["result_digest"] = execution_module._digest_jsonable(payload)
        return payload

    module.builder_ii_run_protocol_subagent = drifted

    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)

    assert gate["gate_state"] == "FAIL"
    assert gate["summary"]["passed"] is False
    assert gate["contract_tests"]["contract_errors"]
    assert validate_deepagents_backend_readiness_gate(gate) == []


def test_backend_readiness_detects_missing_denial_probe(monkeypatch) -> None:
    module = _install_fake_deepagents(monkeypatch)
    module.BUILDER_II_DENIAL_PROBES = {"tool calls": "DENIED"}

    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)

    assert gate["gate_state"] == "FAIL"
    assert any("denial probes" in error for error in gate["summary"]["errors"])


def test_model_gateway_refs_required_when_backend_declares_model_work(monkeypatch, tmp_path: Path) -> None:
    _install_fake_deepagents(monkeypatch, model_work_expected=True)
    receipt_ref = {
        "role": "model_call_receipt",
        "kind": "builder_ii.model_call_receipt",
        "path": str(Path("model-receipt.json")),
        "sha256": "a" * 64,
        "name": "builder-II model call receipt",
        "required": True,
    }

    missing = create_deepagents_backend_readiness_gate(capability_gates_passed=True)
    passing = create_deepagents_backend_readiness_gate(
        capability_gates_passed=True,
        model_call_receipt_refs=[receipt_ref],
    )

    assert missing["gate_state"] == "FAIL"
    assert passing["gate_state"] == "PASS"
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        backend_mode="optional_deepagents",
        backend_readiness_gate=passing,
        backend_readiness_gate_path=tmp_path / "gate.json",
        allowed_subagents=["repo_mapper"],
    )
    assert candidate["model_boundary"]["model_call_receipt_refs"] == [receipt_ref]
    assert validate_deepagents_execution_candidate(candidate) == []


def test_optional_candidate_rejects_failing_gate(monkeypatch, tmp_path: Path) -> None:
    _install_fake_deepagents(monkeypatch)
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=False)

    try:
        create_deepagents_execution_candidate(
            work_plan=work_plan,
            work_plan_path=work_plan_path,
            output_root=tmp_path / "runs",
            backend_mode="optional_deepagents",
            backend_readiness_gate=gate,
            backend_readiness_gate_path=tmp_path / "gate.json",
            allowed_subagents=["repo_mapper"],
        )
        assert False, "failing gate must be rejected"
    except ValueError as exc:
        assert "readiness gate must PASS" in str(exc)


def test_optional_backend_run_records_denial_probes_and_replay(monkeypatch, tmp_path: Path) -> None:
    _gate_path, candidate_path, approval_path = _gate_candidate_approval(monkeypatch, tmp_path)
    output_dir = tmp_path / "runs" / "optional"

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )
    replay = json_lib.loads((output_dir / "deepagents-replay-report.json").read_text(encoding="utf-8"))
    receipt = json_lib.loads((output_dir / "deepagents-execution-receipt.json").read_text(encoding="utf-8"))

    assert summary["status"] == "COMPLETED"
    assert receipt["kind"] == DEEPAGENTS_EXECUTION_RECEIPT_KIND
    assert receipt["receipt_state"] == "COMPLETED"
    assert len(replay["denied_capabilities"]) == 6
    assert replay["replay_executes_runtime"] is False
    assert validate_deepagents_execution_receipt(receipt) == []
    assert validate_deepagents_replay_report(replay) == []

    explicit_replay = replay_deepagents_run(
        events_dir=output_dir / "events",
        output=output_dir / "explicit-replay.json",
    )
    assert explicit_replay["valid"] is True
    assert explicit_replay["replay_executes_runtime"] is False


def test_optional_backend_dependency_absence_is_governed_denial(monkeypatch, tmp_path: Path) -> None:
    _gate_path, candidate_path, approval_path = _gate_candidate_approval(monkeypatch, tmp_path)

    def missing_module(name: str):
        if name == "deepagents":
            raise ModuleNotFoundError(name)
        return __import__(name)

    monkeypatch.setattr(execution_module.importlib, "import_module", missing_module)
    output_dir = tmp_path / "runs" / "missing"

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )
    failed = _event_by_type(output_dir / "events", "run_failed")

    assert summary["status"] == "FAILED"
    assert failed["payload"]["backend_denial"] is True
    assert failed["payload"]["error_type"] == "DeepAgentsBackendDenied"


def test_optional_backend_timeout_is_governed_denial(monkeypatch, tmp_path: Path) -> None:
    _gate_path, candidate_path, approval_path = _gate_candidate_approval(monkeypatch, tmp_path)
    module = sys.modules["deepagents"]

    def timeout(*, subagent_profile: str, task: str) -> dict:
        raise TimeoutError("probe timeout")

    module.builder_ii_run_protocol_subagent = timeout
    output_dir = tmp_path / "runs" / "timeout"

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )
    failed = _event_by_type(output_dir / "events", "run_failed")

    assert summary["status"] == "FAILED"
    assert failed["payload"]["backend_denial"] is True
    assert failed["payload"]["error_type"] == "DeepAgentsBackendDenied"


def test_optional_backend_malformed_result_fails_with_valid_ledger(monkeypatch, tmp_path: Path) -> None:
    _gate_path, candidate_path, approval_path = _gate_candidate_approval(monkeypatch, tmp_path)
    module = sys.modules["deepagents"]
    module.builder_ii_run_protocol_subagent = lambda *, subagent_profile, task: {
        "subagent_profile": subagent_profile,
        "summary": "missing authority fields",
    }
    output_dir = tmp_path / "runs" / "malformed"

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )
    replay = json_lib.loads((output_dir / "deepagents-replay-report.json").read_text(encoding="utf-8"))

    assert summary["status"] == "FAILED"
    assert replay["valid"] is True
    assert replay["status"] == "FAILED"


def test_optional_backend_readiness_gate_is_indexable(monkeypatch, tmp_path: Path) -> None:
    _install_fake_deepagents(monkeypatch)
    gate = create_deepagents_backend_readiness_gate(capability_gates_passed=True)
    _write(tmp_path / "gate.json", gate)

    index = create_artifact_index_record(tmp_path, recursive=True)

    assert index["counts"]["unknown"] == 0
    assert index["counts"]["invalid"] == 0
    assert validate_artifact_index_record(index) == []

def test_optional_backend_uses_module_bound_in_readiness_gate(monkeypatch, tmp_path: Path) -> None:
    custom_module_name = "builder_ii_custom_deepagents_backend"
    invoked_profiles: list[str] = []

    custom_module = ModuleType(custom_module_name)
    custom_module.__version__ = "1.0.0-custom"
    custom_module.BUILDER_II_DEEPAGENTS_PROTOCOL_VERSION = OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION
    custom_module.BUILDER_II_MODEL_WORK_EXPECTED = False
    custom_module.BUILDER_II_DENIAL_PROBES = {
        "tool calls": "DENIED",
        "model calls": "DENIED",
        "shell execution": "DENIED",
        "mcp calls": "DENIED",
        "memory mutation": "DENIED",
        "source writes": "DENIED",
    }

    def create_governed_deep_agent(*args, **kwargs):
        raise AssertionError("readiness must not construct native deepagents")

    def custom_runner(*, subagent_profile: str, task: str) -> dict:
        invoked_profiles.append(subagent_profile)
        return _proposal_payload(subagent_profile, task)

    custom_module.create_governed_deep_agent = create_governed_deep_agent
    custom_module.builder_ii_run_protocol_subagent = custom_runner

    poison_default = ModuleType("deepagents")
    poison_default.__version__ = "1.0.0-poison"
    poison_default.BUILDER_II_DEEPAGENTS_PROTOCOL_VERSION = OPTIONAL_DEEPAGENTS_PROTOCOL_VERSION
    poison_default.BUILDER_II_MODEL_WORK_EXPECTED = False
    poison_default.BUILDER_II_DENIAL_PROBES = custom_module.BUILDER_II_DENIAL_PROBES
    poison_default.create_governed_deep_agent = create_governed_deep_agent

    def poison_runner(*, subagent_profile: str, task: str) -> dict:
        raise AssertionError("default deepagents module must not be used after a custom readiness gate")

    poison_default.builder_ii_run_protocol_subagent = poison_runner

    monkeypatch.setitem(sys.modules, custom_module_name, custom_module)
    monkeypatch.setitem(sys.modules, "deepagents", poison_default)

    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    gate = create_deepagents_backend_readiness_gate(
        module_name=custom_module_name,
        package_name=custom_module_name,
        capability_gates_passed=True,
    )
    gate_path = _write(tmp_path / "custom-backend-readiness-gate.json", gate)

    assert gate["gate_state"] == "PASS"
    assert gate["module"]["module"] == custom_module_name
    assert validate_deepagents_backend_readiness_gate(gate) == []

    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        backend_mode="optional_deepagents",
        backend_readiness_gate=gate,
        backend_readiness_gate_path=gate_path,
        allowed_subagents=["repo_mapper"],
    )
    candidate_path = _write(tmp_path / "candidate.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="Joshua Shay",
        approval_reason="Approve custom optional backend module binding.",
    )
    approval_path = _write(tmp_path / "approval.json", approval)

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=tmp_path / "runs" / "custom-module",
    )

    assert summary["status"] == "COMPLETED"
    assert invoked_profiles.count("readiness_probe") == 2
    assert "repo_mapper" in invoked_profiles
