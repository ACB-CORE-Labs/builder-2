#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a
exec "$ROOT/.venv/bin/python" -c "
from builder_ii.config import load_settings
from builder_ii.backends import list_start_command
import subprocess
cmd = list(list_start_command(load_settings()))
subprocess.execvp(cmd[0], cmd)
"