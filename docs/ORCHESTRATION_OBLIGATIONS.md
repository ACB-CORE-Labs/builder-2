# Governed Obligation Delegation (Ladder 4)

Status: **governed, not yet promoted.** Two artifact kinds (`builder-orchestration`) plus the sealed
runner on `builder-deepagents run-approved --obligation` (PR-4). Minting an obligation still emits an
**inert** JSON artifact — it starts nothing. The runner enforces every mint against the sealed
envelope and classifies each discharge, but it does so **over the `protocol_fake` backend as CI
truth**; the native backend is a separate, two-key-gated claim that this surface does **not** cover.
**No completion-matrix row moves yet** — the flip to `OPERATIONALLY_VERIFIED` is a later, evidence-
backed, operator-applied step (Ladder 4 PR-8). See `docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md` for
the doctrine and `planning/LADDER4_OBLIGATION_DELEGATION_PLAN.md` for the authoritative schema.

## The two laws

> Authority attenuates monotonically down the delegation tree; evidence accumulates monotonically
> up it. Obligations open down; digests seal up; speech is cheap; belief is expensive.

- **Law 1 — no speech without a ticket.** Nothing runs as a delegated step unless an **obligation**
  exists first: who must produce what artifact kind, under what boundary, citing which file-refs
  (never dumps), spending which budget partition, under which parent seal.
- **Law 2 — no belief without discharge.** A result is treated as true only when a discharge binds
  the obligation digest, satisfies the output contract, and attaches the required evidence. Discharge
  classification is enforced by the sealed runner (see below): the proposal-only deepagents lane
  attaches no downstream evidence, so an obligation that requires evidence classifies
  `DISCHARGED_UNVERIFIED` — speech recorded, belief withheld — never a fabricated success.

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

## The sealed runner (`builder-deepagents run-approved --obligation`)

The root **seal** is the existing `builder_ii.deepagents_execution_approval` — minor-bumped, not
forked — so the single typed digest-prefix ceremony now also seals an **obligation envelope**:
`lane_policy_digest`, a four-field `root_budget`, `allowed_obligation_kinds` (kind × max count),
`refused_lanes`, and `native_backend_acknowledged`. The envelope fields live **inside the approval
digest basis** (an unsealed envelope field would be a forgery channel). Legacy candidates/approvals
without the envelope stay valid (N/N-1); an obligation-bearing run against a legacy approval is
refused with a named error.

Seal the candidate's declared envelope, then run:

```bash
builder-deepagents execution-candidate --work-plan plan.json --output-root runs/ \
    --lane-policy lane-policy.json --allowed-obligation-kind planning_step:3 \
    --refused-lane goose --output candidate.json
builder-deepagents approve-candidate --candidate candidate.json \
    --approval-actor "Op" --approval-reason "seal the envelope" --output approval.json
builder-deepagents run-approved --candidate candidate.json --approval approval.json \
    --output-dir runs/obl --obligation obligation-0.json --obligation obligation-1.json
```

Before any subagent runs, the runner enforces **every** mint against the sealed envelope,
fail-closed (R4 grants-not-loans; no refunds in v1): lane policy still current, obligation kind
authorized with count remaining, `budget_partition` fits component-wise inside the parent's
remaining grant, `subagent_profile` approved, and `parent_ref` bound to the seal (or an already
accepted parent). Each accepted mint emits `obligation_minted`; each refusal emits
`obligation_mint_refused` carrying the exact `violated_rule` **and** a `fixing_edit` (zero dead
ends). Each subagent then runs its **own** obligation task (not the root task), and the discharge is
classified `CONTRACT_SATISFIED` / `DISCHARGED_UNVERIFIED` / `CONTRACT_VIOLATED` / `BLOCKED` and
recorded in an `obligation_consumed` event stamped with the obligation and briefing digests. The
run summary carries the discharge tally; the whole event chain replays deterministically.

**Two-key native ack.** For `--backend-mode optional_deepagents`, the seal additionally requires
`--native-backend-acknowledged` (the D7 second key); without it the seal is refused and the runner
will not spawn. `protocol_fake` — the CI-truth backend — needs no ack and produces structural
proposals only.

## What stays refused

No autonomous dispatch; no native deepagents construction, models, tools, shell, Goose, MCP,
source writes, git mutation, or hidden memory. The deepagents lane is proposal-only: it attaches no
downstream evidence, so evidence for `mutation`/`verification` obligations must come from the
already-promoted `hitl_patch` / `verify` lanes — never from a fabricated success here. Registration
and runner enforcement make these kinds *known, validatable, and bounded* — they do **not** promote
the capability. The matrix flip happens only through the eight gates with end-to-end evidence over
the `protocol_fake` backend, operator-applied (Ladder 4 PR-8); backend-initiated mid-run mints and
cross-obligation budget refunds are explicit phase-2 deferrals.
