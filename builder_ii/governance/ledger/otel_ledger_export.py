"""W5.2 — OpenTelemetry-shaped export from the unified event ledger.

Reads hash-chained event records and emits OTLP-compatible span JSON files
(stdlib only — no collector required; M1-safe). Export is a projection of the
ledger; it never weakens digests or grants authority.
"""

from __future__ import annotations

import hashlib
import json as json_lib
import time
from pathlib import Path
from typing import Any

from builder_ii.governance.ledger.event_ledger import load_event_records

OTEL_EXPORT_KIND = "builder_ii.otel_ledger_export"
OTEL_EXPORT_SCHEMA_VERSION = 1


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _span_id_from(event: dict[str, Any]) -> str:
    seed = f"{event.get('event_id')}|{event.get('sequence')}|{event.get('event_type')}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _trace_id_from(session_id: str) -> str:
    return hashlib.sha256(f"trace|{session_id}".encode("utf-8")).hexdigest()[:32]


def event_to_span(event: dict[str, Any], *, session_id: str) -> dict[str, Any]:
    """Map one ledger event to an OTLP-ish span dict (JSON-serializable)."""
    seq = event.get("sequence") if isinstance(event.get("sequence"), int) else 0
    # Synthetic timestamps for offline export (relative to sequence).
    start_ns = int(seq) * 1_000_000
    end_ns = start_ns + 500_000
    attrs = {
        "builder_ii.event_type": str(event.get("event_type") or ""),
        "builder_ii.stage": str(event.get("stage") or ""),
        "builder_ii.session_id": str(event.get("session_id") or session_id),
        "builder_ii.decision_result": str(event.get("decision_result") or ""),
        "builder_ii.command_surface": str(event.get("command_surface") or ""),
        "builder_ii.event_digest": str(event.get("digest") or ""),
    }
    return {
        "traceId": _trace_id_from(session_id),
        "spanId": _span_id_from(event),
        "name": str(event.get("event_type") or "builder_ii.event"),
        "kind": "SPAN_KIND_INTERNAL",
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in sorted(attrs.items())],
        "status": {
            "code": "STATUS_CODE_ERROR"
            if str(event.get("decision_result") or "") in {"failed", "denied"}
            else "STATUS_CODE_OK"
        },
    }


def export_events_dir_to_otel(
    events_dir: Path,
    *,
    output_path: Path,
    service_name: str = "builder-ii",
) -> dict[str, Any]:
    """Load ledger events from ``events_dir`` and write an OTLP JSON export + receipt."""
    existing = load_event_records(events_dir)
    existing = sorted(
        existing,
        key=lambda item: (
            item[0].get("sequence") if isinstance(item[0].get("sequence"), int) else 10**9,
            str(item[1]),
        ),
    )
    if not existing:
        raise ValueError(f"no event records in {events_dir}")

    session_id = str(existing[0][0].get("session_id") or "unknown-session")
    spans = [event_to_span(ev, session_id=session_id) for ev, _path in existing]

    otlp_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}},
                        {
                            "key": "builder_ii.export_kind",
                            "value": {"stringValue": OTEL_EXPORT_KIND},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "builder_ii.event_ledger", "version": "1"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_lib.dumps(otlp_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload_digest = hashlib.sha256(output_path.read_bytes()).hexdigest()

    receipt: dict[str, Any] = {
        "kind": OTEL_EXPORT_KIND,
        "schema_version": OTEL_EXPORT_SCHEMA_VERSION,
        "export_state": "RECORDED_ONLY",
        "service_name": service_name,
        "session_id": session_id,
        "events_dir": str(events_dir),
        "output_path": str(output_path),
        "span_count": len(spans),
        "otlp_payload_sha256": payload_digest,
        "source": "event_ledger",
        "weakens_ledger": False,
        "executes_model": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "exported_at_unix": int(time.time()),
    }
    receipt["digest"] = _digest({k: v for k, v in receipt.items() if k != "digest"})
    receipt_path = output_path.with_suffix(output_path.suffix + ".receipt.json")
    receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def validate_otel_export_receipt(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["otel export receipt must be a JSON object"]
    if record.get("kind") != OTEL_EXPORT_KIND:
        errors.append(f"kind must be {OTEL_EXPORT_KIND}")
    if record.get("schema_version") != OTEL_EXPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {OTEL_EXPORT_SCHEMA_VERSION}")
    if record.get("weakens_ledger") is not False:
        errors.append("weakens_ledger must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if not isinstance(record.get("span_count"), int) or record["span_count"] < 1:
        errors.append("span_count must be a positive int")
    return errors
