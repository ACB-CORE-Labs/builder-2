#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a
exec "$ROOT/.venv/bin/python" -c "
from builder_ii.core.config import load_settings
from builder_ii.routing.backends import list_start_command
import os
cmd = list(list_start_command(load_settings()))
os.execvp(cmd[0], cmd)
"
