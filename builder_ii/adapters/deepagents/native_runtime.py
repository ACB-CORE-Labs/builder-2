"""Official Deep Agents runtime kept subordinate to Builder-II authority.

This module is intentionally imported only by the optional native caller.  The
governance-only base installation therefore does not import LangChain or Deep
Agents.  The native path has one shape:

    approved candidate -> WRP obligations -> create_deep_agent -> interrupt
    -> digest-bound checkpoint -> explicit resume -> evidence bundle

Deep Agents owns graph scheduling and context isolation.  Builder-II continues
to own model/tool admission, budgets, checkpoints, receipts, and the evidence
chain.  No native filesystem, shell, Git, or provider tool is admitted.
"""

from __future__ import annotations

import base64
import hashlib
import json as json_lib
import re
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.middleware.filesystem import FilesystemPermission
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ConfigDict, Field, PrivateAttr

from builder_ii.adapters.deepagents.native_artifacts import (
    DEFAULT_ACTIVE_WORKERS,
    MAX_ACTIVE_WORKERS,
    NATIVE_CHECKPOINT_STORE_KIND,
    NATIVE_EVENT_KIND,
    NATIVE_EVIDENCE_KIND,
    NATIVE_RUNTIME_SCHEMA_VERSION,
    validate_native_evidence_bundle,
)
from builder_ii.core.config_schema import digest_jsonable
from builder_ii.core.mcp_policy import (
    ENVELOPE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
    validate_mcp_receipt,
)
from builder_ii.core.orchestration_obligation import validate_orchestration_obligation
from builder_ii.core.tool_invocation_gateway import execute_tool_envelope
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
from builder_ii.routing.model_route_binding import ModelRouteBinding, advance_route_budget

_NATIVE_ALLOWED_TOOLS = frozenset({"task", "builder_governed_echo", "builder_request_hitl"})
_DENIED_NATIVE_CAPABILITIES = (
    "native filesystem reads",
    "native filesystem writes",
    "shell execution",
    "git mutation",
    "direct provider calls",
    "unapproved external tools",
)
_QWEN_MESSAGE_TERMINATOR = "<|im_end|>"
_FENCED_JSON = re.compile(
    r"^```(?:json)?\s*(?P<payload>\{.*\})\s*```$",
    re.DOTALL,
)


def _canonical_digest(data: dict[str, Any], *, digest_key: str) -> str:
    return digest_jsonable(data, digest_key=digest_key)


def _write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json_lib.loads(path.read_text(encoding="utf-8"))
    except (OSError, json_lib.JSONDecodeError) as exc:
        raise ValueError(f"failed to load {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _raw_file_ref(path: Path, *, role: str, kind: str = "") -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "role": role,
        "kind": kind,
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "required": True,
    }


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(message, AIMessage) and message.tool_calls:
        return json_lib.dumps(
            {
                "content": content,
                "tool_calls": [
                    {
                        "name": call["name"],
                        "args": call["args"],
                        "id": call["id"],
                    }
                    for call in message.tool_calls
                ],
            },
            sort_keys=True,
            default=str,
        )
    if isinstance(content, str):
        return content
    return json_lib.dumps(content, sort_keys=True, default=str)


def _messages_prompt(messages: Sequence[BaseMessage]) -> tuple[str, str]:
    system_parts: list[str] = []
    conversation: list[str] = []
    for message in messages:
        text = _message_text(message)
        if isinstance(message, SystemMessage):
            system_parts.append(text)
        else:
            conversation.append(f"{message.type}: {text}")
    return "\n\n".join(system_parts), "\n".join(conversation) or "Continue the governed run."


def _default_response_strategy(receipt: dict[str, Any], _messages: Sequence[BaseMessage]) -> AIMessage:
    """Decode the narrow JSON tool-call contract or return plain gateway text."""

    text = str(receipt.get("response_text", ""))
    stripped = text.strip()
    if stripped.endswith(_QWEN_MESSAGE_TERMINATOR):
        stripped = stripped.removesuffix(_QWEN_MESSAGE_TERMINATOR).rstrip()
    fenced_json = _FENCED_JSON.fullmatch(stripped)
    if fenced_json is not None:
        stripped = fenced_json.group("payload")
    try:
        value = json_lib.loads(stripped)
    except json_lib.JSONDecodeError:
        return AIMessage(content=text)
    if not isinstance(value, dict):
        return AIMessage(content=text)
    calls = value.get("tool_calls", [])
    if not isinstance(calls, list):
        return AIMessage(content=text)
    normalized: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            raise ValueError("gateway response tool_calls entries must be objects")
        name = call.get("name")
        args = call.get("args")
        if not isinstance(name, str) or not isinstance(args, dict):
            raise ValueError("gateway response tool call requires string name and object args")
        normalized.append(
            {
                "name": name,
                "args": args,
                "id": str(call.get("id") or f"builder-tool-{index}"),
                "type": "tool_call",
            }
        )
    return AIMessage(content=str(value.get("content", "")), tool_calls=normalized)


