from __future__ import annotations

import httpx

from builder_ii.routing.gateway_invocation import (
    CancellationToken,
    GatewayInvocationEngine,
    OpenAICompatibleHTTPTransport,
    StreamChunk,
    TransportRequest,
)

_CANDIDATES = [
    {"model_id": "local-a", "provider_id": "local", "client_id": "a"},
    {"model_id": "local-b", "provider_id": "local", "client_id": "b"},
]


class _Transport:
    def __init__(self, action):
        self.action = action

    def stream(self, request, cancellation):
        yield from self.action(request, cancellation)


def test_streaming_records_real_first_public_chunk() -> None:
    ticks = iter((0, 10, 20, 30))

    def chunks(_request, _cancel):
        yield StreamChunk("", public=False)
        yield StreamChunk("hello")

    result = GatewayInvocationEngine(lambda _c: _Transport(chunks), clock=lambda: next(ticks)).invoke(
        candidates=_CANDIDATES[:1], prompt="p", system_prompt="s", max_tokens=5, temperature=0
    )
    assert result.status == "succeeded"
    assert result.content == "hello"
    assert result.first_token_latency_ms == 0.00002
    assert result.output_chunks == 1


def test_transient_pre_output_failure_retries_once() -> None:
    calls = 0

    def action(_request, _cancel):
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.ConnectError("down")
        yield StreamChunk("ok")

    result = GatewayInvocationEngine(lambda _c: _Transport(action)).invoke(
        candidates=_CANDIDATES[:1], prompt="p", system_prompt="s", max_tokens=5, temperature=0
    )
    assert result.status == "succeeded"
    assert calls == 2
    assert [a.status for a in result.attempts] == ["failed", "succeeded"]


def test_failure_after_public_output_never_retries_or_fails_over() -> None:
    calls = 0

    def action(_request, _cancel):
        nonlocal calls
        calls += 1
        yield StreamChunk("partial")
        raise httpx.ReadTimeout("late")

    result = GatewayInvocationEngine(lambda _c: _Transport(action)).invoke(
        candidates=_CANDIDATES, prompt="p", system_prompt="s", max_tokens=5, temperature=0
    )
    assert result.status == "failed"
    assert result.content == "partial"
    assert calls == 1
    assert result.failover_count == 0


def test_cancellation_after_partial_output_never_retries_or_fails_over() -> None:
    token = CancellationToken()
    calls = 0

    def action(_request, _cancel):
        nonlocal calls
        calls += 1
        yield StreamChunk("partial")
        token.cancel()
        yield StreamChunk("forbidden")

    result = GatewayInvocationEngine(lambda _c: _Transport(action)).invoke(
        candidates=_CANDIDATES, prompt="p", system_prompt="s", max_tokens=5,
        temperature=0, cancellation=token
    )
    assert result.status == "cancelled"
    assert result.content == "partial"
    assert calls == 1
    assert result.failover_count == 0


def test_pre_cancel_makes_zero_provider_calls() -> None:
    token = CancellationToken()
    token.cancel()
    calls = 0

    def factory(_candidate):
        nonlocal calls
        calls += 1
        return _Transport(lambda _r, _c: iter(()))

    result = GatewayInvocationEngine(factory).invoke(
        candidates=_CANDIDATES, prompt="p", system_prompt="s", max_tokens=5,
        temperature=0, cancellation=token
    )
    assert result.status == "cancelled"
    assert calls == 0


def test_permanent_http_4xx_never_retries_or_fails_over() -> None:
    calls = 0

    def action(_request, _cancel):
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", "http://local/v1/chat/completions")
        response = httpx.Response(400, request=request)
        raise httpx.HTTPStatusError("bad request", request=request, response=response)
        yield

    result = GatewayInvocationEngine(lambda _candidate: _Transport(action)).invoke(
        candidates=_CANDIDATES, prompt="p", system_prompt="s", max_tokens=5, temperature=0
    )
    assert result.status == "failed"
    assert calls == 1
    assert result.failover_count == 0


