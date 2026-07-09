# Flagship Demo Script — 15 Minutes, One Governed Loop, One Live Tamper (plan item 3.11)

The canonical presentation script for builder-II. One take, fifteen minutes, seven beats. The
centerpiece is the **live tamper-detection beat**: you edit a receipt on camera and the platform
names the exact file you touched. Governance *felt* is the product — nothing in this script is
mocked, staged, or pre-recorded output.

The whole demo uses one mental model, spoken out loud as you go:

> **artifact → validate → approve → execute → receipt.**

Everything else — chains, ledgers, digests, promotion states — stays behind those five verbs until
the tamper beat drags it on stage.

## Before the take

```bash
# 1. A working builder-II checkout (see FIRST_SESSION.md for first-time setup)
uv sync --all-groups

# 2. A demo target: any local git repository with at least one commit.
#    A tiny fixture works; so does a real project. NEVER point the demo at
#    a repo you can't afford to look at on camera.
export TARGET=/path/to/any/local/git/repo
export OUT=/tmp/builder-ii-flagship-demo

# 3. Dry-run the whole loop once off camera. Every phase must succeed
#    before you record. Re-runs need --force on prepare.
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase prepare --force
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase approve --approve
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase apply
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase verify
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase rollback
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase finalize
uv run builder-platform validate-demo-loop "$OUT/demo-loop-report.json"

# 4. Keep a pristine copy of one receipt for the tamper beat's restore step.
cp "$OUT/post-apply-verification-receipt.json" /tmp/receipt-backup.json
```

For the actual take, delete `$OUT` and start clean so the audience sees every artifact appear.

## The 15 minutes

| Clock | Beat | Verb on stage |
| --- | --- | --- |
| 0:00–1:00 | 1. Framing | the five verbs |
| 1:00–3:30 | 2. Plan, don't touch | artifact |
| 3:30–5:00 | 3. Read the proposal | validate |
| 5:00–7:00 | 4. The authority boundary | approve |
| 7:00–9:00 | 5. Bounded execution | execute |
| 9:00–11:00 | 6. Receipts and rollback | receipt |
| 11:00–13:30 | 7. **The tamper beat** | all five, adversarially |
| 13:30–15:00 | 8. What this is not | (truth matrix) |

### Beat 1 — Framing (0:00–1:00)

Say it plainly:

> "builder-II is a governed control plane for local agent-assisted development. Every capability
> follows one grammar: build an artifact, validate it, approve it at an explicit boundary, execute
> inside that boundary, and get a digest-chained receipt. I'm going to run one complete loop
> against a real repository, and then I'm going to tamper with the evidence on camera."

No slides. The terminal is the deck.

### Beat 2 — Plan, don't touch (1:00–3:30)

```bash
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase prepare
```

Point at three things in the JSON that prints:

- `"phase": "prepare"` and `"ready_for_recording"` — the loop is checkpointed; each phase ends by
  naming the next command. No dead ends.
- `"demo_worktree"` — a **detached temporary worktree** of the target's current HEAD. The source
  checkout is never mutated; prove it later, not now.
- `ls "$OUT"` — preflight, repo map, context pack, deterministic planner, and an
  `hitl-patch-proposal.json`. Artifacts exist; nothing has executed.

> "Everything you see is a plan. Planned is not executed."

### Beat 3 — Read the proposal (3:30–5:00)

```bash
python3 -c "import json; d=json.load(open('$OUT/hitl-patch-proposal.json')); print(d['patch_description']); print(d['patch_digest'])"
```

> "The proposal carries a SHA-256 of the exact patch it wants to apply. That digest is what gets
> approved — not a vibe, not a summary, the content."

### Beat 4 — The authority boundary (5:00–7:00)

```bash
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase approve --approve
```

Open `"$OUT/hitl-patch-approval.json"` and show `approved_by`, `patch_digest`, and the
`confirmation` block:

> "This is the only authorization artifact in the loop, and it is digest-bound: the confirmation
> records a typed prefix of the patch digest. In interactive lanes the operator literally types
> those characters — no `[y/N]` reflex-training, friction exactly at the boundary and nowhere
> else. A model can propose; only this artifact approves. Model output is not approval."

If asked what happens without `--approve`: nothing is minted at all — the absence of a valid
approval *is* the unapproved state.

### Beat 5 — Bounded execution (7:00–9:00)

