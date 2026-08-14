#!/usr/bin/env bash
# Record the builder-II demo segments as asciinema casts (plan item 3.12).
#
# Produces three real recordings — nothing staged, no synthetic output — against a
# throwaway fixture git repository created in a temp dir:
#
#   builder-init.cast    one-command governed onboarding (builder init --non-interactive)
#   governed-loop.cast   the full governed demo loop: prepare -> approve -> apply ->
#                        verify -> rollback -> finalize -> validate
#   tamper-beat.cast     the flagship tamper-detection beat: edit a receipt -> validation
#                        names the file; retarget the approval -> the digest-prefix
#                        confirmation binding refuses (docs/demos/FLAGSHIP_DEMO_SCRIPT.md)
#
# Usage:
#   bash scripts/record-demo.sh [--output-dir docs/recordings] [--pin-timestamp] [--gif]
#
#   --pin-timestamp  Rewrite each cast header's wall-clock "timestamp" to a fixed epoch so
#                    committed takes don't leak recording time and re-takes diff minimally.
#                    Only the recording header is pinned — the timestamps INSIDE the demo's
#                    JSON artifacts are real and untouched (honest surfaces).
#   --gif            Also render a GIF per cast via `agg` (if installed). GIFs are large;
#                    they are render-on-demand by default and not required in the repo.
#
# Requires: asciinema >= 3 (headless recording), uv, git. Optional: agg (for --gif).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/docs/recordings"
PIN_TIMESTAMP=0
RENDER_GIF=0
PINNED_EPOCH=1700000000
WINDOW_SIZE=120x36

while [ $# -gt 0 ]; do
  case "$1" in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --pin-timestamp) PIN_TIMESTAMP=1; shift ;;
    --gif) RENDER_GIF=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v asciinema >/dev/null || { echo "asciinema is required (brew install asciinema)" >&2; exit 1; }
mkdir -p "$OUTPUT_DIR"

# A stable (non-random) work dir keeps the fixture paths identical between takes on the same
# machine, so pinned re-takes diff minimally instead of churning on a random temp suffix.
WORK="${TMPDIR:-/tmp}/builder-ii-recording"
rm -rf "$WORK"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT
TARGET="$WORK/acme-lib"
DEMO_OUT="$WORK/demo-out"
INIT_OUT="$WORK/init-out"

# --- fixture target: any local git repo with one commit ---------------------------------
mkdir -p "$TARGET/src"
git -C "$TARGET" init -q
printf 'def add(a, b):\n    return a + b\n' > "$TARGET/src/calc.py"
printf '# acme-lib\n\nA tiny fixture repository for the recorded demo.\n' > "$TARGET/README.md"
git -C "$TARGET" add src/calc.py README.md
git -C "$TARGET" -c user.email=demo@example.com -c user.name='Demo Operator' commit -qm 'init fixture'

# --- segment scripts ---------------------------------------------------------------------
# Each segment prints the command it is about to run, then runs it for real.
cat > "$WORK/prelude.sh" <<PRELUDE
set -euo pipefail
cd "$REPO_ROOT"
TARGET="$TARGET"
DEMO_OUT="$DEMO_OUT"
INIT_OUT="$INIT_OUT"
run() { printf '\n\033[1;36m\$ %s\033[0m\n' "\$*"; "\$@"; }
refuse() { printf '\n\033[1;36m\$ %s\033[0m\n' "\$*"; if "\$@"; then echo 'UNEXPECTED: command succeeded'; exit 1; else printf '\033[1;33m(refused, as designed)\033[0m\n'; fi }
PRELUDE

cat > "$WORK/segment-init.sh" <<'SEGMENT'
run uv run builder init --root "$TARGET" --output-dir "$INIT_OUT" --target-profile generic --non-interactive
SEGMENT

cat > "$WORK/segment-loop.sh" <<'SEGMENT'
for phase in prepare approve apply verify rollback finalize; do
  extra=""
  [ "$phase" = "prepare" ] && extra="--force"
  [ "$phase" = "approve" ] && extra="--approve"
  run uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$DEMO_OUT" --phase "$phase" $extra
done
run uv run builder-platform validate-demo-loop "$DEMO_OUT/demo-loop-report.json"
run git -C "$TARGET" status --porcelain=v1
printf '\033[1;32msource repo untouched; loop receipted and chain-verified\033[0m\n'
SEGMENT

cat > "$WORK/segment-tamper.sh" <<'SEGMENT'
printf '\n\033[1mNow we cheat: erase the mutation evidence from a receipt.\033[0m\n'
run python3 -c "
import json
p = '$DEMO_OUT/post-apply-verification-receipt.json'
d = json.load(open(p))
d['workspace_mutation_detected'] = False
d['status_lines'] = []
json.dump(d, open(p, 'w'), indent=2, sort_keys=True)
print('receipt edited: mutation evidence erased')
"
refuse uv run builder-platform validate-demo-loop "$DEMO_OUT/demo-loop-report.json"
printf '\n\033[1mSecond twist: re-point the approval at a different patch digest.\033[0m\n'
run python3 -c "
import json
p = '$DEMO_OUT/hitl-patch-approval.json'
d = json.load(open(p))
digest = d['patch_digest']
d['patch_digest'] = ('0' if digest[0] != '0' else '1') + digest[1:]
json.dump(d, open(p, 'w'), indent=2, sort_keys=True)
print('approval retargeted at a patch that was never approved')
"
refuse uv run builder-chain verify-artifacts "$DEMO_OUT/hitl-patch-proposal.json" "$DEMO_OUT/hitl-patch-approval.json"
printf '\033[1;32medited evidence announces itself: artifact is not authority\033[0m\n'
SEGMENT

record_segment() {
  local name="$1"
  local cast="$OUTPUT_DIR/$name.cast"
  echo "recording $name ..."
  asciinema rec --headless -q --window-size "$WINDOW_SIZE" --overwrite \
    -c "bash -c 'source \"$WORK/prelude.sh\"; source \"$WORK/segment-$name.sh\"'" \
    "$cast"
  if [ "$PIN_TIMESTAMP" = "1" ]; then
    python3 - "$cast" "$PINNED_EPOCH" <<'PY'
import json
import sys

path, epoch = sys.argv[1], int(sys.argv[2])
with open(path, encoding="utf-8") as handle:
    lines = handle.readlines()
header = json.loads(lines[0])
header["timestamp"] = epoch
lines[0] = json.dumps(header, separators=(",", ":")) + "\n"
with open(path, "w", encoding="utf-8") as handle:
    handle.writelines(lines)
PY
  fi
  if [ "$RENDER_GIF" = "1" ]; then
    command -v agg >/dev/null && agg "$cast" "$OUTPUT_DIR/$name.gif" || echo "agg not installed; skipped gif for $name"
  fi
  echo "  -> $cast"
}

record_segment init
record_segment loop
record_segment tamper

echo
echo "Done. Replay with: asciinema play $OUTPUT_DIR/<name>.cast"
echo "Render a GIF on demand with: agg $OUTPUT_DIR/<name>.cast <name>.gif"