def test_transient_exhaustion_fails_over_only_in_supplied_order() -> None:
    seen = []

    def factory(candidate):
        seen.append(candidate["model_id"])
        if candidate["model_id"] == "local-a":
            def fail(_r, _c):
                raise httpx.ConnectError("down")
                yield
            return _Transport(fail)
        return _Transport(lambda _r, _c: iter((StreamChunk("ok"),)))

    result = GatewayInvocationEngine(factory).invoke(
        candidates=_CANDIDATES, prompt="p", system_prompt="s", max_tokens=5, temperature=0
    )
    assert result.status == "succeeded"
    assert seen == ["local-a", "local-a", "local-b"]
    assert result.failover_count == 1
    assert result.actual_candidate_index == 1


def test_unhealthy_primary_skips_provider_and_uses_wrp_secondary() -> None:
    seen: list[str] = []

    def health(candidate):
        return (candidate["model_id"] != "local-a", "primary health probe failed")

    def factory(candidate):
        seen.append(candidate["model_id"])
        return _Transport(lambda _r, _c: iter((StreamChunk("ok"),)))

    result = GatewayInvocationEngine(factory, health_for=health).invoke(
        candidates=_CANDIDATES,
        prompt="p",
        system_prompt="s",
        max_tokens=5,
        temperature=0,
    )
    assert result.status == "succeeded"
    assert seen == ["local-b"]
    assert result.failover_count == 1
    assert result.attempts[0].status == "unhealthy"


def test_transport_omits_null_temperature_for_strict_openai_servers() -> None:
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter(("data: [DONE]",))

    class Client:
        def stream(self, _method, _url, **kwargs):
            seen.update(kwargs["json"])
            return Response()

    transport = OpenAICompatibleHTTPTransport(url="http://loopback", client=Client())
    list(
        transport.stream(
            TransportRequest("m", "p", "c", "prompt", "system", 4, None),
            CancellationToken(),
        )
    )
    assert "temperature" not in seen


def test_attempt_record_has_cost_accounting_fields() -> None:
    def action(_request, _cancel):
        yield StreamChunk("hello world")

    engine = GatewayInvocationEngine(lambda _c: _Transport(action))
    result = engine.invoke(
        candidates=_CANDIDATES[:1],
        prompt="say hi",
        system_prompt="system",
        max_tokens=10,
        temperature=0.0,
    )
    assert result.status == "succeeded"
    assert len(result.attempts) == 1
    attempt = result.attempts[0]
    assert attempt.input_tokens > 0
    assert attempt.output_tokens > 0
    assert attempt.total_tokens == attempt.input_tokens + attempt.output_tokens
    assert attempt.token_accounting in ("measured", "estimated")


def test_partial_failure_attempt_records_incurred_cost() -> None:
    def action(_request, _cancel):
        yield StreamChunk("partial text")
        raise httpx.ReadTimeout("interrupted mid-stream")

    engine = GatewayInvocationEngine(lambda _c: _Transport(action))
    result = engine.invoke(
        candidates=_CANDIDATES[:1],
        prompt="prompt with some tokens",
        system_prompt="system",
        max_tokens=10,
        temperature=0.0,
    )
    assert result.status == "failed"
    assert len(result.attempts) == 1
    attempt = result.attempts[0]
    assert attempt.input_tokens > 0
    assert attempt.output_tokens > 0
    assert attempt.total_tokens == attempt.input_tokens + attempt.output_tokens
    assert attempt.status == "failed"


def test_pre_provider_failure_records_zero_cost() -> None:
    def action(_request, _cancel):
        raise httpx.ConnectError("connection refused before request sent")
        yield

    engine = GatewayInvocationEngine(lambda _c: _Transport(action))
    result = engine.invoke(
        candidates=_CANDIDATES[:1],
        prompt="prompt",
        system_prompt="system",
        max_tokens=10,
        temperature=0.0,
    )
    assert result.status == "failed"
    for attempt in result.attempts:
        assert attempt.input_tokens == 0
        assert attempt.output_tokens == 0
        assert attempt.total_tokens == 0
        assert attempt.estimated_usd == 0.0