def _project_stage_tool_calls(
    response: AIMessage,
    stage: str,
    denial_callback: Callable[[dict[str, Any], str], None] | None = None,
) -> AIMessage:
    """Project raw model proposals onto the single tool class admitted for this stage."""

    admitted_name = {
        "delegate_tasks": "task",
        "governed_echo": "builder_governed_echo",
        "request_hitl": "builder_request_hitl",
        "complete": None,
    }.get(stage)
    if stage not in {"delegate_tasks", "governed_echo", "request_hitl", "complete"}:
        raise ValueError(f"unknown native Deep Agents stage: {stage}")
    admitted = [call for call in response.tool_calls if call["name"] == admitted_name]
    if stage in {"governed_echo", "request_hitl"}:
        admitted = admitted[:1]
    admitted_ids = {call["id"] for call in admitted}
    if denial_callback is not None:
        for call in response.tool_calls:
            if call["id"] not in admitted_ids:
                denial_callback(call, stage)
    return AIMessage(content=response.content, tool_calls=admitted)


class GatewayBackedChatModel(BaseChatModel):
    """LangChain chat-model adapter that executes every call through Builder-II."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    gateway: ModelExecutionGateway = Field(exclude=True)
    model_id: str
    route: ModelRouteBinding = Field(exclude=True)
    budget: dict[str, Any] = Field(exclude=True)
    output_dir: Path = Field(exclude=True)
    session_id: str
    max_tokens: int = 256
    temperature: float = 0.0
    approval_path: Path | None = Field(default=None, exclude=True)
    response_strategy: Callable[[dict[str, Any], Sequence[BaseMessage]], AIMessage] = Field(
        default=_default_response_strategy,
        exclude=True,
    )
    receipt_callback: Callable[[dict[str, Any], Path], None] | None = Field(default=None, exclude=True)
    stage_provider: Callable[[], str] | None = Field(default=None, exclude=True)
    stage_denial_callback: Callable[[dict[str, Any], str], None] | None = Field(default=None, exclude=True)

    _counter: int = PrivateAttr(default=0)
    _counter_initialized: bool = PrivateAttr(default=False)
    _counter_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)
    _budget_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)
    _bound_tool_names: tuple[str, ...] = PrivateAttr(default=())
    _bound_tool_specs: tuple[dict[str, Any], ...] = PrivateAttr(default=())

    @property
    def _llm_type(self) -> str:
        return "builder-ii-model-execution-gateway"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "session_id": self.session_id}

    def bind_tools(self, tools: Sequence[Any], **_kwargs: Any) -> GatewayBackedChatModel:
        specs: list[dict[str, Any]] = []
        for item in tools:
            name = getattr(item, "name", None)
            if not isinstance(name, str):
                continue
            input_schema = item.get_input_schema().model_json_schema()
            specs.append(
                {
                    "name": name,
                    "description": str(getattr(item, "description", "")),
                    "parameters": input_schema,
                }
            )
        self._bound_tool_specs = tuple(specs)
        self._bound_tool_names = tuple(spec["name"] for spec in specs)
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **_kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager
        with self._counter_lock:
            if not self._counter_initialized:
                existing = list((self.output_dir / "model-calls").glob("model-call-*-receipt.json"))
                self._counter = len(existing)
                self._counter_initialized = True
            self._counter += 1
            sequence = self._counter
        model_dir = self.output_dir / "model-calls"
        envelope_path = model_dir / f"model-call-{sequence:04d}-envelope.json"
        receipt_path = model_dir / f"model-call-{sequence:04d}-receipt.json"
        system_prompt, prompt = _messages_prompt(messages)
        is_bounded_child = "BUILDER_II_OBLIGATION=" in system_prompt
        if self.stage_provider is not None and not is_bounded_child:
            stage = self.stage_provider()
            stage_instructions = {
                "delegate_tasks": (
                    "Call task exactly once for each still-incomplete required subagent profile. "
                    "Do not call builder_governed_echo or builder_request_hitl yet."
                ),
                "governed_echo": (
                    "Both required subagent tasks are complete. Do not call task again. "
                    "Call builder_governed_echo exactly once with non-empty text."
                ),
                "request_hitl": (
                    "Both required subagent tasks and the governed echo are complete. Do not call task or "
                    "builder_governed_echo again. Call builder_request_hitl exactly once with a non-empty reason."
                ),
                "complete": "The approved HITL action is complete. Return a concise final response with no tool calls.",
            }
            if stage not in stage_instructions:
                raise ValueError(f"unknown native Deep Agents stage: {stage}")
            system_prompt = (
                f"{system_prompt}\n\nBUILDER_II_CURRENT_STAGE={stage}. "
                f"{stage_instructions[stage]} This stage is derived from Builder-II runtime evidence and "
                "overrides any earlier conversational stage wording."
            )
        advertised_tool_names = self._bound_tool_names
        advertised_tool_specs = self._bound_tool_specs
        if self.stage_provider is not None and not is_bounded_child:
            admitted_name = {
                "delegate_tasks": "task",
                "governed_echo": "builder_governed_echo",
                "request_hitl": "builder_request_hitl",
                "complete": None,
            }[stage]
            advertised_tool_names = tuple(name for name in self._bound_tool_names if name == admitted_name)
            advertised_tool_specs = tuple(
                spec for spec in self._bound_tool_specs if spec["name"] == admitted_name
            )
        if advertised_tool_names:
            system_prompt = (
                f"{system_prompt}\n\n"
                "BUILDER_II_TOOL_CALL_PROTOCOL: If you need to call a governed tool, respond with ONLY one JSON "
                "object of the form {\"tool_calls\":[{\"name\":\"TOOL\",\"args\":{}}],\"content\":\"\"}. "
                f"Allowed tool names for this turn: {', '.join(advertised_tool_names)}. "
                f"Tool schemas: {json_lib.dumps(advertised_tool_specs, sort_keys=True)}. "
                "Use exact tool names and object arguments; do not emit Markdown or explanatory prose around JSON. "
                "Complete the outer JSON object with its closing brace before any model message terminator."
            )
        if self.model_id != self.route.selected_candidate.model_id:
            raise ValueError("Deep Agents runtime model does not equal WRP-selected model")
        with self._budget_lock:
            _envelope, receipt, debited = self.gateway.run_routed_model_call(
                route=self.route, prompt=prompt, system_prompt=system_prompt,
                envelope_path=envelope_path, receipt_path=receipt_path,
                budget=self.budget, requested_model_id=self.model_id,
            )
            if debited is not None:
                self.budget = debited
                self.route = advance_route_budget(self.route, debited)
        if self.receipt_callback is not None:
            self.receipt_callback(receipt, receipt_path)
        response = self.response_strategy(receipt, messages)
        if self.stage_provider is not None and not is_bounded_child:
            response = _project_stage_tool_calls(response, stage, self.stage_denial_callback)
        return ChatResult(generations=[ChatGeneration(message=response)])


def _typed_bytes(value: tuple[str, bytes]) -> dict[str, str]:
    return {"type": value[0], "data": base64.b64encode(value[1]).decode("ascii")}


def _load_typed_bytes(value: Any, *, field: str) -> tuple[str, bytes]:
    if not isinstance(value, dict) or not isinstance(value.get("type"), str) or not isinstance(value.get("data"), str):
        raise ValueError(f"{field} must be a serialized typed value")
    try:
        return value["type"], base64.b64decode(value["data"], validate=True)
    except ValueError as exc:
        raise ValueError(f"{field}.data must be valid base64") from exc


class DigestBoundCheckpointSaver(InMemorySaver):
    """An InMemorySaver made process-durable with a digest-bound JSON snapshot.

    The upstream serializer bytes are preserved verbatim.  A fresh instance can
    restore the exact checkpoint, writes, and channel blobs.  Reads fail closed
    if the on-disk payload was edited after the last write.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self._persistence_lock = threading.RLock()
        if path.exists():
            self._restore()

    def _snapshot(self) -> dict[str, Any]:
        storage_entries: list[dict[str, Any]] = []
        for thread_id, namespaces in self.storage.items():
            for namespace, checkpoints in namespaces.items():
                for checkpoint_id, (checkpoint, metadata, parent_id) in checkpoints.items():
                    storage_entries.append(
                        {
                            "thread_id": thread_id,
                            "namespace": namespace,
                            "checkpoint_id": checkpoint_id,
                            "checkpoint": _typed_bytes(checkpoint),
                            "metadata": _typed_bytes(metadata),
                            "parent_checkpoint_id": parent_id,
                        }
                    )
        write_entries: list[dict[str, Any]] = []
        for (thread_id, namespace, checkpoint_id), writes in self.writes.items():
            for (task_id, index), (stored_task_id, channel, value, task_path) in writes.items():
                write_entries.append(
                    {
                        "thread_id": thread_id,
                        "namespace": namespace,
                        "checkpoint_id": checkpoint_id,
                        "task_id": task_id,
                        "index": index,
                        "stored_task_id": stored_task_id,
                        "channel": channel,
                        "value": _typed_bytes(value),
                        "task_path": task_path,
                    }
                )
        blob_entries: list[dict[str, Any]] = []
        for (thread_id, namespace, channel, version), value in self.blobs.items():
            blob_entries.append(
                {
                    "thread_id": thread_id,
                    "namespace": namespace,
                    "channel": channel,
                    "version": version,
                    "value": _typed_bytes(value),
                }
            )
        content: dict[str, Any] = {
            "kind": NATIVE_CHECKPOINT_STORE_KIND,
            "schema_version": NATIVE_RUNTIME_SCHEMA_VERSION,
            "storage": storage_entries,
            "writes": write_entries,
            "blobs": blob_entries,
            "artifact_is_authority": False,
            "grants_authority": False,
        }
        content["checkpoint_store_digest"] = _canonical_digest(content, digest_key="checkpoint_store_digest")
        return content

    def _persist(self) -> None:
        _write_json(self._snapshot(), self.path)

    def _restore(self) -> None:
        payload = _load_json(self.path, label="native Deep Agents checkpoint store")
        expected = _canonical_digest(payload, digest_key="checkpoint_store_digest")
        if payload.get("checkpoint_store_digest") != expected:
            raise ValueError("native Deep Agents checkpoint store digest mismatch")
        if payload.get("kind") != NATIVE_CHECKPOINT_STORE_KIND:
            raise ValueError(f"native checkpoint kind must be {NATIVE_CHECKPOINT_STORE_KIND}")
        for index, entry in enumerate(payload.get("storage", [])):
            self.storage[entry["thread_id"]][entry["namespace"]][entry["checkpoint_id"]] = (
                _load_typed_bytes(entry.get("checkpoint"), field=f"storage[{index}].checkpoint"),
                _load_typed_bytes(entry.get("metadata"), field=f"storage[{index}].metadata"),
                entry.get("parent_checkpoint_id"),
            )
        for index, entry in enumerate(payload.get("writes", [])):
            outer = (entry["thread_id"], entry["namespace"], entry["checkpoint_id"])
            inner = (entry["task_id"], entry["index"])
            self.writes[outer][inner] = (
                entry["stored_task_id"],
                entry["channel"],
                _load_typed_bytes(entry.get("value"), field=f"writes[{index}].value"),
                entry.get("task_path", ""),
            )
        for index, entry in enumerate(payload.get("blobs", [])):
            key = (entry["thread_id"], entry["namespace"], entry["channel"], entry["version"])
            self.blobs[key] = _load_typed_bytes(entry.get("value"), field=f"blobs[{index}].value")

    def _assert_disk_valid(self) -> None:
        if not self.path.exists():
            raise ValueError("native Deep Agents checkpoint store is missing")
        payload = _load_json(self.path, label="native Deep Agents checkpoint store")
        expected = _canonical_digest(payload, digest_key="checkpoint_store_digest")
        if payload.get("checkpoint_store_digest") != expected:
            raise ValueError("native Deep Agents checkpoint store digest mismatch")

    @property
    def snapshot_digest(self) -> str:
        self._assert_disk_valid()
        return str(_load_json(self.path, label="native checkpoint store")["checkpoint_store_digest"])

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        with self._persistence_lock:
            result = super().put(config, checkpoint, metadata, new_versions)
            self._persist()
            return result

    def put_writes(self, config: Any, writes: Any, task_id: str, task_path: str = "") -> None:
        with self._persistence_lock:
            super().put_writes(config, writes, task_id, task_path)
            self._persist()

    def get_tuple(self, config: Any) -> Any:
        with self._persistence_lock:
            if self.path.exists():
                self._assert_disk_valid()
            elif self.storage or self.writes or self.blobs:
                raise ValueError("native Deep Agents checkpoint store is missing")
            return super().get_tuple(config)

    def list(
        self,
        config: Any,
        *,
        filter: dict[str, Any] | None = None,
        before: Any | None = None,
        limit: int | None = None,
    ) -> Iterator[Any]:
        with self._persistence_lock:
            if self.path.exists():
                self._assert_disk_valid()
            elif self.storage or self.writes or self.blobs:
                raise ValueError("native Deep Agents checkpoint store is missing")
            values = list(super().list(config, filter=filter, before=before, limit=limit))
        return iter(values)

    def delete_thread(self, thread_id: str) -> None:
        with self._persistence_lock:
            super().delete_thread(thread_id)
            self._persist()


