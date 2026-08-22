#!/usr/bin/env bash
# Antigravity PreToolUse hook (matcher: run_command).
# Gate qualification/benchmark commands behind a frozen manifest + clean exact tip.
# STUB: wire the real checks to builder_ii_validation_rs.
set -euo pipefail
BUILDER_HOOK_INPUT="$(cat)"
export BUILDER_HOOK_INPUT
python3 - <<'PY'
import json, re, sys, os, subprocess

raw = os.environ.get("BUILDER_HOOK_INPUT", "")
try:
    data = json.loads(raw)
except Exception:
    print(json.dumps({"decision": "force_ask", "reason": "qualification_gate: unparseable hook input"}))
    sys.exit(0)
cmd = ""
ws = os.getcwd()
try:
    cmd = data.get("toolCall", {}).get("args", {}).get("CommandLine", "")
    paths = data.get("workspacePaths")
    if isinstance(paths, list) and paths:
        ws = paths[0]
    elif isinstance(paths, str) and paths:
        ws = paths
except Exception:
    pass

qual_re = re.compile(r"(qualif|benchmark|ttft|measure|receipt|profile)", re.I)
if qual_re.search(cmd or ""):
    # 1. Clean tree check
    git_st = subprocess.run(["git", "status", "--porcelain"], cwd=ws, capture_output=True, text=True)
    if git_st.returncode != 0 or git_st.stdout.strip() != "":
        print(json.dumps({
            "decision": "force_ask",
            "reason": "Tree is not clean. Qualification requires a clean exact tip."
        }))
        sys.exit(0)

    # 2. Frozen manifest / HEAD tip (check latest closure receipt or manifest?)
    # Just checking for ANY valid manifest or receipt using builder_ii_validation_rs.
    ws = data.get("workspacePaths", [os.getcwd()])[0]
    import glob
    manifests = glob.glob(os.path.join(ws, "artifacts", "**", "*.json"), recursive=True)
    valid_manifest = False

    # Let's find a valid goose_session_manifest or closure_receipt
    cargo_cmd = ["cargo", "run", "--quiet", "--manifest-path", os.path.join(ws, "builder_ii_validation_rs", "Cargo.toml"), "--", "--kind"]

    for mf in manifests:
        try:
            with open(mf, 'r') as f:
                content = f.read()
                if '"builder_ii.goose_session_manifest"' in content or '"builder_ii.performance_measurement"' in content or '"builder_ii.hitl_execution_request"' in content:
                    # just pick kind from content roughly
                    kind_match = re.search(r'"kind"\s*:\s*"([^"]+)"', content)
                    if kind_match:
                        kind = kind_match.group(1)
                        res = subprocess.run(cargo_cmd + [kind], input=content, text=True, capture_output=True, cwd=ws)
                        if res.returncode == 0:
                            out = json.loads(res.stdout)
                            if out.get("valid") is True:
                                valid_manifest = True
                                break
        except Exception:
            pass

    if not valid_manifest:
        print(json.dumps({
            "decision": "force_ask",
            "reason": "No valid frozen manifest found. Run /core-exact-tip-closure first."
        }))
        sys.exit(0)

    print(json.dumps({"decision": "allow"}))
else:
    print(json.dumps({"decision": "allow"}))
PY
