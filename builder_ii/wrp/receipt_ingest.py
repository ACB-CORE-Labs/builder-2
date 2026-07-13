"""W4 / P2.4 — Receipt → ExperienceStore ingest (immutable, recorded-only).

Maps execution/verification receipts into trajectory exemplars for the
experience store. Does not apply R* to live routing policy (P4 / M-LEAD).
"""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.experience_store import append_exemplar

# Accepted receipt kind tokens (generic schema, not full gateway artifact kinds).
ACCEPTED_RECEIPT_KINDS: frozenset[str] = frozenset(
    {
        "model_call",
        "tool_call",
        "verification",
        "wrp_live_step",
    }
)

# Ledger event_type → receipt kind mapping (best-effort).
_LEDGER_EVENT_TO_KIND: dict[str, str] = {
    "model_call_executed": "model_call",
    "model_call_failed": "model_call",
    "tool_call_executed": "tool_call",
    "tool_call_denied": "tool_call",
    "tool_call_failed": "tool_call",
    "mcp_call_executed": "tool_call",
    "mcp_call_denied": "tool_call",
    "mcp_call_failed": "tool_call",
}

_LEDGER_FAILURE_EVENTS: frozenset[str] = frozenset(
    {
        "model_call_failed",
        "tool_call_denied",
        "tool_call_failed",
        "mcp_call_denied",
        "mcp_call_failed",
    }
)


def _require_dict(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict")
    return value


def _coerce_features(raw: Any, *, label: str) -> dict[str, float]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a dict of string → float when provided")
    features: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{label} keys must be non-empty strings")
        try:
            features[key] = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label}[{key!r}] must be numeric") from exc
    return features


def _trajectory_id_for(receipt: dict[str, Any], index: int) -> str:
    for key in ("trajectory_id", "receipt_id", "event_id", "step_id"):
        value = receipt.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    digest = receipt.get("digest")
    if isinstance(digest, str) and digest.strip():
        return f"{receipt.get('kind', 'receipt')}:{digest.strip()[:16]}"
    return f"receipt-{index}"


def _error_signal_for(success: bool, receipt: dict[str, Any]) -> float:
    raw = receipt.get("error_signal")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("error_signal must be numeric when provided") from exc
    return 0.0 if success else 1.0


