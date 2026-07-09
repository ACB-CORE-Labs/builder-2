# Ladder 4 — Governed Obligation Delegation: Implementation Plan

**Status:** RATIFIED plan, ready for dispatch (2026-07-08). Design synthesized adversarially across
three models (Fable 5 constitution + external review trunk/vocabulary + amendments), ratified by
the operator. Implementation is delegated to Opus 4.8 / Sonnet 5 agents by the operator; each PR
section below is a self-contained briefing.

**Constitution (the two laws):**

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

**Vocabulary:** *seal* (the one operator approval that opens the tree), *obligation/ticket* (the
minted unit of delegated work), *discharge* (the classified completion), *mint* (creating an
obligation under an envelope). Operators keep the five verbs; no new religion.

## Non-goals (charter — copy into the RFC verbatim)

Does not govern the quality of any agent's thinking, nor model correctness inside an allowed
lane (evidence contracts shrink claim-laundering; nothing eliminates wrong plans). No autonomous
dispatch — the operator invokes. No coordinator model that "decides who does what." Goose's lane
untouched. Subagent output never becomes truth by default. Phase-2 (explicitly deferred): full
command-registry lane totality, token-level budget metering, first-class consumption receipt
kind, making the native deepagents backend the OV centerpiece.

**Never cut:** ⊆ checks at mint; anti-dump briefing validation; three-state discharge;
the `deepagents_runtime.py:219` honesty fix; the tamper beat; operator-applied flip.
**Cut if compressed:** `status` board polish, the recording segment, replay-extension depth.

## Grounding facts (verified against main `686bffc` — do NOT rediscover; do NOT trust memory)

- Trunk CLI exists: `builder-deepagents execution-candidate` (`builder_ii/cli/deepagents_cli.py:554`),
  `approve-candidate` (`:664`), `run-approved` (`:695`). Legacy `run-plan` (`:519`) is NOT the
  trunk and must never be presented as it.
- Spine kinds: `builder_ii/deepagents_execution.py:18-27` — execution_candidate, execution_approval,
  run_envelope, event_record, event_ledger, replay_report, checkpoint, execution_receipt,
  evidence_bundle, backend_readiness_gate.
- Budgets: `deepagents_execution.py:786-788` — `max_subagents=8, max_events=256,
  max_output_bytes=65536` (validated >0 at `:798`).
- Backends: `PROTOCOL_FAKE_BACKEND` (`:36`), `OPTIONAL_DEEPAGENTS_BACKEND` (`:539`);
  `backend_for(mode, readiness_gate)` (`:197`).
- Approval functions: `create_deepagents_execution_approval` (`:869`),
  `validate_deepagents_execution_approval` (`:1377`),
  `validate_deepagents_execution_approval_against_candidate` (`:1421`);
  evidence bundle create/validate (`:1216`/`:1765`).
- **Honesty defect in scope:** `builder_ii/deepagents_runtime.py:219` synthesizes
  `"Subagent {subagent} successfully completed planning task."` — fabricated success text.
  Verified 2026-07-08: **no test pins this string** (`grep -rn "successfully completed" tests/`
  is empty), so the fix has no pinned-test blast radius.
- Briefing precursor: `deepagents_work_artifacts.py:283 create_deepagents_subagent_assignment`
  (target/task/subagent_profile/work_plan_ref; `result_mode: "PROPOSAL_ONLY"`).
- Policy house style: `deepagents_policy.py` — `DEEPAGENTS_POLICY_KIND`, deny-lists
  (`_DENIED_ACTIONS` includes `invoke_subagents`, `execute_shell`, `call_models`, …).
- B2.0 evaluator: `builder_ii/verification_promotion_gate.py` — `PROMOTION_EVIDENCE_KIND`,
  state `RECORDED_ONLY`, `evaluate_verification_promotion_gates(_from_files)`; its docstring:
  a PASS artifact "is input to an operator-applied matrix update — it never flips capability
  state itself."
- Approval ceremony grammar: `APPROVAL_CONFIRMATION_PREFIX_LENGTH = 4`
  (`builder_ii/hitl_patch_approval.py:68`).
- Post-v0.1.0 versioning policy (CHANGELOG + `code_vault/hierarchy.py` precedent): an
  additive-optional field = **minor** schema bump; validators accept version N−1 for one release
  cycle; absence of new fields = old semantics.
