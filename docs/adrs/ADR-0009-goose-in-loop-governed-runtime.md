# ADR-0009: Goose In-Loop Governed Runtime

## Status

**Proposed — DESIGN_ONLY.** Nothing in this document promotes, enables, or implements any
capability. Acceptance authorizes *implementation of the read-only and refusal phases behind
ordinary review*, and *design of the write/shell phase behind the eight promotion gates* —
not activation of any runtime write or shell. The completion-matrix row this ADR anticipates
starts at `DESIGN_ONLY` and may only move on evidence (a closure audit), never on this
document. Operational verified count does not change on acceptance.

Extends [ADR-0002](ADR-0002-builder-convention-layer-over-codename-goose.md) (builder
convention layer over Goose) and composes with
[ADR-0008](ADR-0008-governed-deepagents-model-invocation-lane.md) (governed model-invocation
lane). ADR-0002's rule — wrap Goose, do not fork it, and preserve explicit authority and
evidence boundaries — is not reversed; it is made load-bearing at runtime.

## Context

builder-II governs Goose today by **amputation at the boundary**. `launch_readonly`
(`adapters/goose/goose_runtime_harness.py`) spawns `goose session --with-builtin ""`, takes
a preflight digest snapshot of every target file, and on close emits a no-mutation
postflight that fails on any change. The capability is removed rather than governed, and the
run happens in a suspended terminal that the operator console cannot observe. An operator who
wants Goose to perform real work must leave the governed lane.

Two facts from the code shape the decision:

1. **Goose is an external binary** (`shutil.which("goose")`), driven by recipes,
   `--with-builtin`, `GOOSE_MODE`, and env. There is no in-tree Goose source to patch, and
   recipes already declare `extensions:`. Goose is interposable without modifying it.
2. **The governed substrate already exists**: a hash-chained event ledger
   (`governance/ledger/event_ledger.py`), MCP policy/envelope/receipt validators with
   deny-by-default and shell/mutation pinned off (`core/mcp_policy.py`), a tool-invocation
   gateway, and the deepagents run lifecycle with checkpoints and receipts.

The Manifesto's **Third Door** names the failure this addresses: weak read-only theater on
one side, reckless automation on the other. A wrapper that can only refuse capability
delivers neither power nor a governance lesson once the operator's real need is to run work.
The governed path is not "never execute" — it is *execute through the same artifacts,
approvals, and receipts as the CLI lane*, with the approval moved in-flight.

## Decision

builder-II shall interpose on Goose through a **builder-II-owned governed MCP server** that
Goose loads as its only extension (paired with `--with-builtin ""`), rather than through
Goose's native builtins or any modification of Goose. Every tool call Goose issues passes
through this server, which runs the governed ceremony — envelope → policy check → (for
mutating classes) in-flight HITL gate → effect → receipt — and appends one hash-chained
event record per call. The governing rules:

1. **Interposition, not forking.** No Goose source is patched. Ledger emission, step
   checkpoints, and receipts live in builder-II code. This upholds ADR-0002.
2. **Deny by default.** Write, shell, target mutation, memory mutation, and external MCP
   remain denied. Read-only tools operate first; mutating tool classes are wired but refuse,
   composing the governed approval CLI, until a promotion moves them.
3. **The gate is in the tool, not the model runtime.** The approval boundary lives in the
   MCP tool handler under builder-II's control. `GOOSE_MODE=approve` is an additional prompt,
   not the boundary.
4. **Same artifacts, same receipts.** A Goose-driven effect writes the same envelope and
   receipt kinds, and the same event chain, as the CLI lane. The invocation surface is
   recorded; nothing else distinguishes them.
5. **Write/shell is a promotion.** Relaxing the `mcp_policy` envelope pins
   (`executes_shell`, `mutates_target_repo`) happens only behind a validated `approval_ref`,
   only via a new `RUNTIME_PROMOTION.md` state above `read_only_runtime_candidate`, only with
   the eight gates and a matrix flip, and only with docs and code landing together.

MCP transport is a hand-rolled, standard-library-only stdio JSON-RPC server; no runtime
dependency is added.

## Consequences

- The console can stream a live, hash-chained transcript of a Goose run by tailing the same
  event ledger the server writes — inside the observe-and-compose contract, with no dispatch
  authority in the TUI.
- The read-only lane gains real observability and a real refusal gate without crossing any
  boundary; the write/shell lane has a concrete, evidence-backed promotion path rather than
  an all-or-nothing amputation.
- Sequencing and file-level detail live in
  [`docs/plan/GOOSE_IN_LOOP_GOVERNED_RUNTIME.md`](../plan/GOOSE_IN_LOOP_GOVERNED_RUNTIME.md).
  The write/shell phase (G4) is designed only after the read-only and refusal phases (G1–G3)
  are battery-green and producing refusal receipts.

## Promotion gates (for the write/shell phase only)

The read-only server (G1), recipe interposition (G2), and refusing in-loop gate (G3) are
inside the current contract and need no promotion. The write/shell phase must, before any
capability moves, satisfy the eight promotion gates recorded in `docs/CAPABILITY_PROMOTION.md`
and `docs/RUNTIME_PROMOTION.md`, add a new runtime state above `read_only_runtime_candidate`,
carry no-hidden-writes and no-hidden-shell tests inverted into approval-gated form, and flip
its completion-matrix row only on a closure audit. This ADR does not grant that move.
