#!/usr/bin/env bash
# Antigravity Stop hook. Prevent premature closure: if no valid closure receipt
# exists, force the agent back into the loop to run /core-exact-tip-closure.
# STUB: replace receipt check with builder_ii_validation_rs validation.
set -euo pipefail
BUILDER_HOOK_INPUT="$(cat)"
export BUILDER_HOOK_INPUT
python3 - <<'PY'
import json, os, sys, glob, subprocess
from pathlib import Path

from builder_ii.governance.ledger.gate_battery_receipt import validate_gate_battery_receipt
raw = os.environ.get("BUILDER_HOOK_INPUT", "")
try:
    data = json.loads(raw)
except Exception:
    data = {}
ws = ""
try:
    w = data.get("workspacePaths")
    if isinstance(w, list) and w:
        ws = w[0]
    elif isinstance(w, str):
        ws = w
except Exception:
    pass
ws = ws or os.getcwd()

workspace = Path(ws).resolve()
receipts = glob.glob(str(workspace / ".builder" / "**" / "*.json"), recursive=True)
valid_receipt = False
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, capture_output=True, text=True)
status = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, capture_output=True, text=True)
current_head = head.stdout.strip() if head.returncode == 0 else ""
clean = status.returncode == 0 and not status.stdout.strip()

for receipt in receipts:
    try:
        artifact = json.loads(Path(receipt).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    if artifact.get("kind") != "builder_ii.gate_battery_receipt":
        continue
    if (
        not validate_gate_battery_receipt(artifact)
        and artifact.get("overall_state") == "PASSED"
        and artifact.get("working_tree_clean") is True
        and artifact.get("head_sha_stable") is True
        and artifact.get("head_sha_before") == current_head
        and artifact.get("head_sha_after") == current_head
        and clean
    ):
        valid_receipt = True
        break

if valid_receipt:
    print(json.dumps({"decision": "allow"}))
else:
    print(json.dumps({
        "decision": "continue",
        "reason": ("No canonical PASSED gate-battery receipt matches the current clean exact head. "
                   "Run receipt-backed local CI before claiming closure.")
    }))
PY
