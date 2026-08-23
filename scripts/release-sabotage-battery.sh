#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WHEEL="${1:?usage: release-sabotage-battery.sh WHEEL WHEEL_SHA256 OUTPUT}"
WHEEL_SHA256="${2:?usage: release-sabotage-battery.sh WHEEL WHEEL_SHA256 OUTPUT}"
OUTPUT="${3:?usage: release-sabotage-battery.sh WHEEL WHEEL_SHA256 OUTPUT}"

cd "$REPO_ROOT"
uv run pytest -q \
  tests/test_tool_invocation_gateway.py \
  tests/test_hitl_patch_approval.py \
  tests/test_verification_execution_approval.py \
  tests/test_model_budget.py \
  tests/test_deepagents_execution.py \
  tests/test_goose_runtime_harness.py \
  tests/test_mcp_plan_set_3b3_verification_execution.py \
  tests/test_hitl_patch_apply.py \
  tests/test_delivery.py

uv run builder-release host-proof \
  --output "$OUTPUT" \
  --lane release_sabotage \
  --wheel "$(basename "$WHEEL")" \
  --wheel-sha256 "$WHEEL_SHA256" \
  --command "denied tool and write" \
  --command "forged stale and substituted approval" \
  --command "budget exhaustion" \
  --command "Deep Agents interruption and resume" \
  --command "Goose and MCP disconnect refusal" \
  --command "verification and patch drift refusal" \
  --command "remote mismatch and forbidden push" \
  --command "apply rollback and corrective delivery" \
  --limitation "External-vendor disconnects use deterministic local transport seams."
uv run builder-release validate-evidence "$OUTPUT"
