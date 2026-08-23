from __future__ import annotations

import json as json_lib
from collections.abc import Sequence
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage

from builder_ii.adapters.deepagents.native_runtime import (
    MAX_ACTIVE_WORKERS,
    BuilderGovernanceMiddleware,
    DigestBoundCheckpointSaver,
    NativeDeepAgentsRuntime,
    NativeEventRecorder,
    NativeRuntimeLimits,
    _default_response_strategy,
    _hitl_tool,
    _messages_prompt,
    validate_native_evidence_bundle,
    wrp_subagents_from_obligations,
)
from builder_ii.core.artifact_chain_verification import verify_artifact_chain
from builder_ii.core.config import Settings
from builder_ii.core.orchestration_lane_policy import create_orchestration_lane_policy_artifact
from builder_ii.core.orchestration_obligation import create_orchestration_obligation
from builder_ii.governance.ledger.artifact_index_records import create_artifact_index_record
from builder_ii.routing.gateway_invocation import GatewayInvocationEngine, StreamChunk
from builder_ii.routing.model_budget import create_model_budget
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
from builder_ii.routing.model_route_binding import build_model_route_binding
from builder_ii.routing.model_routing_policy import create_model_execution_policy


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        target_repo=tmp_path / "target",
        backend="mlx-lm",
        model_tier="primary",
        model_alias="qwen-coder",
        model_primary="gemma-4-12b-4bit",
        model_fast="gemma-4-e4b-4bit",
        mlx_model_primary="mlx-community/gemma-4-12B-it-4bit",
        mlx_model_fast="mlx-community/gemma-4-e4b-it-4bit",
        mlx_model_phi="mlx-community/Phi-4-mini-reasoning-4bit",
        mlx_model_qwen="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        mlx_model_deepseek="mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        mlx_model_llama="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        mlx_model_codegeex="mlx-community/codegeex4-all-9b-4bit",
        mlx_model_qwen14="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        mlx_model_qwen3_coder="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.0,
        project_root=tmp_path,
        allow_cloud_models=True,
    )


class _Transport:
    def stream(self, _request, _cancel):
        yield StreamChunk("scripted")


def _gateway(tmp_path: Path):
    registry = create_model_client_registry()
    root = Path("tests/fixtures/artifacts")
    recommendation = json_lib.loads((root / "model-recommendation.json").read_text())
    assignment = json_lib.loads((root / "agent-assignment-plan.json").read_text())
    policy = create_model_execution_policy(recommendation, max_tokens=1024)
    budget = create_model_budget(session_id="native-plan-set-2-proof", max_output_tokens=16_384,
                                 max_total_tokens=100_000, max_usd=5)
    route = build_model_route_binding(recommendation=recommendation, assignment=assignment,
                                      execution_policy=policy, registry=registry, budget=budget,
                                      session_id="native-plan-set-2-proof", run_id="native-run",
                                      obligation_id="native-parent", role="deepagents_parent", max_tokens=256)
    gateway = ModelExecutionGateway(_settings(tmp_path), registry, policy,
                                    invocation_engine=GatewayInvocationEngine(lambda _c: _Transport()))
    return gateway, route, budget


def _obligations() -> list[dict]:
    lane_policy = create_orchestration_lane_policy_artifact()
    lane_digest = lane_policy["lane_policy_digest"]
    seal_digest = "a" * 64
    common = {
        "lane": "deepagents",
        "obligation_kind": "planning_step",
        "output_contract_expected_kind": "builder_ii.deepagents_native_child_result",
        "output_contract_required_evidence_kinds": [],
        "denied_actions": ["shell", "filesystem mutation", "git mutation", "provider bypass"],
        "refused_lanes": ["hitl_patch", "goose"],
        "file_refs": [],
        "briefing_bytes": 128,
        "budget_partition": {
            "max_subagents": 1,
            "max_events": 32,
            "max_output_bytes": 4096,
            "max_human_gates": 1,
        },
        "parent_ref": {"seal_digest": seal_digest},
        "lane_policy_digest": lane_digest,
    }
    return [
        create_orchestration_obligation(
            **common,
            task="Analyze the first bounded planning obligation.",
            subagent_profile="native-alpha",
        ),
        create_orchestration_obligation(
            **common,
            task="Analyze the second bounded planning obligation.",
            subagent_profile="native-beta",
        ),
    ]


