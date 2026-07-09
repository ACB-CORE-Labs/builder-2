#!/usr/bin/env bash
# Shared gate-running + receipt-emission mechanism for scripts/ci.sh.
#
# Sourced, never executed directly, and must be sourced *after* `set -o errexit/nounset/pipefail`
# and the `cd` to the repo root. Defines gate()/skip() -- the same functions ci.sh has always
# had, plus the machinery that turns a battery run into a `builder_ii.gate_battery_receipt`
# artifact when `--receipt <path>` is requested.
#
# Kept in its own file (rather than inline in ci.sh) so the mechanism is testable without ever
# running the real, slow, nine-gate battery inside a test: a test can source this file with a
# throwaway two- or three-command fake battery instead. See
# tests/test_gate_battery_receipt_shell.py.
#
# Emission is opt-in and additive: with no --receipt flag, RECEIPT_PATH stays empty, gate() and
# skip() skip all recording work, and the EXIT trap does nothing but preserve the real exit
# code -- `bash scripts/ci.sh` with no arguments behaves exactly as it did before this file
# existed.

RECEIPT_PATH=""
GATE_LOG=""
HEAD_SHA_BEFORE=""
SKIPPED=()

# Absolute path to this repo, resolved from where this file lives on disk -- not from the
# caller's cwd. `uv run --project` is passed this explicitly so gate()/skip()'s calls into the
# receipt tool resolve the right project environment even when a test sources this file from an
# unrelated throwaway git repo used only to control HEAD/working-tree state.
_GBR_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

_gbr_run_receipt_tool() {
  uv run --project "$_GBR_REPO_ROOT" python -m builder_ii.gate_battery_receipt "$@"
}

_gbr_parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --receipt)
        if [ $# -lt 2 ]; then
          printf -- '--receipt requires a path argument\n' >&2
          exit 2
        fi
        RECEIPT_PATH="$2"
        shift 2
        ;;
      *)
        printf 'unknown argument: %s\n' "$1" >&2
        exit 2
        ;;
    esac
  done
}

_gbr_init() {
  if [ -n "$RECEIPT_PATH" ]; then
    GATE_LOG="$(mktemp)"
    HEAD_SHA_BEFORE="$(git rev-parse HEAD 2>/dev/null || printf '')"
  fi
}

# gate NAME CMD [ARGS...] -- run CMD, print its banner, and (when a receipt was requested)
# record its argv/exit_code/duration/status. `"$@" || rc=$?` keeps errexit exempt for this one
# statement so recording always happens, even for a failing gate; `return "$rc"` then lets
# errexit fire at the *call site* exactly as it always has, aborting the battery immediately
# after the failing gate is durably recorded.
gate() {
  local name="$1"
  shift
  printf '\n=== [GATE] %s ===\n' "$name"
  local start=$SECONDS
  local rc=0
  "$@" || rc=$?
  local duration=$((SECONDS - start))
  if [ -n "$RECEIPT_PATH" ]; then
    _gbr_run_receipt_tool record-gate --log "$GATE_LOG" --name "$name" --exit-code "$rc" --duration "$duration" -- "$@"
  fi
  return "$rc"
}

skip() {
  printf '\n=== [SKIP] %s ===\n  reason: %s\n' "$1" "$2"
  SKIPPED+=("$1")
  if [ -n "$RECEIPT_PATH" ]; then
    _gbr_run_receipt_tool record-gate --log "$GATE_LOG" --name "$1" --skip-reason "$2"
  fi
}

# Installed via `trap _gbr_emit_receipt EXIT`. Captures $? as the very first statement, since
# every subsequent command in this function would otherwise overwrite it; ends with
# `exit "$final_rc"` so the script's real exit code (0, or a failing gate's code) survives
# regardless of what the receipt-writing step itself returns.
_gbr_emit_receipt() {
  local final_rc=$?
  if [ -n "$RECEIPT_PATH" ]; then
    local head_sha_after working_tree_clean
    head_sha_after="$(git rev-parse HEAD 2>/dev/null || printf '')"
    if [ -z "$(git status --porcelain=v1 2>/dev/null)" ]; then
      working_tree_clean=true
    else
      working_tree_clean=false
    fi
    _gbr_run_receipt_tool build \
      --gate-log "$GATE_LOG" \
      --output "$RECEIPT_PATH" \
      --head-sha-before "$HEAD_SHA_BEFORE" \
      --head-sha-after "$head_sha_after" \
      --working-tree-clean "$working_tree_clean" || true
    rm -f "$GATE_LOG"
  fi
  exit "$final_rc"
}
