# Ratification grants

builder-II stops to confirm things. This document is about which of those confirmations you can
choose to stop being asked, which ones you can never stop being asked, and why that split is
enforced by two independent machine checks rather than by convention.

The goal is not less governance. It is the same governance with the friction placed where the
operator wants it: builder-II should feel like any other coding tool, while producing a stronger
audit trail than one — determinism, traceability, and an attributable answer to "who allowed this".

## The distinction the whole feature rests on

> A standing grant may relocate confirmation friction. It may never originate approval.

Some prompts are friction. When `builder-setup apply` prints an overlay plan digest and asks you to
type its first characters back, you already made the decision — when you authored and reviewed the
plan. The prompt only binds *which artifact* is about to be consumed.

Other prompts **are** the decision. The prompt in `builder-hitl approve-patch` does not confirm an
approval; it mints one, and the artifact it writes is evidence that a human decided. Delegating
that would manufacture human approval evidence for a decision no human made.

An `auto: true` config flag cannot tell those apart, and deletes the authority decision either way.
A grant relocates it: you make one explicit, attributable, digest-bound decision, and every
confirmation it later satisfies names it — in the consuming receipt, in stdout, and in the ledger.

## What is delegable today

| Point | Command | Delegable |
| --- | --- | --- |
| `setup.apply.overlay_digest` | `builder-setup apply` | yes |
| `setup.rollback.receipt_digest` | `builder-setup rollback` | yes |
| `hitl.approve_patch.patch_digest` | `builder-hitl approve-patch` | **never** — `human_approval_mint` |
| `hitl.refuse_patch.proposal_digest` | `builder-hitl refuse-patch` | **never** — `human_approval_mint` |
| `hitl.promotion_decision.candidate_digest` | `builder-hitl promotion-decision` | **never** — `promotion_decision` |

Run `builder-govern list-points` for the live answer; the table above is a snapshot, and
eligibility is recomputed from the command-authority registry, not read from this file.

The ungrantable points are **registered**, not merely omitted. An absent point refuses by accident
and cannot be pinned; a registered `human_approval_mint` point refuses on the record, and
`tests/test_ratification_points.py` pins the refusal.

## The two guards

Eligibility is never a field an author sets to `True`. `grant_eligibility()` recomputes it, and a
point must clear **both** of these independently:

1. **Declared kind.** Only `plan_digest_confirmation` is ever grantable. `human_approval_mint` and
   `promotion_decision` never are.
2. **Live authority record.** The owning command may not require HITL artifacts, may not be
   forbidden/unpromoted, must pass `check_command_authority`, and may not carry any capability flag
   outside `allows_source_writes`, `allows_artifact_writes`, `allows_state_writes`. Anything with
   shell, model, runtime-start, process-control, git-mutation, memory-mutation, subprocess, or
   external-tool capability is ineligible regardless of what kind it declares.

The second guard exists because the first alone was not enough, and the near-miss is worth
recording: `builder-hitl approve-patch` carries `approval_mode = none`. It needs no approval *to
run*, because running it is how an approval gets made. Deriving eligibility from the approval mode
alone would have made patch approval auto-grantable.

### Why eligibility is recomputed every time

Nothing about eligibility is stored in the grant artifact and read back. A grant records an
`eligibility_at_grant` block, but that is a receipt of what was true when you decided — it is
deliberately not load-bearing. Two consequences follow:

- A command promoted from `explicit_operator_invocation` to `hitl_artifact_required` invalidates
  every outstanding grant against it, with nobody remembering to revoke them.
- A grant file hand-edited to claim eligibility it never had buys nothing, because the claim is not
  what gets read. `tests/test_ratification_grants.py` pins this with a re-digested forgery that is
  internally valid and still does not satisfy.

## Using it

The walkthrough offers each delegable confirmation in context, states what granting it costs, and
names the ones it will not let you turn off:

```bash
builder onboard                 # interactive: choose per confirmation
builder onboard --no-prompt     # describe everything, write nothing
```

Or work with the points directly:

```bash
builder-govern list-points
builder-govern grant-auto setup.apply.overlay_digest --granted-by you@example
builder-govern list-grants
builder-govern trace setup.apply.overlay_digest
builder-govern revoke <grant-digest> --revoked-by you@example --reason "rotating delegations"
builder-govern validate-ledger
```

`grant-auto` requires you to type the point id back before it writes; `--yes` skips that for
scripted flows. `--granted-by` is required either way, so no grant exists without a named delegator.

## What you get in exchange

Delegating a confirmation does not make the action quieter. When a grant satisfies a prompt:

- **stdout still names it**: `Auto-accepted under standing grant <digest>`, plus how to revoke and
  audit. A confirmation that silently stops appearing is indistinguishable from one that was never
  required.
- **the receipt records `standing_ratification_grant`**, never `interactive_digest_prefix_confirmation`.
  A receipt never claims a human typed something a grant satisfied.
- **the ledger records it**, chained, alongside grants, revocations, and manually typed
  confirmations — so "what was auto-accepted, under whose delegation, when" is answerable later.

## The audit ledger

`ratification_ledger.jsonl` in the ratification store, kind `builder_ii.ratification_ledger_event`,
one line per decision: `grant_created`, `grant_revoked`, `auto_accepted`, `manual_ratified`.

Each `entry_digest` covers the whole entry **including** `prev_digest`, so the chain is a chain:
digesting the payload alone would leave every digest verifying after a line was deleted and the
next re-pointed around it. Appends hold an exclusive `flock` across read-tail-then-append, because
this file is shared across commands and concurrent appends fork the chain — and a fork is
indistinguishable from tampering.

**`RECORDED_ONLY`.** The same process that takes the action writes the line, so this is a receipt,
never independent proof. It closes transcription gaps, quiet single-line edits, and deletions. It
does not close dishonesty, and an attacker who rewrites every following line rebuilds a valid
chain. Tamper-evident, not tamper-proof.

## Store location

Default `.builder/artifacts/ratification/`, overridable with `BUILDER_RATIFICATION_ROOT` or a
`--root` flag on the `builder-govern` commands.

`builder-setup apply` and `rollback` append to the ledger **only where a store already exists**.
They will not conjure a governance store inside every repository they touch; where none exists no
grant can exist either, and the receipt already records the typed confirmation.

## Promotion status

`ARTIFACT_ONLY`. This lane mints, validates, and audits artifacts. It grants no new execution
capability: the operational-verified count is unchanged, and no completion-matrix row moves. What a
grant changes is *which confirmation path satisfied an already-promoted command* — recorded
faithfully in that command's receipt.

## Verification

```bash
uv run pytest tests/test_ratification_points.py tests/test_ratification_grants.py \
              tests/test_ratification_ledger.py tests/test_govern_cli.py \
              tests/test_onboarding_golden_path.py \
              tests/scenarios/test_governed_ratification_lane.py -q
```
