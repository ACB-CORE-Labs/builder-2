#!/usr/bin/env bash
# Phased resumable download for throttled networks (~3GB/session caps).
#
# Strategy: small files first (always fits), then one big weight file that
# HuggingFace resumes byte-by-byte across sessions.
#
# Usage:
#   ./scripts/pull-phased.sh              # show status
#   ./scripts/pull-phased.sh small        # config/tokenizer only (~35MB)
#   ./scripts/pull-phased.sh weights      # model.safetensors only (resumable)
#   ./scripts/pull-phased.sh all          # small then weights
#   ./scripts/pull-phased.sh qwen-fallback  # smaller 3.1GB alt if Gemma won't finish
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HF="${ROOT}/.venv/bin/hf"
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_XET_HIGH_PERFORMANCE=0

GEMMA_REPO="mlx-community/gemma-4-e4b-it-4bit"
QWEN_REPO="mlx-community/Qwen3.5-4B-MLX-4bit"
WEIGHTS="model.safetensors"
SMALL_FILES=(
  config.json tokenizer.json tokenizer_config.json chat_template.jinja
  generation_config.json processor_config.json .gitattributes README.md
  model.safetensors.index.json
)

cache_slug() {
  echo "${HOME}/.cache/huggingface/hub/models--${1//\//--}"
}

progress() {
  local repo="$1"
  local dir
  dir="$(cache_slug "$repo")"
  if [[ ! -d "$dir" ]]; then
    echo "  cache: (none)"
    return
  fi
  local total incomplete complete
  total="$(du -sh "$dir" 2>/dev/null | cut -f1)"
  incomplete="$(find "$dir" -name '*.incomplete' 2>/dev/null | wc -l | tr -d ' ')"
  complete="$(find "$dir/snapshots" -name 'model.safetensors' 2>/dev/null | wc -l | tr -d ' ')"
  echo "  cache: ${total} | incomplete_blobs: ${incomplete} | weights_complete: ${complete}"
  if [[ "$incomplete" -gt 0 ]]; then
    find "$dir/blobs" -name '*.incomplete' -exec ls -lh {} \; 2>/dev/null | head -3
  fi
}

pull_small() {
  local repo="$1"
  echo "=== Phase 1: small files for ${repo} (~35MB) ==="
  "$HF" download "$repo" "${SMALL_FILES[@]}"
}

pull_weights() {
  local repo="$1"
  echo "=== Phase 2: ${WEIGHTS} for ${repo} (RESUMABLE — re-run until complete) ==="
  echo "    Gemma E4B weights ≈ 5.2GB → expect 2+ library sessions at 3GB cap."
  "$HF" download "$repo" "$WEIGHTS"
}

status() {
  echo "Gemma E4B (${GEMMA_REPO}):"
  progress "$GEMMA_REPO"
  echo ""
  echo "Qwen fallback (${QWEN_REPO}):"
  progress "$QWEN_REPO"
  echo ""
  echo "Commands:"
  echo "  $0 small          # finish metadata if missing"
  echo "  $0 weights        # resume weight download (run every library visit)"
  echo "  $0 qwen-fallback  # 3.1GB total alternative"
}

cmd="${1:-status}"
case "$cmd" in
  status) status ;;
  small) pull_small "$GEMMA_REPO" ;;
  weights) pull_weights "$GEMMA_REPO" ;;
  all)
    pull_small "$GEMMA_REPO"
    pull_weights "$GEMMA_REPO"
    ;;
  qwen-fallback)
    pull_small "$QWEN_REPO"
    pull_weights "$QWEN_REPO"
    ;;
  *)
    echo "Unknown: $cmd"
    status
    exit 1
    ;;
esac

echo ""
case "$cmd" in
  qwen-fallback) progress "$QWEN_REPO" ;;
  status) ;;
  *) progress "$GEMMA_REPO" ;;
esac