# Governed deepagents Model-Invocation Lane — full design

> **Status: DESIGN_ONLY.** Companion to
> [`ADR-0008`](../adrs/ADR-0008-governed-deepagents-model-invocation-lane.md). Nothing here
> is implemented or promoted; this document exists so implementation PRs can be reviewed
> against a fixed, operator-approved design instead of drifting one convenience at a time.
> The capability row introduced here starts `DESIGN_ONLY` and moves only on closure-audit
> evidence.

## 1. One-paragraph shape

A deepagents run whose approval seals a **model-invocation grant** may, during
`run-approved` / `resume-approved`, route think-steps through the **existing**
`model_execution_gateway` (`builder_ii.model_call_envelope` →
`builder_ii.model_call_receipt`), debiting a sealed budget before every call, appending
`model_call_recorded` / `model_call_refused` events to the existing tamper-evident ledger,
and still terminating in a **proposal-only** result that a human reviews. No grant → the
lane behaves exactly as today. No path exists from the lane to providers except the
gateway.

## 2. The grant artifact

Kind: `builder_ii.deepagents_model_invocation_grant` (schema v1).

| Field | Meaning | Fail-closed rule |
|---|---|---|
| `model_aliases` | Allowlist of registry aliases callable in this run | Call with alias outside list → `model_call_refused` |
| `max_calls` | Hard ceiling on gateway invocations | Ceiling reached → refuse + checkpoint |
| `budget_ref` | Digest-pinned ref to a `builder_ii.model_budget` artifact | Missing/invalid/exhausted → refuse before call |
| `isolation_envelope` | `local_network` or `cloud_egress`, explicit | Gateway target class ≠ envelope → refuse |
| `redaction_policy` | Named policy for prompt/receipt storage | Unresolvable policy → refuse at mint |
| `grant_digest` | SHA-256 over canonical grant content | Sealed into the approval digest basis |

Sealing follows the Ladder 4 obligation-envelope precedent exactly: the grant's fields go
**inside** the candidate approval's digest basis, so what the human approved and what the
run may spend are the same bytes. A tampered grant fails the existing mint check; there is
no separate enforcement path to keep honest.

## 3. Event-ledger extension

Two new event types in the existing `EVENT_TYPES` chain (digest-stamped, hash-chained,
replay-covered like every other event):

- `model_call_recorded` — fields: `envelope_digest`, `receipt_digest`, `alias`,
  `prompt_tokens`, `completion_tokens`, `cost_estimate`, `budget_remaining_after`.
- `model_call_refused` — fields: `refusal_reason` (one of the taxonomy below), `alias`,
  `attempted_at_call_index`. Refusals are *events, not exceptions swallowed*: an operator
  reading the ledger sees every attempt the envelope denied.

Refusal taxonomy (closed set, validated): `alias_not_granted`, `max_calls_exhausted`,
`budget_exhausted`, `isolation_envelope_mismatch`, `gateway_validation_failed`,
`redaction_policy_unresolvable`, `grant_missing`.

## 4. Execution flow (delta over today's lane)

```text
candidate (backend_mode=optional_deepagents, sealed grant)     [NEW: grant sealed]
  → HITL digest approval (human; grant inside digest basis)    [same approval kind]
  → run-approved
      each think-step:
        1. preflight: grant present? alias allowed? calls left? budget left?
           isolation ok?                                        [fail closed → refusal event]
        2. debit budget                                         [before the call, never after]
        3. mint model_call_envelope → gateway → receipt         [existing gateway, unchanged]
        4. append model_call_recorded                           [chained event]
      exhaustion / operator stop → CHECKPOINTED                 [existing status]
  → proposal-only result (kind unchanged)                       [PROPOSAL_ONLY preserved]
  → human reviews proposal                                      [unchanged]
```

The backend result schema changes in exactly one place: `calls_models` may be `true` **iff**
the run's approval sealed a grant, and then the result must carry the list of receipt
digests it claims. A result claiming calls without matching ledger events (or vice versa)
fails validation — the cross-check both directions is the point.

