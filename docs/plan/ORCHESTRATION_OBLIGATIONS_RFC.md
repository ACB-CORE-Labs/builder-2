# Orchestration Obligations RFC

## Constitution

> **Authority attenuates monotonically down the delegation tree; evidence accumulates monotonically up it.**
>
> Operationally: *obligations open down; digests seal up; speech is cheap; belief is expensive.*

- **Law 1 — no speech without a ticket.** Nothing runs as a subagent step unless an **obligation** exists first: who must produce what artifact kind, under what boundary, citing which file-refs (never dumps), spending which budget partition, under which parent seal. No ticket → no run.
- **Law 2 — no belief without discharge.** A result may exist as bytes; the session treats it as true only when a **discharge** binds the obligation digest, satisfies the output contract, and attaches the required evidence refs. Missing evidence → `DISCHARGED_UNVERIFIED` (speech happened; belief did not). Consuming unverified speech is itself a ledgered event, visible forever.
- **Corollary (attenuation as ticket algebra):** a child obligation's capability set and budget must be ⊆ the parent's remaining grant. Widening is not a "policy violation narrative" — it is an **invalid mint**, refused the way a broken digest is refused.

## Trunk (candidate -> seal -> run-approved)

The trunk CLI execution path is strictly `execution-candidate` -> `approve-candidate` -> `run-approved`.
- Legacy `run-plan` (`builder_ii/cli/deepagents_cli.py:519`) is NOT the trunk and must never be presented as it. The correct path is `execution-candidate` (`:554`), `approve-candidate` (`:664`), and `run-approved` (`:695`).
- **Honesty Defect:** At `builder_ii/adapters/deepagents/deepagents_runtime.py:219`, there is an honesty defect where it synthesizes `"Subagent {subagent} successfully completed planning task."` — a fabricated success text. This must be replaced with derived, never asserted summaries based on discharge classification.

## Object Model

### Obligation — NEW kind `builder_ii.orchestration_obligation` (schema v1)

New module `builder_ii/core/orchestration_obligation.py`. Fields:

- `kind`, `schema_version: 1`
- `obligation_id` — attach_digest over canonical content (use `builder_ii.config_schema.attach_digest`)
- `lane` — one of the lane-policy lanes (see below)
- `obligation_kind` — `planning_step | interactive_ops | model_call | mutation | verification`
- `task` — non-empty string, **≤ 2000 chars**
- `boundary` — `{denied_actions: [str], refused_lanes: [str]}` (deny-list house style)
- `output_contract` — `{expected_kind: str, required_evidence_kinds: [str]}`
- `file_refs` — `[{path: str, sha256: str}]`; **anti-dump validation: reject any ref field value longer than 512 chars and reject any `content`/`body`/`text` key anywhere in refs**
- `briefing_bytes` — int, recorded actual serialized briefing size; must be ≤ the partition's `max_output_bytes`
- `budget_partition` — `{max_subagents: int, max_events: int, max_output_bytes: int, max_human_gates: int}` (all ≥ 0; see R4 accounting semantics)
- `parent_ref` — `{seal_digest: str}` XOR `{obligation_digest: str}` (exactly one)
- `lane_policy_digest` — pins the policy in force
- `subagent_profile` — non-empty string
- standard governance block (`build_standard_governance` house pattern; `artifact_is_authority: false`)

### Root seal — EXTEND `builder_ii.deepagents_execution_approval` (minor schema bump)

New optional-at-parse, required-at-Ladder-4-runtime fields on the approval:

- `lane_policy_digest: str`
- `root_budget` — the same four-field budget object
- `allowed_obligation_kinds` — `[{kind: str, max_count: int}]`
- `refused_lanes: [str]` — explicit negative space (macaroon-style caveats, not allowlist-only)
- `native_backend_acknowledged: bool` — **two-key rule:** REQUIRED `true` when the bound candidate's `backend_mode == "optional_deepagents"`; the runner refuses to spawn otherwise (mirrors the D7 execution-risk-ack pattern exactly)

