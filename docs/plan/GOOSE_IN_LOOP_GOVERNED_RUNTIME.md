# Goose In-Loop Governed Runtime — plan for sign-off

> **Status: DESIGN_ONLY.** Nothing in this document implements, enables, or promotes any
> capability. It records a direction and a file-level sequence for future work. The one
> phase that would cross a non-authority boundary (G4, write/shell) is design-gated and may
> only move on evidence through the eight promotion gates and a completion-matrix flip —
> never on this document alone. Operational verified count (OV) does not change on
> acceptance of this plan.

Companion records: [`ADR-0009`](../adrs/ADR-0009-goose-in-loop-governed-runtime.md) (the
directional decision, Proposed), [`docs/plan/STRATUM_ORCHESTRATION_COCKPIT.md`](STRATUM_ORCHESTRATION_COCKPIT.md)
(the cockpit staging this plan's TUI lane builds on), and the existing seam RFCs
[`GOOSE_DEEPAGENTS_MCP_SEAM.md`](GOOSE_DEEPAGENTS_MCP_SEAM.md),
[`MCP_POLICY_ARTIFACT_RFC.md`](MCP_POLICY_ARTIFACT_RFC.md),
[`MCP_TOOL_INVENTORY_RFC.md`](MCP_TOOL_INVENTORY_RFC.md).

## 1. Problem

builder-II governs Goose today by **amputation at the boundary**:
`GooseRuntimeHarness.launch_readonly` spawns `goose session --with-builtin ""` (no
builtins, so no developer/shell), snapshots every target file's digest before launch, and
on close emits a no-mutation postflight that fails if any target file moved. Safety comes
from removing capability, and the run itself happens out in a suspended terminal — invisible
to the operator console. This is honest but inert: an operator who wants Goose to *do* work
must leave the governed lane entirely.

The frontier operator experience is the mirror image: a live run is the centerpiece —
watch it work, drill in, review its diffs, steer it — but the run just happens, ungoverned.
builder-II has the opposite: masterful governance, an invisible run.

This plan moves the model from **governance-at-the-boundary** (safety by read-only
amputation) toward **governance-in-the-loop** (safety by construction, via an in-flight
approval gate and digest-bound receipts on every effect), and makes the governed run
legible and live inside STRATUM. Write and shell stay denied by default; they are not
unlocked by this document.

## 2. Architecture correction (grounded in the code)

An earlier framing proposed "narrow, rebase-able patches to Goose" for ledger and
checkpoint emission. Reading the code rules that out and replaces it with something
cleaner:

- Goose is an **external binary**, located via `shutil.which("goose")`
  (`adapters/goose/goose_launcher.py`) and driven as a subprocess. There is no Goose source
  in-tree; patches to a third-party binary are neither rebase-able nor consistent with
  ADR-0002's "wrap, do not fork Goose."
- Goose is fully **interposable without patching it**: recipes (`--recipe`), builtins
  (`--with-builtin`), `GOOSE_MODE`, and env. Recipes already declare `extensions:`
  (`recipes/core-platform.yaml`, `recipes/subrecipes/*.yaml`) — Goose's MCP-extension
  mechanism is an existing pattern here.

**Decision:** the interposition surface is a **builder-II-owned governed MCP server that
Goose loads as its only extension**, paired with `--with-builtin ""`. Every tool call Goose
makes flows through our server, which runs the governed ceremony (envelope → gate → effect →
receipt) and appends a hash-chained event record. Ledger emission, step checkpoints, and
receipts live in code we own, version, and test — not in Goose. The in-loop approval gate
lives inside the MCP tool handler, a boundary we control; Goose's own `GOOSE_MODE=approve`
is a belt-and-suspenders prompt, never the governance boundary.

**MCP transport (locked):** a hand-rolled, standard-library-only stdio JSON-RPC server
(`initialize`, `tools/list`, `tools/call`). No new runtime dependency enters the locked
universe; the surface stays small and fully tested. The official MCP SDK is not adopted
now and would itself require dependency governance before use.

## 3. Substrate reused (this plan composes; it does not rebuild)

| Piece | Location | Role |
|---|---|---|
| Hash-chained event ledger | `governance/ledger/event_ledger.py` (`create_event_record`, `replay_events`, `validate_event_chain_integrity`, `previous_event_ref`) | Transcript source (TUI) **and** in-loop receipt chain |
| MCP policy/envelope/receipt validators | `core/mcp_policy.py` (deny-by-default; `executes_shell`/`mutates_target_repo` pinned false) | Governed-call schema; stays read-only — G4 does not relax these pins, it delegates to the governed apply lane |
| Tool invocation gateway | `core/tool_invocation_gateway.execute_tool_envelope`, `builder-mcp call` | Execution primitive the MCP server wraps |
| deepagents run lifecycle | `adapters/deepagents/deepagents_execution.py` (`deepagents_run_envelope`, `deepagents_checkpoint`, `deepagents_execution_receipt`, `deepagents_evidence_bundle`; statuses `COMPLETED`/`CHECKPOINTED`/`FAILED`; `DeepAgentsBackend.run_subagent`) | Cockpit roster + subagent tree source; `run_subagent` is the subagent-with-subagents recursion point |
| Goose read-only harness | `adapters/goose/goose_runtime_harness.py` (preflight digest snapshot + `no_mutation_postflight`) | Baseline evidence the read-only phases must preserve |

## 4. Two lanes and the phase ladder

- **Lane G (Goose in-loop):** G0 design record → G1 governed MCP server (read-only tools) →
  G2 recipe interposition + governed launch → G3 in-loop HITL gate on mutating tool classes
  (wired, but denied by default so it always refuses) → 〔promotion〕 G4 write/shell unlock.
- **Lane T (TUI streaming):** T2a live ledger transcript widget → T2b run roster + cockpit
  (Cockpit Stage 1) → T3 live subagent tree → T4 HITL inline diff + fully-bound compose →
  T1 verb-stage-machine reframe (last, once the pattern is proven).

**Convergence:** T2a tails the same `event_record` chain that G1's MCP server writes. Once
G1 and G2 land, STRATUM's center panel streams a live Goose run transcript with no extra
plumbing. Lane G and Lane T start in parallel worktrees off PR0.

## 5. File-level sequence (each a battery-green PR)

Legend: created ⁺ / modified ~. Boundary = whether the PR stays inside the current
observe-and-compose contract.

| PR | Title | Files | Artifact / validator | Proof | Boundary |
|---|---|---|---|---|---|
| **PR0** | Design record (this) | ⁺`docs/plan/GOOSE_IN_LOOP_GOVERNED_RUNTIME.md` ⁺`docs/adrs/ADR-0009-*.md` ~`docs/ROADMAP.md` | — | `builder-platform audit-docs` passes; docs-truth enforcement test passes | inside |
| **G1** | Governed MCP server, read-only tools | ⁺`adapters/mcp/server.py` ⁺`adapters/mcp/tools.py` ~`cli/mcp_cli.py` (`serve`) | `mcp_call_receipt` + `event_record`; `validate_mcp_receipt`, `validate_event_chain_integrity` | in-process test: read tool call → receipt validates, ledger chain intact, `executes_shell` stays false, no mutation | inside |
| **G2** | Recipe interposition + governed launch | ⁺`recipes/governed-readonly.yaml` ~`adapters/goose/goose_runtime_harness.py` (`launch_governed`) | reuses launch/close/postflight receipts | launch test: argv carries our extension + `--with-builtin ""`; `no_mutation_postflight` passes; verify-by-experiment that Goose loads a stdio MCP extension | inside |
| **G1b** | Real read-only tools on the governed surface | ⁺`core/readonly_repo_tools.py` ~`core/tool_invocation_gateway.py` (allowlist + one dispatch) ~`adapters/mcp/governed_call.py` (specs, per-tool output cap) ~`adapters/mcp/server.py` (`target_root`) ~`recipes/governed-readonly.yaml` | `mcp_call_receipt` + `event_record`; denied receipt on a jail refusal | `tests/test_readonly_repo_tools.py` (jail: absolute, `..`, `.git`/`.builder`, symlink out of tree, symlink into `.git`; bounds); `tests/scenarios/test_governed_mcp_readonly_session.py` (list→grep→read→refused-escape on one replayable chain; tree digest unchanged) | inside |
| **G2b** | Reachable entry point + one chain per run | ~`cli/goose_cli.py` (`start-governed`) ~`governance/authority/authority_registry.py` ⁺`governance/ledger/session_ledger.py` ~`adapters/goose/goose_runtime_harness.py` (lifecycle events) ~`adapters/mcp/governed_call.py` ~`adapters/mcp/governed_apply.py` (share the appender) | `event_record` chain; `validate_event_record`, `replay_events` | `tests/test_goose_cli_start_governed.py`: fail-closed before spawn on missing/unreadable/non-read-only manifest and on authority denial; argv carries the governed recipe + `--with-builtin ""`; start/close events chain from sequence 1 and replay valid | inside |
| **G3** | In-loop HITL gate (mutating tools refuse) | ~`adapters/mcp/tools.py` ~`governance/hitl/hitl_command_execution.py` (wire) | `hitl_execution_request` + refusal `mcp_call_receipt` | test: a write/shell tool call emits a HITL request and a refusal receipt and never mutates the target; denied-action test | inside (refusal path only) |
| **G4** | In-loop governed patch apply (deny-by-default candidate) | ⁺`adapters/mcp/governed_apply.py` ~`adapters/mcp/server.py` (routes `propose_patch`) | delegates to `apply_hitl_patch`; no schema relax, no new write primitive | fail-closed tests; deny-by-default (flag + digest-bound approval); no matrix/OV flip | **implemented; closure audit to `enabled` is the operator step** |
| **T2a** | Live ledger transcript widget | ⁺`tui/widgets/transcript.py` ⁺`tui/projections/run_transcript.py` | reads `event_record` chain; honest empty state | `tests/scenarios/test_tui_exploration.py` tails a fixture ledger; digest-literal ban stays green | inside |
| **T2b** | Run roster + cockpit (Stage 1) | ⁺`tui/projections/runs.py` ~`tui/widgets/stratum.py` (`RUN_COCKPIT`) ~`tui/app.py` (binding) | projects deepagents `run_envelope`/status | scenario: roster renders fixture runs; Stop/Resume/Start compose argv only (no-dispatch pin) | inside |
| **T3** | Live subagent tree | ⁺`tui/projections/subagent_tree.py` ~`tui/widgets/stratum.py` | projects `run_envelope` + subagent `execution_receipt` + `checkpoint` | scenario vs fixture multi-subagent run | inside |
| **T4** | HITL inline diff + bound compose | ⁺`tui/widgets/hitl_diff.py` ~`tui/projections/hitl_compose.py` ~`tui/app.py` (drop "HITL diff viewer" from unimplemented surfaces) | reads `hitl_patch_proposal` | closes audit C2: `--proposal`/`--output` + digest present when path known; symmetric-truth pin updated same PR | inside |
| **T1** | Verb-stage-machine reframe | ~`tui/widgets/stratum.py` ~`tui/app.py` | PREPARE→PLAN→APPROVE→EXECUTE→VERIFY→PROMOTE axis | every stage reachable via the semantic driver; all prior honesty pins stay green | inside |

## 6. Governance ladder and the promotion boundary

Lane T (T1–T4) and Goose phases G1–G3 stay inside the current observe-and-compose contract:
ordinary reviewable feature work, no promotion decision, OV unchanged.

**G4 crosses the four load-bearing non-authority boundaries** recorded in
`docs/ROADMAP.md` (no autonomous source writes; no shell execution as an agent capability;
no Goose runtime activation from manifests; no memory mutation). It requires a new
`docs/RUNTIME_PROMOTION.md` state above `read_only_runtime_candidate`, its own gate battery
(the existing no-hidden-writes and no-hidden-shell tests invert into "writes and shell only
through a validated approval"), a completion-matrix flip on closure evidence, and docs and
code landing together. G4 is a promotion, not a sprint — and G1–G3's in-loop refusal gate,
producing real receipts, is the evidence that would earn it. G4 is briefed only after G1–G3
are battery-green (locked decision).

**Implemented 2026-07-23 (operator sign-off) via delegation — not a new state or a schema
relaxation.** Reading the code showed builder-II already carries a governed source-write lane
(`apply_hitl_patch`, `hitl_runtime_candidate`), so the in-loop gate routes a validated
`propose_patch` to it, deny-by-default behind `BUILDER_MCP_GOVERNED_APPLY` and a digest-bound
approval. The completion matrix is not flipped (OV unchanged); the closure audit that would move it to `enabled` is the operator step. Full detail: the G4 brief §0.

## 7. Proof discipline

Every PR names a pinned assertion, not "tests pass": ledger honesty via
`validate_event_chain_integrity` and `validate_event_record`; no mutation via
`no_mutation_postflight`; TUI honesty via the digest-shaped-literal ban, the symmetric-truth
pin in `tests/test_stratum_tui.py`, the no-TTY-scraping ban, and `run_tui` return-code
propagation. Each PR runs `bash scripts/ci.sh` before push, in its own worktree.

## 8. What this plan does not do

This plan does not enable memory mutation, deepagents construction, shell execution, model
calls, source mutation, MCP connection to external servers, MCP tool execution against a
target, target repo mutation, execution candidate activation, or Goose runtime write/shell
authority. It records a sequence; each step carries its own review, and the one step that
would cross a boundary carries the eight gates before any capability moves.
