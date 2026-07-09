# Governed Obligation Delegation — RFC (Ladder 4)

Status: **design-only RFC** (post-beta ladder item 4). This document captures ratified doctrine
and the object model for governed obligation delegation. **It implements nothing:** no
`orchestration_obligation` module, no `orchestration_lane_policy`, no CLI, no approval-schema
bump, no runtime change, and no completion-matrix flip ships with it. The matrix rows do not
move. Implementation is delegated across gated PRs (PR-1 … PR-8), each carrying the full gate
battery; the promotion flip is applied only by the **operator's merge of PR-8** (tier C — evidence
first, operator applies). The binding schema source is
`planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md`; where this RFC and that plan ever diverge, the
plan governs and this RFC is corrected.

## Purpose

The deepagents lane already has a real trunk — `execution-candidate` → `approve-candidate` (the
one seal) → `run-approved`. What it lacks is two things:

1. **Nothing forces a subagent step to exist as a governed unit before it runs.** A run can spawn
   work that was never scoped, boundaried, or budgeted.
2. **Nothing forces a result to be classified before it is believed.** The runtime today even
   *fabricates* success text (`builder_ii/deepagents_runtime.py:219` synthesizes
   `"Subagent {subagent} successfully completed planning task."`), which is exactly the
   fabricated-success pattern D5 banned in STRATUM.

Ladder 4 closes both gaps by making delegation **obligation-first**: no step runs without a
ticket, and no result becomes truth without a discharge. It is the governed-delegation promotion
that rides on the now-landed B2.0 promotion-gate evaluator
(`builder_ii/verification_promotion_gate.py`, `PROMOTION_EVIDENCE_KIND`, state `RECORDED_ONLY`).

This RFC changes no capability state. Promotion happens only through the eight gates with
end-to-end evidence, operator-applied, as always.

## The constitution (the two laws)

> **Authority attenuates monotonically down the delegation tree; evidence accumulates
> monotonically up it.**
>
> Operationally: *obligations open down; digests seal up; speech is cheap; belief is expensive.*

- **Law 1 — no speech without a ticket.** Nothing runs as a subagent step unless an **obligation**
  exists first: who must produce what artifact kind, under what boundary, citing which file-refs
  (never dumps), spending which budget partition, under which parent seal. No ticket → no run.
- **Law 2 — no belief without discharge.** A result may exist as bytes; the session treats it as
  true only when a **discharge** binds the obligation digest, satisfies the output contract, and
  attaches the required evidence refs. Missing evidence → `DISCHARGED_UNVERIFIED` (speech
  happened; belief did not). Consuming unverified speech is itself a ledgered event, visible
  forever.
- **Corollary (attenuation as ticket algebra):** a child obligation's capability set and budget
  must be ⊆ the parent's remaining grant. Widening is not a "policy violation narrative" — it is
  an **invalid mint**, refused the way a broken digest is refused.

**Vocabulary (five verbs, no new religion):** *seal* (the one operator approval that opens the
tree), *obligation/ticket* (the minted unit of delegated work), *discharge* (the classified
completion), *mint* (creating an obligation under an envelope).

## The trunk (grounding — verified against `main` 7bc61d2; do not trust memory)

- **Trunk:** `builder-deepagents execution-candidate` (`builder_ii/cli/deepagents_cli.py:555`) →
  `approve-candidate` (`:665`, the one seal) → `run-approved` (`:695`).
- **`run-plan` (`deepagents_cli.py:519`) is NOT the trunk** and must never be presented as it. It
  is legacy planning theatre; Ladder 4 does not build on it, and the closure audit (PR-8) rewords
  the existing `deepagents runtime/subagents` matrix-row blockers to name the trunk honestly.
- **Honesty defect in scope:** `builder_ii/deepagents_runtime.py:219` synthesizes an unconditional
  success sentence — asserted, not derived. Verified 2026-07-08: **no test pins this string**
  (`grep -rn "successfully completed" tests/` is empty), so the fix is a free move. Ladder 4
  replaces it with a summary **derived** from the discharge classification (see R3).
