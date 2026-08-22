"""Transport-only invocation mechanics for ModelExecutionGateway."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol

import httpx

from builder_ii.core.config import Settings
from builder_ii.governance.authority.capabilities import chat_completions_url

MAX_ATTEMPTS_PER_CANDIDATE = 2


class InvocationCancelled(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise InvocationCancelled("model invocation cancelled")


@dataclass(frozen=True)
class StreamChunk:
    text: str
    public: bool = True


@dataclass(frozen=True)
class TransportRequest:
    model_id: str
    provider_id: str
    client_id: str
    prompt: str
    system_prompt: str
    max_tokens: int
    temperature: float | None


class StreamingTransport(Protocol):
    def stream(self, request: TransportRequest, cancellation: CancellationToken) -> Iterable[StreamChunk]: ...


@dataclass(frozen=True)
class AttemptRecord:
    candidate_index: int
    attempt: int
    model_id: str
    provider_id: str
    client_id: str
    status: str
    started_ns: int
    first_public_chunk_ns: int | None
    completed_ns: int
    output_chunks: int
    error: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class InvocationResult:
    status: str
    content: str
    actual_candidate_index: int | None
    attempts: tuple[AttemptRecord, ...]
    first_token_latency_ms: float | None
    total_latency_ms: float
    output_chunks: int
    failover_count: int
    completion_state: str


def _transient(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return bool(getattr(exc, "retryable", False))


class GatewayInvocationEngine:
    """Bounded retry/failover executor. Candidate order is supplied by WRP."""

    def __init__(
        self,
        transport_for: Callable[[Mapping[str, Any]], StreamingTransport],
        *,
        clock: Callable[[], int] = time.monotonic_ns,
        health_for: Callable[[Mapping[str, Any]], tuple[bool, str]] | None = None,
    ):
        self._transport_for = transport_for
        self._clock = clock
        self._health_for = health_for

    def close(self) -> None:
        close = getattr(self._transport_for, "close", None)
        if callable(close):
            close()
        health_close = getattr(self._health_for, "close", None)
        if callable(health_close):
            health_close()

    def invoke(
        self,
        *,
        candidates: Iterable[Mapping[str, Any]],
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float | None,
        cancellation: CancellationToken | None = None,
        before_attempt: Callable[[Mapping[str, Any], int], None] | None = None,
        on_public_chunk: Callable[[str], None] | None = None,
    ) -> InvocationResult:
        token = cancellation or CancellationToken()
        started = self._clock()
        records: list[AttemptRecord] = []
        candidate_list = list(candidates)
        if token.cancelled:
            completed = self._clock()
            return InvocationResult("cancelled", "", None, (), None,
                                    (completed - started) / 1_000_000, 0, 0, "incomplete")
        for candidate_index, candidate in enumerate(candidate_list):
            if token.cancelled:
                completed = self._clock()
                return InvocationResult("cancelled", "", None, tuple(records), None,
                                        (completed - started) / 1_000_000, 0,
                                        max(0, candidate_index - 1), "incomplete")
            if self._health_for is not None:
                health_started = self._clock()
                healthy, health_detail = self._health_for(candidate)
                if not healthy:
                    completed = self._clock()
                    records.append(
                        AttemptRecord(
                            candidate_index,
                            0,
                            str(candidate["model_id"]),
                            str(candidate["provider_id"]),
                            str(candidate["client_id"]),
                            "unhealthy",
                            health_started,
                            None,
                            completed,
                            0,
                            health_detail[:500],
                            False,
                        )
                    )
                    continue
            for attempt in range(1, MAX_ATTEMPTS_PER_CANDIDATE + 1):
                token.raise_if_cancelled()
                if before_attempt is not None:
                    before_attempt(candidate, attempt)
                attempt_started = self._clock()
                first_ns: int | None = None
                chunks: list[str] = []
                try:
                    transport = self._transport_for(candidate)
                    request = TransportRequest(
                        model_id=str(candidate["model_id"]), provider_id=str(candidate["provider_id"]),
                        client_id=str(candidate["client_id"]), prompt=prompt, system_prompt=system_prompt,
                        max_tokens=max_tokens, temperature=temperature,
                    )
                    for chunk in transport.stream(request, token):
                        token.raise_if_cancelled()
                        if not chunk.public or not chunk.text:
                            continue
                        if first_ns is None:
                            first_ns = self._clock()
                        chunks.append(chunk.text)
                        if on_public_chunk is not None:
                            on_public_chunk(chunk.text)
                    completed = self._clock()
                    content = "".join(chunks)
                    records.append(AttemptRecord(candidate_index, attempt, request.model_id, request.provider_id,
                                                 request.client_id, "succeeded", attempt_started, first_ns, completed,
                                                 len(chunks)))
                    return InvocationResult("succeeded", content, candidate_index, tuple(records),
                                            None if first_ns is None else (first_ns - started) / 1_000_000,
                                            (completed - started) / 1_000_000, len(chunks), candidate_index, "complete")
                except InvocationCancelled:
                    completed = self._clock()
                    records.append(AttemptRecord(candidate_index, attempt, str(candidate["model_id"]),
                                                 str(candidate["provider_id"]), str(candidate["client_id"]),
                                                 "cancelled", attempt_started, first_ns, completed, len(chunks),
                                                 "cancelled", False))
                    return InvocationResult("cancelled", "".join(chunks), candidate_index, tuple(records),
                                            None if first_ns is None else (first_ns - started) / 1_000_000,
                                            (completed - started) / 1_000_000, len(chunks), candidate_index, "incomplete")
                except Exception as exc:
                    completed = self._clock()
                    retryable = first_ns is None and _transient(exc)
                    records.append(AttemptRecord(candidate_index, attempt, str(candidate["model_id"]),
                                                 str(candidate["provider_id"]), str(candidate["client_id"]),
                                                 "failed", attempt_started, first_ns, completed, len(chunks),
                                                 str(exc)[:500], retryable))
                    # Any public output forbids retry and failover.
                    if first_ns is not None:
                        return InvocationResult("failed", "".join(chunks), candidate_index, tuple(records),
                                                (first_ns - started) / 1_000_000,
                                                (completed - started) / 1_000_000, len(chunks), candidate_index, "incomplete")
                    if not retryable:
                        return InvocationResult("failed", "", candidate_index, tuple(records), None,
                                                (completed - started) / 1_000_000, 0,
                                                candidate_index, "incomplete")
                    if attempt == MAX_ATTEMPTS_PER_CANDIDATE:
                        break
                    if token.cancelled:
                        cancelled_at = self._clock()
                        return InvocationResult("cancelled", "", candidate_index, tuple(records), None,
                                                (cancelled_at - started) / 1_000_000, 0,
                                                candidate_index, "incomplete")
        completed = self._clock()
        return InvocationResult("failed", "", None, tuple(records), None,
                                (completed - started) / 1_000_000, 0,
                                max(0, len({r.candidate_index for r in records}) - 1), "incomplete")


class OpenAICompatibleHTTPTransport:
    """Reusable bounded httpx streaming transport; credentials stay in headers only."""

    def __init__(self, *, url: str, headers: Mapping[str, str] | None = None, client: httpx.Client | None = None, timeout: float = 120.0):
        self.url = url
        self.headers = dict(headers or {})
        self._owned = client is None
        self.client = client or httpx.Client(limits=httpx.Limits(max_connections=4, max_keepalive_connections=2), timeout=timeout)

    def close(self) -> None:
        if self._owned:
            self.client.close()

    def stream(self, request: TransportRequest, cancellation: CancellationToken) -> Iterator[StreamChunk]:
        cancellation.raise_if_cancelled()
        payload = {
            "model": request.model_id,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        with self.client.stream("POST", self.url, headers=self.headers, json=payload) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                cancellation.raise_if_cancelled()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    body = json.loads(data)
                    choice = (body.get("choices") or [{}])[0]
                    text = (choice.get("delta") or {}).get("content") or choice.get("text") or ""
                except (ValueError, TypeError, IndexError, AttributeError):
                    continue
                if isinstance(text, str) and text:
                    yield StreamChunk(text)


def openai_transport_factory(settings: Settings) -> Callable[[Mapping[str, Any]], StreamingTransport]:
    """Create transports for validated registry clients without persisting secrets."""
    shared = httpx.Client(limits=httpx.Limits(max_connections=4, max_keepalive_connections=2), timeout=120.0)

    def factory(candidate: Mapping[str, Any]) -> StreamingTransport:
        if candidate.get("endpoint_kind") == "cloud_stub" or candidate.get("provider_id") in {
            "openai_stub_provider", "anthropic_stub_provider"
        }:
            class _Stub:
                def stream(self, request: TransportRequest, cancellation: CancellationToken) -> Iterator[StreamChunk]:
                    cancellation.raise_if_cancelled()
                    yield StreamChunk(f"Mocked stub response for model '{request.model_id}' to: {request.prompt[:30]}...")
            return _Stub()
        if candidate.get("endpoint_kind") == "openai_compatible_cloud":
            from builder_ii.adapters.openai_compat.cloud_chat import _load_api_key, resolve_cloud_endpoint
            endpoint = resolve_cloud_endpoint(candidate)
            return OpenAICompatibleHTTPTransport(
                url=endpoint.chat_completions_url,
                headers={"Authorization": f"Bearer {_load_api_key(endpoint.api_key_env)}",
                         "Content-Type": "application/json"},
                client=shared,
            )
        return OpenAICompatibleHTTPTransport(url=chat_completions_url(settings), client=shared)

    setattr(factory, "close", shared.close)
    return factory


def backend_candidate_health(settings: Settings) -> Callable[[Mapping[str, Any]], tuple[bool, str]]:
    """Project existing backend/model identity probes into a transport health input."""

    from builder_ii.routing.backends import served_models

    client = httpx.Client(limits=httpx.Limits(max_connections=2, max_keepalive_connections=1), timeout=3.0)
    cached: dict[str, tuple[float, tuple[bool, str]]] = {}

    def check(candidate: Mapping[str, Any]) -> tuple[bool, str]:
        if candidate.get("risk_classification") == "cloud_external" or candidate.get("provider_id") in {
            "openai_stub_provider",
            "anthropic_stub_provider",
        }:
            return True, "cloud/stub health is evaluated by its governed transport"
        if str(candidate["model_id"]) != settings.active_model_id:
            return False, (
                "resident managed runtime is bound to "
                f"{settings.active_model_id}, not WRP candidate {candidate['model_id']}"
            )
        key = str(candidate["model_id"])
        now = time.monotonic()
        prior = cached.get(key)
        if prior is not None and now - prior[0] <= 5.0:
            return prior[1]
        status = served_models(settings, client=client)
        if not status.ok:
            result = (False, status.message)
            cached[key] = (now, result)
            return result
        expected = str(candidate["model_id"])
        if any(served == expected or served == expected.split("/")[-1] for served in status.model_ids):
            result = (True, f"healthy and serving {expected}")
        else:
            result = (False, f"healthy backend is not serving WRP candidate {expected}: {', '.join(status.model_ids)}")
        cached[key] = (now, result)
        return result

    setattr(check, "close", client.close)
    return check


def governed_invocation_engine(settings: Settings) -> GatewayInvocationEngine:
    """Production engine with bounded pooled transport and health-based traversal."""

    return GatewayInvocationEngine(
        openai_transport_factory(settings),
        health_for=backend_candidate_health(settings),
    )