The digest-prefix ceremony (`approve-candidate`) is UNCHANGED — one typed 4-char prefix, once, at the root.

### Dynamic mint (the envelope semantics)

The seal pre-authorizes **kinds × max counts × budget** — never an exact ticket list. Obligations mint at plan time or mid-run under that envelope. Every mint is validated fail-closed at mint time: (1) `obligation_kind` is in `allowed_obligation_kinds` with count remaining; (2) budget partition ≤ parent's remaining; (3) lane matches the lane policy for that kind; (4) anti-dump passes; (5) human-gates ≤ remaining. Every mint emits a ledger event (`obligation_minted` / `obligation_mint_refused`); refusals carry the exact violated rule and the fixing edit.

### Discharge — classification on EXISTING results/events (no new kind)

States: `CONTRACT_SATISFIED` (result kind == `expected_kind` AND every `required_evidence_kinds` entry attached as a digest ref) · `DISCHARGED_UNVERIFIED` (right shape, missing evidence — consumable only as unverified; consumption eventized) · `CONTRACT_VIOLATED` (wrong shape — **not consumable at all**) · `BLOCKED` (refused mint or boundary violation). Consumption = new event types on the existing deepagents event ledger: `obligation_consumed {obligation_digest, discharge_state}`. `PROPOSAL_ONLY` remains the result mode underneath; discharge classification is orthogonal metadata layered on it.

### Lane policy — NEW kind `builder_ii.orchestration_lane_policy` (derived view)

New module `builder_ii/core/orchestration_lane_policy.py`. Rendered from ONE small in-code table:

| obligation_kind | lane | allowed discharge mechanisms |
| --- | --- | --- |
| planning_step | deepagents | `builder-deepagents run-approved` (protocol) |
| interactive_ops | goose | goose readonly session / proposal artifacts |
| model_call | gateway | model execution receipt |
| mutation | hitl_patch | `builder-hitl apply-patch` only |
| verification | verify | verification execution receipt |

## Nuance Maps (R1 - R5) Summarized

- **R1: Approval schema bump:** The `deepagents_execution_approval` schema is minor-bumped to include lane policy, budget, and obligation envelope. We do NOT fork a second approval kind. Legacy approvals degrade safely, and the seal remains the only friction point in the tree.
- **R2: Truth inflation at the flip:** The promotion flip for obligation delegation must clearly specify what was verified (the `protocol_fake` backend). Native backend is a separate claim. Hand-editing `KNOWN_LIMITATIONS.md` is forbidden; matrix row changes and 8-gate evidence are strictly required.
- **R3: Honesty fix:** The fabricated success text in `deepagents_runtime.py:219` must be removed. Summaries must be derived from the discharge classification (e.g., `CONTRACT_SATISFIED` vs `DISCHARGED_UNVERIFIED`) and explicitly label provenance for `protocol_fake`.
- **R4: Budget conservation arithmetic:** Budgets are grants. `Remaining(parent) = grant(parent) - minted children - recorded spend`. Checks occur fail-closed at mint time component-wise. Unspent child grants do not return to the parent in v1. Overspending is a governance event resulting in a `BLOCKED` discharge.
- **R5: Contended-file serialization:** Only designated PRs may touch heavily contended files (`command_authority.py`, `artifact_index_records.py`, `artifact_chain_verification.py`, `platform_completion_audit.py`, pinned truth tests) to prevent collision.

## Phase-2 Deferrals

- Full command-registry lane totality.
- Token-level budget metering.
- First-class consumption receipt kind.
- Making the native deepagents backend the OV centerpiece.
- Budget refunds (unspent child grants do not return to the parent).

## Non-goals

Does not govern the quality of any agent's thinking, nor model correctness inside an allowed lane (evidence contracts shrink claim-laundering; nothing eliminates wrong plans). No autonomous dispatch — the operator invokes. No coordinator model that "decides who does what." Goose's lane untouched. Subagent output never becomes truth by default.