class NativeEventRecorder:
    """Small monotonic digest chain for native runtime evidence."""

    def __init__(self, events_dir: Path) -> None:
        self.events_dir = events_dir
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        for path in sorted(events_dir.glob("event-*.json")):
            self._events.append(_load_json(path, label="native event"))
        errors = self.validate()
        if errors:
            raise ValueError("invalid native event chain: " + "; ".join(errors))

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous = self._events[-1].get("event_digest", "") if self._events else ""
            event: dict[str, Any] = {
                "kind": NATIVE_EVENT_KIND,
                "schema_version": NATIVE_RUNTIME_SCHEMA_VERSION,
                "sequence": len(self._events) + 1,
                "event_type": event_type,
                "previous_event_digest": previous,
                "payload": payload,
                "artifact_is_authority": False,
                "grants_authority": False,
            }
            event["event_digest"] = _canonical_digest(event, digest_key="event_digest")
            path = self.events_dir / f"event-{event['sequence']:04d}-{event_type}.json"
            _write_json(event, path)
            self._events.append(event)
            return event

    @property
    def events(self) -> list[dict[str, Any]]:
        return [dict(event) for event in self._events]

    def validate(self) -> list[str]:
        errors: list[str] = []
        previous = ""
        for expected_sequence, event in enumerate(self._events, start=1):
            if event.get("sequence") != expected_sequence:
                errors.append(f"event sequence {event.get('sequence')} must be {expected_sequence}")
            if event.get("previous_event_digest") != previous:
                errors.append(f"event {expected_sequence} previous digest mismatch")
            expected = _canonical_digest(event, digest_key="event_digest")
            if event.get("event_digest") != expected:
                errors.append(f"event {expected_sequence} digest mismatch")
            previous = str(event.get("event_digest", ""))
        return errors


