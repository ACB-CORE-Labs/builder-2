#!/usr/bin/env bash
# Antigravity PreToolUse hook (matcher: run_command).
# Gate qualification/benchmark commands behind a frozen manifest + clean exact tip.
# STUB: wire the real checks to builder_ii_validation_rs.
set -euo pipefail
python3 - <<'PY'
import json, re, sys
raw = sys.stdin.read()
try:
    data = json.loads(raw)
except Exception:
    print(json.dumps({"decision": "force_ask", "reason": "qualification_gate: unparseable hook input"}))
    sys.exit(0)
cmd = ""
try:
    cmd = data["toolCall"]["args"].get("CommandLine", "")
except Exception:
    pass
qual_re = re.compile(r"(qualif|benchmark|ttft|measure|receipt|profile)", re.I)
if qual_re.search(cmd or ""):
    # TODO: call builder_ii_validation_rs to verify clean tree + frozen manifest + HEAD == tip.
    print(json.dumps({
        "decision": "force_ask",
        "reason": ("Qualification/benchmark command detected. Run /core-exact-tip-closure first; "
                   "confirm frozen manifest + clean exact tip. (stub — wire to builder_ii_validation_rs)")
    }))
else:
    print(json.dumps({"decision": "allow"}))
PY