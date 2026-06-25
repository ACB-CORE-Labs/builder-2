#!/usr/bin/env bash
# Backward-compatible wrapper for the older phased downloader.
#
# The governed roster now lives in scripts/pull-roster.sh. This file remains so
# older docs/commands keep working on spotty library Wi-Fi.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cmd="${1:-status}"
case "$cmd" in
  small|weights|all)
    exec "${ROOT}/scripts/pull-roster.sh" recommended
    ;;
  qwen-fallback)
    exec "${ROOT}/scripts/pull-roster.sh" alias qwen-coder
    ;;
  status)
    exec "${ROOT}/scripts/pull-roster.sh" status
    ;;
  *)
    exec "${ROOT}/scripts/pull-roster.sh" "$@"
    ;;
esac
