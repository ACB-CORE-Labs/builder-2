import json
from pathlib import Path

import httpx

from builder_ii.adapters.goose.goose_launcher import derive_goose_environment
from builder_ii.adapters.goose.model_gateway_adapter import (
    GooseGatewayContext,
    GooseModelGatewayAdapter,
    generate_loopback_credential,
)
from builder_ii.core.config import Settings
from builder_ii.routing.gateway_invocation import GatewayInvocationEngine, StreamChunk
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
from builder_ii.routing.model_route_binding import build_model_route_binding


class _Transport:
    def stream(self, _request, _cancel):
        yield StreamChunk("hello ")
        yield StreamChunk("goose")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        target_repo=tmp_path, project_root=tmp_path, backend="mlx-lm", model_tier="primary",
        model_alias="qwen-coder", model_primary="gemma-4-12b-4bit", model_fast="gemma-4-e4b-4bit",
        mlx_model_primary="mlx-community/gemma-4-12B-it-4bit",
        mlx_model_fast="mlx-community/gemma-4-e4b-it-4bit",
        mlx_model_phi="mlx-community/Phi-4-mini-reasoning-4bit",
        mlx_model_qwen="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        mlx_model_deepseek="mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        mlx_model_llama="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        mlx_model_codegeex="mlx-community/codegeex4-all-9b-4bit",
        mlx_model_qwen14="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        mlx_model_qwen3_coder="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        base_url="http://127.0.0.1:8080/v1", host="127.0.0.1", port=8080,
        temperature=0.0, allow_cloud_models=False,
    )


def _context(tmp_path, route_sources_factory):
    sources = route_sources_factory("goose-route")
    route = build_model_route_binding(
        recommendation=sources["recommendation"], assignment=sources["assignment"],
        execution_policy=sources["execution_policy"], registry=sources["registry"],
        budget=sources["budget"], session_id=sources["session_id"], run_id=sources["run_id"],
        obligation_id=sources["obligation_id"], role=sources["role"], max_tokens=sources["max_tokens"],
    )
    gateway = ModelExecutionGateway(
        _settings(tmp_path), sources["registry"], sources["execution_policy"],
        invocation_engine=GatewayInvocationEngine(lambda _c: _Transport()),
    )
    return GooseGatewayContext(gateway=gateway, route=route, budget=sources["budget"],
                               artifact_dir=tmp_path / "goose-artifacts",
                               local_credential=generate_loopback_credential(route.route_digest))


def test_goose_loopback_streams_only_through_gateway(tmp_path, route_sources_factory) -> None:
    context = _context(tmp_path, route_sources_factory)
    adapter = GooseModelGatewayAdapter(context)
    adapter.start()
    try:
        with httpx.stream(
            "POST", adapter.base_url + "/v1/chat/completions",
            headers={"Authorization": f"Bearer {context.local_credential}"},
            json={"model": context.route.selected_candidate.model_id,
                  "messages": [{"role": "user", "content": "hi"}], "stream": True},
        ) as response:
            text = "\n".join(response.iter_lines())
        assert response.status_code == 200
        assert "hello " in text and "goose" in text and "[DONE]" in text
        receipts = list((tmp_path / "goose-artifacts").glob("*-receipt.json"))
        assert len(receipts) == 1
        receipt = json.loads(receipts[0].read_text())
        assert receipt["route_digest"]
        assert receipt["actual_model"] == context.route.selected_candidate.model_id
    finally:
        adapter.close()


def test_goose_model_substitution_refuses_before_provider(tmp_path, route_sources_factory) -> None:
    context = _context(tmp_path, route_sources_factory)
    adapter = GooseModelGatewayAdapter(context)
    adapter.start()
    try:
        response = httpx.post(adapter.base_url + "/v1/chat/completions",
                              headers={"Authorization": f"Bearer {context.local_credential}"},
                              json={"model": "foreign", "messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code == 400
        assert not list((tmp_path / "goose-artifacts").glob("*-envelope.json"))
    finally:
        adapter.close()


def test_goose_environment_exposes_only_local_adapter_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "real-provider-secret")
    monkeypatch.setenv("GROQ_API_KEY", "another-provider-secret")
    settings = _settings(tmp_path)
    env, report = derive_goose_environment(settings, model_gateway_url="http://127.0.0.1:9999",
                                           model_gateway_credential="local-only", route_model_id="wrp-model")
    assert env["OPENAI_API_KEY"] == "local-only"
    assert "real-provider-secret" not in json.dumps(env)
    assert "another-provider-secret" not in json.dumps(env)
    assert report["provider_credentials_exposed"] is False


def test_goose_client_disconnect_propagates_into_cancellation(tmp_path, route_sources_factory) -> None:
    import socket
    import time

    from builder_ii.routing.model_execution_gateway import validate_model_call_receipt

    sources = route_sources_factory("goose-route-cancel")
    route = build_model_route_binding(
        recommendation=sources["recommendation"], assignment=sources["assignment"],
        execution_policy=sources["execution_policy"], registry=sources["registry"],
        budget=sources["budget"], session_id=sources["session_id"], run_id=sources["run_id"],
        obligation_id=sources["obligation_id"], role=sources["role"], max_tokens=sources["max_tokens"],
    )
    yielded_chunks: list[str] = []

    class _DisconnectTransport:
        def stream(self, _request, cancellation):
            for i in range(1, 10):
                cancellation.raise_if_cancelled()
                chunk = f"chunk-{i} "
                yielded_chunks.append(chunk)
                yield StreamChunk(chunk)
                time.sleep(0.04)

    gateway = ModelExecutionGateway(
        _settings(tmp_path), sources["registry"], sources["execution_policy"],
        invocation_engine=GatewayInvocationEngine(lambda _c: _DisconnectTransport()),
    )
    context = GooseGatewayContext(
        gateway=gateway, route=route, budget=sources["budget"],
        artifact_dir=tmp_path / "goose-artifacts",
        local_credential=generate_loopback_credential(route.route_digest)
    )
    adapter = GooseModelGatewayAdapter(context)
    adapter.start()
    try:
        host = "127.0.0.1"
        port = adapter.server.server_address[1]
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        body = json.dumps({
            "model": route.selected_candidate.model_id,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }).encode("utf-8")
        req = (
            f"POST /v1/chat/completions HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Authorization: Bearer {context.local_credential}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode("utf-8") + body
        s.sendall(req)
        # Read initial response headers
        _ = s.recv(256)
        # Abruptly close the socket so next write from loopback handler gets BrokenPipeError
        s.close()

        # Allow time for server to detect broken pipe on next write and complete cancellation
        time.sleep(0.25)

        receipts = list((tmp_path / "goose-artifacts").glob("*-receipt.json"))
        assert len(receipts) == 1
        receipt = json.loads(receipts[0].read_text())
        assert receipt["status"] == "cancelled"
        assert receipt["complete"] is False
        assert receipt["completion_state"] == "incomplete"
        assert receipt["attempt_count"] == 1
        assert receipt["failover_count"] == 0
        assert receipt["attempt_history"][0]["status"] == "cancelled"
        assert receipt["attempt_history"][0]["input_tokens"] > 0
        assert len(yielded_chunks) < 10
        assert validate_model_call_receipt(receipt, route=route) == []
    finally:
        adapter.close()