- **Spine kinds:** `builder_ii/deepagents_execution.py:18-27` — execution_candidate,
  execution_approval, run_envelope, event_record, event_ledger, replay_report, checkpoint,
  execution_receipt, evidence_bundle, backend_readiness_gate.
- **Envelope budgets:** `deepagents_execution.py:786-788` — `max_subagents=8, max_events=256,
  max_output_bytes=65536` (validated `>0`).
- **Approval functions:** `create_deepagents_execution_approval` (`:869`),
  `validate_deepagents_execution_approval` (`:1377`),
  `validate_deepagents_execution_approval_against_candidate` (`:1421`).
- **Root seal ceremony grammar:** `APPROVAL_CONFIRMATION_PREFIX_LENGTH = 4`
  (`builder_ii/hitl_patch_approval.py:68`) — one typed 4-char digest prefix, once, at the root.
- **Promotion evaluator this rides on:** `builder_ii/verification_promotion_gate.py` —
  `PROMOTION_EVIDENCE_KIND`, state `RECORDED_ONLY`; a PASS artifact "is input to an
  operator-applied matrix update — it never flips capability state itself."

## Object model (the schema — authoritative source is the plan doc)

The following is reproduced for doctrine capture. The binding schema is
`planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md § Object model`; implementers pin field lists
there, not here.

### Obligation — NEW kind `builder_ii.orchestration_obligation` (schema v1)

New module `builder_ii/orchestration_obligation.py`. Fields:

- `kind`, `schema_version: 1`
- `obligation_id` — `attach_digest` over canonical content
  (`builder_ii.config_schema.attach_digest`, digest key `obligation_id`)
- `lane` — one of the lane-policy lanes
- `obligation_kind` — `planning_step | interactive_ops | model_call | mutation | verification`
- `task` — non-empty string, **≤ 2000 chars**
- `boundary` — `{denied_actions: [str], refused_lanes: [str]}` (deny-list house style)
- `output_contract` — `{expected_kind: str, required_evidence_kinds: [str]}`
- `file_refs` — `[{path: str, sha256: str}]`; **anti-dump: reject any ref field value longer than
  512 chars and reject any `content`/`body`/`text` key anywhere in refs**
- `briefing_bytes` — int; must be ≤ the partition's `max_output_bytes`
- `budget_partition` — `{max_subagents, max_events, max_output_bytes, max_human_gates}` (all ≥ 0)
- `parent_ref` — `{seal_digest}` XOR `{obligation_digest}` (exactly one)
- `lane_policy_digest` — pins the policy in force
- `subagent_profile` — non-empty string
- standard governance block (`build_standard_governance`; `artifact_is_authority: false`)

### Root seal — EXTEND `builder_ii.deepagents_execution_approval` (minor schema bump)

New optional-at-parse, required-at-Ladder-4-runtime fields on the approval:

- `lane_policy_digest: str`
- `root_budget` — the four-field budget object
- `allowed_obligation_kinds` — `[{kind: str, max_count: int}]`
- `refused_lanes: [str]` — explicit negative space (macaroon-style caveats, not allowlist-only)
- `native_backend_acknowledged: bool` — **two-key rule:** REQUIRED `true` when the bound
  candidate's `backend_mode == "optional_deepagents"`; the runner refuses to spawn otherwise
  (mirrors the D7 execution-risk-ack pattern exactly)

The digest-prefix ceremony (`approve-candidate`) is **UNCHANGED** — one typed 4-char prefix, once,
at the root. The new fields go **inside** the digested content (they are what is being approved).

> **As-built note (Ladder 4 PR-8 closure audit):** the ceremony description above imported the
> `builder-hitl` grammar, but the implemented `builder-deepagents approve-candidate` was already —
> and remains — flag-driven and non-interactive (`--approval-actor`/`--approval-reason`; no
> `typer.prompt`, no typed-prefix transcription). The "UNCHANGED" clause is true in the sense that
> PR-4 did not change the command's ceremony; the seal's authority comes from the digest binding
> (the envelope fields live inside the approval digest basis), not from prompt theatre. Adding an
> interactive typed-prefix confirmation for ceremony parity with `builder-hitl approve-patch` /
> `builder-setup apply` would be a behavior change on an authority surface — deliberately left out
> of the PR-8 promotion and recorded as a possible follow-up in
> `docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md`.

