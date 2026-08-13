# ADR-0008: Governed deepagents Model-Invocation Lane

## Status

**Proposed — DESIGN_ONLY.** Nothing in this document promotes, enables, or implements any
capability. Acceptance of this ADR authorizes *implementation behind the eight promotion
gates*, not activation. The matrix row this ADR introduces starts at `DESIGN_ONLY` and may
only move on evidence (a closure audit), never on this document alone.

## Context

The 2026-07-22 adversarial audit (finding F2) measured that the deepagents lane has drifted
from *governed* to *denied*. Today, in `builder_ii/adapters/deepagents/deepagents_execution.py`:

- `DENIED_CAPABILITIES` includes **"native deepagents model invocation"** and
  **"direct tool execution"** alongside the genuinely authority-bearing denials
  (source writes, shell, git mutation, MCP, Goose activation, memory mutation).
- Even the `optional_deepagents` backend must return a payload that *proves*
  `calls_models = False` (with `calls_tools`, `writes_source`, `calls_mcp`,
  `mutates_memory`, `constructs_deepagents` all likewise false) or the run is refused.
- Consequently a subagent can only emit structural bookkeeping. An obligation whose
  output contract requires evidence can never reach `CONTRACT_SATISFIED` in this lane;
  it discharges `DISCHARGED_UNVERIFIED` by construction.

An agent that may not invoke a model is not a governed agent; it is an inert data
structure. This is the failure mode the Manifesto's **Third Door** names explicitly: weak
safety theater on one side, reckless automation on the other. builder-II's promise is
*powerful because governed* — the denial of the **reasoning step itself** delivers neither
power nor a governance lesson, because there is nothing to govern.

Meanwhile the platform already carries a governed model-call seam, built and verified
elsewhere:

- `builder_ii/routing/model_execution_gateway.py` mints `builder_ii.model_call_envelope`
  and `builder_ii.model_call_receipt` artifacts with registry/policy validation, price-book
  cost accounting, token accounting, and secret redaction.
- `builder-model call` / `standalone-call` / `validate-receipt` expose that seam as a
  governed command surface; the completion matrix records the model client registry as
  verified *under the governed execution gateway*.
- `builder_ii.model_budget` provides budget artifacts with remaining-balance semantics.
- The deepagents lane itself already has the sealed obligation envelope (Ladder 4): sealed
  fields inside the approval digest basis, fail-closed mint checks, a digest-stamped
  tamper-evident event ledger, checkpoints, resume, and replay.

Every ingredient of a *governed* think-step exists. They are simply not composed.

## Decision (proposed)

Permit the deepagents execution lane to invoke models **exclusively through the existing
model execution gateway**, inside a **sealed, digest-approved, budget-bounded grant**, with
every call ledgered and the lane's output remaining proposal-only.

Concretely:

1. **Replace the denial, keep the boundary.** `DENIED_CAPABILITIES` drops
   `"native deepagents model invocation"` and gains `"ungoverned model invocation"`.
   Direct provider/client use from inside the lane stays forbidden; the gateway is the
   only path. All other denials are untouched.
2. **A new sealed grant artifact** — `builder_ii.deepagents_model_invocation_grant` —
   carried *inside the approval digest basis* exactly like the Ladder 4 obligation
   envelope: model-alias allowlist, max call count, token/cost budget reference
   (`builder_ii.model_budget`), redaction policy, and the provider isolation envelope
   (`local_network` vs `cloud_egress`) named explicitly. No grant, no calls. An approval
   that does not seal a grant preserves today's behavior bit-for-bit.
3. **Every call is two artifacts and one ledger event.** Each think-step mints a
   `model_call_envelope`, executes via the gateway, stores the `model_call_receipt`, and
   appends a `model_call_recorded` event (envelope digest, receipt digest, actual token
   cost) to the existing tamper-evident event ledger. Refusals (budget exhausted, alias
   not granted, gateway validation failure) append `model_call_refused` with the named
   reason — fail closed, always visible.
4. **Budget is debited before the call.** Exhaustion checkpoints the run
   (`CHECKPOINTED`), resumable only after a fresh human grant. This is the governed
   version of "freedom": more capability purchased with more evidence, never with less.
5. **Output stays PROPOSAL_ONLY.** The result contract kind is unchanged. Obligations
   whose output contract names *reasoned proposal with call receipts* may now discharge
   `CONTRACT_SATISFIED` on the strength of those receipts; mutation and verification
   evidence contracts still discharge only in the hitl_patch and verify lanes.
6. **Replay is two-tier and says so.** Structural chain replay remains deterministic and
   unchanged. Model calls are **recorded, not replayed**: replay verifies envelope/receipt
   digests and spend against the ledger and never re-invokes a model. The replay report
   states `model_calls: recorded_not_replayed` — the same honesty grammar as
   `RECORDED_ONLY`.
7. **HITL brackets the lane.** A human approves the grant *before* any call and reviews
   the proposal *after*. Model output is never approval. Nothing self-approves.

## Alternatives considered

- **Status quo (denied).** Rejected: safety theater; produces inert agents and teaches
  operators that governance means lobotomy.
- **Native deepagents/LangGraph model binding inside the graph.** Rejected: an ungoverned
  client inside the harness bypasses registry, policy, price book, redaction, and budget —
  the exact bypass shape the README's "wrong shape" diagram forbids.
- **A bespoke model client in the deepagents adapter.** Rejected: duplicates the gateway,
  violates mechanical sympathy, and creates a second egress surface to govern.

## Consequences

- Subagents can *reason* about real work and produce reviewable, evidence-bound proposals;
  the platform's cost/budget HUD surfaces their spend from the same artifact kinds it
  already reads.
- Replay honesty becomes two-tier (structural vs recorded) and must be documented and
  pinned as such.
- Grant approval adds one HITL step per run; the Forge wizard should default sensible
  grants so the friction is one confirmation, not a form.
- Implementation must clear all eight promotion gates (docs, tests, command surface,
  failure mode, human approval boundary, output artifact, rollback path, verification
  path) with an evidence-backed matrix flip. See
  [`docs/DEEPAGENTS_RUNTIME.md`](../plan/DEEPAGENTS_MODEL_INVOCATION_LANE.md)
  for the full lane design, failure-mode taxonomy, test plan, and rollout ladder.
