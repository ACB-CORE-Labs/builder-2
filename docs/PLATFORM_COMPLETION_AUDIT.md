# Platform Completion Audit

This document is the human mirror of the R0 truth machine. The machine-readable source is:

```bash
builder-platform matrix
builder-platform status
builder-platform audit-docs
```

## Truth State

builder-II is a generic governed local agent/developer platform. CORE is a target profile, not the platform identity, not a second runtime, and not CORE Workbench/UI.

Current platform truth:

- passive foundation state: `PASSIVE_FOUNDATION`
- platform-wide ambient runtime authority state: not `OPERATIONALLY_VERIFIED`; operational authority is capability-scoped by the matrix
- setup/config kernel state: R1.4 passive schema, source resolution, setup plan, overlay plan, rollback snapshot, digest-bound apply/rollback, and legacy setup-surface reconciliation exist; the interactive setup wizard (`builder init`, plan item 2.2/2.6) is operational as a plans-only surface; generic rollback remains non-operational
- current sequence: `B8 deferred; B9 complete`; historical dependency spine: `R0 -> R1 -> B1`

R1.4 keeps the setup/config kernel non-operational beyond the governed artifact chain. Legacy `builder setup` now fails closed and redirects to `builder-setup`. Ambient runtime execution, Goose runtime promotion, native deepagents backend execution, autonomous writes, source CORE checkout mutation, and commit/push automation remain unpromoted; model/provider calls, MCP/tool invocation, the bounded deepagents protocol lane with governed obligation delegation (protocol_fake as CI truth), and the governed demo loop are operational only inside their explicit capability-scoped envelopes.

Operator-invoked HITL patch application and rollback execution are `OPERATIONALLY_VERIFIED` (plan item 1.7; `docs/audits/B4_CLOSURE_AUDIT.md`): both run only through an interactive digest-prefix approval boundary, a required verification receipt, the command-authority gate, and a drift-hardened, ledger-traced rollback. The commands stay Tier 3 candidates, not `enabled`; autonomous or automatic patch application remains forbidden and unpromoted.

The interactive setup wizard is `OPERATIONALLY_VERIFIED` (plan item 2.6; `docs/audits/R1_CLOSURE_AUDIT_2_6.md`): `builder init` (plan item 2.2) prompts the four wizard decisions with registry-validated answers, plans the full setup chain as passive artifacts, and never applies. Setup mutation remains exclusively the separately digest-approved `builder-setup apply` (inline flag or interactive digest-prefix confirmation); Goose config merge, skill copying, and recipe installation remain manual operator steps (R1.7).

Governed obligation delegation is `OPERATIONALLY_VERIFIED` with assurance `BOUNDED_EXECUTION_VERIFIED` (Ladder 4 PR-8; `docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md`): one flag-driven, digest-bound seal (`builder-deepagents approve-candidate`) opens an obligation envelope; every mint is enforced fail-closed against it, with each refusal naming the exact violated rule and a fixing edit; discharges classify `CONTRACT_SATISFIED` / `DISCHARGED_UNVERIFIED` / `CONTRACT_VIOLATED` / `BLOCKED`; the event chain is digest-stamped, tamper-evident, and replayable. The verified claim is scoped to the `protocol_fake` backend as CI truth — the two laws (authority attenuates down, evidence accumulates up) are enforced fail-closed and evidenced end-to-end. It is not a claim about agent-output quality, and the native `optional_deepagents` backend remains unpromoted behind its readiness gate and two-key acknowledgement; mutation obligations discharge only through the already-promoted HITL patch lane.

HITL-approved verification execution carries assurance `BOUNDED_EXECUTION_VERIFIED` (Ladder 9; `docs/audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md`). Its completion state does not change and `operationally_verified_count` stays 19: this is an assurance-only flip, the first of its kind. `builder-verify run-approved` spawns `sys.executable -m builder_ii.verification_runner_entrypoints <sub>` with fixed argv, `shell=False`, a minimal env, and an import path the target repository cannot supply, under two-key HITL approval, and binds a digest-stable receipt to the plan and the approval. The claim is scoped exactly to the fixed `platform_status` and `docs_audit` profiles, which run builder-II's own audit code over the target's data; `pytest_full` and `builder_full` execute the target repository's own suite behind the mandatory D7 execution-risk acknowledgement and are outside this claim. `BOUNDED_EXECUTION_VERIFIED` describes the envelope of the invocation and does not describe the behaviour of the code that ran inside it. Container isolation is containment of that residual, never attestation of the evidence (`docs/plan/VERIFICATION_ISOLATION_RFC.md`), so the assurance state does not depend on it.

