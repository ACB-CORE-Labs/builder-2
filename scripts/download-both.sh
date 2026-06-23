#!/usr/bin/env bash
# Download BOTH models we use. Re-run until builder status shows COMPLETE.
# Resumes automatically — safe after library disconnect.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HF="${ROOT}/.venv/bin/hf"
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_XET_HIGH_PERFORMANCE=0

E4B="mlx-community/gemma-4-e4b-it-4bit"
B12="mlx-community/gemma-4-12B-it-4bit"

echo "=== E4B fast: model.safetensors (5.2GB) ==="
"$HF" download "$E4B" model.safetensors || true

echo "=== 12B primary: shard 2 first (1.4GB) ==="
"$HF" download "$B12" model-00002-of-00002.safetensors || true

echo "=== 12B primary: shard 1 (5.4GB) ==="
"$HF" download "$B12" model-00001-of-00002.safetensors || true

echo "=== status ==="
du -sh "${HOME}/.cache/huggingface/hub/models--mlx-community--gemma-4-e4b-it-4bit" \
        "${HOME}/.cache/huggingface/hub/models--mlx-community--gemma-4-12B-it-4bit" 2>/dev/null || true
find "${HOME}/.cache/huggingface/hub/models--mlx-community--gemma-4-e4b-it-4bit" \
     "${HOME}/.cache/huggingface/hub/models--mlx-community--gemma-4-12B-it-4bit" \
     -name '*.incomplete' 2>/dev/null | wc -l | xargs echo "incomplete_blobs:"