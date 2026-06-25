#!/usr/bin/env bash
# Governed resumable MLX model downloader for builder-II on MacBook Pro M1 16GB.
#
# Thin compatibility wrapper. The canonical implementation lives in
# scripts/pull-models-resumable.sh because that script includes retry logic,
# captive-portal detection, stale-lock cleanup, and strict process management.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "${ROOT}/scripts/pull-models-resumable.sh" "$@"