`OPERATIONALLY_VERIFIED` is a legacy matrix state, not a life-safety or global-runtime clearance. Machine-readable matrix rows now also carry a sharper `assurance_state`, drawn from the vocabulary defined below. That list is generated from `builder_ii/assurance.py` and pinned against it; this sentence deliberately does not repeat the state names, because a second copy of them is a second place for the truth to drift.

For high-consequence work, the assurance state is authoritative for risk interpretation. A live provider call, a temporary demo loop, and passive candidate specifications are not equivalent just because older rows may share the same legacy completion label.

## Assurance States

Each state says what the capability *does*. These lines are generated from
`builder_ii/assurance.py`'s `ASSURANCE_STATE_DEFINITIONS` and pinned by
`tests/test_assurance.py`; edit the module, never this list.

- `PASSIVE_ARTIFACT_VERIFIED` — Builds, validates, or reads governed artifacts and renders them. It starts no runtime, spawns no process, calls no provider, and writes nothing outside the artifact store.
- `LOCAL_STATE_MUTATION_VERIFIED` — Writes or deletes builder-II's own local state -- runtime markers, lockfiles, caches -- outside the artifact store and outside every target repository. It starts no runtime, spawns no process, and calls no provider. Nothing snapshots the write, so it is undone by re-establishing the state, never by a rollback.
- `READ_ONLY_RUNTIME_VERIFIED` — Starts, or hands the operator's terminal to, a runtime whose policy denies writes. The read-only boundary is enforced by that runtime's own preflight and postflight, never by the caller's intent.
- `BOUNDED_EXECUTION_VERIFIED` — Causes work to run -- a subprocess, an external tool, or a sealed backend -- inside a fixed, pre-approved envelope: fixed argv with shell=False or a digest-bound seal, an approval, and a digest-bound receipt. It attests the envelope of the invocation. It never attests the behaviour of the code that ran inside it.
- `MUTATION_WITH_ROLLBACK_VERIFIED` — Writes to the target repository's source tree or git state, and only behind an interactive digest-prefix approval, a required verification receipt, and a snapshot that makes the write reversible.
- `LIVE_PROVIDER_VERIFIED` — Reaches a live model provider over the network. Its output is not deterministic and is never, on its own, evidence.
- `DEMO_ONLY_VERIFIED` — Exercised end to end only inside the governed demo loop, against a synthetic target. A demo pass is not evidence for the corresponding real lane.
- `BLOCKED_BY_EVIDENCE` — No claim is supported: the capability is not operationally verified, or its command surface is a forbidden or unpromoted record. This is the state that absence takes. It is never a default for something that runs.
- `SAFETY_CRITICAL_PROHIBITED` — Names a capability whose promotion is refused regardless of the evidence offered for it. `allows_memory_mutation` is the only one, and `validate_registry_invariants` rejects it at every tier, so the state is derivable but no row or record carries it: a record claiming the flag is refused before anything can read its state. Unlike BLOCKED_BY_EVIDENCE, no evidence unblocks it.

Every `OPERATIONALLY_VERIFIED` row is assigned one of these by an explicit decision recorded
in `assurance_state_for_row`. There is no default: a row that no one classified is an error,
not a passive artifact.

## State Labels

Allowed labels:

- `NOT_STARTED`
- `DESIGN_ONLY`
- `ARTIFACT_ONLY`
- `PASSIVE_FOUNDATION`
- `IMPLEMENTED_ON_BRANCH`
- `PR_OPEN`
- `MERGED_BUT_NOT_OPERATIONAL`
- `OPERATIONALLY_VERIFIED`

Every row has exactly one label. A valid artifact is not authority. Approval is not execution. Execution is not verification. Verification is not promotion unless receipt, postflight, rollback/no-mutation proof, ledger, and replay/audit close the loop.

## Capability Matrix

