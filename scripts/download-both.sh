#!/usr/bin/env bash
# Backward-compatible wrapper: the old "both" set is now the recommended M1
# roster, phi-reasoning + qwen-coder. Re-run safely; Hugging Face resumes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${ROOT}/scripts/pull-roster.sh" recommended
