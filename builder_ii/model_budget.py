"""Token/USD model budget artifacts for the governed execution seam.

kind: builder_ii.model_budget

Distinct from Ladder-4 orchestration_obligation budget_partition (events/bytes).
This budget meters model tokens and estimated USD only.
"""

from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.price_book import lookup_price_entry
from builder_ii.token_accounting import count_tokens, estimate_usd

MODEL_BUDGET_KIND = "builder_ii.model_budget"
MODEL_BUDGET_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_BUDGET_STATES = frozenset({"ACTIVE", "EXHAUSTED", "REVOKED"})


class BudgetExceededError(ValueError):
    """Raised when a model call would exceed the remaining budget."""


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_governance() -> dict[str, Any]:
    return {
        "capability_state": "model_budget",
        "model_execution": "DISABLED",
        "runtime_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_authority": False,
        "core_workbench_coupling": "NONE",
    }


def create_model_budget(
    *,
    session_id: str,
    task_id: str = "",
    max_input_tokens: int = 100_000,
    max_output_tokens: int = 16_384,
    max_total_tokens: int = 100_000,
    max_usd: float = 1.0,
    spent_input_tokens: int = 0,
    spent_output_tokens: int = 0,
    spent_total_tokens: int = 0,
    spent_usd: float = 0.0,
    budget_version: int = 1,
    state: str = "ACTIVE",
) -> dict[str, Any]:
    if state not in ALLOWED_BUDGET_STATES:
        raise ValueError(f"state must be one of {sorted(ALLOWED_BUDGET_STATES)}")
    for name, val in (
        ("max_input_tokens", max_input_tokens),
        ("max_output_tokens", max_output_tokens),
        ("max_total_tokens", max_total_tokens),
        ("spent_input_tokens", spent_input_tokens),
        ("spent_output_tokens", spent_output_tokens),
        ("spent_total_tokens", spent_total_tokens),
    ):
        if not isinstance(val, int) or val < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if max_usd < 0:
        raise ValueError("max_usd must be non-negative")
    if spent_usd < 0:
        raise ValueError("spent_usd must be non-negative")
    if not session_id.strip():
        raise ValueError("session_id must be non-empty")

    budget: dict[str, Any] = {
        "kind": MODEL_BUDGET_KIND,
        "schema_version": MODEL_BUDGET_SCHEMA_VERSION,
        "budget_state": state,
        "session_id": session_id.strip(),
        "task_id": task_id.strip(),
        "budget_version": int(budget_version),
        "max_input_tokens": max_input_tokens,
        "max_output_tokens": max_output_tokens,
        "max_total_tokens": max_total_tokens,
        "max_usd": float(max_usd),
        "spent_input_tokens": spent_input_tokens,
        "spent_output_tokens": spent_output_tokens,
        "spent_total_tokens": spent_total_tokens,
        "spent_usd": float(spent_usd),
        "executes_model": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "governance": _default_governance(),
    }
    budget["digest"] = _digest({k: v for k, v in budget.items() if k != "digest"})
    return budget