def _scripted_response(_receipt: dict, messages: Sequence[BaseMessage]) -> AIMessage:
    combined = "\n".join(str(message.content) for message in messages)
    if "BUILDER_II_OBLIGATION=" in combined:
        return AIMessage(content="bounded child obligation completed")

    prior_calls = [
        call
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]
    if not any(call["name"] == "task" for call in prior_calls):
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "task",
                    "args": {"description": "Discharge alpha obligation", "subagent_type": "native-alpha"},
                    "id": "task-alpha",
                    "type": "tool_call",
                },
                {
                    "name": "task",
                    "args": {"description": "Discharge beta obligation", "subagent_type": "native-beta"},
                    "id": "task-beta",
                    "type": "tool_call",
                },
            ],
        )
    if not any(call["name"] == "write_file" for call in prior_calls):
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": "/tmp/forbidden", "content": "must not be written"},
                    "id": "forbidden-write",
                    "type": "tool_call",
                }
            ],
        )
    if not any(call["name"] == "builder_governed_echo" for call in prior_calls):
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "builder_governed_echo",
                    "args": {"text": "native governed tool proof"},
                    "id": "governed-echo",
                    "type": "tool_call",
                }
            ],
        )
    if not any(call["name"] == "builder_request_hitl" for call in prior_calls):
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "builder_request_hitl",
                    "args": {"reason": "two obligations and governed tool call completed"},
                    "id": "hitl-request",
                    "type": "tool_call",
                }
            ],
        )
    return AIMessage(content="native parent run completed after exact-checkpoint HITL resume")


def test_default_response_strategy_accepts_fenced_json_tool_calls() -> None:
    response = _default_response_strategy(
        {
            "response_text": '```json\n{"tool_calls":[{"name":"builder_request_hitl","args":{"reason":"pause"}}],"content":""}\n```'
        },
        [],
    )
    assert response.tool_calls[0]["name"] == "builder_request_hitl"
    assert response.tool_calls[0]["args"] == {"reason": "pause"}


def test_default_response_strategy_accepts_qwen_fenced_json_terminator() -> None:
    response = _default_response_strategy(
        {
            "response_text": (
                '```json\n{"tool_calls":[{"name":"builder_request_hitl","args":{}}],"content":""}\n```'
                "<|im_end|>"
            )
        },
        [],
    )
    assert response.tool_calls[0]["name"] == "builder_request_hitl"
    assert response.tool_calls[0]["args"] == {}


def test_messages_prompt_preserves_prior_tool_call_continuity() -> None:
    system, conversation = _messages_prompt(
        [
            SystemMessage(content="Use the staged protocol."),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {"description": "alpha", "subagent_type": "native-alpha"},
                        "id": "task-alpha",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(content="bounded child complete", tool_call_id="task-alpha", name="task"),
        ]
    )

    assert system == "Use the staged protocol."
    assert '"name": "task"' in conversation
    assert '"subagent_type": "native-alpha"' in conversation
    assert "tool: bounded child complete" in conversation


def test_hitl_tool_defers_until_the_native_workload_is_complete() -> None:
    ready = False
    hitl = _hitl_tool(lambda: ready)

    assert hitl.invoke({"reason": "too early"}) == (
        "HITL request deferred: complete both obligations and the governed tool call first."
    )

    ready = True
    assert hitl.invoke({"reason": "workload complete"}) == "operator approved continuation: workload complete"


def _runtime(tmp_path: Path) -> NativeDeepAgentsRuntime:
    gateway, route, budget = _gateway(tmp_path)
    return NativeDeepAgentsRuntime(
        gateway=gateway,
        route=route,
        budget=budget,
        obligations=_obligations(),
        output_dir=tmp_path / "native-run",
        session_id="native-plan-set-2-proof",
        authority_refs=[{"role": "approval", "sha256": "a" * 64}],
        limits=NativeRuntimeLimits(active_workers=2, max_model_calls=16, max_tool_calls=16),
        response_strategy=_scripted_response,
    )