### Dynamic mint (envelope semantics — no pre-committed ticket lists)

The seal pre-authorizes **kinds × max counts × budget** — never an exact ticket list. Obligations
mint at plan time or mid-run under that envelope. Every mint is validated fail-closed at mint
time: (1) `obligation_kind` is in `allowed_obligation_kinds` with count remaining; (2) budget
partition ≤ parent's remaining; (3) lane matches the lane policy for that kind; (4) anti-dump
passes; (5) human-gates ≤ remaining. Every mint emits a ledger event (`obligation_minted` /
`obligation_mint_refused`); refusals carry the exact violated rule and the fixing edit (zero dead
ends). Pre-committed lists would forbid runtime task discovery and castrate deepagents' native
planning strength.

### Discharge — classification on EXISTING results/events (no new kind)

States: `CONTRACT_SATISFIED` (result kind == `expected_kind` AND every `required_evidence_kinds`
entry attached as a digest ref) · `DISCHARGED_UNVERIFIED` (right shape, missing evidence —
consumable only as unverified; consumption eventized) · `CONTRACT_VIOLATED` (wrong shape — **not
consumable at all**) · `BLOCKED` (refused mint or boundary violation). Consumption = new event
types on the existing deepagents event ledger: `obligation_consumed {obligation_digest,
discharge_state}`. `PROPOSAL_ONLY` remains the result mode underneath; discharge classification is
orthogonal metadata layered on it.

### Lane policy — NEW kind `builder_ii.orchestration_lane_policy` (derived view)

New module `builder_ii/orchestration_lane_policy.py`, rendered from ONE small in-code table
(never a hand-maintained parallel registry):

| obligation_kind | lane | allowed discharge mechanisms |
| --- | --- | --- |
| planning_step | deepagents | `builder-deepagents run-approved` (protocol) |
| interactive_ops | goose | goose readonly session / proposal artifacts |
| model_call | gateway | model execution receipt |
| mutation | hitl_patch | `builder-hitl apply-patch` only |
| verification | verify | verification execution receipt |

CI totality proof: every `obligation_kind` maps to exactly one lane; every command-form discharge
mechanism named exists in `COMMAND_AUTHORITY_REGISTRY`. Collisions resolve by policy lookup, never
by "whichever adapter got invoked first."

## High-risk nuance maps (summary — full maps live in the plan doc)

- **R1 — approval schema bump is an authority-surface edit (PR-4, HIGH).** Extending the approval
  is widening what one human ceremony authorizes. One approval kind, minor-bumped — never a second
  "orchestration approval" (that would create the parallel authority stack this design exists to
  prevent). N / N−1 acceptance for one release cycle; absence of new fields = legacy semantics and
  the runner refuses obligation-bearing candidates against a legacy approval with a **named**
  error. New fields go inside the digest basis. Two-key native ack enforced in the runner, before
  `backend_for(...)`. Registry boundary text + regenerated table move in the same PR.
- **R2 — truth inflation at the flip (PR-8, HIGH).** The row goes `OPERATIONALLY_VERIFIED` /
  `BOUNDED_EXECUTION_VERIFIED`, and the scope sentence must say *what* was verified: obligation-
  governed delegation over the **protocol_fake backend as CI truth**; the native backend is a
  separate, two-key-gated, readiness-gated claim NOT covered by the flip. "Verified" means the
  laws are enforced fail-closed and evidenced end-to-end — it never means "agents are smart." The
  eight gates map to concrete evidence (docs, unit + unmocked scenario tests, command surface,
  named failure modes, one-seal HITL boundary, output artifacts, rollback = delete emitted
  artifacts, B2.0 tree-profile PASS). **The operator's merge is the flip.**