- Flip machinery: `scripts/b4_flip_assistant.py` (`FLIP_CAPABILITIES` tuple; extend it),
  `tests/test_platform_completion_truth.py` (currently `operationally_verified_count == 18`),
  mirror table in `docs/PLATFORM_COMPLETION_AUDIT.md`, closure-audit precedent
  `docs/audits/R1_CLOSURE_AUDIT_2_6.md`, generated `docs/KNOWN_LIMITATIONS.md`
  (regenerate via `uv run builder-platform known-limitations --output docs/KNOWN_LIMITATIONS.md`
  — NEVER hand-edit; an exact-equality test pins it).
- Existing deepagents registry subcommands: `command_authority.py:419-431` (policy, validate,
  readiness, validate-readiness, forge, delegate, work-plan, assign-subagent, record-result,
  review-result, request-human-gate, record-blocked-action, proposal-result, …). Space-form
  names; `docs/COMMAND_AUTHORITY.md` is a generated table (regen snippet below).

**COMMAND_AUTHORITY.md regeneration snippet (the only sanctioned way to update the table):**

```python
from pathlib import Path
from builder_ii.command_authority import render_registry_markdown_table
doc = Path("docs/COMMAND_AUTHORITY.md")
lines = doc.read_text(encoding="utf-8").splitlines(keepends=True)
start = next(i for i, line in enumerate(lines) if line.startswith("| "))
end = start
while end < len(lines) and lines[end].startswith("|"):
    end += 1
table = render_registry_markdown_table()
doc.write_text("".join(lines[:start]) + table + ("" if table.endswith("\n") else "\n") + "".join(lines[end:]), encoding="utf-8")
```

## Object model (exact schemas — implement as written; do not invent fields)

### Obligation — NEW kind `builder_ii.orchestration_obligation` (schema v1)

New module `builder_ii/orchestration_obligation.py`. Fields:

- `kind`, `schema_version: 1`
- `obligation_id` — attach_digest over canonical content (use `builder_ii.config_schema.attach_digest`)
- `lane` — one of the lane-policy lanes (see below)
- `obligation_kind` — `planning_step | interactive_ops | model_call | mutation | verification`
- `task` — non-empty string, **≤ 2000 chars**
- `boundary` — `{denied_actions: [str], refused_lanes: [str]}` (deny-list house style)
- `output_contract` — `{expected_kind: str, required_evidence_kinds: [str]}`
- `file_refs` — `[{path: str, sha256: str}]`; **anti-dump validation: reject any ref field value
  longer than 512 chars and reject any `content`/`body`/`text` key anywhere in refs**
- `briefing_bytes` — int, recorded actual serialized briefing size; must be ≤ the partition's
  `max_output_bytes`
- `budget_partition` — `{max_subagents: int, max_events: int, max_output_bytes: int,
  max_human_gates: int}` (all ≥ 0; see R4 accounting semantics)
- `parent_ref` — `{seal_digest: str}` XOR `{obligation_digest: str}` (exactly one)
- `lane_policy_digest` — pins the policy in force
- `subagent_profile` — non-empty string
- standard governance block (`build_standard_governance` house pattern;
  `artifact_is_authority: false`)

### Root seal — EXTEND `builder_ii.deepagents_execution_approval` (minor schema bump)

New optional-at-parse, required-at-Ladder-4-runtime fields on the approval:

- `lane_policy_digest: str`
- `root_budget` — the same four-field budget object
- `allowed_obligation_kinds` — `[{kind: str, max_count: int}]`
- `refused_lanes: [str]` — explicit negative space (macaroon-style caveats, not allowlist-only)
- `native_backend_acknowledged: bool` — **two-key rule:** REQUIRED `true` when the bound
  candidate's `backend_mode == "optional_deepagents"`; the runner refuses to spawn otherwise
  (mirrors the D7 execution-risk-ack pattern exactly)

The digest-prefix ceremony (`approve-candidate`) is UNCHANGED — one typed 4-char prefix, once,
at the root. See risk map R1 before touching this kind.

### Dynamic mint (the envelope semantics — do NOT implement pre-committed ticket lists)

