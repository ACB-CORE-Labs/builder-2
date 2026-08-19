"""Hand-rolled, stdlib-only stdio JSON-RPC MCP server (G1).

Speaks newline-delimited JSON-RPC 2.0 on stdin/stdout and handles the minimal MCP method set
Goose needs from a tool extension: ``initialize``, ``tools/list``, ``tools/call``. Every
``tools/call`` runs the governed ceremony in :mod:`builder_ii.adapters.mcp.governed_call`,
which is deny-by-default, read-only, and ledgered. The server itself holds no authority and
adds no tool capability; it is the interposition surface, not a new power.

Framing is deliberately the simplest interoperable shape (one JSON object per line). The
exact framing Goose expects for a custom stdio extension is pinned against a real launch in
G2; :meth:`GovernedMcpServer.handle_request` is framing-independent and unit-tested directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from builder_ii.adapters.mcp.governed_apply import run_gated_patch_apply
from builder_ii.adapters.mcp.governed_call import (
    GATED_TOOL_SPECS,
    TOOL_SPECS,
    refuse_gated_tool_call,
    run_governed_tool_call,
)
from builder_ii.adapters.mcp.governed_services import _service_receipt, run_service

_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "builder-ii-governed-mcp"
_SERVER_VERSION = "0.1.0"

_METHOD_NOT_FOUND = -32601
_INVALID_REQUEST = -32600
_PARSE_ERROR = -32700


class GovernedMcpServer:
    """A governed MCP server exposing only allowlisted read-only stub tools."""

    def __init__(
        self, *, session_id: str, builder_root: Path, target_root: Path | None = None, target_name: str = "generic"
    ) -> None:
        self.session_id = session_id
        self.builder_root = Path(builder_root)
        self.target_root = Path(target_root) if target_root is not None else Path.cwd()
        self.target_name = target_name

    # -- protocol (framing-independent, unit-tested) --------------------------------------

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC request object; return the response, or None for notifications."""
        method = request.get("method")
        req_id = request.get("id")

        # Notifications carry no id and expect no response.
        if req_id is None and isinstance(method, str) and method.startswith("notifications/"):
            return None

        if method == "initialize":
            return self._result(req_id, self._initialize())
        if method == "tools/list":
            return self._result(req_id, {"tools": self._tool_list()})
        if method == "tools/call":
            return self._result(req_id, self._tools_call(request.get("params") or {}))

        if req_id is None:
            return None
        return self._error(req_id, _METHOD_NOT_FOUND, f"method not found: {method}")

    def _initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
        }

    @staticmethod
    def _tool_list() -> list[dict[str, Any]]:
        # Legacy stubs remain callable for compatibility but are no longer advertised;
        # 3B1 inventory is the governed service family plus deliberately gated tools.
        specs = {
            name: spec
            for name, spec in TOOL_SPECS.items()
            if name in {"repo_map", "repo_search", "content_read", "prepare_package", "validate_prepare_package"}
        }
        specs.update(GATED_TOOL_SPECS)
        return [
            {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
            for name, spec in specs.items()
        ]

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}

        # G4: the write path routes to the governed apply lane behind a validated approval and
        # the deny-by-default enablement flag. run_shell has no governed bounded lane to
        # delegate to, so it stays refused (G3).
        if name == "propose_patch":
            outcome = run_gated_patch_apply(
                arguments=dict(arguments),
                session_id=self.session_id,
                builder_root=self.builder_root,
            )
            return {
                "content": [{"type": "text", "text": outcome.reason}],
                "isError": outcome.status != "applied",
                "_meta": {
                    "governed": True,
                    "gated": True,
                    "applied": outcome.status == "applied",
                    "event_path": str(outcome.event_path),
                    "receipt_dir": outcome.receipt_dir,
                },
            }

        if name in GATED_TOOL_SPECS:
            refusal = refuse_gated_tool_call(
                tool_name=str(name),
                arguments=dict(arguments),
                session_id=self.session_id,
                builder_root=self.builder_root,
            )
            return {
                "content": [{"type": "text", "text": f"{refusal.reason} {refusal.compose_hint}"}],
                "isError": True,
                "_meta": {
                    "governed": True,
                    "gated": True,
                    "refused": True,
                    "event_path": str(refusal.event_path),
                },
            }

        if name not in {"repo_map", "repo_search", "content_read", "prepare_package", "validate_prepare_package"}:
            return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}

        if str(name) in {"repo_map", "repo_search", "content_read", "prepare_package", "validate_prepare_package"}:
            try:
                result, receipt_path, event_path = run_service(
                    tool_name=str(name),
                    arguments=dict(arguments),
                    session_id=self.session_id,
                    builder_root=self.builder_root,
                    target_root=self.target_root,
                    target_name=self.target_name,
                )
                status = str(result.get("status", "succeeded"))
                return {
                    "content": [{"type": "text", "text": json.dumps(result.get("result", result), sort_keys=True)}],
                    "isError": status != "succeeded",
                    "_meta": {
                        "governed": True,
                        "status": status,
                        "receipt_path": str(receipt_path),
                        "event_path": str(event_path),
                    },
                }
            except (KeyError, TypeError, ValueError, OSError) as exc:
                _, receipt_path, event_path = _service_receipt(
                    builder_root=self.builder_root,
                    session_id=self.session_id,
                    target_name=self.target_name,
                    tool_name=str(name),
                    arguments=dict(arguments),
                    result={"kind": "builder_ii.denied_service", "error_type": type(exc).__name__, "reason": str(exc)},
                    status="denied",
                )
                return {
                    "content": [{"type": "text", "text": f"denied: {type(exc).__name__}"}],
                    "isError": True,
                    "_meta": {
                        "governed": True,
                        "status": "denied",
                        "typed_error": type(exc).__name__,
                        "receipt_path": str(receipt_path),
                        "event_path": str(event_path),
                    },
                }

        outcome = run_governed_tool_call(
            tool_name=str(name),
            arguments=dict(arguments),
            session_id=self.session_id,
            builder_root=self.builder_root,
        )
        return {
            "content": [{"type": "text", "text": outcome.output_text}],
            "isError": outcome.status != "succeeded",
            "_meta": {
                "governed": True,
                "status": outcome.status,
                "receipt_path": str(outcome.receipt_path),
                "event_path": str(outcome.event_path),
            },
        }

    @staticmethod
    def _result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    # -- stdio loop -----------------------------------------------------------------------

    def serve_stdio(self, *, stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
        """Read newline-delimited JSON-RPC requests and write responses until EOF."""
        source = stdin if stdin is not None else sys.stdin
        sink = stdout if stdout is not None else sys.stdout

        for raw in source:
            line = raw.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._write(sink, self._error(None, _PARSE_ERROR, "parse error"))
                continue
            if not isinstance(request, dict):
                self._write(sink, self._error(None, _INVALID_REQUEST, "invalid request"))
                continue
            response = self.handle_request(request)
            if response is not None:
                self._write(sink, response)

    @staticmethod
    def _write(sink: TextIO, payload: dict[str, Any]) -> None:
        sink.write(json.dumps(payload) + "\n")
        sink.flush()