| Capability | State | Next PR |
|---|---|---|
| generic platform identity | `PASSIVE_FOUNDATION` | R0 |
| target profiles | `OPERATIONALLY_VERIFIED` | B4 |
| agent profiles | `PASSIVE_FOUNDATION` | B5 |
| verification profiles | `PASSIVE_FOUNDATION` | B1 |
| context packs | `OPERATIONALLY_VERIFIED` | B4 |
| profile packs | `PASSIVE_FOUNDATION` | defer runtime materialization |
| config schema | `PASSIVE_FOUNDATION` | R1 |
| config source precedence | `PASSIVE_FOUNDATION` | R1 |
| interactive setup wizard | `OPERATIONALLY_VERIFIED` | R1 complete (2.6) |
| non-interactive setup/apply/validate | `MERGED_BUT_NOT_OPERATIONAL` | R1 |
| Goose config overlay/rollback | `PASSIVE_FOUNDATION` | R1 |
| recipe generator/wizard | `ARTIFACT_ONLY` | R1 |
| skill generator/installer/validator | `MERGED_BUT_NOT_OPERATIONAL` | R1 |
| target profile wizard | `NOT_STARTED` | R1 |
| agent profile wizard | `NOT_STARTED` | R1 |
| verification profile wizard | `NOT_STARTED` | R1 |
| deepagents/researcher setup wizard | `NOT_STARTED` | R1 |
| setup receipt + rollback artifact | `PASSIVE_FOUNDATION` | R1 |
| model registry | `OPERATIONALLY_VERIFIED` | B7 |
| model routing | `OPERATIONALLY_VERIFIED` | B7 |
| model/provider execution | `OPERATIONALLY_VERIFIED` | B7 |
| tool registry | `PASSIVE_FOUNDATION` | B7 |
| low-risk tool invocation | `OPERATIONALLY_VERIFIED` | B7 |
| MCP invocation | `PASSIVE_FOUNDATION` | B7 |
| passive orchestration assignment | `PASSIVE_FOUNDATION` | B5 |
| workflow/event ledger | `PASSIVE_FOUNDATION` | B1 then B6/B7/B8 |
| replay/audit | `PASSIVE_FOUNDATION` | B1 |
| readonly founder demo | `PASSIVE_FOUNDATION` | defer after R0 |
| orchestration founder demo wrapper | `PASSIVE_FOUNDATION` | B9 |
| HITL promotion bridge | `PASSIVE_FOUNDATION` | B1 |
| execution candidate manifests | `PASSIVE_FOUNDATION` | B1 |
| HITL-approved verification execution | `OPERATIONALLY_VERIFIED` | B2.0 |
| HITL patch proposal | `OPERATIONALLY_VERIFIED` | B4 |
| HITL patch application | `OPERATIONALLY_VERIFIED` | B4.8 |
| rollback execution | `OPERATIONALLY_VERIFIED` | B4.8 |
| postflight verification | `OPERATIONALLY_VERIFIED` | B1.5 |
| Goose setup | `MERGED_BUT_NOT_OPERATIONAL` | B4 after R0/B3 |
| governed read-only runtime | `OPERATIONALLY_VERIFIED` | B4 |
| Goose readonly runtime | `OPERATIONALLY_VERIFIED` | B5 |
| Goose command proposals | `PASSIVE_FOUNDATION` | B1/B4 |
| deepagents policy/readiness | `PASSIVE_FOUNDATION` | B6 |
| deepagents passive work artifacts | `PASSIVE_FOUNDATION` | B6 |
| deepagents runtime/subagents | `OPERATIONALLY_VERIFIED` | B6 |
| governed obligation delegation | `OPERATIONALLY_VERIFIED` | Ladder 4 complete (PR-8) |
| notes/handoff artifacts | `PASSIVE_FOUNDATION` | defer operational memory |
| artifact memory | `PASSIVE_FOUNDATION` | defer operational memory |
| operator quickstart/golden path | `OPERATIONALLY_VERIFIED` | B9 complete |
| governed demo loop | `OPERATIONALLY_VERIFIED` | B4.9 complete |
| platform doctor/status/audit | `PASSIVE_FOUNDATION` | R1 then B1 |
| release proof/quality gates | `PASSIVE_FOUNDATION` | B1 |
| command authority as runtime gate | `OPERATIONALLY_VERIFIED` | B1.5 |
| docs truth enforcement | `PASSIVE_FOUNDATION` | R1 then B1 |

