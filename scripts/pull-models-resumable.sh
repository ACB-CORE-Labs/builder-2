#!/usr/bin/env bash
# Resumable model downloads for throttled networks (e.g. public library ~3GB cap).
# HuggingFace cache resumes automatically — re-run until complete.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

# Single connection, no Xet high-perf (friendlier on captive portals).
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_XET_HIGH_PERFORMANCE=0

TIER="${1:-fast}"
RAPID="${ROOT}/.venv/bin/rapid-mlx"
HF="${ROOT}/.venv/bin/hf"

pull_one() {
  local alias="$1"
  echo "=== Pulling ${alias} (resumable; safe to re-run after throttle) ==="
  if [[ -x "$RAPID" ]]; then
    "$RAPID" pull "$alias" || return 1
  else
    echo "rapid-mlx not found"
    return 1
  fi
}

case "$TIER" in
  fast)
    pull_one "gemma-4-e4b-4bit"
    ;;
  primary)
    pull_one "gemma-4-12b-4bit"
    ;;
  all)
    pull_one "gemma-4-e4b-4bit"
    pull_one "gemma-4-12b-4bit"
    ;;
  *)
    echo "Usage: $0 [fast|primary|all]"
    echo "  fast    — ~2–3 GB, start here at the library"
    echo "  primary — ~7 GB, do at home if library throttles"
    echo "  all     — both, in size order"
    exit 1
    ;;
esac

echo ""
echo "Done (or partial — re-run same command to resume)."
echo "Check cache: du -sh ~/.cache/huggingface/hub/models--mlx-community--gemma-4*"