- **R3 — the honesty fix at `deepagents_runtime.py:219` (PR-4, doctrine-sensitive).** The summary
  must be **derived** from the discharge classification, never asserted (`CONTRACT_SATISFIED` →
  "discharged: produced <kind>, evidence attached"; `DISCHARGED_UNVERIFIED` → "speech recorded,
  belief withheld: missing <evidence kinds>"; etc.), and under `protocol_fake` must carry its
  provenance ("protocol-fake backend — structural truth only"). Add NEW pins asserting the
  truthful forms and the absence of unconditional success text.
- **R4 — budget conservation arithmetic (PR-1/PR-4, correctness trap).** Budgets are grants, not
  loans, v1: `Remaining(parent) = grant(parent) − Σ grant(minted children) − own recorded spend`;
  mint check is component-wise `child.budget_partition ≤ Remaining(parent)`, fail-closed at mint
  time. **No refunds in v1** — an unspent child grant does not return to the parent. Overspend at
  runtime = governance event + `BLOCKED`, never silent clamping. `max_human_gates` checked at
  plan/mint time against scheduled `request-human-gate` intents; root default 2.
- **R5 — contended-file serialization (all PRs, process risk).** Five files are append-contested
  platform-wide (`command_authority.py`, `artifact_index_records.py`,
  `artifact_chain_verification.py`, `platform_completion_audit.py`, the pinned truth tests). Only
  PR-3, PR-4 (registry text only), and PR-8 may touch them; one such PR in flight at a time;
  Sonnet-assigned PRs never touch them. All branches fresh from current `main` at dispatch time;
  same-wave agents use separate git worktrees.

## Phase-2 (explicitly deferred — do not build in Ladder 4)

Full command-registry lane totality (this RFC colors only the five obligation kinds); token-level
budget metering; a first-class consumption-receipt kind; budget refunds; making the native
deepagents backend the OV centerpiece. Documented here so nobody "helpfully" adds them untested.

## Non-goals (charter)

Ladder 4 does not govern the quality of any agent's thinking, nor model correctness inside an
allowed lane — evidence contracts shrink claim-laundering; nothing eliminates wrong plans. There
is **no autonomous dispatch** (the operator invokes) and **no coordinator model** that "decides
who does what." Goose's lane is untouched. Subagent output never becomes truth by default.

## What stays refused

Fabricated success text of any kind; a `--yes` path or any programmatic harvest of the approval
prefix outside the interactive prompt; a `native_backend_acknowledged` that defaults to true;
accepting a legacy approval for an obligation-bearing run "for convenience"; counting `run-plan`
outputs as delegation evidence; forking a second approval kind; hand-editing generated docs; and
any capability-state flip on docs alone. Promotion is the eight gates with evidence, operator-
applied.

## Implementation plan (ordered PRs, each fully gated)

Gate battery per PR: `uv run pytest -q` · `uv run ruff check builder_ii tests` · targeted mypy per
CLAUDE.md · `uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607` ·
`uv run python -m compileall -q builder_ii tests` · `uv run builder-platform audit-docs` ·
regenerate `docs/COMMAND_AUTHORITY.md` when the registry changed.

- **PR-0 — this RFC** (design-only; `docs/plan/` boundary).
- **PR-1 — obligation kind** (`orchestration_obligation.py` + test; new files only).
- **PR-2 — lane policy** (`orchestration_lane_policy.py` + test; new files only).
- **PR-3 — registry + CLI wiring** (serialized, contended files; registers both kinds; adds
  `builder-orchestration` subcommands; new operator doc `docs/ORCHESTRATION_OBLIGATIONS.md`).
- **PR-4 — seal + runner enforcement + honesty fix** (the trunk PR, serialized; R1, R3, R4).
- **PR-5 — `status` / `why` / replay extension** (reader board; owns all `status`/`why` output
  assertions).
- **PR-6 — unmocked scenario E2E + tamper beat** (asserts on artifacts and ledger events only).
- **PR-7 — B2.0 tree profile** (sibling evaluator; PASS artifact feeds the closure audit).
- **PR-8 — closure audit + flip prep** (serialized; **the operator's merge applies the flip**).

Sequencing is logical (dependencies + serialization), never chronological. Wave 1 = PR-0 ∥ PR-1 ∥
PR-2 (fully disjoint). Wave 2 = PR-3 alone. Wave 3 = PR-4 alone. Wave 4 = PR-5 ∥ PR-6 (decoupled)
with PR-7 authoring in overlap. Wave 5 = PR-7 finish → PR-8 (operator-merged).
