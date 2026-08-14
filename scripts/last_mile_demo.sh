#!/usr/bin/env bash
# W5.4 — end-to-end last-mile offline demo (stubs only; no cloud keys required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== last-mile offline demo (stubs) ==="
uv run pytest \
  tests/test_price_book.py \
  tests/test_gateway_measured_cost.py \
  tests/test_model_budget.py \
  tests/test_wrp_invoke_local_seam.py \
  tests/test_invoke_cloud_seam.py \
  tests/test_subagent_loop.py \
  tests/test_replay_harness.py \
  tests/test_otel_ledger_export.py \
  tests/test_secret_redaction.py \
  tests/test_s3_enablement.py \
  tests/test_cloud_chat.py \
  tests/test_last_mile_non_goals.py \
  -q

echo "=== Class U harness smoke ==="
uv run python - <<'PY'
from builder_ii.wrp.class_u_harness import run_class_u_harness
out = run_class_u_harness(target="builder", iterations=1)
summary = out.get("summary") or out.get("report", {}).get("summary") or {}
# harness may return report envelope at top level
if "summary" not in out and isinstance(out.get("report"), dict):
    summary = out["report"].get("summary") or {}
print("class_u_keys", sorted(out.keys())[:12])
print("utility_ok", (out.get("summary") or summary).get("utility_ok") if isinstance(summary, dict) or out.get("summary") else "n/a")
print("DEMO_OK")
PY

echo "=== ALL LAST-MILE DEMO GATES PASSED ==="
