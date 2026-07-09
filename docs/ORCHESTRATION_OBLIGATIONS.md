# Governed Obligation Delegation (Ladder 4)

Status: **artifact-only** surface. This document describes two governed artifact kinds and the
`builder-orchestration` subcommands that create and validate them. Minting an obligation emits an
**inert** JSON artifact — it starts nothing. The sealed runner that enforces the budget envelope,
mints obligations dynamically, and classifies discharges is a later, separately gated stage
(Ladder 4 PR-4); it is **not** part of this surface. No completion-matrix row moves with these
kinds. See `docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md` for the doctrine and
`planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md` for the authoritative schema.

## The two laws

> Authority attenuates monotonically down the delegation tree; evidence accumulates monotonically
> up it. Obligations open down; digests seal up; speech is cheap; belief is expensive.

- **Law 1 — no speech without a ticket.** Nothing runs as a delegated step unless an **obligation**
  exists first: who must produce what artifact kind, under what boundary, citing which file-refs
  (never dumps), spending which budget partition, under which parent seal.
- **Law 2 — no belief without discharge.** A result is treated as true only when a discharge binds
  the obligation digest, satisfies the output contract, and attaches the required evidence.
  (Discharge classification is enforced by the PR-4 runner, not by this artifact surface.)

## Artifact kinds

### `builder_ii.orchestration_obligation` (schema v1)

The minted unit of delegated work. Its `obligation_id` is a SHA-256 digest over the canonical
content, so any tampering is detected on re-validation. Key fields: `lane`, `obligation_kind`
(`planning_step | interactive_ops | model_call | mutation | verification`), `task` (≤ 2000 chars),
`boundary` (deny-list), `output_contract` (`expected_kind` + `required_evidence_kinds`),
`file_refs` (path + sha256 citations — **anti-dump enforced**: no oversized values, no
`content`/`body`/`text` keys), `budget_partition` (`max_subagents`, `max_events`,
`max_output_bytes`, `max_human_gates`), `parent_ref` (exactly one of `seal_digest` **or**
`obligation_digest`), and `lane_policy_digest` (pins the policy in force).

### `builder_ii.orchestration_lane_policy` (schema v1, derived view)

Renders one fixed in-code table binding each `obligation_kind` to exactly one lane and its allowed
discharge mechanisms:

| obligation_kind | lane | allowed discharge mechanisms |
| --- | --- | --- |
| `planning_step` | `deepagents` | `builder-deepagents run-approved` (protocol) |
| `interactive_ops` | `goose` | goose readonly session / proposal artifacts |
| `model_call` | `gateway` | model execution receipt |
| `mutation` | `hitl_patch` | `builder-hitl apply-patch` only |
| `verification` | `verify` | verification execution receipt |

Every `obligation_kind` maps to exactly one lane (totality); resolving a kind under the wrong lane
raises a named `LanePolicyViolation`, never a silent "whichever adapter got invoked first". Each
**command-form** discharge mechanism is checked against `COMMAND_AUTHORITY_REGISTRY` at render and
validate time (read-only; the policy never edits the registry).

## CLI surface (`builder-orchestration`)

All four commands are Tier 1 (artifact-only / validation-only), require no approval, and never run,
spawn, call models, or mutate a target repository.

```bash
# Render the lane policy (deterministic; also checks the registry linkage)
builder-orchestration lane-policy --output lane-policy.json
builder-orchestration validate-lane-policy lane-policy.json

# Mint an obligation under a seal; the lane is derived from (and checked against) the policy
builder-orchestration mint-obligation \
    --obligation-kind planning_step \
    --task "Draft the tree-profile plan for module X" \
    --expected-kind builder_ii.deepagents_execution_receipt \
    --required-evidence builder_ii.verification_execution_receipt \
    --subagent-profile planner \
    --lane-policy lane-policy.json \
    --seal-digest <root-seal-digest> \
    --max-subagents 1 --max-events 8 --max-output-bytes 4096 --max-human-gates 1 \
    --output obligation.json
builder-orchestration validate-obligation obligation.json
```

`mint-obligation` refuses fail-closed on: a lane/kind mismatch, anti-dump or schema violations, a
`parent_ref` that is not exactly one of seal/obligation, or a `briefing_bytes` that exceeds
`max_output_bytes`. The emitted obligation is validated before it is written.

## What stays refused

No autonomous dispatch; no runtime; no model or shell execution; no target-repo writes; no budget
enforcement or discharge belief from this surface (that is the PR-4 sealed runner). Registration in
`artifact_index_records.py` and `artifact_chain_verification.py` makes these kinds *known and
validatable* — it does not grant them any execution authority. Promotion happens only through the
eight gates with end-to-end evidence, operator-applied.
