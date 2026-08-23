#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WHEEL="${1:?usage: release-linux-candidate.sh WHEEL WHEEL_SHA256 OUTPUT}"
WHEEL_SHA256="${2:?usage: release-linux-candidate.sh WHEEL WHEEL_SHA256 OUTPUT}"
OUTPUT="${3:?usage: release-linux-candidate.sh WHEEL WHEEL_SHA256 OUTPUT}"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 2; }
WHEEL="$(cd "$(dirname "$WHEEL")" && pwd)/$(basename "$WHEEL")"
OUTPUT="$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")"

docker run --rm \
  -v "$REPO_ROOT:/workspace:ro" \
  -v "$WHEEL:/candidate/$(basename "$WHEEL"):ro" \
  -v "$(dirname "$OUTPUT"):/proof" \
  -w /workspace \
  python:3.12.13-bookworm \
  bash -c 'set -euo pipefail
    apt-get update -qq
    apt-get install -y -qq git curl >/dev/null
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    bash scripts/clean-clone-smoke.sh \
      --source /workspace \
      --candidate-wheel "/candidate/'"$(basename "$WHEEL")"'" \
      --candidate-wheel-sha256 "'"$WHEEL_SHA256"'" \
      --candidate-extras deepagents \
      --host-proof "/proof/'"$(basename "$OUTPUT")"'"'
