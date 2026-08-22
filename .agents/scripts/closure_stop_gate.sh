#!/usr/bin/env bash
# Antigravity Stop hook. Prevent premature closure: if no valid closure receipt
# exists, force the agent back into the loop to run /core-exact-tip-closure.
# STUB: replace receipt check with builder_ii_validation_rs validation.
set -euo pipefail
python3 - <<'PY'
import json, os, sys, glob
raw = sys.stdin.read()
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
    ws = ""
ws = ws or os.getcwd()
# TODO: replace with a builder_ii_validation_rs call that validates a signed closure receipt.
receipts = glob.glob(os.path.join(ws, "artifacts", "**", "closure_receipt.json"), recursive=True)
if receipts:
    print(json.dumps({"decision": "allow"}))
else:
    print(json.dumps({
        "decision": "continue",
        "reason": ("No closure receipt found. Run /core-exact-tip-closure and the pre-completion "
                   "self-review (see GEMINI.md) before stopping. (stub — wire to builder_ii_validation_rs)")
    }))
PY