```bash
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase apply
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase verify
cat "$OUT/demo-worktree/docs/builder_ii_demo_marker.md"
git -C "$TARGET" status --porcelain=v1
```

Two proofs on screen:

- The approved patch exists **only** in the temporary worktree (the marker file).
- The source repo's `git status` prints nothing. Untouched.

> "Verification here is fail-closed: if anything beyond the approved marker had changed in that
> worktree — anything — the verify phase refuses. Executed is not verified; this is what earns it."

### Beat 6 — Receipts and rollback (9:00–11:00)

```bash
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase rollback
uv run builder-platform demo-loop --target-repo "$TARGET" --output-dir "$OUT" --phase finalize
uv run builder-platform validate-demo-loop "$OUT/demo-loop-report.json"
```

Show `{"valid": true}` and open `"$OUT/DEMO_EVIDENCE.md"`:

> "Every artifact in this run — approvals, receipts, postflights — is listed with its canonical
> SHA-256, chain-verified, and indexed. The patch is rolled back, the worktree is clean, the
> source repo was never touched. This bundle is digest-chained evidence you can hand to a
> reviewer."

### Beat 7 — THE TAMPER BEAT (11:00–13:30)

> "Now the part that matters. Evidence you can't check is theater. So let's cheat."

Edit the post-apply verification receipt **on camera** — erase the record that anything was
mutated:

```bash
python3 - <<'EOF'
import json, os
p = os.path.expandvars("$OUT/post-apply-verification-receipt.json")
d = json.load(open(p))
d["workspace_mutation_detected"] = False
d["status_lines"] = []
json.dump(d, open(p, "w"), indent=2, sort_keys=True)
print("receipt edited: mutation evidence erased")
EOF

uv run builder-platform validate-demo-loop "$OUT/demo-loop-report.json"
```

It exits non-zero and prints, naming your exact file:

```
demo report validation error: evidence artifact content does not match its recorded sha256:
.../post-apply-verification-receipt.json
```

> "The report recorded the canonical hash of every evidence file at finalize time, and validation
> recomputes them from disk. An edited receipt announces itself."

Optional second twist (30 seconds, if the room is technical) — retarget the *approval* at a
different patch digest and check the pair directly:

```bash
python3 - <<'EOF'
import json, os
p = os.path.expandvars("$OUT/hitl-patch-approval.json")
d = json.load(open(p))
d["patch_digest"] = ("0" if d["patch_digest"][0] != "0" else "1") + d["patch_digest"][1:]
json.dump(d, open(p, "w"), indent=2, sort_keys=True)
EOF

uv run builder-chain verify-artifacts "$OUT/hitl-patch-proposal.json" "$OUT/hitl-patch-approval.json"
```

```
confirmation.digest_prefix must be a prefix of patch_digest
```

> "You can't re-point an approval at a different patch: the typed confirmation is welded to the
> digest it approved. Artifact is not authority — and forged authority doesn't validate."

Restore before questions:

```bash
cp /tmp/receipt-backup.json "$OUT/post-apply-verification-receipt.json"
```

(The approval stays broken — leave it as a conversation piece, or re-run the loop with `--force`.)

Honesty note, if asked: these are integrity digests, not signatures. The receipts are
digest-chained evidence for review; builder-II makes no cryptographic-signature claims.

### Beat 8 — What this is not (13:30–15:00)

```bash
uv run builder-platform matrix | head -40
```

> "This matrix is CI-enforced truth: docs claiming capabilities the code doesn't back fail the
> build. What you just watched is one of the few operationally verified lanes. What you did NOT
> see: no commit, no push, no model call, no autonomous writes — those are explicitly unpromoted.
> The demo's only mutation was one approved marker in a throwaway worktree, and we rolled it back
> and receipted it. Planned isn't executed, executed isn't verified, verified isn't promoted."

Close with the pointer: `FIRST_SESSION.md` gets a stranger to this same loop in minutes.

## Contingencies

- **A phase fails mid-take**: read the error aloud — every error names its cause and the fixing
  command. That *is* the product behaving; narrate it and continue.
- **`prepare` refuses because `$OUT` exists**: add `--force` (stale outputs are cleared, the
  worktree is rebuilt).
- **Target repo has uncommitted changes**: preflight will say so; commit or pick another target.
- **You fumble the tamper edit and break the JSON itself**: even better —
  `validate-demo-loop` reports the file as invalid JSON. Same lesson, louder.