class BuilderGovernanceMiddleware(AgentMiddleware):
    """Admission, budget, cancellation, concurrency, and event middleware."""

    def __init__(
        self,
        *,
        recorder: NativeEventRecorder,
        max_model_calls: int,
        max_tool_calls: int,
        active_workers: int = DEFAULT_ACTIVE_WORKERS,
    ) -> None:
        if not 1 <= active_workers <= MAX_ACTIVE_WORKERS:
            raise ValueError(f"active_workers must be between 1 and {MAX_ACTIVE_WORKERS}")
        if max_model_calls <= 0 or max_tool_calls <= 0:
            raise ValueError("model and tool call budgets must be positive")
        self.recorder = recorder
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls
        self.active_workers = active_workers
        prior_events = recorder.events
        self.cancelled = any(event.get("event_type") == "run_cancelled" for event in prior_events)
        self._model_calls = sum(event.get("event_type") == "model_admitted" for event in prior_events)
        self._tool_calls = sum(event.get("event_type") == "tool_admitted" for event in prior_events)
        if self._model_calls > max_model_calls or self._tool_calls > max_tool_calls:
            raise ValueError("persisted native runtime events exceed the configured call budgets")
        self._active_tasks = 0
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            if self.cancelled:
                return
            self.cancelled = True
        self.recorder.append(
            "run_cancelled",
            {"model_calls": self._model_calls, "tool_calls": self._tool_calls},
        )

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage:
        with self._lock:
            if self.cancelled:
                raise RuntimeError("native Deep Agents run is cancelled")
            if self._model_calls >= self.max_model_calls:
                raise RuntimeError("native Deep Agents model-call budget exhausted")
            self._model_calls += 1
            count = self._model_calls
        self.recorder.append("model_admitted", {"model_call": count})
        return handler(request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        name = str(request.tool_call.get("name", ""))
        call_id = str(request.tool_call.get("id", ""))
        if name not in _NATIVE_ALLOWED_TOOLS:
            self.recorder.append("tool_denied", {"tool": name, "reason": "not Builder-governed"})
            return ToolMessage(
                content=f"Tool {name!r} denied: not admitted by Builder-II.",
                tool_call_id=call_id,
                name=name,
                status="error",
            )
        is_task = name == "task"
        with self._lock:
            if self.cancelled:
                raise RuntimeError("native Deep Agents run is cancelled")
            if self._tool_calls >= self.max_tool_calls:
                raise RuntimeError("native Deep Agents tool-call budget exhausted")
            if is_task and self._active_tasks >= self.active_workers:
                self.recorder.append(
                    "tool_denied",
                    {"tool": name, "reason": "active worker cap reached", "cap": self.active_workers},
                )
                return ToolMessage(
                    content="Subagent task denied: active worker cap reached.",
                    tool_call_id=call_id,
                    name=name,
                    status="error",
                )
            self._tool_calls += 1
            if is_task:
                self._active_tasks += 1
            count = self._tool_calls
        args = request.tool_call.get("args", {})
        self.recorder.append("tool_admitted", {"tool": name, "tool_call": count, "args": args})
        try:
            result = handler(request)
            self.recorder.append(
                "tool_completed",
                {"tool": name, "tool_call": count, "call_id": call_id, "args": args},
            )
            return result
        finally:
            if is_task:
                with self._lock:
                    self._active_tasks -= 1


class GovernedEchoTool:
    """Factory for the only executable test/tool surface admitted to native agents."""

    def __init__(self, output_dir: Path, recorder: NativeEventRecorder) -> None:
        self.output_dir = output_dir
        self.recorder = recorder
        self._counter = len(list((output_dir / "tool-calls").glob("tool-call-*-receipt.json")))
        self._lock = threading.Lock()

    def build(self) -> BaseTool:
        @tool("builder_governed_echo")
        def governed_echo(text: str) -> str:
            """Echo bounded text through the Builder-II tool invocation gateway."""

            with self._lock:
                self._counter += 1
                sequence = self._counter
            tool_dir = self.output_dir / "tool-calls"
            policy_path = tool_dir / f"tool-call-{sequence:04d}-policy.json"
            envelope_path = tool_dir / f"tool-call-{sequence:04d}-envelope.json"
            receipt_path = tool_dir / f"tool-call-{sequence:04d}-receipt.json"
            policy = {
                "kind": TOOL_POLICY_KIND,
                "schema_version": POLICY_SCHEMA_VERSION,
                "denied_by_default": True,
                "artifact_is_authority": False,
                "grants_authority": False,
                "allowed_operations": ["invoke"],
                "allowed_risk_classes": ["low"],
                "allowed_tools": ["builtin.echo"],
                "max_input_bytes": 4096,
                "max_output_bytes": 4096,
                "timeout_seconds": 30,
                "network_allowed": False,
                "mutation_allowed": False,
                "credential_access_allowed": False,
                "cost_allowed": False,
                "requires_approval_for_mutation": True,
                "requires_approval_for_external_network": True,
                "requires_approval_for_credentials": True,
                "governance": {"artifact_is_authority": False},
            }
            _write_json(policy, policy_path)
            arguments = {"text": text}
            envelope = {
                "kind": TOOL_ENVELOPE_KIND,
                "schema_version": ENVELOPE_SCHEMA_VERSION,
                "operation_name": "invoke",
                "tool_id": "builtin.echo",
                "executes_tool": True,
                "input_digest": hashlib.sha256(
                    json_lib.dumps(arguments, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "policy_ref": {
                    "role": "policy",
                    "kind": TOOL_POLICY_KIND,
                    "path": str(policy_path),
                    "sha256": canonical_digest(policy),
                    "required": True,
                },
                "effect_classification": "pure",
                "risk_classification": "low",
                "rollback_requirement": "none",
                "timeout": 30,
                "output_cap": 4096,
                "credential_redaction_declaration": True,
                "requires_human_promotion_for_execution": True,
                "executes_shell": False,
                "mutates_target_repo": False,
                "grants_authority": False,
                "artifact_is_authority": False,
                "arguments": arguments,
            }
            _write_json(envelope, envelope_path)
            receipt = execute_tool_envelope(envelope, envelope_path, policy, policy_path)
            errors = validate_mcp_receipt(receipt)
            if errors:
                raise ValueError("invalid governed tool receipt: " + "; ".join(errors))
            _write_json(receipt, receipt_path)
            self.recorder.append(
                "governed_tool_receipt_recorded",
                {"tool": "builtin.echo", "receipt_ref": _raw_file_ref(receipt_path, role="tool_receipt", kind=receipt["kind"])},
            )
            return str(receipt["bounded_stdout"])

        return governed_echo


def _hitl_tool(prerequisites_complete: Callable[[], bool]) -> BaseTool:
    @tool("builder_request_hitl")
    def request_hitl(reason: str) -> str:
        """Record the operator-approved continuation after the native graph pauses."""

        if not prerequisites_complete():
            return "HITL request deferred: complete both obligations and the governed tool call first."
        return f"operator approved continuation: {reason}"

    return request_hitl


def wrp_subagents_from_obligations(
    obligations: Sequence[dict[str, Any]],
    *,
    governed_tools: Sequence[BaseTool],
) -> list[dict[str, Any]]:
    """Translate validated WRP obligation tickets into upstream subagent specs."""

    if len(obligations) < 2:
        raise ValueError("native Deep Agents run requires at least two bounded obligations")
    names: set[str] = set()
    specs: list[dict[str, Any]] = []
    deny_permissions = [FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="deny")]
    for index, obligation in enumerate(obligations):
        errors = validate_orchestration_obligation(obligation)
        if errors:
            raise ValueError(f"invalid obligation {index}: " + "; ".join(errors))
        if obligation.get("lane") != "deepagents":
            raise ValueError(f"obligation {index} must be assigned to the deepagents lane")
        name = str(obligation["subagent_profile"])
        if name in names:
            raise ValueError("native Deep Agents obligation subagent profiles must be unique")
        names.add(name)
        inherited = {
            "obligation_id": obligation["obligation_id"],
            "parent_ref": obligation["parent_ref"],
            "budget_partition": obligation["budget_partition"],
            "boundary": obligation["boundary"],
            "output_contract": obligation["output_contract"],
            "file_refs": obligation["file_refs"],
        }
        specs.append(
            {
                "name": name,
                "description": f"Discharge bounded WRP obligation {obligation['obligation_id'][:12]}.",
                "system_prompt": (
                    "You are a Builder-II bounded subagent. Do only the obligation below. "
                    "You possess no authority to widen it. Native filesystem, shell, Git, and direct provider "
                    "actions are denied. Return a concise result to the parent.\n\n"
                    f"BUILDER_II_OBLIGATION={json_lib.dumps(inherited, sort_keys=True)}"
                ),
                "tools": list(governed_tools),
                "permissions": deny_permissions,
            }
        )
    return specs


@dataclass(frozen=True)
class NativeRuntimeLimits:
    active_workers: int = DEFAULT_ACTIVE_WORKERS
    max_model_calls: int = 32
    max_tool_calls: int = 32
    max_tokens_per_call: int = 256

    def validate(self) -> None:
        if not 1 <= self.active_workers <= MAX_ACTIVE_WORKERS:
            raise ValueError(f"active_workers must be between 1 and {MAX_ACTIVE_WORKERS}")
        if min(self.max_model_calls, self.max_tool_calls, self.max_tokens_per_call) <= 0:
            raise ValueError("native runtime limits must be positive")


class NativeDeepAgentsRuntime:
    """Official ``create_deep_agent`` caller with Builder-II-owned boundaries."""

    def __init__(
        self,
        *,
        gateway: ModelExecutionGateway,
        route: ModelRouteBinding,
        budget: dict[str, Any],
        obligations: Sequence[dict[str, Any]],
        output_dir: Path,
        session_id: str,
        authority_refs: Sequence[dict[str, Any]],
        limits: NativeRuntimeLimits | None = None,
        response_strategy: Callable[[dict[str, Any], Sequence[BaseMessage]], AIMessage] = _default_response_strategy,
        model_approval_path: Path | None = None,
    ) -> None:
        self.gateway = gateway
        self.model_id = route.selected_candidate.model_id
        self.route = route
        self.budget = budget
        self.obligations = [dict(obligation) for obligation in obligations]
        self.output_dir = output_dir
        self.session_id = session_id
        self.authority_refs = [dict(ref) for ref in authority_refs]
        self.limits = limits or NativeRuntimeLimits()
        self.limits.validate()
        self.response_strategy = response_strategy
        self.checkpoint_path = output_dir / "native-checkpoint-store.json"
        self.recorder = NativeEventRecorder(output_dir / "native-events")
        self.checkpointer = DigestBoundCheckpointSaver(self.checkpoint_path)
        self.middleware = BuilderGovernanceMiddleware(
            recorder=self.recorder,
            max_model_calls=self.limits.max_model_calls,
            max_tool_calls=self.limits.max_tool_calls,
            active_workers=self.limits.active_workers,
        )
        echo = GovernedEchoTool(output_dir, self.recorder).build()
        self.tools = [echo, _hitl_tool(self._hitl_prerequisites_complete)]

        def record_model_receipt(receipt: dict[str, Any], path: Path) -> None:
            self.recorder.append(
                "model_receipt_recorded",
                {
                    "model_id": self.model_id,
                    "receipt_ref": _raw_file_ref(path, role="model_receipt", kind=str(receipt.get("kind", ""))),
                },
            )

        self.model = GatewayBackedChatModel(
            gateway=gateway,
            model_id=self.model_id,
            route=route,
            budget=budget,
            output_dir=output_dir,
            session_id=session_id,
            max_tokens=self.limits.max_tokens_per_call,
            temperature=0.0,
            approval_path=model_approval_path,
            response_strategy=response_strategy,
            receipt_callback=record_model_receipt,
            stage_provider=self._current_parent_stage,
            stage_denial_callback=self._record_stage_denial,
        )
        subagents = wrp_subagents_from_obligations(self.obligations, governed_tools=[echo])
        deny_permissions = [FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="deny")]
        self.agent = create_deep_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=(
                "Operate only inside the Builder-II approved obligation envelope. Delegate every listed "
                "obligation through the upstream task tool. Use only Builder-governed tools. Execute exactly "
                "three stages in order: first delegate both distinct obligations, then call the governed echo "
                "tool, then request HITL. Emit tool calls for only the current stage; never combine a HITL "
                "request with an earlier stage. A HITL request before both obligation completions and the "
                "governed-tool receipt is deferred and cannot interrupt the run."
            ),
            middleware=[self.middleware],
            subagents=subagents,
            permissions=deny_permissions,
            interrupt_on={
                "builder_request_hitl": {
                    "allowed_decisions": ["approve"],
                    "when": lambda _request: self._hitl_prerequisites_complete(),
                }
            },
            checkpointer=self.checkpointer,
            name="builder-ii-native-deepagents",
        )

    @property
    def _config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.session_id}}

    def _obligation_refs(self) -> list[dict[str, Any]]:
        return [
            {
                "obligation_id": obligation["obligation_id"],
                "subagent_profile": obligation["subagent_profile"],
                "parent_ref": obligation["parent_ref"],
            }
            for obligation in self.obligations
        ]

    def _hitl_prerequisites_complete(self) -> bool:
        """Permit the native interrupt only after the frozen workload completed."""

        completed_profiles = {
            str(event["payload"].get("args", {}).get("subagent_type"))
            for event in self.recorder.events
            if event.get("event_type") == "tool_completed" and event["payload"].get("tool") == "task"
        }
        required_profiles = {str(obligation["subagent_profile"]) for obligation in self.obligations}
        has_governed_tool_receipt = any(
            event.get("event_type") == "governed_tool_receipt_recorded" for event in self.recorder.events
        )
        return required_profiles.issubset(completed_profiles) and has_governed_tool_receipt

    def _current_parent_stage(self) -> str:
        """Derive the next parent action from recorded execution, never model inference."""

        if any(event.get("event_type") == "hitl_resumed" for event in self.recorder.events):
            return "complete"
        completed_profiles = {
            str(event["payload"].get("args", {}).get("subagent_type"))
            for event in self.recorder.events
            if event.get("event_type") == "tool_completed" and event["payload"].get("tool") == "task"
        }
        required_profiles = {str(obligation["subagent_profile"]) for obligation in self.obligations}
        if not required_profiles.issubset(completed_profiles):
            return "delegate_tasks"
        if not any(
            event.get("event_type") == "governed_tool_receipt_recorded" for event in self.recorder.events
        ):
            return "governed_echo"
        return "request_hitl"

    def _record_stage_denial(self, call: dict[str, Any], stage: str) -> None:
        self.recorder.append(
            "tool_denied",
            {
                "tool": str(call.get("name", "")),
                "call_id": str(call.get("id", "")),
                "reason": "not admitted in current Builder-II stage",
                "stage": stage,
            },
        )

    def start(self, task: str) -> dict[str, Any]:
        if self.recorder.events:
            raise ValueError("native run already has events; use resume with the checkpoint digest")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.recorder.append(
            "native_run_started",
            {
                "session_id": self.session_id,
                "factory": "deepagents.create_deep_agent",
                "model_id": self.model_id,
                "active_workers": self.limits.active_workers,
                "obligations": self._obligation_refs(),
                "authority_refs": self.authority_refs,
            },
        )
        result = self.agent.invoke({"messages": [{"role": "user", "content": task}]}, config=self._config)
        interrupts = result.get("__interrupt__", [])
        if not interrupts:
            self.recorder.append("native_run_failed", {"reason": "required HITL interrupt was not reached"})
            raise RuntimeError("native Deep Agents run completed without the required HITL interrupt")
        request = [getattr(item, "value", item) for item in interrupts]
        self.recorder.append(
            "hitl_interrupted",
            {"requests": request, "checkpoint_store_digest": self.checkpointer.snapshot_digest},
        )
        return self._write_evidence(status="INTERRUPTED", approved_checkpoint_digest="")

    def resume(self, *, approved_checkpoint_digest: str) -> dict[str, Any]:
        observed = self.checkpointer.snapshot_digest
        if approved_checkpoint_digest != observed:
            raise ValueError("approved native checkpoint digest does not match persisted state")
        self.recorder.append(
            "hitl_resumed",
            {"approved_checkpoint_digest": approved_checkpoint_digest, "approval_mode": "exact_digest_cli"},
        )
        result = self.agent.invoke(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config=self._config,
        )
        if result.get("__interrupt__"):
            raise RuntimeError("native Deep Agents run reached an unexpected second HITL interrupt")
        final_message = result.get("messages", [])[-1] if result.get("messages") else None
        self.recorder.append(
            "native_run_completed",
            {
                "final_response": _message_text(final_message) if isinstance(final_message, BaseMessage) else "",
                "checkpoint_store_digest": self.checkpointer.snapshot_digest,
            },
        )
        evidence = self._write_evidence(status="COMPLETED", approved_checkpoint_digest=approved_checkpoint_digest)
        errors = validate_native_evidence_bundle(evidence)
        if errors:
            raise ValueError("native Deep Agents evidence failed validation: " + "; ".join(errors))
        return evidence

    def _write_evidence(self, *, status: str, approved_checkpoint_digest: str) -> dict[str, Any]:
        events = self.recorder.events
        event_types = [str(event.get("event_type", "")) for event in events]
        model_refs = [
            event["payload"]["receipt_ref"]
            for event in events
            if event.get("event_type") == "model_receipt_recorded"
        ]
        tool_refs = [
            event["payload"]["receipt_ref"]
            for event in events
            if event.get("event_type") == "governed_tool_receipt_recorded"
        ]
        delegated = [
            event["payload"].get("args", {}).get("subagent_type")
            for event in events
            if event.get("event_type") == "tool_admitted" and event["payload"].get("tool") == "task"
        ]
        completed_task_events = [
            event
            for event in events
            if event.get("event_type") == "tool_completed" and event["payload"].get("tool") == "task"
        ]
        completed_tasks = len(completed_task_events)
        completed_profiles = {
            str(event["payload"].get("args", {}).get("subagent_type"))
            for event in completed_task_events
            if isinstance(event["payload"].get("args", {}).get("subagent_type"), str)
        }
        event_paths = sorted((self.output_dir / "native-events").glob("event-*.json"))
        content: dict[str, Any] = {
            "kind": NATIVE_EVIDENCE_KIND,
            "schema_version": NATIVE_RUNTIME_SCHEMA_VERSION,
            "status": status,
            "session_id": self.session_id,
            "official_factory": "deepagents.create_deep_agent",
            "model_adapter": "builder_ii.ModelExecutionGateway",
            "model_id": self.model_id,
            "single_model_instance": True,
            "active_workers": self.limits.active_workers,
            "worker_cap": MAX_ACTIVE_WORKERS,
            "obligations": self._obligation_refs(),
            "delegated_subagents": delegated,
            "completed_task_count": completed_tasks,
            "parent_child_chain": [
                {
                    **item,
                    "delegated": item["subagent_profile"] in delegated,
                    "completed": item["subagent_profile"] in completed_profiles,
                }
                for item in self._obligation_refs()
            ],
            "model_receipt_refs": model_refs,
            "tool_receipt_refs": tool_refs,
            "checkpoint_ref": _raw_file_ref(
                self.checkpoint_path,
                role="checkpoint_store",
                kind=NATIVE_CHECKPOINT_STORE_KIND,
            ),
            "checkpoint_store_digest": self.checkpointer.snapshot_digest,
            "approved_checkpoint_digest": approved_checkpoint_digest,
            "event_types": event_types,
            "event_count": len(events),
            "event_tail_digest": events[-1]["event_digest"] if events else "",
            "event_refs": [
                _raw_file_ref(path, role="native_event", kind=NATIVE_EVENT_KIND) for path in event_paths
            ],
            "denied_capabilities": list(_DENIED_NATIVE_CAPABILITIES),
            "target_repo_mutation": False,
            "shell_execution": False,
            "git_mutation": False,
            "direct_provider_bypass": False,
            "artifact_is_authority": False,
            "grants_authority": False,
        }
        content["evidence_digest"] = _canonical_digest(content, digest_key="evidence_digest")
        _write_json(content, self.output_dir / "native-deepagents-evidence.json")
        return content
