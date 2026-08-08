"""Hand-rolled, stdlib-only stdio JSON-RPC MCP server (G1).

Speaks newline-delimited JSON-RPC 2.0 on stdin/stdout and handles the minimal MCP method set
Goose needs from a tool extension: ``initialize``, ``tools/list``, ``tools/call``. Every
``tools/call`` runs the governed ceremony in :mod:`builder_ii.adapters.mcp.governed_call`,
which is deny-by-default, read-only, and ledgered. The server itself holds no authority and
adds no tool capability; it is the interposition surface, not a new power.

The target root is captured once when the server is constructed and is threaded into every
repository-read and in-loop patch-proposal path.  A proposal therefore binds the same target
root the read jail exposed to Goose; it cannot infer a different repository from an artifact
location or ambient cwd.
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

_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "builder-ii-governed-mcp"
_SERVER_VERSION = "0.1.0"

_METHOD_NOT_FOUND = -32601
_INVALID_REQUEST = -32600
_PARSE_ERROR = -32700


class GovernedMcpServer:
    """Governed MCP server exposing the bounded tool allowlist for one run."""

    def __init__(
        self,
        *,
        session_id: str,
        builder_root: Path,
        target_root: Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.builder_root = Path(builder_root).expanduser().resolve()
        self.target_root = (
            Path(target_root).expanduser().resolve()
            if target_root is not None
            else Path.cwd().resolve()
        )

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        req_id = request.get("id")

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
        specs = {**TOOL_SPECS, **GATED_TOOL_SPECS}
        return [
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": spec["inputSchema"],
            }
            for name, spec in specs.items()
        ]

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}

        if name == "propose_patch":
            outcome = run_gated_patch_apply(
                arguments=dict(arguments),
                session_id=self.session_id,
                builder_root=self.builder_root,
                target_root=self.target_root,
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
                "content": [
                    {"type": "text", "text": f"{refusal.reason} {refusal.compose_hint}"}
                ],
                "isError": True,
                "_meta": {
                    "governed": True,
                    "gated": True,
                    "refused": True,
                    "event_path": str(refusal.event_path),
                },
            }

        if name not in TOOL_SPECS:
            return {
                "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True,
            }

        outcome = run_governed_tool_call(
            tool_name=str(name),
            arguments=dict(arguments),
            session_id=self.session_id,
            builder_root=self.builder_root,
            target_root=self.target_root,
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
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def serve_stdio(
        self, *, stdin: TextIO | None = None, stdout: TextIO | None = None
    ) -> None:
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