## Corrections

- Passive model routing exists through `builder-model-policy`; provider execution remains unpromoted.
- Legacy operator-managed helpers such as `builder start`, `builder ask`, `builder doctor`, and `builder status` are separate from canonical governed passive lanes.
- Legacy `builder setup` is no longer operator-managed setup execution; it is a fail-closed redirect to the governed `builder-setup` path.
- Canonical governed passive lanes include `builder-config`, `builder-setup plan`, `builder-setup overlay-plan`, `builder-setup rollback-snapshot`, `builder-session`, `builder-profile-pack`, `builder-model-policy`, `builder-orchestration`, `builder-workflow`, `builder-ledger`, `builder-platform`, and `builder-memory`.
- Canonical governed demo execution is limited to `builder-platform demo-loop` and `builder-platform wow`, both of which operate on a temporary detached worktree of the operator-designated target repo (AssetOverflow/core remains a supported profile) and not the source checkout.
- R1 Config + Onboarding Kernel must precede B1 verification execution because execution authority depends on canonical target roots, artifact roots, config source precedence, setup receipts, rollback artifacts, and auditable capability defaults.
- `builder-setup plan`, `builder-setup overlay-plan`, and `builder-setup rollback-snapshot` are passive setup planning only. They record future planned overlays and prior-state snapshot metadata but cannot write Goose config, write `.goosehints`, copy skills, install recipes, apply setup, execute rollback, start models, start Goose, construct deepagents, call MCP/tools, or apply patches.
- `builder-memory` records explicit memory atoms, indexes, deterministic search results, and replay-stable reconstructions only. Hidden memory, vector stores, and autonomous memory writes remain disabled.

## Validation

Use:

```bash
CORE_REPO_PATH=. uv run pytest -q
CORE_REPO_PATH=. uv run python scripts/verify_v0_release.py --output-dir /tmp/builder-ii-v0-proof-r1-4
uv run builder-platform matrix
uv run builder-platform status
uv run builder-platform audit-docs
uv run builder-memory atom /tmp/builder-ii-memory-source.json --output /tmp/builder-ii-memory-atom.json
uv run builder-memory index /tmp/builder-ii-memory-atom.json --output /tmp/builder-ii-memory-index.json
uv run builder-memory search /tmp/builder-ii-memory-index.json --query "artifact memory" --output /tmp/builder-ii-memory-search.json
uv run builder-memory reconstruct /tmp/builder-ii-memory-index.json --query "artifact memory" --output /tmp/builder-ii-memory-reconstruction.json
uv run builder-config schema
uv run builder-config resolve
uv run builder-setup plan --output /tmp/builder-ii-setup-plan-r1-4.json
uv run builder-setup validate-plan /tmp/builder-ii-setup-plan-r1-4.json
uv run builder-setup overlay-plan /tmp/builder-ii-setup-plan-r1-4.json --output /tmp/builder-ii-setup-overlay-r1-4.json
uv run builder-setup validate-overlay-plan /tmp/builder-ii-setup-overlay-r1-4.json
uv run builder-setup rollback-snapshot /tmp/builder-ii-setup-overlay-r1-4.json --output /tmp/builder-ii-setup-rollback-snapshot-r1-4.json
uv run builder-setup validate-rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot-r1-4.json
uv run builder-platform r1-closure --output-dir /tmp/builder-ii-r1-6-proof
uv run builder-platform validate-r1-closure /tmp/builder-ii-r1-6-proof/r1-closure-report.json
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase prepare --force
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase approve --approve
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase apply
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase verify
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase rollback
uv run builder-platform demo-loop --target-name core --target-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase finalize
uv run builder-platform validate-demo-loop /tmp/builder-ii-core-demo/demo-loop-report.json
```

## R1.4 update

R1.4 leaves the governed setup apply and rollback slices intact and reconciles the remaining legacy bypass: `builder setup` now fails closed and prints the governed `builder-setup` sequence instead of writing Goose config, `.goosehints`, skills, or recipes. B1, B2, B3, runtime, model/provider, MCP/tool, Goose runtime, deepagents runtime, shell/subprocess execution in the setup path, patch, and autonomous write authority remain unpromoted.