## 5. Discharge semantics

- Obligations whose `output_contract` names **reasoned-proposal-with-receipts** may reach
  `CONTRACT_SATISFIED`, with the receipts as contract evidence.
- Obligations requiring **mutation or verification evidence** still cannot be satisfied
  here — that evidence only exists in the hitl_patch and verify lanes. They continue to
  discharge `DISCHARGED_UNVERIFIED`, and the provenance stamp continues to say so.
- `protocol_fake` runs never mint grants and never record model calls; their discharge
  provenance stays `structural truth only`. The fabricated-success ban is unaffected.

## 6. Replay honesty (two-tier)

- **Tier 1 — structural:** chain digests, event ordering, budget arithmetic, grant
  enforcement decisions. Deterministic, re-derived on every replay, unchanged from today.
- **Tier 2 — recorded:** model calls. Replay verifies envelope/receipt digests and spend
  totals against the ledger; it **never re-invokes a model**. The replay report gains
  `model_calls: recorded_not_replayed`.

This is the same honesty grammar as `RECORDED_ONLY`: the audit trail is deterministic and
tamper-evident; the model output is pinned evidence, not a re-derivable computation. Docs
and tests must never describe tier 2 as deterministic replay.

## 7. Failure modes (gate 4 of 8)

| Failure | Behavior | Where visible |
|---|---|---|
| Grant tampered after approval | Mint check refuses the run (existing sealed-envelope path) | run refusal artifact |
| Budget exhausted mid-run | Refusal event + `CHECKPOINTED`; resume requires fresh grant | ledger + run status |
| Gateway/provider down | `gateway_validation_failed` refusal event; run may checkpoint | ledger |
| Receipt/ledger mismatch | Result validation fails; run classified `CONTRACT_VIOLATED` | validator output |
| Operator stop | Checkpoint event; no partial call is silently retried | ledger + cockpit (Track C) |
| Secret in prompt/response | Existing gateway redaction applies before storage | receipt artifact |

## 8. Test plan (gate 2 of 8)

- Unit: grant validator (every field, every refusal reason); seal/digest round-trip;
  budget debit-before-call ordering (mutation-test the ordering — a debit-after-call
  mutant must die).
- Cross-validation: result claims N calls ↔ ledger has exactly N `model_call_recorded`
  events ↔ N receipts exist on disk, in both tamper directions.
- Scenario (`tests/scenarios/`): full lane — grant → approval → run with a stubbed
  gateway transport → refusal on exhaustion → checkpoint → re-grant → resume → proposal;
  replay verifies both tiers; a doctored receipt digest must fail replay.
- Real-transport smoke (explicit opt-in, local model only): one call through the real
  gateway against the local backend, asserting receipt shape and spend accounting — the
  closure-audit evidence for the matrix flip.

## 9. Rollout ladder (each PR battery-green; no promotion until PR-5's audit)

1. **PR-1** — grant artifact + validator + seal-into-approval (behavior identical with no
   grant; proves bit-for-bit today-equivalence).
2. **PR-2** — ledger event types + refusal taxonomy + cross-validators.
3. **PR-3** — gateway wiring in `run-approved`/`resume-approved` behind the sealed grant;
   stubbed transport in CI.
4. **PR-4** — CLI surface (`builder-deepagents grant`, extensions to `execution-candidate`
   / `approve-candidate` / `replay-run`) + Forge wizard grant step + docs.
5. **PR-5** — closure audit against a real local-model call; matrix row
   `DESIGN_ONLY → OPERATIONALLY_VERIFIED` only on that evidence, operator-approved.

## 10. Non-goals (unchanged denials)

Source writes, shell execution, git mutation, MCP calls, Goose activation, persistent
memory mutation, direct tool execution, and any provider path that bypasses the gateway
remain denied in this lane. This design adds exactly one capability — the governed
reasoning step — and nothing else.
