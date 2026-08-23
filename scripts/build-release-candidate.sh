#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="${1:-$REPO_ROOT/dist/release-candidate}"

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

cd "$REPO_ROOT"
uv build --out-dir "$OUT_DIR"

WHEEL="$(find "$OUT_DIR" -maxdepth 1 -type f -name 'builder_ii-1.0.0-*.whl' -print -quit)"
SDIST="$(find "$OUT_DIR" -maxdepth 1 -type f -name 'builder_ii-1.0.0.tar.gz' -print -quit)"
[ -n "$WHEEL" ] && [ -n "$SDIST" ] || {
  echo "release candidate must contain builder_ii 1.0.0 wheel and sdist" >&2
  exit 1
}

uv run python - "$WHEEL" <<'PY'
import csv
import sys
import zipfile
from pathlib import Path

wheel = Path(sys.argv[1])
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
    required = {
        "builder_ii/tui/stratum.tcss",
        "builder_ii/tui_theme_patch.md",
    }
    missing = sorted(required - names)
    if missing:
        raise SystemExit(f"wheel missing runtime resources: {missing}")
    metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
    metadata = archive.read(metadata_name).decode("utf-8")
    for field in ("Name: builder-ii", "Version: 1.0.0", "Requires-Python: <3.13,>=3.12.13"):
        if field not in metadata:
            raise SystemExit(f"wheel metadata missing {field!r}")
    record_name = next(name for name in names if name.endswith(".dist-info/RECORD"))
    rows = list(csv.reader(archive.read(record_name).decode("utf-8").splitlines()))
    if not rows or not all(row and row[0] in names for row in rows):
        raise SystemExit("wheel RECORD does not inventory every entry")
print(wheel)
PY

SMOKE_ROOT="$(mktemp -d -t builder-ii-wheel-install)"
cleanup() { rm -rf "$SMOKE_ROOT"; }
trap cleanup EXIT

UV_TOOL_DIR="$SMOKE_ROOT/base-tools" UV_TOOL_BIN_DIR="$SMOKE_ROOT/base-bin" \
  uv tool install --python 3.12.13 --force "$WHEEL"
"$SMOKE_ROOT/base-bin/builder" --help >/dev/null
"$SMOKE_ROOT/base-bin/builder-release" --help >/dev/null

UV_TOOL_DIR="$SMOKE_ROOT/deepagents-tools" UV_TOOL_BIN_DIR="$SMOKE_ROOT/deepagents-bin" \
  uv tool install --python 3.12.13 --force "$WHEEL[deepagents]"
"$SMOKE_ROOT/deepagents-bin/builder-deepagents" --help >/dev/null

echo "release candidate build and base/deepagents tool installs: PASS"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$SDIST" "$WHEEL"
else
  sha256sum "$SDIST" "$WHEEL"
fi