## R1.5 update

R1.5 adds `builder-setup init`, `builder-setup wizard`, `builder onboarding`, and `builder-setup validate-onboarding-intent` to provide a governed onboarding UX over the R1 setup chain. It generates passive onboarding intent reports and prints deferred apply commands only. Setup mutation remains exclusively owned by existing `builder-setup apply --approve-digest`. B1, B2, B3, runtime, model/provider, MCP/tool, Goose runtime, deepagents runtime, shell/subprocess execution in the setup path, patch, and autonomous write authority remain unpromoted.

## R1.6 update

R1.6 completes R1 by introducing `builder-platform r1-closure` and `builder-platform validate-r1-closure`. These commands execute the entire passive config/setup/onboarding chain and emit a canonical, auditable `r1-closure-report.json` alongside the full evidence artifact chain (`config-schema.json`, `config-resolution.json`, `setup-plan.json`, `setup-overlay.json`, `setup-rollback-snapshot.json`, and `onboarding-intent.json`). This proves the R1 golden path while ensuring that setup apply/rollback execution remains explicit and B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority remain unpromoted.

B1.1 adds `builder_ii.verification_execution_plan` plus `builder-verify plan` and `builder-verify validate-plan` as a passive verification execution planning surface. B1.2 adds `builder_ii.verification_execution_approval` plus `builder-verify approve-plan` and `builder-verify validate-approval` as a digest-bound HITL approval binding surface. Those planning and approval artifacts remain non-authoritative by themselves. B1.3A adds a receipt contract. B1.3B adds the first bounded approved verification runner for `platform_status`. B1.5 broadens the same fixed-profile, `shell=False`, HITL-bound runner to `docs_audit`, routes the lane through the central command authority gate, and emits a generated postflight sidecar bound to receipt/git preflight/postflight evidence. Arbitrary argv, broad shell execution, live read authority, patching, model/MCP/Goose/deepagents runtime, and B2 write authority remain disabled.

## R1 closure update (2.6)

Plan item 2.6 closes the R1 interactive-wizard gap flagged since R0. `builder init` (plan item 2.2) is the unified onboarding orchestrator: four prompted wizard decisions (output directory, target profile, model backend, model alias) validated against live registries with a 3-attempt re-prompt, five defaulted decisions echoed with their override flags, and the full passive artifact chain (setup plan, overlay plan, rollback snapshot, onboarding intent report) emitted without ever applying. The rendered follow-up `builder-setup apply` command carries no inline digest; apply/rollback approval is either `--approve-digest` (scripted) or an interactive typed digest-prefix confirmation, and receipts record which path was used in `approval_mode`. The matrix flip is operator-applied (tier C): evidence and the full pinned-site edit set are recorded in `docs/audits/R1_CLOSURE_AUDIT_2_6.md`, and `validate_r1_config_onboarding_mapping` now fails closed for every R1 row except those explicitly listed in `R1_OPERATOR_FLIPPED_CAPABILITIES`. The remaining R1 wizard rows (recipe, target/agent/verification profile, deepagents/researcher) stay non-operational.

## B7 update

B7 implements `builder_ii.mcp_policy`, `builder_ii.tool_invocation_gateway`, and `builder-mcp` + `builder-tools invoke` to govern explicit low-risk MCP and tool execution. Invocation requires explicitly constructed JSON envelopes validated against a strictly constrained `MCPToolPolicy` (deny-by-default, fixed args, rollback classifications) before execution via the gateway. Receipts are written alongside operational event ledger entries `tool_call_executed`/`tool_call_denied`. Only safe stub operations (`echo`, `date`) are supported as a proof-of-capability. Shell execution, source writes, broader model automation, Goose runtime, deepagents orchestration, and patch application remain unpromoted and fully blocked.

## B8 update

B8 adds `builder_ii.artifact_memory`, `builder_ii.memory_cli`, and the `builder-memory` command group to convert explicit validated artifacts into governed memory atoms, deterministic indexes, lexical search results, and replay-stable reconstruction artifacts. This promotes `artifact memory` from `DESIGN_ONLY` to `PASSIVE_FOUNDATION`. The lane remains artifact-only: hidden memory, vector-store retrieval, autonomous memory writes, model authority, shell execution, runtime activation, and target-repo mutation remain disabled.