def budget_ref(budget: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    digest = budget.get("digest")
    if not isinstance(digest, str) or not _SHA256_RE.match(digest):
        digest = _digest({k: v for k, v in budget.items() if k != "digest"})
    ref: dict[str, Any] = {
        "kind": MODEL_BUDGET_KIND,
        "sha256": digest,
        "role": "model_budget",
        "required": True,
        "budget_version": budget.get("budget_version"),
    }
    if path is not None:
        ref["path"] = str(path)
    return ref


def project_call_cost(
    *,
    prompt: str,
    max_output_tokens: int,
    model_id: str,
    price_book: dict[str, Any],
) -> dict[str, Any]:
    """Project worst-case token/USD cost for a call (input measured, output capped)."""
    in_tc = count_tokens(prompt, model_id=model_id)
    entry = lookup_price_entry(price_book, model_id) or {}
    input_rate = float(entry.get("input_usd_per_1k") or 0.0)
    output_rate = float(entry.get("output_usd_per_1k") or 0.0)
    out_tokens = max(0, int(max_output_tokens))
    usd = estimate_usd(
        input_tokens=in_tc.token_count,
        output_tokens=out_tokens,
        input_usd_per_1k=input_rate,
        output_usd_per_1k=output_rate,
    )
    return {
        "input_tokens": in_tc.token_count,
        "output_tokens": out_tokens,
        "total_tokens": in_tc.token_count + out_tokens,
        "estimated_usd_total": usd["estimated_usd_total"],
        "token_accounting": in_tc.token_accounting,
        "tokenizer_id": in_tc.tokenizer_id,
        "tokenizer_version": in_tc.tokenizer_version,
    }


def remaining(budget: dict[str, Any]) -> dict[str, float | int]:
    return {
        "input_tokens": int(budget["max_input_tokens"]) - int(budget["spent_input_tokens"]),
        "output_tokens": int(budget["max_output_tokens"]) - int(budget["spent_output_tokens"]),
        "total_tokens": int(budget["max_total_tokens"]) - int(budget["spent_total_tokens"]),
        "usd": float(budget["max_usd"]) - float(budget["spent_usd"]),
    }


def assert_budget_allows_call(budget: dict[str, Any], projected: dict[str, Any]) -> None:
    errors = validate_model_budget(budget)
    if errors:
        raise ValueError(f"invalid model budget: {'; '.join(errors)}")
    if budget.get("budget_state") != "ACTIVE":
        raise BudgetExceededError(f"budget state is {budget.get('budget_state')}, not ACTIVE")
    rem = remaining(budget)
    if int(projected["input_tokens"]) > int(rem["input_tokens"]):
        raise BudgetExceededError(
            f"projected input_tokens {projected['input_tokens']} exceeds remaining {rem['input_tokens']}"
        )
    if int(projected["output_tokens"]) > int(rem["output_tokens"]):
        raise BudgetExceededError(
            f"projected output_tokens {projected['output_tokens']} exceeds remaining {rem['output_tokens']}"
        )
    if int(projected["total_tokens"]) > int(rem["total_tokens"]):
        raise BudgetExceededError(
            f"projected total_tokens {projected['total_tokens']} exceeds remaining {rem['total_tokens']}"
        )
    if float(projected.get("estimated_usd_total") or 0.0) > float(rem["usd"]) + 1e-12:
        raise BudgetExceededError(
            f"projected USD {projected.get('estimated_usd_total')} exceeds remaining {rem['usd']}"
        )


def debit_budget(budget: dict[str, Any], cost_report: dict[str, Any]) -> dict[str, Any]:
    """Return a new budget version with spent counters increased (immutable)."""
    errors = validate_model_budget(budget)
    if errors:
        raise ValueError(f"invalid model budget: {'; '.join(errors)}")
    in_tok = int(cost_report.get("input_tokens") or 0)
    out_tok = int(cost_report.get("output_tokens") or 0)
    total = int(cost_report.get("total_tokens") or (in_tok + out_tok))
    usd = float(cost_report.get("estimated_usd_total") or 0.0)

    spent_in = int(budget["spent_input_tokens"]) + in_tok
    spent_out = int(budget["spent_output_tokens"]) + out_tok
    spent_total = int(budget["spent_total_tokens"]) + total
    spent_usd = float(budget["spent_usd"]) + usd

    state = "ACTIVE"
    if (
        spent_in >= int(budget["max_input_tokens"])
        or spent_out >= int(budget["max_output_tokens"])
        or spent_total >= int(budget["max_total_tokens"])
        or spent_usd >= float(budget["max_usd"])
    ):
        state = "EXHAUSTED"

    return create_model_budget(
        session_id=str(budget["session_id"]),
        task_id=str(budget.get("task_id") or ""),
        max_input_tokens=int(budget["max_input_tokens"]),
        max_output_tokens=int(budget["max_output_tokens"]),
        max_total_tokens=int(budget["max_total_tokens"]),
        max_usd=float(budget["max_usd"]),
        spent_input_tokens=spent_in,
        spent_output_tokens=spent_out,
        spent_total_tokens=spent_total,
        spent_usd=spent_usd,
        budget_version=int(budget.get("budget_version") or 1) + 1,
        state=state,
    )


def dumps_model_budget(budget: dict[str, Any]) -> str:
    return json_lib.dumps(budget, indent=2, sort_keys=True) + "\n"


def write_model_budget(budget: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_model_budget(budget), encoding="utf-8")


def validate_model_budget(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["model budget must be a JSON object"]
    if record.get("kind") != MODEL_BUDGET_KIND:
        errors.append(f"kind must be {MODEL_BUDGET_KIND}")
    if record.get("schema_version") != MODEL_BUDGET_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_BUDGET_SCHEMA_VERSION}")
    if record.get("budget_state") not in ALLOWED_BUDGET_STATES:
        errors.append(f"budget_state must be one of {sorted(ALLOWED_BUDGET_STATES)}")
    if not isinstance(record.get("session_id"), str) or not record.get("session_id"):
        errors.append("session_id must be a non-empty string")
    if not isinstance(record.get("budget_version"), int) or record["budget_version"] < 1:
        errors.append("budget_version must be a positive integer")
    for field in (
        "max_input_tokens",
        "max_output_tokens",
        "max_total_tokens",
        "spent_input_tokens",
        "spent_output_tokens",
        "spent_total_tokens",
    ):
        val = record.get(field)
        if not isinstance(val, int) or val < 0:
            errors.append(f"{field} must be a non-negative integer")
    for field in ("max_usd", "spent_usd"):
        val = record.get(field)
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
            errors.append(f"{field} must be a non-negative number")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    return errors


def validate_model_budget_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"file not found or not a file: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_model_budget(data)
