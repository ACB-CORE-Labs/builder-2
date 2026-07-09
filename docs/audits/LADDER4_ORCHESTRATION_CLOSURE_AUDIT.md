# Ladder 4 Closure Audit — Governed Obligation Delegation Flip (PR-8)

This audit records the evidence for, and the full pinned-site edit set of, the Ladder 4 matrix
flip: a new completion-matrix row `governed obligation delegation` lands at
`OPERATIONALLY_VERIFIED` (assurance `BOUNDED_EXECUTION_VERIFIED`), and
`operationally_verified_count` moves 18 → 19. Per the ratified plan
(`planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md`, risk map R2) this flip is tier C — evidence
first, operator-applied second: this document plus the accompanying diff **is** the edit set; the
flip is applied only by the operator merging it. Nothing in this PR — and nothing in the lane it
promotes — flips capability state by itself.

## Scope of the claim (read this before citing the row)

The verified claim is exactly: **the two Ladder 4 laws are enforced fail-closed and evidenced
end-to-end over the `protocol_fake` backend as CI truth.**

> Authority attenuates monotonically down the delegation tree; evidence accumulates monotonically
> up it. Obligations open down; digests seal up; speech is cheap; belief is expensive.

What this row does **not** claim:

- **Not the native backend.** `optional_deepagents` execution remains a separate, readiness-gated,
  two-key-acknowledged claim with no promoted execution; nothing in this flip covers it.
- **Not agent quality.** `OPERATIONALLY_VERIFIED` here means the governance physics hold — mints
  refuse, discharges classify, chains tamper-evidence — never that any agent's plan or output is
  good, and never "smart agents".
- **Not the legacy path.** `builder-deepagents run-plan` is a structural projection that runs no
  backend and verifies nothing; its outputs are not evidence for this row (the
  `deepagents runtime/subagents` row is reworded in this same PR to say exactly that).
- **Not `LIVE_*` assurance.** The row's assurance state is `BOUNDED_EXECUTION_VERIFIED`.

## What closed the gap (mechanism)

