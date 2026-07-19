"""W5.2 OTel ledger export."""

from __future__ import annotations

from pathlib import Path

from builder_ii.otel_ledger_export import export_events_dir_to_otel, validate_otel_export_receipt
from builder_ii.runtime_event_append import append_runtime_event


def test_export_spans_from_events(tmp_path: Path) -> None:
    events = tmp_path / "events"
    append_runtime_event(
        events_dir=events,
        session_id="sess-otel",
        event_type="model_call_executed",
        message="ok",
        command_surface="test",
        decision_result="executed",
    )
    append_runtime_event(
        events_dir=events,
        session_id="sess-otel",
        event_type="budget_debited",
        message="debit",
        command_surface="test",
        decision_result="recorded",
    )
    out = tmp_path / "otel.json"
    receipt = export_events_dir_to_otel(events, output_path=out)
    assert receipt["span_count"] == 2
    assert validate_otel_export_receipt(receipt) == []
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "resourceSpans" in text
    assert "model_call_executed" in text
