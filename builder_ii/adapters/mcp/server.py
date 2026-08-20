"""Hand-rolled, stdlib-only stdio JSON-RPC MCP server (G1).

Speaks newline-delimited JSON-RPC 2.0 on stdin/stdout and handles the minimal MCP method set
Goose needs from a tool extension: ``initialize``, ``tools/list``, ``tools/call``. Every
admitted service call is routed to Builder-II's governed service layer. The server itself
holds no authority and adds no tool capability; it is the interposition surface, not a new
power.

Framing is deliberately the simplest interoperable shape (one JSON object per line). The
exact framing Goose expects for a custom stdio extension is pinned against a real launch in
G2; :meth:`GovernedMcpServer.handle_request` is framing-independent and unit-tested directly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, TextIO

from builder_ii.adapters.mcp.governed_call import TOOL_SPECS
from builder_ii.adapters.mcp.governed_services import (
    MAX_SERVICE_INPUT_BYTES,
    SERVICE_TOOLS,
    TARGET_PROFILES,
    CorruptLedgerError,
    ServiceDenied,
    _service_receipt,
    run_service,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "builder-ii-governed-mcp"
_SERVER_VERSION = "0.1.0"
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

_METHOD_NOT_FOUND = -32601
_INVALID_REQUEST = -32600
_PARSE_ERROR = -32700


def _bounded_evidence_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Capture admissible arguments, or only digest/size provenance for oversized input."""
    raw = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(raw) <= MAX_SERVICE_INPUT_BYTES:
        return arguments
    return {
        "rejected_input": {
            "canonical_sha256": canonical_digest(arguments),
            "canonical_bytes": len(raw),
            "content_captured": False,
        }
    }


class GovernedMcpServer:
    """A governed MCP server exposing only inventory-admitted services."""

    def __init__(
        self,
        *,
        session_id: str,
        builder_root: Path,
        target_root: Path | None = None,
        target_name: str = "generic",
        config_root: Path | None = None,
    ) -> None:
        if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
            raise ValueError("session_id must be a 1-128 character path-safe identifier")
        if target_name not in TARGET_PROFILES:
            raise ValueError("target_name must be one of generic, builder, core")
        self.session_id = session_id
        self.builder_root = Path(builder_root)
        self.target_root = Path(target_root) if target_root is not None else Path.cwd()
        self.target_name = target_name
        self.config_root = Path(config_root) if config_root is not None else None

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
        specs = {name: spec for name, spec in TOOL_SPECS.items() if name in SERVICE_TOOLS}
        return [
            {"name": name, "description": spec["description"], "inputSchema": spec["inputSchema"]}
            for name, spec in specs.items()
        ]

    def _service_error_response(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        exc: Exception,
        status: str,
    ) -> dict[str, Any]:
        result_kind = "builder_ii.denied_service" if status == "denied" else "builder_ii.failed_service"
        evidence_result = {
            "kind": result_kind,
            "error_type": type(exc).__name__,
            "reason": str(exc),
        }
        evidence_arguments = _bounded_evidence_arguments(arguments)
        try:
            _, receipt_path, event_path = _service_receipt(
                builder_root=self.builder_root,
                session_id=self.session_id,
                target_name=self.target_name,
                tool_name=name,
                arguments=evidence_arguments,
                result=evidence_result,
                status=status,
            )
        except CorruptLedgerError as ledger_exc:
            return {
                "content": [{"type": "text", "text": f"failed: {type(ledger_exc).__name__}"}],
                "isError": True,
                "_meta": {
                    "governed": True,
                    "status": "failed",
                    "typed_error": type(ledger_exc).__name__,
                    "evidence_appended": False,
                    "reason": str(ledger_exc),
                },
            }
        except Exception as evidence_exc:
            return {
                "content": [{"type": "text", "text": f"failed: {type(exc).__name__}"}],
                "isError": True,
                "_meta": {
                    "governed": True,
                    "status": "failed",
                    "typed_error": type(exc).__name__,
                    "evidence_appended": False,
                    "evidence_error": f"{type(evidence_exc).__name__}: {evidence_exc}",
                },
            }
        return {
            "content": [{"type": "text", "text": f"{status}: {type(exc).__name__}"}],
            "isError": True,
            "_meta": {
                "governed": True,
                "status": status,
                "typed_error": type(exc).__name__,
                "receipt_path": str(receipt_path),
                "event_path": str(event_path),
                "evidence_appended": True,
            },
        }

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        raw_arguments = params.get("arguments")
        # Inventory-first: legacy echo/utc_static and all unknown names are retired at the
        # transport boundary, not merely hidden from tools/list.
        if name not in SERVICE_TOOLS:
            return {
                "content": [{"type": "text", "text": f"unknown or unadvertised tool: {name}"}],
                "isError": True,
                "_meta": {"governed": True, "status": "denied", "inventory_admitted": False},
            }

        service_arguments: Any = {} if raw_arguments is None else raw_arguments
        if not isinstance(service_arguments, dict):
            return self._service_error_response(
                name=str(name),
                arguments={},
                exc=ServiceDenied("arguments must be an object"),
                status="denied",
            )

        try:
            result, receipt_path, event_path = run_service(
                tool_name=str(name),
                arguments=dict(service_arguments),
                session_id=self.session_id,
                builder_root=self.builder_root,
                target_root=self.target_root,
                target_name=self.target_name,
                config_root=self.config_root,
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
        except ServiceDenied as exc:
            return self._service_error_response(
                name=str(name),
                arguments=dict(service_arguments),
                exc=exc,
                status="denied",
            )
        except CorruptLedgerError as exc:
            return {
                "content": [{"type": "text", "text": f"failed: {type(exc).__name__}"}],
                "isError": True,
                "_meta": {
                    "governed": True,
                    "status": "failed",
                    "typed_error": type(exc).__name__,
                    "evidence_appended": False,
                    "reason": str(exc),
                },
            }
        except (KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
            return self._service_error_response(
                name=str(name),
                arguments=dict(service_arguments),
                exc=exc,
                status="failed",
            )

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