def test_routed_model_call_debits_budget_on_partial_failure(tmp_path, route_sources_factory) -> None:
    from builder_ii.core.config import Settings
    from builder_ii.routing.model_execution_gateway import ModelExecutionGateway, validate_model_call_receipt
    from builder_ii.routing.model_route_binding import build_model_route_binding

    sources = route_sources_factory("partial-fail-route")
    route = build_model_route_binding(
        recommendation=sources["recommendation"],
        assignment=sources["assignment"],
        execution_policy=sources["execution_policy"],
        registry=sources["registry"],
        budget=sources["budget"],
        session_id=sources["session_id"],
        run_id=sources["run_id"],
        obligation_id=sources["obligation_id"],
        role=sources["role"],
        max_tokens=sources["max_tokens"],
    )

    def partial_action(_request, _cancel):
        yield StreamChunk("partial response tokens")
        raise httpx.ReadTimeout("socket timed out")

    settings = Settings(
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
    gateway = ModelExecutionGateway(
        settings,
        sources["registry"],
        sources["execution_policy"],
        invocation_engine=GatewayInvocationEngine(lambda _c: _Transport(partial_action)),
    )
    env_path = tmp_path / "env.json"
    rec_path = tmp_path / "rec.json"
    budget_path = tmp_path / "budget_succ.json"

    _env, receipt, debited = gateway.run_routed_model_call(
        route=route,
        prompt="test prompt for partial failure",
        budget=sources["budget"],
        envelope_path=env_path,
        receipt_path=rec_path,
        budget_path=budget_path,
    )

    assert receipt["status"] == "failed"
    assert receipt["complete"] is False
    assert receipt["completion_state"] == "incomplete"
    assert receipt["cost_report"]["total_tokens"] > 0
    assert debited is not None
    assert debited["spent_total_tokens"] > 0
    assert debited["budget_version"] == sources["budget"]["budget_version"] + 1
    assert validate_model_call_receipt(receipt, route=route) == []


def test_provider_contacted_timeout_before_first_chunk_accounts_input_cost() -> None:
    price_book = {
        "entries": [{"model_id": "local-a", "input_usd_per_1k": 0.005, "output_usd_per_1k": 0.015, "currency": "USD"}]
    }

    def action(_request, _cancel):
        # Provider contacted and accepted request, but timed out before yielding any chunk
        raise httpx.ReadTimeout("read timeout before first token")
        yield

    engine = GatewayInvocationEngine(lambda _c: _Transport(action), price_book=price_book)
    result = engine.invoke(
        candidates=_CANDIDATES[:1],
        prompt="prompt with some tokens",
        system_prompt="system",
        max_tokens=10,
        temperature=0.0,
    )
    assert result.status == "failed"
    assert len(result.attempts) >= 1
    attempt = result.attempts[0]
    assert attempt.provider_contacted is True
    assert attempt.input_tokens > 0
    assert attempt.output_tokens == 0
    assert attempt.total_tokens == attempt.input_tokens
    assert attempt.estimated_usd > 0.0


def test_provider_contacted_http_500_accounts_input_cost() -> None:
    price_book = {
        "entries": [{"model_id": "local-a", "input_usd_per_1k": 0.005, "output_usd_per_1k": 0.015, "currency": "USD"}]
    }

    def action(_request, _cancel):
        req = httpx.Request("POST", "http://provider")
        res = httpx.Response(500, request=req)
        raise httpx.HTTPStatusError("500 internal server error", request=req, response=res)
        yield

    engine = GatewayInvocationEngine(lambda _c: _Transport(action), price_book=price_book)
    result = engine.invoke(
        candidates=_CANDIDATES[:1],
        prompt="prompt with some tokens",
        system_prompt="system",
        max_tokens=10,
        temperature=0.0,
    )
    assert result.status == "failed"
    assert len(result.attempts) >= 1
    attempt = result.attempts[0]
    assert attempt.provider_contacted is True
    assert attempt.input_tokens > 0
    assert attempt.output_tokens == 0
    assert attempt.total_tokens == attempt.input_tokens
    assert attempt.estimated_usd > 0.0