def _validate_receipt(receipt: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError(f"receipts[{index}] must be a dict")
    kind = receipt.get("kind")
    if kind not in ACCEPTED_RECEIPT_KINDS:
        raise ValueError(
            f"receipts[{index}].kind must be one of "
            f"{sorted(ACCEPTED_RECEIPT_KINDS)}; got {kind!r}"
        )
    if "success" not in receipt:
        raise ValueError(f"receipts[{index}].success is required (bool)")
    if not isinstance(receipt["success"], bool):
        raise ValueError(f"receipts[{index}].success must be a bool")
    if "cost_tokens" in receipt and receipt["cost_tokens"] is not None:
        cost = receipt["cost_tokens"]
        if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
            raise ValueError(f"receipts[{index}].cost_tokens must be a non-negative number")
    if "digest" in receipt and receipt["digest"] is not None:
        if not isinstance(receipt["digest"], str):
            raise ValueError(f"receipts[{index}].digest must be a string when provided")
    # Validate optional feature map early (clear errors before append).
    _coerce_features(receipt.get("workload_features"), label=f"receipts[{index}].workload_features")
    if "error_signal" in receipt and receipt["error_signal"] is not None:
        _error_signal_for(bool(receipt["success"]), receipt)
    return receipt


def receipt_to_exemplar_fields(receipt: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    """Map a validated receipt into append_exemplar kwargs (no store mutation)."""
    validated = _validate_receipt(receipt, index=index)
    success = bool(validated["success"])
    features = _coerce_features(
        validated.get("workload_features"),
        label=f"receipts[{index}].workload_features",
    )
    # Surface cost as an optional feature axis when present.
    if validated.get("cost_tokens") is not None:
        features = {**features, "cost_tokens": float(validated["cost_tokens"])}
    notes_parts = [f"kind={validated['kind']}"]
    if isinstance(validated.get("digest"), str) and validated["digest"]:
        notes_parts.append(f"digest={validated['digest'][:16]}")
    if isinstance(validated.get("notes"), str) and validated["notes"].strip():
        notes_parts.append(validated["notes"].strip())
    return {
        "trajectory_id": _trajectory_id_for(validated, index),
        "success": success,
        "error_signal": _error_signal_for(success, validated),
        "features": features,
        "notes": "; ".join(notes_parts),
    }


def ingest_receipts(store: dict[str, Any], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """Append exemplars derived from receipts; return a NEW store (immutable).

    Does not mutate ``store``. Rejects malformed receipts with ValueError.
    Does not apply corrections to live routing policy.
    """
    store = _require_dict(store, label="store")
    if not isinstance(receipts, list):
        raise ValueError("receipts must be a list")

    # Validate all receipts first so a bad mid-batch receipt fails closed
    # without partially applying earlier ones.
    exemplar_fields: list[dict[str, Any]] = []
    for index, receipt in enumerate(receipts):
        exemplar_fields.append(receipt_to_exemplar_fields(receipt, index=index))

    updated = store
    for fields in exemplar_fields:
        updated = append_exemplar(
            updated,
            trajectory_id=fields["trajectory_id"],
            success=fields["success"],
            error_signal=fields["error_signal"],
            features=fields["features"],
            notes=fields["notes"],
        )
    return updated


def from_ledger_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best-effort normalize ledger-like events into generic WRP receipts.

    Unknown event types are skipped. Missing fields are filled with safe defaults.
    """
    if not isinstance(events, list):
        raise ValueError("events must be a list")

    receipts: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] must be a dict")
        event_type = event.get("event_type")
        if not isinstance(event_type, str):
            # Allow already-normalized kind on ledger-shaped records.
            kind = event.get("kind")
            if kind in ACCEPTED_RECEIPT_KINDS:
                receipt = {
                    "kind": kind,
                    "success": bool(event["success"]) if isinstance(event.get("success"), bool) else True,
                }
                for optional in (
                    "trajectory_id",
                    "receipt_id",
                    "event_id",
                    "step_id",
                    "cost_tokens",
                    "workload_features",
                    "digest",
                    "error_signal",
                    "notes",
                ):
                    if optional in event:
                        receipt[optional] = event[optional]
                receipts.append(receipt)
            continue

        kind = _LEDGER_EVENT_TO_KIND.get(event_type)
        if kind is None:
            continue

        success = event_type not in _LEDGER_FAILURE_EVENTS
        if isinstance(event.get("success"), bool):
            success = event["success"]
        elif event.get("decision_result") in ("denied", "failed", "error"):
            success = False
        elif event.get("status") in ("failed", "denied", "error"):
            success = False
        elif event.get("status") in ("succeeded", "executed", "ok"):
            success = True

        receipt: dict[str, Any] = {
            "kind": kind,
            "success": success,
        }

        for src, dest in (
            ("event_id", "event_id"),
            ("trajectory_id", "trajectory_id"),
            ("receipt_id", "receipt_id"),
            ("step_id", "step_id"),
        ):
            value = event.get(src)
            if isinstance(value, str) and value.strip():
                receipt[dest] = value.strip()

        if "cost_tokens" in event:
            receipt["cost_tokens"] = event["cost_tokens"]
        else:
            cost_report = event.get("cost_report")
            if isinstance(cost_report, dict) and cost_report.get("total_tokens") is not None:
                receipt["cost_tokens"] = cost_report["total_tokens"]

        if "workload_features" in event:
            receipt["workload_features"] = event["workload_features"]
        if isinstance(event.get("digest"), str):
            receipt["digest"] = event["digest"]
        elif isinstance(event.get("payload_sha256"), str):
            receipt["digest"] = event["payload_sha256"]
        if "error_signal" in event:
            receipt["error_signal"] = event["error_signal"]
        if isinstance(event.get("message"), str) and event["message"].strip():
            receipt["notes"] = event["message"].strip()

        receipts.append(receipt)

    return receipts