def test_native_runtime_delegates_calls_tools_interrupts_and_resumes_from_disk(tmp_path: Path) -> None:
    interrupted = _runtime(tmp_path).start("Delegate both obligations, use the governed tool, then pause for HITL.")

    assert interrupted["status"] == "INTERRUPTED"
    assert interrupted["official_factory"] == "deepagents.create_deep_agent"
    assert len(set(interrupted["delegated_subagents"])) == 2
    assert interrupted["tool_receipt_refs"]
    approved_digest = interrupted["checkpoint_store_digest"]

    # Reconstruct the runtime and saver to prove resume uses persisted state,
    # not the original in-process graph object.
    completed = _runtime(tmp_path).resume(approved_checkpoint_digest=approved_digest)

    assert completed["status"] == "COMPLETED"
    assert completed["approved_checkpoint_digest"] == approved_digest
    assert completed["completed_task_count"] == 2
    assert completed["active_workers"] == 2
    assert completed["single_model_instance"] is True
    assert len(completed["model_receipt_refs"]) >= 5
    assert completed["tool_receipt_refs"]
    assert validate_native_evidence_bundle(completed) == []
    assert all(child["delegated"] and child["completed"] for child in completed["parent_child_chain"])
    assert {"hitl_interrupted", "hitl_resumed", "native_run_completed"}.issubset(
        completed["event_types"]
    )
    assert "tool_denied" in completed["event_types"]
    index = create_artifact_index_record(tmp_path / "native-run", recursive=True)
    assert index["counts"]["unknown"] == 0
    assert index["counts"]["invalid"] == 0
    chain = verify_artifact_chain(sorted((tmp_path / "native-run").rglob("*.json")))
    assert chain["valid"] is True, chain["errors"]


def test_checkpoint_tamper_fails_closed(tmp_path: Path) -> None:
    interrupted = _runtime(tmp_path).start("Run the native scenario.")
    checkpoint_path = tmp_path / "native-run" / "native-checkpoint-store.json"
    payload = json_lib.loads(checkpoint_path.read_text(encoding="utf-8"))
    payload["artifact_is_authority"] = True
    checkpoint_path.write_text(json_lib.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="checkpoint store digest mismatch"):
        DigestBoundCheckpointSaver(checkpoint_path)
    with pytest.raises(ValueError, match="checkpoint store digest mismatch"):
        _runtime(tmp_path).resume(approved_checkpoint_digest=interrupted["checkpoint_store_digest"])


def test_runtime_limits_cap_workers_and_wrp_specs_inherit_boundaries(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="active_workers"):
        NativeRuntimeLimits(active_workers=MAX_ACTIVE_WORKERS + 1).validate()

    runtime = _runtime(tmp_path)
    specs = wrp_subagents_from_obligations(_obligations(), governed_tools=runtime.tools[:1])
    assert [spec["name"] for spec in specs] == ["native-alpha", "native-beta"]
    assert all("BUILDER_II_OBLIGATION=" in spec["system_prompt"] for spec in specs)
    assert all(spec["permissions"][0].mode == "deny" for spec in specs)
    assert all(spec["tools"] == runtime.tools[:1] for spec in specs)


def test_middleware_restores_cumulative_budgets_and_cancellation(tmp_path: Path) -> None:
    recorder = NativeEventRecorder(tmp_path / "events")
    recorder.append("model_admitted", {"model_call": 1})
    recorder.append("tool_admitted", {"tool": "task", "tool_call": 1})

    middleware = BuilderGovernanceMiddleware(
        recorder=NativeEventRecorder(tmp_path / "events"),
        max_model_calls=2,
        max_tool_calls=2,
    )
    assert middleware._model_calls == 1
    assert middleware._tool_calls == 1

    middleware.cancel()
    restored = BuilderGovernanceMiddleware(
        recorder=NativeEventRecorder(tmp_path / "events"),
        max_model_calls=2,
        max_tool_calls=2,
    )
    assert restored.cancelled is True
    assert restored.recorder.events[-1]["event_type"] == "run_cancelled"