Ladder 4 (Forgejo PRs #38–#45; plan `planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md`) built the
lane across seven merged PRs (RFC, obligation kind, lane policy, registry/CLI wiring, seal +
runner enforcement + honesty fix, status/why board, unmocked E2E + tamper beat, B2.0 tree-profile
evaluator). The mechanism, end to end:

- **Law 1 — no speech without a ticket.** `builder_ii/orchestration_obligation.py` mints
  digest-stable obligation tickets: task (≤ 2000 chars), deny-list boundary, output contract,
  anti-dump file refs (no `content`/`body`/`text` keys anywhere, no value over 512 chars), a
  four-field budget partition, and a `parent_ref` bound (XOR) to the root seal or a parent
  obligation. `builder_ii/orchestration_lane_policy.py` binds each obligation kind to exactly one
  lane (totality validated) and refuses collisions with a named `LanePolicyViolation` — never
  "whichever adapter got invoked first".
- **The seal — one friction point.** `builder-deepagents approve-candidate` binds a flag-driven,
  digest-bound approval to the exact candidate digest; an obligation-bearing candidate seals its
  envelope (lane policy digest, root budget, allowed kinds × max counts, refused lanes, native
  ack) **inside the approval digest basis** — an unsealed envelope field would be a forgery
  channel. Sub-mints inside the envelope never re-prompt; anything outside it is an invalid mint.
- **Fail-closed mint enforcement.** `run-approved --obligation` refuses an obligation-bearing run
  against a legacy (non-envelope) approval with a named error; re-derives the lane policy and
  refuses drift; validates every obligation before writing any event; and enforces each mint
  against the sealed envelope with eight named refusal rules (`lane_policy_drift`,
  `lane_policy_collision`, `obligation_kind_not_authorized`, `obligation_kind_count_exhausted`,
  `parent_seal_mismatch`, `parent_obligation_unknown`, `budget_partition_exceeds_remaining`,
  `subagent_not_approved`), each refusal carrying the exact `violated_rule` **and** a
  `fixing_edit` — zero dead ends. Budget fits are component-wise ⊆ against the parent's remaining
  grant with minted siblings deducted (grants-not-loans; no refunds in v1). Widening is an invalid
  mint, refused the way a broken digest is refused.
- **Law 2 — no belief without discharge.** Each accepted obligation runs its **own** task (never
  the root task) and its discharge is classified `CONTRACT_SATISFIED` / `DISCHARGED_UNVERIFIED` /
  `CONTRACT_VIOLATED` / `BLOCKED` from the output contract and attached evidence only. The
  proposal-only deepagents lane attaches no downstream evidence, so an obligation that requires
  evidence classifies `DISCHARGED_UNVERIFIED` — speech recorded, belief withheld, never a
  fabricated success. `builder-orchestration status` / `why` re-derive belief fresh from the raw
  per-event files (never the frozen replay snapshot) and exit non-zero on anything not believed.
- **Honesty at the runtime seam (R3).** The legacy `run-plan` projection emits derived summaries
  ("no backend ran and no result was checked … legacy projection"), never asserted success.
- **Tamper evidence.** Every obligation lifecycle event is stamped with the obligation and
  briefing digests and hash-chained; the unmocked E2E forges a discharge state on disk and replay
  names both the forged node (self-digest mismatch) and the broken `previous_event_sha256` link at
  its successor.

## Evidence — the eight promotion gates

The full suite passes on the edited tree (battery results in the PR body). Per gate:

| # | Gate | Covering evidence |
|---|---|---|
| 1 | Docs | `docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md` (doctrine, PR-0), `docs/ORCHESTRATION_OBLIGATIONS.md` (operator surface), registry boundary text for every lane command in the generated `docs/COMMAND_AUTHORITY.md` |
| 2 | Tests | Unit/integration: `tests/test_orchestration_obligation.py` (anti-dump, ⊆, conservation, XOR, digest stability), `tests/test_orchestration_lane_policy.py` (totality, collision refusal, registry linkage), `tests/test_orchestration_delegation_run.py` (seal, N/N−1 legacy refusal, mint rules, discharge classification, two-key), `tests/test_orchestration_obligation_cli.py`, `tests/test_orchestration_status_why.py`; unmocked E2E: `tests/scenarios/test_full_obligation_delegation_lane.py` |
| 3 | Command surface | `builder-orchestration lane-policy / validate-lane-policy / mint-obligation / validate-obligation / status / why` and `builder-deepagents execution-candidate / approve-candidate / run-approved` all registered in `COMMAND_AUTHORITY_REGISTRY` (`validate_command_surfaces` covers the row's surfaces); table regenerated in this PR; operator-status parity auto-covered by `tests/test_operator_status.py` |
| 4 | Failure mode | Refused widening mint carries `violated_rule="budget_partition_exceeds_remaining"` + `fixing_edit` and a `BLOCKED` discharge (E2E); count-exhaustion refusal (`tests/test_orchestration_delegation_run.py`); anti-dump and invalid-mint rejections (`tests/test_orchestration_obligation.py`, CLI validate lanes) — every refusal is named and fix-carrying |
| 5 | HITL boundary | Exactly one root seal per tree: the digest-bound approval with the envelope inside its digest basis; sub-mints never re-prompt; the two-key `--native-backend-acknowledged` is required at seal time **and** re-checked at the spawn point for `optional_deepagents` (D7 pattern) |
| 6 | Output artifact | Obligation artifacts, `obligation_minted` / `obligation_mint_refused` / `obligation_consumed` (discharge-classified) events, run envelope, execution receipt, event ledger, replay report, evidence bundle — all digest-bound JSON |
| 7 | Rollback | The lane emits artifacts only; deleting the emitted output directory removes every trace. No target mutation exists in this lane — mutation obligations discharge exclusively through the already-promoted `hitl_patch` lane |
| 8 | Verification | B2.0 delegation-tree PASS artifact over a clean run bundle: `planning/evidence/ladder4-b2-delegation-tree-pass.json`, digest `61c9e46405594ac8f9a6d48f384b89492bc3cd3e047e62938b92bc6804757475` — 9/9 machine gates PASS, `capability_name` bound to this row, pinned in CI by `tests/test_ladder4_closure_evidence.py` |

**Gate 8 notes.** The PR-7 evaluator (`evaluate_delegation_tree_promotion_gates`) covers the nine
machine-checkable gates (seal validity, candidate↔seal binding, CI-truth backend, event-chain
integrity, mint attenuation, named refusals, discharge re-derivation, bundle validity, ledger↔
replay binding) and states in its own docstring that docs/tests/command-surface/rollback are
human gates — asserted by this audit, not by the artifact. The digest quoted in the PR-7 body was
generated pre-review and the artifact is path- and timestamp-dependent, so PR-8 regenerated the
bundle with the merged evaluator (whose subject digests bind real artifacts — the PR-7 review fix,
commit `907cce3`) and committed the evidence; the pin test keeps it schema-valid, PASS,
digest-intact (re-derived, not just shape-checked), and bound to this capability name on every CI
run. Fresh bundles are regenerated and re-evaluated on every CI run by
`tests/scenarios/test_promotion_gate_delegation_tree.py`.

## Audit findings reconciled in this PR (wording and registry text only)

An end-to-end audit of the lane against the plan's constitution was run while preparing this flip.
The enforcement code was found true to the two laws — no logic changes were needed or made. Three
honesty items are reconciled here:

1. **`approve-candidate` "typed prefix" theatre.** The command's docstring, its
   `command_authority.py` runtime-boundary text, and `docs/ORCHESTRATION_OBLIGATIONS.md` said "one
   typed prefix seals the whole envelope" — but the command has no interactive prompt; it is
   flag-driven (`--approval-actor` / `--approval-reason`). The seal itself is real (digest-bound,
   envelope inside the digest basis); the prompt ceremony was not. All three sites now describe
   the flag-driven reality, and the RFC carries an as-built note. Whether the command should
   *gain* the interactive typed-prefix ceremony (parity with `builder-hitl approve-patch` /
   `builder-setup apply`) is a behavior change on an authority surface — deliberately **not**
   bundled into this promotion; recorded as a follow-up decision for the operator.
2. **Stale `status`/`why` registration note.** `docs/ORCHESTRATION_OBLIGATIONS.md` still described
   the `STATE_SPEC_ONLY` placeholder gap as open with an intentionally-failing test; the registry
   records were in fact already promoted to `STATE_VALIDATION_ONLY` with live boundary text and a
   passing pin (`test_status_why_records_promoted_to_validation_only_with_live_cli`). The note now
   records the resolved state.
3. **`deepagents runtime/subagents` row named the legacy path as its surface.** The row's command
   surfaces listed `run-plan`; its blockers never named the trunk. It now names
   `execution-candidate → approve-candidate → run-approved` (plus `replay-run`) as the verified
   trunk and states that `run-plan` is a legacy structural projection whose outputs are not
   execution evidence — the scope restatement mandated by R2, not a second flip.

## Pin edit set authorized by this audit

- `builder_ii/platform_completion_audit.py` — new `governed obligation delegation` row (state,
  evidence files, command surfaces, tests, scope-honest blockers, `next_pr` "Ladder 4 complete
  (PR-8)"); `REQUIRED_CAPABILITIES` entry; `assurance_state_for_row` maps the row to
  `BOUNDED_EXECUTION_VERIFIED`; reworded `deepagents runtime/subagents` row.
- `tests/test_platform_completion_truth.py` — `operationally_verified_count` 18 → 19; new
  assurance pin; new scoped-state pin
  (`test_ladder4_obligation_delegation_flip_is_scoped_to_protocol_fake`).
- `scripts/b4_flip_assistant.py` — "governed obligation delegation" added to `FLIP_CAPABILITIES`
  (assurance + mirror checks; the assistant still never writes).
- `docs/PLATFORM_COMPLETION_AUDIT.md` — matrix table row, truth-state prose, flip paragraph,
  "Ladder 4 closure update (PR-8)" section.
- `builder_ii/command_authority.py` — `builder-deepagents approve-candidate` runtime-boundary
  wording only (no tier, mode, or effect-flag changes) + regenerated `docs/COMMAND_AUTHORITY.md`.
- `planning/evidence/ladder4-b2-delegation-tree-pass.json` (gate-8 evidence) +
  `tests/test_ladder4_closure_evidence.py` (its CI pin).
- `builder_ii/cli/deepagents_cli.py` (docstring), `builder_ii/deepagents_execution.py` (comment),
  `docs/ORCHESTRATION_OBLIGATIONS.md` (status + seal wording + registration note),
  `docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md` (as-built note) — honesty reconcile set.
- `docs/KNOWN_LIMITATIONS.md` — regenerated from the post-flip matrix via
  `uv run builder-platform known-limitations --output docs/KNOWN_LIMITATIONS.md` (never
  hand-edited).
- `docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md` — this document.

## Still not promoted (unchanged by this flip)

- The native `optional_deepagents` backend: readiness-gated, two-key-acknowledged, no promoted
  execution. Making it the operationally verified centerpiece is the explicitly deferred phase-2
  claim and needs its own eight-gate battery.
- Autonomous dispatch, coordinator models, backend-initiated mid-run mints, token-level budget
  metering, cross-obligation budget refunds, and a first-class consumption-receipt kind (phase-2
  deferrals per the RFC).
- Mutation authority: mutation obligations discharge only through the already-promoted
  `hitl_patch` lane; verification obligations only through the approved verification lane. No new
  model, tool, shell, Goose, MCP, source-write, git, or memory authority anywhere in this flip.
- Goose's lane is untouched.

## Next gate

Ladder 4 closes with the operator's merge of this PR. The promotion-shaped decisions that remain
on this lane, in the operator's hands: (a) whether `approve-candidate` gains the interactive
typed-prefix ceremony — an authority-surface behavior change, its own PR if wanted; (b) the
phase-2 native-backend claim over `optional_deepagents`, which requires a fresh eight-gate battery
under the readiness gate and two keys; (c) Ladders 5–9 sequencing per the post-beta mandate.