## B9 update

B9 completes the Operator Product Polish by introducing the governed local golden path via `builder-platform operator-status`, `builder-platform next`, and `builder-platform golden-path`. These primitives compose a coherent platform UX derived from existing truth boundaries (matrix, ledger, memory, authority) without claiming operational authority, shell access, model execution, or target repo writes. Golden path validation and next-step alignment operate exclusively via artifact generation, explicitly isolating builder-II from autonomous control planes and CORE Workbench coupling.

## Governed demo loop update

The governed demo loop provides `builder-platform demo-loop`, `builder-platform validate-demo-loop`, and the recording alias `builder-platform wow`. The loop targets a real local git checkout designated by the operator (`--target-repo`/`--target-name`; AssetOverflow/core remains a supported profile with its identity check and sensitive-module policy) by creating a detached temporary worktree from the target's current `HEAD`, then walks through preflight, repo map, context pack, deterministic planner, HITL patch proposal, explicit approval (the generic `builder_ii.hitl_patch_approval`), patch apply receipt, bounded verification receipt, rollback receipt, final postflight, artifact index, chain verification, and `DEMO_EVIDENCE.md`. B4.9 (plan item 1.8) generalized this lane from CORE-only; evidence: `docs/audits/B4_9_DEMO_GENERALIZATION_AUDIT.md`.

This is not a synthetic product tour. It uses the real target repository structure and Git state, but the only approved mutation is a temporary documentation marker inside the detached worktree. The source checkout is not mutated. The loop never commits, pushes, starts Goose, calls models, invokes MCP, writes hidden memory, or touches CORE Workbench/UI.


## B1.5 readiness pass update

B1.5 closes the smallest foundational authority gap without promoting ambient autonomy. `builder_ii.command_authority.enforce_command_authority()` is now a central fail-closed runtime gate that allows registered passive commands, denies unknown commands, denies unknown or over-authority effects, and requires HITL binding for HITL-gated lanes. `builder-verify run-approved` consults this gate before crossing subprocess/artifact-write authority. The approved verification runner now supports exactly two fixed profiles, `platform_status` and `docs_audit`; it still rejects arbitrary argv and shell strings. Real verification execution now produces a postflight record sidecar that links the receipt, plan, approval, preflight git fingerprint, postflight git fingerprint, and mutation verdict. This promotes the verification-runner postflight lane only; broad shell, broad Goose autonomy, broad MCP/live tool execution, hidden/autonomous memory, source CORE checkout mutation, commit/push automation, and model-driven file mutation remain unpromoted.

## Ladder 4 closure update (PR-8)

Ladder 4 (governed obligation delegation) adds the row `governed obligation delegation` at `OPERATIONALLY_VERIFIED` / `BOUNDED_EXECUTION_VERIFIED` and moves `operationally_verified_count` 18 → 19. The lane: `builder-orchestration lane-policy` renders the fixed obligation-kind → lane table (totality validated, collisions refused by name); `builder-orchestration mint-obligation` mints inert, digest-stable obligation tickets (anti-dump file refs, deny-list boundary, budget partition, parent bound to seal or parent obligation); `builder-deepagents execution-candidate --lane-policy … | approve-candidate | run-approved --obligation …` seals the envelope into the approval digest basis and enforces every mint fail-closed (eight named refusal rules, each carrying a fixing edit; widening is an invalid mint); discharges classify `CONTRACT_SATISFIED` / `DISCHARGED_UNVERIFIED` / `CONTRACT_VIOLATED` / `BLOCKED`; `builder-orchestration status` / `why` re-derive belief from the raw event chain and exit non-zero on anything not believed. The flip is tier C, operator-applied: evidence, the audit-findings reconcile (approve-candidate wording honesty, the `deepagents runtime/subagents` trunk restatement), and the full pinned-site edit set are recorded in `docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md`, with the B2.0 delegation-tree PASS evidence committed at `planning/evidence/ladder4-b2-delegation-tree-pass.json` and pinned by `tests/test_ladder4_closure_evidence.py`. Scope stays exactly what was verified: the two laws enforced fail-closed over the `protocol_fake` backend as CI truth — the native `optional_deepagents` backend, autonomous dispatch, backend-initiated mid-run mints, and budget refunds remain unpromoted/deferred.
