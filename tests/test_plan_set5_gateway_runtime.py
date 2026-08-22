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
