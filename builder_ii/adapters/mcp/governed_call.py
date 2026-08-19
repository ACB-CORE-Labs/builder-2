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
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

_SERVER_ID = "builtin.mcp_server"

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
    "repo_map": {"tool_id": "service.repo_map", "description": "Return a bounded governed repository map.", "inputSchema": {"type": "object", "properties": {"max_files": {"type": "integer"}, "max_file_bytes": {"type": "integer"}}}},
    "repo_search": {"tool_id": "service.repo_search", "description": "Search bounded repository-map metadata.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    "content_read": {"tool_id": "service.content_read", "description": "Read bounded content through the governed read policy.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    "prepare_package": {"tool_id": "service.prepare_package", "description": "Create a passive governed preparation package under the session artifact root.", "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}}}},
    "validate_prepare_package": {"tool_id": "service.validate_prepare_package", "description": "Validate a governed preparation package without execution.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
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


def build_read_only_policy() -> dict[str, Any]:
    """A deny-by-default MCP policy that permits only the low-risk read-only stub path."""
    return {
        "kind": MCP_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_state": "ACTIVE",
        "allowed_servers": [_SERVER_ID],
        "allowed_operations": ["invoke"],
        "denied_by_default": True,
        "allowed_risk_classes": ["low_risk"],
        "max_input_bytes": 1024,
        "max_output_bytes": 1024,
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
    tool_id: str, arguments: dict[str, Any], policy: dict[str, Any], policy_path: Path
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
        "output_cap": 1024,
        "credential_redaction_declaration": True,
        "requires_human_promotion_for_execution": True,
        "executes_shell": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
    }


def _artifact_ref(data: dict[str, Any], path: Path, role: str) -> dict[str, Any]:
    return {
        "kind": data.get("kind"),
        "path": str(path),
        "sha256": canonical_digest(data),
        "role": role,
        "name": role.replace("_", " "),
        "required": True,
    }


def _previous_event_ref(existing: list[tuple[dict[str, Any], Path]]) -> dict[str, Any] | None:
    if not existing:
        return None
    last_event, last_path = existing[-1]
    return {
        "role": "event",
        "kind": EVENT_RECORD_KIND,
        "path": str(last_path),
        "sha256": canonical_digest(last_event),
        "name": str(last_event.get("event_type", "")),
        "required": True,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_governed_tool_call(
    *, tool_name: str, arguments: dict[str, Any], session_id: str, builder_root: Path
) -> GovernedCallOutcome:
    """Run one tool call through policy -> envelope -> executor -> receipt -> ledger."""
    spec = TOOL_SPECS.get(tool_name)
    if spec is None:
        raise KeyError(f"unknown tool: {tool_name}")
    tool_id = str(spec["tool_id"])

    session_dir = Path(builder_root) / "sessions" / session_id
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    existing = load_event_records(events_dir)
    sequence = len(existing) + 1

    policy = build_read_only_policy()
    policy_path = mcp_dir / f"{sequence:03d}_policy.json"
    _write_json(policy_path, policy)

    envelope = build_call_envelope(tool_id, arguments, policy, policy_path)
    envelope_path = mcp_dir / f"{sequence:03d}_envelope.json"
    _write_json(envelope_path, envelope)

    receipt = execute_tool_envelope(
        envelope=envelope, envelope_path=envelope_path, policy=policy, policy_path=policy_path
    )
    receipt_errors = validate_mcp_receipt(receipt)
    if receipt_errors:
        raise ValueError(f"receipt validation failed: {receipt_errors}")
    receipt_path = mcp_dir / f"{sequence:03d}_receipt.json"
    _write_json(receipt_path, receipt)

    current_stage = "initialized"
    if existing:
        replay = replay_events(existing, session_id=session_id)
        if replay.get("valid"):
            current_stage = str(replay.get("current_stage") or "initialized")

    event = create_event_record(
        event_id=f"evt_mcp_serve_{session_id}_{sequence}",
        session_id=session_id,
        sequence=sequence,
        event_type="mcp_call_executed",
        stage=current_stage,
        subject_refs=[
            _artifact_ref(envelope, envelope_path, "mcp_call_envelope"),
            _artifact_ref(receipt, receipt_path, "mcp_call_receipt"),
        ],
        command_surface="builder-mcp serve",
        policy_snapshot_ref=_artifact_ref(policy, policy_path, "mcp_tool_policy"),
        previous_event_ref=_previous_event_ref(existing),
        message=f"governed MCP tool call: {tool_name}",
    )
    event_errors = validate_event_record(event)
    if event_errors:
        raise ValueError(f"event validation failed: {event_errors}")
    event_path = events_dir / f"{sequence:03d}_mcp_call_executed.json"
    write_event_record(event, event_path)

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
    session_dir = Path(builder_root) / "sessions" / session_id
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    existing = load_event_records(events_dir)
    sequence = len(existing) + 1

    # A policy snapshot is referenced by the ledger event; it is deny-by-default read-only.
    policy = build_read_only_policy()
    policy_path = mcp_dir / f"{sequence:03d}_policy.json"
    _write_json(policy_path, policy)

    reason = (
        f"Mutating tool '{tool_name}' is gated: this governed session refuses it in-loop. "
        "No envelope was built and nothing was executed or mutated."
    )
    compose_hint = (
        "To perform a mutating action, open an approved execution candidate through the "
        "governed HITL lane (builder-hitl); the in-loop unlock is a future promotion (ADR-0009 G4)."
    )

    current_stage = "initialized"
    if existing:
        replay = replay_events(existing, session_id=session_id)
        if replay.get("valid"):
            current_stage = str(replay.get("current_stage") or "initialized")

    event = create_event_record(
        event_id=f"evt_mcp_gate_{session_id}_{sequence}",
        session_id=session_id,
        sequence=sequence,
        event_type="mcp_call_denied",
        stage=current_stage,
        subject_refs=[],
        command_surface="builder-mcp serve",
        policy_snapshot_ref=_artifact_ref(policy, policy_path, "mcp_tool_policy"),
        previous_event_ref=_previous_event_ref(existing),
        message=reason,
    )
    event_errors = validate_event_record(event)
    if event_errors:
        raise ValueError(f"event validation failed: {event_errors}")
    event_path = events_dir / f"{sequence:03d}_mcp_call_denied.json"
    write_event_record(event, event_path)

    return GatedRefusalOutcome(
        tool_name=tool_name, reason=reason, compose_hint=compose_hint, event_path=event_path
    )
