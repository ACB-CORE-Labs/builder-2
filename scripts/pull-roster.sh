#!/usr/bin/env bash
# Governed resumable MLX model downloader for builder-II on MacBook Pro M1 16GB.
#
# This script intentionally separates recommended, alternate, candidate, and heavy
# lanes. Do not download every model unless you have disk/time to burn. The M1
# runtime should load one model at a time; this script only populates cache.
#
# Usage:
#   ./scripts/pull-roster.sh status
#   ./scripts/pull-roster.sh recommended      # phi-reasoning + qwen-coder
#   ./scripts/pull-roster.sh fast             # phi-reasoning only
#   ./scripts/pull-roster.sh primary          # qwen-coder only
#   ./scripts/pull-roster.sh all-safe         # recommended + Gemma/Llama alternates
#   ./scripts/pull-roster.sh candidates       # CodeGeeX/Qwen14/Qwen3/DeepSeek candidates
#   ./scripts/pull-roster.sh alias qwen-coder
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HF="${ROOT}/.venv/bin/hf"
if [[ ! -x "$HF" ]]; then
  HF="$(command -v hf || true)"
fi
if [[ -z "$HF" ]]; then
  echo "Missing Hugging Face CLI. Run: uv sync  (or: uv pip install huggingface-hub[cli])" >&2
  exit 1
fi

export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-0}"
export HF_XET_HIGH_PERFORMANCE="${HF_XET_HIGH_PERFORMANCE:-0}"

# Defaults mirror builder_ii.config. Override any repo with env vars when testing
# a newer MLX conversion or a renamed community repo.
declare -A REPOS=(
  [phi-reasoning]="${CORE_AGENT_MLX_MODEL_PHI:-mlx-community/Phi-4-mini-reasoning-4bit}"
  [qwen-coder]="${CORE_AGENT_MLX_MODEL_QWEN:-mlx-community/Qwen2.5-Coder-7B-Instruct-4bit}"
  [gemma-fast]="${CORE_AGENT_MLX_MODEL_FAST:-mlx-community/gemma-4-e4b-it-4bit}"
  [gemma-primary]="${CORE_AGENT_MLX_MODEL_PRIMARY:-mlx-community/gemma-4-12B-it-4bit}"
  [llama]="${CORE_AGENT_MLX_MODEL_LLAMA:-mlx-community/Meta-Llama-3.1-8B-Instruct-4bit}"
  [codegeex]="${CORE_AGENT_MLX_MODEL_CODEGEEX:-mlx-community/codegeex4-all-9b-4bit}"
  [qwen-coder-14b]="${CORE_AGENT_MLX_MODEL_QWEN14:-mlx-community/Qwen2.5-Coder-14B-Instruct-4bit}"
  [qwen3-coder-heavy]="${CORE_AGENT_MLX_MODEL_QWEN3_CODER:-mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit}"
  [deepseek]="${CORE_AGENT_MLX_MODEL_DEEPSEEK:-mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit}"
)

cache_slug() {
  local repo="$1"
  echo "${HOME}/.cache/huggingface/hub/models--${repo//\//--}"
}

progress() {
  local alias="$1"
  local repo="${REPOS[$alias]}"
  local dir
  dir="$(cache_slug "$repo")"
  printf '%-20s %s\n' "$alias" "$repo"
  if [[ ! -d "$dir" ]]; then
    echo "  cache: (missing)"
    return
  fi
  local total incomplete safes
  total="$(du -sh "$dir" 2>/dev/null | cut -f1 || true)"
  incomplete="$(find "$dir" -name '*.incomplete' 2>/dev/null | wc -l | tr -d ' ')"
  safes="$(find "$dir/snapshots" -name '*.safetensors' 2>/dev/null | wc -l | tr -d ' ')"
  echo "  cache: ${total:-?} | safetensors: ${safes} | incomplete_blobs: ${incomplete}"
  if [[ "${incomplete}" != "0" ]]; then
    find "$dir/blobs" -name '*.incomplete' -exec ls -lh {} \; 2>/dev/null | head -5 || true
  fi
}

pull_alias() {
  local alias="$1"
  if [[ -z "${REPOS[$alias]:-}" ]]; then
    echo "Unknown alias: $alias" >&2
    echo "Known aliases: ${!REPOS[*]}" >&2
    exit 1
  fi
  local repo="${REPOS[$alias]}"
  echo "=== Pulling ${alias}: ${repo} ==="
  echo "This is resumable. Re-run the same command after network/library interruptions."
  "$HF" download "$repo"
  echo ""
  progress "$alias"
}

status() {
  echo "Recommended M1 16GB lanes: phi-reasoning + qwen-coder"
  echo "Candidate/heavy lanes are explicit opt-in; do not use them as defaults."
  echo ""
  for alias in phi-reasoning qwen-coder gemma-fast gemma-primary llama codegeex qwen-coder-14b qwen3-coder-heavy deepseek; do
    progress "$alias"
    echo ""
  done
}

cmd="${1:-status}"
case "$cmd" in
  status)
    status
    ;;
  recommended)
    pull_alias phi-reasoning
    pull_alias qwen-coder
    ;;
  fast)
    pull_alias phi-reasoning
    ;;
  primary)
    pull_alias qwen-coder
    ;;
  all-safe)
    pull_alias phi-reasoning
    pull_alias qwen-coder
    pull_alias gemma-fast
    pull_alias gemma-primary
    pull_alias llama
    ;;
  candidates)
    echo "Candidate downloads may fail if an MLX community conversion was renamed or unavailable."
    echo "Override repo env vars before running if needed."
    pull_alias codegeex || true
    pull_alias qwen-coder-14b || true
    pull_alias qwen3-coder-heavy || true
    pull_alias deepseek || true
    ;;
  alias)
    pull_alias "${2:?usage: $0 alias <model-alias>}"
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    echo "Usage: $0 status|recommended|fast|primary|all-safe|candidates|alias <name>" >&2
    exit 1
    ;;
esac
