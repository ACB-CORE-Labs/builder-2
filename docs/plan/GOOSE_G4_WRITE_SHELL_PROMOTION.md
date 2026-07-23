# Goose G4 — write/shell unlock promotion (design for sign-off)

> **Status: DESIGN_ONLY.** This document designs a promotion; it enables nothing. The
> capability it describes stays denied and refused until the eight promotion gates are
> satisfied with evidence and a completion-matrix row is flipped on a closure audit — never
> on this document. Operational verified count does not change on acceptance. This is the
> Phase 3 (G4) design that [`ADR-0009`](../adrs/ADR-0009-goose-in-loop-governed-runtime.md)
> defers until the read-only and refusal phases (G1–G3) land — which they now have.

## 0. Implementation status (2026-07-23)

Reading the code refined the design, and it is now implemented at a **deny-by-default candidate
state**. It is **not** enabled by default and does **not** flip the completion matrix (OV
unchanged); the remaining step **before** an `enabled` state is a closure audit, which is an
operator decision and is **not** performed here.

- **Delegation, not pin relaxation.** builder-II already carries a governed source-write lane,
  `builder-hitl apply-patch` / `apply_hitl_patch`, which enforces command authority, a
  schema-valid unexpired digest-bound approval, a clean tree, and a verification receipt at the
  execution boundary, and emits a receipt + rollback bundle. G4 routes a validated
  `propose_patch` in-loop call to that lane rather than relaxing the read-only `mcp_call_envelope`
  schema. The read-only-by-schema law is therefore **not** touched, and no new write primitive is
  minted. The honest state is the existing `hitl_runtime_candidate` — no new state is required.
- **Deny-by-default at two levels.** The in-loop apply path is off unless the operator sets
  `BUILDER_MCP_GOVERNED_APPLY`; even then a mutation requires a valid digest-bound approval, and
  `apply_hitl_patch` re-validates everything and fails closed. Absent the flag or a valid
  approval, `propose_patch` refuses exactly as G3 did (an `mcp_call_denied` event).
- **Write path only.** `run_shell` has no governed bounded lane to delegate to, so it is **not**
  unlocked and always refuses; arbitrary shell is out of G4 scope.
- Code: `builder_ii/adapters/mcp/governed_apply.py` (+ server routing);
  `tests/test_mcp_governed_apply.py` proves the deny-by-default and fail-closed matrix. Sections
  1–7 below record the original design; this section governs where they differ.

## 1. Where G1–G3 leave us (the evidence base)

Landed and inside the observe-and-compose contract:

- **G1** — a governed stdio MCP server (`builder-mcp serve`) whose read-only tool calls run
  the envelope -> receipt -> hash-chained event ceremony.
- **G2** — `recipes/governed-readonly.yaml` + `launch_governed`, pointing Goose at that
  server as its only tool surface (no developer/shell builtins).
- **G3** — the in-loop gate: mutating tool classes (`propose_patch`, `run_shell`) are
  advertised but **refused**, deny-by-default, each refusal recorded as an `mcp_call_denied`
  event. Measured live: `run_shell` refused (`mcp_call_denied`) and `echo` executed
  (`mcp_call_executed`) in one chained session.

That refusing gate, producing real denial receipts, is the evidence G4 builds on: the seam
that would perform a mutation already exists and already refuses. G4 does not invent a new
path; it makes the existing refusal path *conditionally* execute behind a validated approval.

## 2. The boundary G4 crosses

G4 crosses the four load-bearing non-authority boundaries in `docs/ROADMAP.md`: *no
autonomous source writes; no shell execution as an agent capability; no Goose runtime
activation into mutation; no memory mutation.* Two schema pins in `core/mcp_policy.py`
(`executes_shell` and `mutates_target_repo`, currently forced `false` on every envelope)
would relax — **only** when a validated `approval_ref` is present on the envelope. Absent a
valid approval, every mutating call refuses exactly as it does today.

## 3. What G4 would change (the precise code delta)

1. **Conditional envelope pins** (`core/mcp_policy.py`): allow `executes_shell=true` /
   `mutates_target_repo=true` **iff** `approval_ref` validates against a digest-bound HITL
   approval; otherwise the existing hard refusal stands. Deny-by-default is preserved.
2. **Gated tool execution** (`adapters/mcp/`): `propose_patch` / `run_shell` consume a bound
   approval and perform the effect through a governed runner that snapshots before, applies
   the bounded change, emits a real receipt + `mcp_call_executed` event, and records a
   rollback artifact. Without a bound approval they continue to refuse (`mcp_call_denied`).
3. **Approval binding**: the approval is minted by the existing HITL lane (`builder-hitl`),
   not by the TUI or the MCP server. The server only *consumes* a validated approval, exactly
   as the CLI execution lane does; a missing, tampered, or stale approval refuses identically.

No new authority is minted inside Goose or the server. A cockpit- or Goose-driven mutation
writes the same artifacts as the CLI lane; only the recorded invocation surface differs.

## 4. The eight promotion gates (what closure evidence must show)

| Gate | Evidence required |
|---|---|
| **Docs** | This brief promoted to an operator doc; `docs/RUNTIME_PROMOTION.md` gains a state above `read_only_runtime_candidate`; the is/is-not and boundary tables updated in the same change as the code. |
| **Tests** | A mutating call **with** a valid approval applies a bounded change and emits a receipt; **without** approval refuses and mutates nothing; a tampered/stale approval refuses; the no-hidden-writes and no-hidden-shell tests invert into "writes/shell only through a validated approval." |
| **Command surface** | The approval-minting and execution surfaces stay the existing `builder-hitl` / `builder-mcp` commands; any new subcommand registered in the authority registry with a regenerated `docs/COMMAND_AUTHORITY.md`. |
| **Failure mode** | Fails closed: missing/invalid approval, digest mismatch, or a mid-write interruption leaves the target unchanged (or rolled back) and records a denial. |
| **Human approval boundary** | A digest-bound HITL approval is required before any mutation; the operator confirms against digests, not prose. |
| **Output artifact** | Each mutation emits a receipt + `mcp_call_executed` event + a rollback artifact, all hash-chained. |
| **Rollback path** | The pre-change snapshot + rollback artifact restore the target; the procedure is documented and tested. |
| **Verification path** | Named `pytest` targets plus the no-mutation-without-approval check; `builder-platform audit-docs` and `matrix` when docs/matrix change. |

## 5. Promotion state and matrix

The gated tools move from their current denied/refused posture toward
`hitl_runtime_candidate`, and only to `enabled` when all eight gates carry evidence. A new
`docs/RUNTIME_PROMOTION.md` state names the write/shell-behind-approval posture explicitly;
its completion-matrix row starts at design state and flips only on a closure audit, never on
this document. Docs and code land together or not at all.

## 6. Failure modes

| Failure | Behavior |
|---|---|
| Mutating call, no approval bound | Refusal (`mcp_call_denied`); nothing executes — the G3 path, unchanged |
| Approval missing/tampered/stale | Refusal with the validator's error; nothing scheduled |
| Interruption mid-write | Rollback artifact restores the target; a denial or failure is recorded; no silent retry |
| Approval valid but effect out of the approved bound | Refusal; the bound is part of what the approval commits to |

## 7. What this document does not do

It enables no write, no shell, no target mutation, and no Goose runtime write authority. It
records a promotion design and the closure evidence that a future, separately-reviewed change
must produce before any capability moves. Until then, the in-loop gate refuses, and that
refusal is the honest state.
