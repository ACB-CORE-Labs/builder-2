"""Thin OpenAI-compatible loopback adapter for canonical Goose inference."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from builder_ii.routing.gateway_invocation import CancellationToken, InvocationCancelled
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
from builder_ii.routing.model_route_binding import ModelRouteBinding, advance_route_budget


@dataclass
class GooseGatewayContext:
    gateway: ModelExecutionGateway
    route: ModelRouteBinding
    budget: dict[str, Any]
    artifact_dir: Path
    local_credential: str
    close_gateway_on_close: bool = True
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _sequence: int = 0

    @property
    def credential_ref(self) -> str:
        return "token-ref:BUILDER_GOOSE_LOOPBACK_CREDENTIAL"

    def next_paths(self) -> tuple[Path, Path, Path]:
        self._sequence += 1
        base = self.artifact_dir / f"goose-model-call-{self._sequence:04d}"
        return base.with_name(base.name + "-envelope.json"), base.with_name(base.name + "-receipt.json"), base.with_name(base.name + "-budget.json")


def _prompt(messages: Any) -> tuple[str, str]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    system: list[str] = []
    conversation: list[str] = []
    for item in messages:
        if not isinstance(item, dict) or not isinstance(item.get("content"), str):
            raise ValueError("messages entries require string content")
        if item.get("role") == "system":
            system.append(item["content"])
        else:
            conversation.append(f"{item.get('role', 'user')}: {item['content']}")
    return "\n\n".join(system) or "Answer helpfully.", "\n".join(conversation)


def make_goose_gateway_handler(context: GooseGatewayContext) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "BuilderIIGooseGateway/1"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _json_error(self, status: int, message: str) -> None:
            raw = json.dumps({"error": {"message": message, "type": "builder_ii_refusal"}}).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/v1/chat/completions", "/chat/completions"}:
                self._json_error(404, "unknown endpoint")
                return
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {context.local_credential}":
                self._json_error(401, "invalid loopback credential")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                if payload.get("model") != context.route.selected_candidate.model_id:
                    raise ValueError("Goose model does not equal WRP-selected model")
                system, prompt = _prompt(payload.get("messages"))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json_error(400, str(exc))
                return

            request_cancellation = CancellationToken()
            if context.cancellation.cancelled:
                request_cancellation.cancel()

            streaming = payload.get("stream") is True
            with context._lock:
                envelope_path, receipt_path, budget_path = context.next_paths()
                if streaming:
                    try:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Cache-Control", "no-cache")
                        self.end_headers()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        request_cancellation.cancel()
                        return

                def emit(text: str) -> None:
                    if not streaming:
                        return
                    if request_cancellation.cancelled or context.cancellation.cancelled:
                        request_cancellation.cancel()
                        raise InvocationCancelled("Goose client disconnected or cancelled")
                    data = {"id": f"builder-{context._sequence}", "object": "chat.completion.chunk",
                            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]}
                    try:
                        self.wfile.write(("data: " + json.dumps(data) + "\n\n").encode())
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as exc:
                        request_cancellation.cancel()
                        raise InvocationCancelled(f"Goose client disconnected during streaming: {exc}") from exc

                try:
                    _envelope, receipt, debited = context.gateway.run_routed_model_call(
                        route=context.route, prompt=prompt, budget=context.budget,
                        envelope_path=envelope_path, receipt_path=receipt_path, budget_path=budget_path,
                        system_prompt=system, cancellation=request_cancellation,
                        requested_model_id=str(payload.get("model")), on_public_chunk=emit,
                    )
                    if debited is not None:
                        context.budget = debited
                        context.route = advance_route_budget(context.route, debited)
                except InvocationCancelled:
                    if streaming:
                        try:
                            if not request_cancellation.cancelled:
                                self.wfile.write(b"data: [DONE]\n\n")
                                self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                            pass
                    return
                except Exception as exc:  # response is already streaming when applicable
                    if streaming:
                        try:
                            if not request_cancellation.cancelled:
                                self.wfile.write(("data: " + json.dumps({"error": {"message": str(exc)[:500]}}) + "\n\n").encode())
                                self.wfile.write(b"data: [DONE]\n\n")
                                self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                            pass
                        return
                    self._json_error(502, str(exc)[:500])
                    return
                if streaming:
                    try:
                        if not request_cancellation.cancelled:
                            self.wfile.write(b"data: [DONE]\n\n")
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        pass
                    return
                content = str(receipt.get("response_text") or "")
                body = {"id": f"builder-{context._sequence}", "object": "chat.completion",
                        "model": context.route.selected_candidate.model_id,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                     "finish_reason": "stop"}]}
                raw = json.dumps(body).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    pass

    return Handler


class GooseModelGatewayAdapter:
    """Bounded localhost server. It translates protocol only; gateway owns truth."""

    def __init__(self, context: GooseGatewayContext, *, host: str = "127.0.0.1", port: int = 0):
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("Goose model gateway must bind loopback only")
        self.context = context
        self.server = ThreadingHTTPServer((host, port), make_goose_gateway_handler(context))
        self.thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{cast(str, host)}:{port}"

    def start(self) -> None:
        if self.thread is not None:
            raise RuntimeError("Goose model gateway already started")
        self.thread = threading.Thread(target=self.server.serve_forever, name="builder-goose-model-gateway", daemon=True)
        self.thread.start()

    def close(self) -> None:
        context = self.context
        context.cancellation.cancel()
        self.server.shutdown()
        self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)
            self.thread = None
        if context.close_gateway_on_close:
            context.gateway.close()


def generate_loopback_credential(route_digest: str) -> str:
    """Non-provider local bearer; never grants authority outside the bound adapter."""
    return hashlib.sha256(("builder-goose-loopback:" + route_digest).encode()).hexdigest()
