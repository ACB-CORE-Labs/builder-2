# Demo Recordings (plan item 3.12)

Real asciinema recordings of builder-II's governed lanes. Nothing staged: each cast is a live
run against a throwaway fixture git repository, recorded headlessly by
`scripts/record-demo.sh`. Replay any of them locally:

```bash
asciinema play docs/recordings/loop.cast
```

| Cast | What it shows |
| --- | --- |
| `init.cast` | One-command governed onboarding: `builder init --non-interactive` resolves and registry-validates the nine onboarding decisions, emits the passive plan/overlay/snapshot/intent artifacts, and renders the deferred apply command **without** an inline digest. |
| `loop.cast` | The full governed demo loop against a fixture repo: prepare → approve → apply → verify → rollback → finalize → validate, ending with the source repo's empty `git status` — planned ≠ executed ≠ verified, receipted end to end. |
| `tamper.cast` | The flagship tamper-detection beat (see `docs/demos/FLAGSHIP_DEMO_SCRIPT.md`): a receipt is edited to erase mutation evidence and `validate-demo-loop` names the exact file; the approval is re-pointed at a different patch digest and the digest-prefix confirmation binding refuses. |

## Re-recording

```bash
bash scripts/record-demo.sh --pin-timestamp          # refresh the committed casts
bash scripts/record-demo.sh --pin-timestamp --gif    # also render GIFs via agg (not committed)
```

Requires `asciinema` >= 3 (`brew install asciinema`); `agg` only for `--gif`. GIFs are
render-on-demand and intentionally not committed — the `.cast` files are the canonical assets
(small, text, diffable).

## Timestamp pinning (reproducible takes)

`--pin-timestamp` rewrites each cast header's wall-clock `timestamp` to a fixed epoch
(`1700000000`) so committed takes don't leak recording time and re-takes diff minimally. The
recording harness also uses a stable (non-random) work directory for the fixture so paths stay
identical between takes on the same machine.

Only the recording header is pinned. The timestamps inside the demo's JSON artifacts — receipts,
approvals, postflights — are real and untouched: recordings must show honest surfaces, and an
artifact with a doctored timestamp would not be one.