The seal pre-authorizes **kinds × max counts × budget** — never an exact ticket list. Obligations
mint at plan time or mid-run under that envelope. Every mint is validated fail-closed at mint
time: (1) `obligation_kind` is in `allowed_obligation_kinds` with count remaining; (2) budget
partition ≤ parent's remaining (see R4); (3) lane matches the lane policy for that kind;
(4) anti-dump passes; (5) human-gates ≤ remaining. Every mint emits a ledger event
(`obligation_minted` / `obligation_mint_refused`); refusals carry the exact violated rule and the
fixing edit (zero dead ends). Rationale: pre-committed lists would forbid runtime task discovery
and castrate deepagents' native planning strength (craft doctrine #6).

### Discharge — classification on EXISTING results/events (no new kind)

States: `CONTRACT_SATISFIED` (result kind == `expected_kind` AND every
`required_evidence_kinds` entry attached as a digest ref) · `DISCHARGED_UNVERIFIED` (right
shape, missing evidence — consumable only as unverified; consumption eventized) ·
`CONTRACT_VIOLATED` (wrong shape — **not consumable at all**) · `BLOCKED` (refused mint or
boundary violation). Consumption = new event types on the existing deepagents event ledger:
`obligation_consumed {obligation_digest, discharge_state}`. `PROPOSAL_ONLY` remains the result
mode underneath; discharge classification is orthogonal metadata layered on it.

### Lane policy — NEW kind `builder_ii.orchestration_lane_policy` (derived view)

New module `builder_ii/orchestration_lane_policy.py`. Rendered from ONE small in-code table
(never hand-maintained as a parallel registry):

| obligation_kind | lane | allowed discharge mechanisms |
| --- | --- | --- |
| planning_step | deepagents | `builder-deepagents run-approved` (protocol) |
| interactive_ops | goose | goose readonly session / proposal artifacts |
| model_call | gateway | model execution receipt |
| mutation | hitl_patch | `builder-hitl apply-patch` only |
| verification | verify | verification execution receipt |

CI totality proof: every `obligation_kind` maps to exactly one lane; every discharge command
named exists in `COMMAND_AUTHORITY_REGISTRY`. Collisions resolve by policy lookup, never by
"whichever adapter got invoked first." Full-registry coloring is phase-2 — out of scope.

---

## HIGH-RISK NUANCE MAPS (read the map for your PR before writing code)

### R1 — Approval schema bump is an authority-surface edit (PR-4) — HIGH

