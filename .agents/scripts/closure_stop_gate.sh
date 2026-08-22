#!/usr/bin/env bash
# Antigravity Stop hook. Prevent premature closure: if no valid closure receipt
# exists, force the agent back into the loop to run /core-exact-tip-closure.
# STUB: replace receipt check with builder_ii_validation_rs validation.
set -euo pipefail
python3 - <<'PY'
import json, os, sys, glob, subprocess
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
    pass
ws = ws or os.getcwd()

receipts = glob.glob(os.path.join(ws, "artifacts", "**", "closure_receipt.json"), recursive=True)
valid_receipt = False
cargo_cmd = ["cargo", "run", "--quiet", "--manifest-path", os.path.join(ws, "builder_ii_validation_rs", "Cargo.toml"), "--", "--kind", "builder_ii.closure_receipt"]

for receipt in receipts:
    try:
        with open(receipt, 'r') as f:
            content = f.read()
            res = subprocess.run(cargo_cmd, input=content, text=True, capture_output=True, cwd=ws)
            if res.returncode == 0:
                out = json.loads(res.stdout)
                if out.get("valid") is True:
                    valid_receipt = True
                    break
    except Exception:
        pass

if valid_receipt:
    print(json.dumps({"decision": "allow"}))
else:
    print(json.dumps({
        "decision": "continue",
        "reason": ("No valid signed closure receipt found. Run /core-exact-tip-closure and the pre-completion "
                   "self-review (see GEMINI.md) before stopping.")
    }))
PY