## Covering lanes

The tamper beat is pinned by tests, not by hope:
`tests/test_demo_loop.py::test_demo_validate_cli_catches_tampered_receipt` and
`::test_demo_validate_cli_catches_retargeted_approval`. The loop itself is covered by the rest of
`tests/test_demo_loop.py` and the clean-clone smoke gate (`scripts/clean-clone-smoke.sh`).

## Act II — tamper the cognition chain (sequel, not part of the promoted take)

This sequel is not part of the fifteen-minute take above, and it exercises a capability that is
governed but not yet promoted (see `docs/ORCHESTRATION_OBLIGATIONS.md` and
`planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md`): the Ladder 4 governed obligation delegation
lane, one layer up the delegation tree from the patch lane Act I tampers. Where Act I edits a
receipt, Act II edits one event inside the sealed runner's own hash-chained event log — the same
"evidence you can't check is theater" lesson, one level deeper into the machinery, over the
`protocol_fake` backend as CI truth.

Setup (all real, existing commands — nothing here is a recorded take):

```bash
# 1. Render the lane policy and seal a candidate with an obligation envelope.
uv run builder-orchestration lane-policy --output lane-policy.json
uv run builder-deepagents execution-candidate --work-plan plan.json --output-root runs/ \
    --lane-policy lane-policy.json --allowed-obligation-kind planning_step:4 \
    --refused-lane goose --output candidate.json
uv run builder-deepagents approve-candidate --candidate candidate.json \
    --approval-actor "Op" --approval-reason "seal the envelope" --output approval.json

# 2. Mint an obligation and run it under the seal (protocol_fake backend, no dispatch,
#    no model calls, no writes — an artifact-only lane).
uv run builder-orchestration mint-obligation --obligation-kind planning_step \
    --task "..." --expected-kind builder_ii.deepagents_proposal_only_result \
    --subagent-profile repo_mapper --lane-policy lane-policy.json \
    --seal-digest <approval_digest> --max-subagents 1 --max-events 10 \
    --max-output-bytes 1024 --max-human-gates 0 --output obligation.json
uv run builder-deepagents run-approved --candidate candidate.json --approval approval.json \
    --output-dir runs/obl --obligation obligation.json
```

`run-approved` writes one `event-XXXX-<event_type>.json` file per event under `runs/obl/events/`;
each one carries its own digest and a `previous_event_sha256` link to the event immediately before
it — a hash chain, not just a list.

Tamper one on camera:

```bash
python3 - <<'EOF'
import json, glob
path = sorted(glob.glob("runs/obl/events/event-*-obligation_consumed.json"))[0]
d = json.load(open(path))
d["payload"]["discharge_state"] = "CONTRACT_VIOLATED"   # lie about what was actually discharged
json.dump(d, open(path, "w"), indent=2, sort_keys=True)
print("event edited:", path)
EOF

uv run builder-deepagents replay-run --events-dir runs/obl/events --output runs/obl/replay-after-tamper.json
```

The replay comes back `"valid": false`: the forged event's own digest no longer matches its
content, and the very next event's `previous_event_sha256` no longer matches the (now different)
hash of the event before it. Both are named by file path in the report's `errors`.

> "The event you edited announces itself, and so does the one right after it. You cannot forge one
> link in this chain without the next link telling on you."

Honesty notes, if asked: the replay report written at run completion is a snapshot from that
moment — it does not retroactively invalidate itself when a file is edited afterward; only a fresh
`replay-run` (or the equivalent reconstruction from events on disk) catches a change made after the
fact. This is a hash-chain integrity check, not a cryptographic signature. Minting an obligation
remains an inert JSON artifact — nothing above starts, dispatches, or autonomously spawns anything;
the optional native `deepagents` backend is a separate, two-key-gated surface this beat does not
touch or claim.

### Covering lanes (Act II)

`tests/scenarios/test_full_obligation_delegation_lane.py` drives this exact sequence unmocked —
lane policy, sealed candidate, obligations covering all four discharge outcomes
(`CONTRACT_SATISFIED`, `DISCHARGED_UNVERIFIED`, `CONTRACT_VIOLATED`, `BLOCKED`, the last from a
mint the seal refuses for widening past its budget), and the tamper beat above — and pins that the
forged event is named and that the chain break is reported on the `previous_event_sha256` link.
