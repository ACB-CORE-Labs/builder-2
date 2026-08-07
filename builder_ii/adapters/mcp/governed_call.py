"""The governed ceremony behind one MCP ``tools/call``.

Given a tool name and arguments, this builds a deny-by-default read-only policy and a
matching call envelope, runs the existing governed executor
(:func:`builder_ii.core.tool_invocation_gateway.execute_tool_envelope`), validates the
receipt, and appends one hash-chained event record to the session ledger. It never mutates
the target repo, never enables shell, and grants no authority — the executor's low-risk path
invariants and the receipt validator both enforce that.

Only tools already present in the executor's allowlist
(:data:`builder_ii.core.tool_invocation_gateway.ALLOWED_STUB_TOOLS`) are exposed. G1 adds no
new tool capability; it adds the interposition seam and the ledger entry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.core.mcp_policy import (
    ENVELOPE_SCHEMA_VERSION,
    MCP_ENVELOPE_KIND,
    MCP_POLICY_KIND,
    POLICY_SCHEMA_VERSION,
    validate_mcp_receipt,
)
from builder_ii.core.tool_invocation_gateway import execute_tool_envelope
from builder_ii.governance.ledger.session_ledger import session_event_append
from builder_ii.governance.ledger.workflow_records import canonical_digest

_SERVER_ID = "builtin.mcp_server"

#: Output ceiling for the repo-read tools. The original 1024 was sized for `echo`; a file read
#: capped at a kilobyte would truncate almost every source file in this repo into uselessness.
#: Matches `readonly_repo_tools.DEFAULT_MAX_READ_BYTES` so the tool's own bound and the
#: envelope's agree rather than silently cutting each other.
_READ_OUTPUT_CAP = 65536

#: Retained for `echo`/`utc_static`, whose outputs are small by construction.
_STUB_OUTPUT_CAP = 1024

# MCP-facing tool name -> the executor's allowlisted tool_id + its MCP schema. The tool_ids
# must already be in ``tool_invocation_gateway.ALLOWED_STUB_TOOLS``; nothing here widens it.
TOOL_SPECS: dict[str, dict[str, Any]] = {
    "echo": {
        "tool_id": "builtin.echo",
        "description": "Echo the provided text back (deterministic, read-only stub).",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    "utc_static": {
        "tool_id": "builtin.utc_static",
        "description": "Return a fixed deterministic UTC timestamp (read-only stub).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "read_file": {
        "tool_id": "builtin.read_file",
        "description": (
            "Read a UTF-8 text file relative to the repository root (read-only). Paths are "
            "jailed to the repo: absolute paths, '..', and .git/.builder are refused."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Repo-relative file path."}},
            "required": ["path"],
        },
        "output_cap": _READ_OUTPUT_CAP,
    },
    "list_dir": {
        "tool_id": "builtin.list_dir",
        "description": (
            "List a directory relative to the repository root (read-only). Directories are "
            "suffixed '/'. Same path jail as read_file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repo-relative directory; defaults to the root."}
            },
        },
        "output_cap": _READ_OUTPUT_CAP,
    },
    "grep": {
        "tool_id": "builtin.grep",
        "description": (
            "Search the repository for a literal substring (read-only), returning "
            "'path:line:text'. Literal, not regex, and bounded in matches and files scanned."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Literal substring to find."},
                "path": {"type": "string", "description": "Repo-relative subtree to search; defaults to the root."},
            },
            "required": ["pattern"],
        },
        "output_cap": _READ_OUTPUT_CAP,
    },
}


@dataclass(frozen=True)
class GovernedCallOutcome:
    """The result of one governed tool call, plus the artifacts it left on disk."""

    status: str
    output_text: str
    receipt: dict[str, Any]
    receipt_path: Path
    event_path: Path


def _canonical_input_digest(arguments: dict[str, Any]) -> str:
    raw = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_read_only_policy(*, max_output_bytes: int = _STUB_OUTPUT_CAP) -> dict[str, Any]:
    """A deny-by-default MCP policy that permits only the low-risk read-only tool path.

    ``max_output_bytes`` is per-call because the tools differ by orders of magnitude in what a
    legitimate result looks like; the executor takes the ``min`` of policy and envelope, so a
    tool cannot raise its own ceiling past what the policy minted for it.
    """
    return {
        "kind": MCP_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_state": "ACTIVE",
        "allowed_servers": [_SERVER_ID],
        "allowed_operations": ["invoke"],
        "denied_by_default": True,
        "allowed_risk_classes": ["low_risk"],
        "max_input_bytes": 1024,
        "max_output_bytes": max_output_bytes,
        "timeout_seconds": 30,
        "network_allowed": False,
        "mutation_allowed": False,
        "credential_access_allowed": False,
        "cost_allowed": False,
        "requires_approval_for_mutation": True,
        "requires_approval_for_external_network": True,
        "requires_approval_for_credentials": True,
        "grants_authority": False,
        "artifact_is_authority": False,
        "governance": {"artifact_is_authority": False},
    }


def build_call_envelope(
    tool_id: str,
    arguments: dict[str, Any],
    policy: dict[str, Any],
    policy_path: Path,
    *,
    output_cap: int = _STUB_OUTPUT_CAP,
) -> dict[str, Any]:
    """A low-risk read-only MCP call envelope whose policy_ref digest binds the policy."""
    return {
        "kind": MCP_ENVELOPE_KIND,
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "operation_name": "invoke",
        "server_id": _SERVER_ID,
        "tool_id": tool_id,
        "invokes_mcp": True,
        "arguments": arguments,
        "input_digest": _canonical_input_digest(arguments),
        "policy_ref": {
            "role": "policy",
            "kind": MCP_POLICY_KIND,
            "path": str(policy_path),
            "sha256": canonical_digest(policy),
            "name": "active read-only policy",
            "required": True,
        },
        "effect_classification": "read_only",
        "risk_classification": "low_risk",
        "rollback_requirement": "no_rollback_required_for_read_only",
        "timeout": 30,
        "output_cap": output_cap,
        "credential_redaction_declaration": True,
        "requires_human_promotion_for_execution": True,
        "executes_shell": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
    }


def run_governed_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    session_id: str,
    builder_root: Path,
    target_root: Path | None = None,
) -> GovernedCallOutcome:
    """Run one tool call through policy -> envelope -> executor -> receipt -> ledger.

    The whole span runs inside the session's append lock: the sidecar artifacts are named by the
    sequence the event will carry, so deriving that sequence and writing the event cannot be
    interleaved with another writer's (see :mod:`builder_ii.governance.ledger.session_ledger`).
    """
    spec = TOOL_SPECS.get(tool_name)
    if spec is None:
        raise KeyError(f"unknown tool: {tool_name}")
    tool_id = str(spec["tool_id"])

    output_cap = int(spec.get("output_cap", _STUB_OUTPUT_CAP))

    with session_event_append(Path(builder_root), session_id) as appender:
        policy = build_read_only_policy(max_output_bytes=output_cap)
        policy_path, policy_ref = appender.write_policy_snapshot(policy)

        envelope = build_call_envelope(tool_id, arguments, policy, policy_path, output_cap=output_cap)
        envelope_path, envelope_ref = appender.write_sidecar(envelope, "envelope", "mcp_call_envelope")

        receipt = execute_tool_envelope(
            envelope=envelope,
            envelope_path=envelope_path,
            policy=policy,
            policy_path=policy_path,
            target_root=target_root,
        )
        receipt_errors = validate_mcp_receipt(receipt)
        if receipt_errors:
            raise ValueError(f"receipt validation failed: {receipt_errors}")
        receipt_path, receipt_ref = appender.write_sidecar(receipt, "receipt", "mcp_call_receipt")

        event_path = appender.append(
            event_id=f"evt_mcp_serve_{session_id}_{appender.sequence}",
            event_type="mcp_call_executed",
            command_surface="builder-mcp serve",
            policy_snapshot_ref=policy_ref,
            subject_refs=[envelope_ref, receipt_ref],
            message=f"governed MCP tool call: {tool_name}",
        )

    return GovernedCallOutcome(
        status=str(receipt.get("status", "failed")),
        output_text=str(receipt.get("bounded_stdout", "")),
        receipt=receipt,
        receipt_path=receipt_path,
        event_path=event_path,
    )


# Mutating tool classes (G3). The server advertises these so the interposition seam is real,
# but a tools/call on them is REFUSED in-loop, deny-by-default: no envelope is built (the
# mcp_call_envelope schema pins mutates_target_repo/executes_shell false), nothing executes
# or mutates, and a hitl_gate_refused event is ledgered. Unlocking them is the G4 promotion
# (ADR-0009), which relaxes those pins only behind a validated approval — never here.
GATED_TOOL_SPECS: dict[str, dict[str, Any]] = {
    "propose_patch": {
        "description": "Propose a file edit (MUTATING — gated; refused in this governed session).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        },
    },
    "run_shell": {
        "description": "Run a shell command (MUTATING — gated; refused in this governed session).",
        "inputSchema": {"type": "object", "properties": {"cmd": {"type": "string"}}},
    },
}


@dataclass(frozen=True)
class GatedRefusalOutcome:
    """The result of refusing a mutating tool call in-loop."""

    tool_name: str
    reason: str
    compose_hint: str
    event_path: Path


def refuse_gated_tool_call(
    *, tool_name: str, arguments: dict[str, Any], session_id: str, builder_root: Path
) -> GatedRefusalOutcome:
    """Refuse a mutating tool call in-loop: ledger the refusal, execute and mutate nothing.

    This is the in-loop gate proving it refuses. It runs no envelope (the read-only envelope
    schema cannot represent a mutation) and writes no execution receipt; it appends one
    hash-chained ``hitl_gate_refused`` event and returns the composed governed HITL path.
    """
    reason = (
        f"Mutating tool '{tool_name}' is gated: this governed session refuses it in-loop. "
        "No envelope was built and nothing was executed or mutated."
    )
    compose_hint = (
        "To perform a mutating action, open an approved execution candidate through the "
        "governed HITL lane (builder-hitl); the in-loop unlock is a future promotion (ADR-0009 G4)."
    )

    with session_event_append(Path(builder_root), session_id) as appender:
        # A policy snapshot is referenced by the ledger event; it is deny-by-default read-only.
        _, policy_ref = appender.write_policy_snapshot(build_read_only_policy())
        event_path = appender.append(
            event_id=f"evt_mcp_gate_{session_id}_{appender.sequence}",
            event_type="mcp_call_denied",
            command_surface="builder-mcp serve",
            policy_snapshot_ref=policy_ref,
            subject_refs=[],
            message=reason,
        )

    return GatedRefusalOutcome(
        tool_name=tool_name, reason=reason, compose_hint=compose_hint, event_path=event_path
    )