**Vision.** The approval artifact is the single most authority-laden object in the deepagents
lane: it is what the operator's typed digest prefix binds to. Extending it is not "adding
fields" — it is widening what one human ceremony authorizes. The design intent: the ceremony
stays exactly one typed prefix, but what it seals now includes the lane policy, the budget, and
the obligation envelope. The seal must remain **the only friction point in the tree** (craft
standard #3): sub-mints inside the envelope never re-prompt; anything outside the envelope is an
invalid mint, not a new prompt.

**Nuances the implementer must honor:**
1. **Do not fork a second approval kind.** One approval kind, minor-bumped. A parallel
   "orchestration approval" would create the parallel authority stack this design exists to
   prevent.
2. **N/N−1 acceptance:** `validate_deepagents_execution_approval` (`deepagents_execution.py:1377`)
   accepts the previous schema for one release cycle; absence of the new fields = legacy
   semantics (no obligation enforcement) and the runner then refuses obligation-bearing
   candidates against a legacy approval with a named error — never silently degrades.
3. **Find every consumer BEFORE editing:**
   `grep -rn "deepagents_execution_approval\|DEEPAGENTS_EXECUTION_APPROVAL_KIND" builder_ii tests`
   — creators, validators, cross-validators (`:1421` binds approval↔candidate; extend it to
   check `lane_policy_digest` equality and that candidate `backend_mode` vs
   `native_backend_acknowledged` are consistent), CLI (`approve-candidate` at
   `deepagents_cli.py:664`), fixtures, scenario tests.
4. **Digest semantics:** the new fields go INSIDE the digested content (they are what is being
   approved). Never add fields outside the digest basis — an unsealed field on an approval is a
   forgery channel.
5. **Two-key enforcement point is the runner, before spawn** (the D7 pattern): check in
   `run-approved` path prior to `backend_for(...)` construction, refuse with a receipt-visible
   blocked-action record, not an exception trace.
6. **Registry lockstep:** `builder-deepagents approve-candidate` and `run-approved` records in
   `command_authority.py` must have their `approval_boundary`/`runtime_boundary` text updated in
   the same PR + table regenerated, or `test_command_authority.py` fails on doc-table equality.

**What would be WRONG:** a `--yes` path; harvesting the prefix programmatically anywhere except
the interactive prompt; making `native_backend_acknowledged` default to true; accepting a legacy
approval for an obligation-bearing run "for convenience."

### R2 — Truth inflation at the flip (PR-8) — HIGH

**Vision.** The flip is the moment this feature either becomes real or becomes theatre. The row
`governed obligation delegation` goes `OPERATIONALLY_VERIFIED` with assurance
`BOUNDED_EXECUTION_VERIFIED` — and the *scope sentence in the row must say what was verified*:
obligation-governed delegation over the **protocol_fake backend as CI truth**, with the native
backend a separate, two-key-gated, readiness-gated claim that is NOT covered by this flip.
"OPERATIONALLY_VERIFIED" here means: the laws are enforced fail-closed and evidenced end-to-end
— it does not mean "agents are smart" and must never be worded to imply it.

**The eight gates mapped to concrete evidence (the closure audit must cite each):**
1. *Docs* — RFC + `docs/ORCHESTRATION_OBLIGATIONS.md` + registry text.
2. *Tests* — unit suites (PR-1/2/4) + the unmocked scenario E2E (PR-6).
3. *Command surface* — registered subcommands, table regenerated, operator-status parity
   (`test_operator_status.py` auto-covers count).
4. *Failure mode* — refused mints/widenings/dump-briefings each produce named, fix-carrying
   blocked-action records (asserted in tests).
5. *HITL boundary* — exactly one root seal, 1.1 grammar, two-key native ack.
6. *Output artifact* — obligations, discharges, ledger events, evidence bundle, replay report.
7. *Rollback* — delete emitted artifacts; no target mutation exists in this lane (mutation
   obligations discharge ONLY through the already-promoted hitl_patch lane).
8. *Verification* — B2.0 tree-profile PASS artifact over the E2E chain (PR-7) — B2.0's first
   live consumer, cited by digest in the audit.

**Flip mechanics checklist (pinned sites move in lockstep, ONE PR, operator merges):**
matrix row (+ scope-honest blockers) in `platform_completion_audit.py`; assurance mapping for
the new row in `assurance_state_for_row` (→ `BOUNDED_EXECUTION_VERIFIED`); truth-test pins —
`operationally_verified_count` 18→19, new assurance assert, any scoped-state asserts;
`scripts/b4_flip_assistant.py` `FLIP_CAPABILITIES` += the row (assistant must print ALL PASS);
mirror table + prose in `docs/PLATFORM_COMPLETION_AUDIT.md`; regenerate `docs/KNOWN_LIMITATIONS.md`
via the command; closure audit doc `docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md`
(follow `R1_CLOSURE_AUDIT_2_6.md`'s structure: mechanism → evidence table → pin edit set →
still-not-promoted → next gate). Also REWORD the existing `deepagents runtime/subagents` row's
blockers to name the trunk honestly (candidate→seal→run-approved; run-plan is legacy) — a scope
restatement, not a second flip.

**What would be truth inflation (refuse these):** flipping with only protocol_fake coverage but
row text implying native execution; counting `run-plan` outputs as evidence; an audit citing the
synthesized-success string era as "verified subagent execution"; hand-editing
KNOWN_LIMITATIONS.md; merging the flip PR yourself — **the operator's merge IS the flip.**

### R3 — The honesty fix at `deepagents_runtime.py:219` (PR-4) — doctrine-sensitive

**Vision.** D5 banned fabricated success in STRATUM; the same rule applies to what a runtime
*says about its subagents*. The summary must be **derived, never asserted**: from the discharge
classification (`CONTRACT_SATISFIED` → "discharged: produced <kind>, evidence attached";
`DISCHARGED_UNVERIFIED` → "speech recorded, belief withheld: missing <evidence kinds>"; etc.)
and, under `protocol_fake`, the text must carry its provenance ("protocol-fake backend —
structural truth only"). Verified: no test pins the current string, so this is a free move —
but implementers must add NEW pins asserting the truthful forms and asserting the absence of
unconditional success text, not merely delete the old sentence.

### R4 — Budget conservation arithmetic (PR-1/PR-4) — correctness trap

**Vision.** Budgets are grants, not loans, v1: conservative and simple beats financial-grade.
- Remaining(parent) = grant(parent) − Σ grant(minted children) − own recorded spend where
  tracked (events/output bytes come from the existing envelope counters; subagent slots and
  human gates are mint-time quantities).
- Mint check: `child.budget_partition ≤ Remaining(parent)` component-wise, at mint time,
  fail-closed. **No refunds in v1:** an unspent child grant does not return to the parent
  (deferred to phase-2; document this in the RFC so nobody "helpfully" adds it untested).
- Overspend at runtime (events/bytes exceeding a partition) = governance event + `BLOCKED`
  discharge for that obligation; never silent clamping.
- `max_human_gates` is checked at PLAN/mint time against the tree's scheduled
  `request-human-gate` intents — if the tree wants more interrupts than the seal granted, it
  fails closed BEFORE running (operator attention as conserved physics). Root default: 2.

### R5 — Contended-file serialization (all PRs) — process risk

Five files are append-contested platform-wide: `command_authority.py`,
`artifact_index_records.py`, `artifact_chain_verification.py`, `platform_completion_audit.py`,
and the pinned truth tests. **Rule: only PR-3, PR-4 (registry text only), and PR-8 may touch
them; one such PR in flight at a time; Sonnet-assigned PRs never touch them.** (This rule
prevented a collision once already — the 3.13 incident.) All work branches fresh from current
`main` **at dispatch time** (not from when a briefing was written); agents running in the same
wave use **separate git worktrees** — even disjoint-file PRs collide on shared working-directory
git state. PRs via `tea --repo core-labs/builder-II --login core-gitquarters` (Forgejo; never
`gh`, never github.com, never direct-to-main, no AI attribution trailers, explicit staging only
— never `git add -A`).

---

## PR sequence (each = one branch, one PR, full gate battery)

**Gate battery (every PR):** `uv run pytest -q` · `uv run ruff check builder_ii tests` ·
targeted mypy per CLAUDE.md · `uv run bandit -q -r builder_ii -s B101,B105,B106,B110,B112,B404,B603,B607` ·
`uv run python -m compileall -q builder_ii tests` · `uv run builder-platform audit-docs` ·
regenerate COMMAND_AUTHORITY.md when the registry changed. PR body must include the battery
results.

### PR-0 — RFC (Opus 4.8) — `docs/plan/ORCHESTRATION_OBLIGATIONS_RFC.md`
Design-only. Contents: the constitution above verbatim; trunk = candidate→seal→run-approved
(quote the `run-plan`/`:519` vs `run-approved`/`:695` distinction and the `runtime.py:219`
finding); the object model verbatim; R1–R5 nuance maps summarized; phase-2 deferrals; non-goals.
*Boundary: `docs/plan/` only. Nothing else.*

### PR-1 — Obligation kind (Sonnet 5) — new files only
`builder_ii/orchestration_obligation.py` + `tests/test_orchestration_obligation.py`.
Create/validate/dumps/write + budget-arithmetic helpers (`remaining()`, `fits_within()`).
Tests: anti-dump rejection (oversized ref value; smuggled `content` key), ⊆ failures per
component, conservation (Σ children > parent refused), human-gates check, parent_ref XOR,
task length bound, digest stability. *Boundary: the two new files ONLY. No registry, no CLI,
no contended files (registration happens in PR-3).* Read: Object model, R4.

### PR-2 — Lane policy (Sonnet 5) — new files only
`builder_ii/orchestration_lane_policy.py` + `tests/test_orchestration_lane_policy.py`.
The table above as code → render/validate; totality test (every obligation_kind exactly one
lane); collision refusal test (mint `interactive_ops` under lane `deepagents` → named error);
discharge-mechanism existence checked lazily against `COMMAND_AUTHORITY_REGISTRY` (import is
fine; editing it is not). *Boundary: the two new files ONLY.* Read: Object model, R5.

### PR-3 — Registry + CLI wiring (Opus 4.8) — SERIALIZED, contended files
Register both kinds in `artifact_index_records.py` + `artifact_chain_verification.py`
VALIDATORS + `docs/ARTIFACT_INDEX.md` bullet list. Add `builder-orchestration` subcommands:
`mint-obligation`, `validate-obligation`, `lane-policy`, `validate-lane-policy` (follow
`orchestration` CLI house style; function-local imports) + names in `command_authority.py` +
regen the table. New operator doc `docs/ORCHESTRATION_OBLIGATIONS.md` + `docs/README.md` index
row. *Depends: PR-1, PR-2 merged.* Read: R5, regen snippet.

### PR-4 — Seal + runner enforcement + honesty fix (Opus 4.8) — THE TRUNK PR, SERIALIZED
(a) Approval schema bump per Object model + R1 (validators `:1377`/`:1421`, CLI `:664`, all
consumers via the R1 grep). (b) Candidate gains `lane_policy_ref` + obligation-envelope echo.
(c) `run-approved` (`deepagents_cli.py:695` → `deepagents_execution.py` run path): loads
obligations, passes `obligation.task` to the backend (not the root task), stamps
`obligation_digest` + `briefing_digest` on every event, enforces mint-time rules for dynamic
mints mid-run (R4), classifies discharges (three states + BLOCKED), enforces the two-key native
ack before spawn. (d) **`deepagents_runtime.py:219` honesty fix per R3** + new truthful-text
pins. (e) Registry boundary-text updates for `approve-candidate`/`run-approved` + regen.
*Depends: PR-3. Boundary: may touch `command_authority.py` for record text ONLY; must NOT touch
the matrix or truth tests.* Read: R1, R3, R4, R5.

### PR-5 — `status` / `why` / replay extension (Sonnet 5)
`builder-orchestration status` (board: OPEN / SATISFIED / UNVERIFIED / VIOLATED / BLOCKED with
budget columns) and `builder-orchestration why <artifact-path>` ("believed? NO —
DISCHARGED_UNVERIFIED; required: verification_execution_receipt; attached: none; consumed: no").
Deterministic read-only walks over the output dir + digests; no model; exit non-zero on
violated/missing chains. Extend the existing `DEEPAGENTS_REPLAY_REPORT_KIND` walk with the
obligation chain. **PR-5 owns ALL `status`/`why` OUTPUT assertions in its own test file — PR-6
must not assert on them (Wave-4 decoupling rule).** Registry additions for the two new
subcommands are handed to whichever serialized registry PR is open (or a follow-up Opus
micro-PR) — *Sonnet does not touch contended files; ship the commands + tests + a TODO note for
the registry pass if needed.* *Depends: PR-4 only; runs in parallel with PR-6 in a separate
worktree.* Read: Object model (discharge states), R5, Wave-4 decoupling rule.

### PR-6 — Unmocked scenario E2E + tamper beat (Sonnet 5)
`tests/scenarios/test_full_obligation_delegation_lane.py`, protocol_fake, no monkeypatched
validators: lane policy → candidate → REAL seal fixture (drive `approve-candidate`'s prompt via
CliRunner input with the 4-char prefix) → run-approved with: one dynamic mint that succeeds, one
**refused widening mint**, one `DISCHARGED_UNVERIFIED` (missing evidence ref), one
`CONTRACT_VIOLATED` (wrong kind) → **tamper beat**: edit a discharge JSON on disk → replay/chain
verification names the forged obligation node → clean-run evidence bundle for PR-7.
**Wave-4 decoupling rule (binding): assert on artifacts and ledger events ONLY — discharge
states, refused-mint records, tamper detection. Do NOT assert on `status`/`why` command output;
PR-5 owns those in its own tests.** Plus: sequel section in `docs/demos/FLAGSHIP_DEMO_SCRIPT.md`
("Act II — tamper the cognition chain") and optionally a `record-demo.sh` segment.
*Depends: PR-4 only; runs in parallel with PR-5 in a separate worktree.* Read: Object model,
R3, Wave-4 decoupling rule.

### PR-7 — B2.0 tree profile (Opus 4.8)
Extend `verification_promotion_gate.py` with a sibling evaluator (same gate grammar, same
`PROMOTION_EVIDENCE_KIND`, `RECORDED_ONLY`) consuming seal + obligations + discharge events +
evidence bundle; per-gate pass/fail rows mapped as in R2. Feed it PR-6's clean-run bundle in a
test; PASS artifact digest goes into the PR body for the closure audit to cite.
*Depends: PR-6.* Read: R2.

### PR-8 — Closure audit + flip prep (Opus 4.8) — SERIALIZED; **operator merges**
Everything in R2's flip-mechanics checklist, one atomic PR, flip assistant ALL PASS in the PR
body. The PR is prepared by the agent; **the operator's merge applies the flip** (tier C —
evidence first, operator applies; identical ceremony to 1.7/2.6). *Depends: PR-7.* Read: R2, R5.

## Dispatch waves & dependency structure

Sequencing is logical (dependencies and serialization), never chronological — no clocks, no
calendars. A wave opens when the prior wave's PRs are merged; everything inside a wave runs
concurrently.

```
Wave 1:  PR-0 ∥ PR-1 ∥ PR-2          (Opus + Sonnet + Sonnet — fully disjoint files)
Wave 2:  PR-3                        (Opus ALONE — contended files, R5)
Wave 3:  PR-4                        (Opus ALONE — contended files, R5; the critical path)
Wave 4:  PR-5 ∥ PR-6                 (Sonnet + Sonnet — decoupled by design, see below)
         PR-7 may START in overlap   (Opus — evaluator authored against this plan's spec;
                                      its test finalizes only after PR-6 merges)
Wave 5:  PR-7 finish ──► PR-8        (Opus prep; the OPERATOR's merge of PR-8 is the flip)
```

- **Wave 1 relaxation (deliberate):** PR-1 and PR-2 do NOT wait for PR-0. Their schemas are
  pinned in THIS plan document; the RFC is doctrine capture, not a schema source. Three agents
  launch simultaneously.
- **Wave 4 decoupling rule (binding on both Sonnets):** PR-6's scenario asserts on **artifacts
  and ledger events only** — discharge states, refused-mint records, tamper detection via
  replay/chain verification. The `status`/`why` OUTPUT assertions belong exclusively to PR-5's
  own test file. This removes every dependency between the two PRs.
- **The irreducible middle:** PR-3 → PR-4 cannot be parallelized with anything — both own
  contended files (R5). Do not schedule speculative pre-drafting of PR-5/PR-6 during Wave 3:
  interfaces settle in PR-4 and parallel drafts become rework.
- **Concurrency hygiene:** every agent branches fresh from current `main` at dispatch time (not
  from when its briefing was written); agents running in the same wave work in **separate git
  worktrees** — even disjoint-file PRs collide on shared working-directory git state.

Overall complexity: **HIGH** (authority surface + promotion). Model split: Opus 4.8 → PR-0,
PR-3, PR-4, PR-7, PR-8 (tier-C, contended files, authority semantics); Sonnet 5 → PR-1, PR-2,
PR-5, PR-6 (new-file bounded, tests, readers, docs).

## Risk register (summary)

| Risk | Sev | Map | Mitigation |
| --- | --- | --- | --- |
| Approval schema bump blast radius | HIGH | R1 | N/N−1, consumer grep, digest-basis rule, one kind |
| Truth inflation at flip | HIGH | R2 | 8-gate evidence table, assistant ALL PASS, operator-applied merge |
| Fabricated-success regression | MED | R3 | derived summaries + new truthful pins (no old pins exist — verified) |
| Conservation arithmetic bugs | MED | R4 | grants-not-loans v1, component-wise ⊆, no refunds, overspend = event |
| Contended-file collision | MED | R5 | serialization rule; Sonnets never touch the five files |
| Dynamic-mint runaway | LOW | — | seal max counts + max_events ceiling; every mint eventized |

## Operator delegation map (point each agent at its rows)

| Wave | Model | Read first | Build |
| --- | --- | --- | --- |
| 1 (three in parallel) | Opus 4.8 | Constitution, Grounding, R1–R5 | PR-0 |
| 1 (three in parallel) | Sonnet 5 | Object model, R4 | PR-1 |
| 1 (three in parallel) | Sonnet 5 | Object model, R5 | PR-2 |
| 2 (alone — R5) | Opus 4.8 | R5, regen snippet | PR-3 |
| 3 (alone — R5) | Opus 4.8 | R1, R3, R4 | PR-4 |
| 4 (two in parallel) | Sonnet 5 | Discharge states, R5, Wave-4 rule | PR-5 |
| 4 (two in parallel) | Sonnet 5 | Object model, R3, Wave-4 rule | PR-6 |
| 4-overlap → 5 | Opus 4.8 | R2 | PR-7 (may start during Wave 4; test finalizes after PR-6) |
| 5 (alone — R5) | Opus 4.8 | R2 (flip checklist) | PR-8 — **operator merges** |
