#!/usr/bin/env bash
# Regenerates every measurement in opus_phase_4_verification_report.md from a clean tree.
# Run from the repo root. Requires: uv sync --all-groups
set -uo pipefail

echo "== A. Registry ground truth (no TUI involved) =="
uv run python -c "
from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY as R, TIER_3, TIER_4, check_command_authority as C
auth=[r for r in R if r.tier in (TIER_3,TIER_4)]
print('  records                    :', len(list(R)))
print('  rec.tier in (\"TIER_3\",\"TIER_4\") ->', sum(1 for r in R if r.tier in ('TIER_3','TIER_4')), '(what the pre-fix app.py computed)')
print('  rec.tier in (TIER_3,TIER_4)     ->', len(auth), '(ground truth)')
print('  permitted (render ⚡)       :', sum(1 for r in auth if C(r.name).allowed))
print('  refused   (render ⊘)       :', sum(1 for r in auth if not C(r.name).allowed))
"

echo
echo "== B. Semantic DOM measurement (no pexpect; Textual run_test only) =="
uv run python scripts/semantic_tui_driver.py \
  '{"app":"StratumApp","steps":[{"action":"press","target":"escape"},{"action":"press","target":"question_mark"}]}' \
  > /tmp/opus_palette.json
uv run python -c "
import json,re,collections
d=json.load(open('/tmp/opus_palette.json'))
print('  active_screen :', d['final_state']['active_screen'])
ws=[w for w in d['final_state']['widgets'] if w['type']=='PaletteEntry']
t=collections.Counter()
for w in ws:
    m=re.search(r'\](T[0-4]|\?\?)\[', w.get('text',''))
    t[m.group(1) if m else '??']+=1
print('  PaletteEntry  :', len(ws))
print('  tier badges   :', dict(t))
print('  rendering ??  :', sum(1 for w in ws if '??' in w.get('text','')))
print('  rendering ⚡   :', sum(1 for w in ws if '⚡' in w.get('text','')))
print('  rendering ⊘   :', sum(1 for w in ws if '⊘' in w.get('text','')))
"

echo
echo "== C. Mutation proof: which lane actually detects the defect? =="
cp builder_ii/tui/app.py /tmp/app.py.bak
python3 - <<'PY'
from pathlib import Path
p=Path("builder_ii/tui/app.py"); s=p.read_text()
p.write_text(s.replace('"requires_authority": rec.tier in (TIER_3, TIER_4),',
                       '"requires_authority": rec.tier in ("TIER_3", "TIER_4"),'))
PY
echo "  -- app.py mutated back to the pre-fix comparison --"
verdict() {  # $1 = nodeid, $2 = label
  if uv run pytest "$1" -q >/dev/null 2>&1; then
    echo "  $2: PASSED  <- cannot see the defect"
  else
    echo "  $2: FAILED  <- correctly catches the defect"
  fi
}
verdict tests/test_stratum_tui.py::test_palette_flags_every_authority_requiring_command_in_the_real_registry \
        "NEW lane (real registry)  "
verdict tests/test_stratum_tui.py::test_stratum_palette_authority \
        "OLD lane (mocked registry)"
cp /tmp/app.py.bak builder_ii/tui/app.py
echo "  -- app.py restored --"
echo
echo "  Expected: NEW=FAILED, OLD=PASSED -- both against the SAME broken tree."
echo "  The old lane passing on broken code IS the finding."
