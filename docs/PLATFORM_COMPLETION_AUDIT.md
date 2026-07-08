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
- setup/config kernel state: R1.4 passive schema, source resolution, setup plan, overlay plan, rollback snapshot, digest-bound apply/rollback, and legacy setup-surface reconciliation exist; generic rollback remains non-operational
- current sequence: `B8 deferred; B9 complete`; historical dependency spine: `R0 -> R1 -> B1`

R1.4 keeps the setup/config kernel non-operational beyond the governed artifact chain. Legacy `builder setup` now fails closed and redirects to `builder-setup`. Ambient runtime execution, Goose runtime promotion, deepagents runtime, autonomous writes, source CORE checkout mutation, and commit/push automation remain unpromoted; model/provider calls, MCP/tool invocation, and the CORE demo loop are operational only inside their explicit capability-scoped envelopes.

Similarly, operator-safe promoted patch application and rollback execution remain gated as unpromoted candidate behaviors (though passive patch proposal and apply artifacts exist with improved rollback bundle/evidence).

`OPERATIONALLY_VERIFIED` is a legacy matrix state, not a life-safety or global-runtime clearance. Machine-readable matrix rows now also carry a sharper `assurance_state`: `PASSIVE_ARTIFACT_VERIFIED`, `READ_ONLY_RUNTIME_VERIFIED`, `BOUNDED_EXECUTION_VERIFIED`, `MUTATION_WITH_ROLLBACK_VERIFIED`, `LIVE_PROVIDER_VERIFIED`, `DEMO_ONLY_VERIFIED`, `BLOCKED_BY_EVIDENCE`, or `SAFETY_CRITICAL_PROHIBITED`.

For high-consequence work, the assurance state is authoritative for risk interpretation. A live provider call, a temporary demo loop, and passive candidate specifications are not equivalent just because older rows may share the same legacy completion label.

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
| interactive setup wizard | `NOT_STARTED` | R1 |
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
| HITL patch application | `MERGED_BUT_NOT_OPERATIONAL` | B4 |
| rollback execution | `MERGED_BUT_NOT_OPERATIONAL` | B4 |
| postflight verification | `OPERATIONALLY_VERIFIED` | B1.5 |
| Goose setup | `MERGED_BUT_NOT_OPERATIONAL` | B4 after R0/B3 |
| governed read-only runtime | `OPERATIONALLY_VERIFIED` | B4 |
| Goose readonly runtime | `OPERATIONALLY_VERIFIED` | B5 |
| Goose command proposals | `PASSIVE_FOUNDATION` | B1/B4 |
| deepagents policy/readiness | `PASSIVE_FOUNDATION` | B6 |
| deepagents passive work artifacts | `PASSIVE_FOUNDATION` | B6 |
| deepagents runtime/subagents | `OPERATIONALLY_VERIFIED` | B6 |
| notes/handoff artifacts | `PASSIVE_FOUNDATION` | defer operational memory |
| artifact memory | `PASSIVE_FOUNDATION` | defer operational memory |
| operator quickstart/golden path | `OPERATIONALLY_VERIFIED` | B9 complete |
| CORE demo loop | `OPERATIONALLY_VERIFIED` | demo loop complete |
| platform doctor/status/audit | `PASSIVE_FOUNDATION` | R1 then B1 |
| release proof/quality gates | `PASSIVE_FOUNDATION` | B1 |
| command authority as runtime gate | `OPERATIONALLY_VERIFIED` | B1.5 |
| docs truth enforcement | `PASSIVE_FOUNDATION` | R1 then B1 |

## Corrections

- Passive model routing exists through `builder-model-policy`; provider execution remains unpromoted.
- Legacy operator-managed helpers such as `builder start`, `builder ask`, `builder doctor`, and `builder status` are separate from canonical governed passive lanes.
- Legacy `builder setup` is no longer operator-managed setup execution; it is a fail-closed redirect to the governed `builder-setup` path.
- Canonical governed passive lanes include `builder-config`, `builder-setup plan`, `builder-setup overlay-plan`, `builder-setup rollback-snapshot`, `builder-session`, `builder-profile-pack`, `builder-model-policy`, `builder-orchestration`, `builder-workflow`, `builder-ledger`, `builder-platform`, and `builder-memory`.
- Canonical governed CORE demo execution is limited to `builder-platform demo-loop` and `builder-platform wow`, both of which operate on a temporary detached AssetOverflow/core worktree and not the source CORE checkout.
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
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase prepare --force
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase approve --approve
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase apply
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase verify
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase rollback
uv run builder-platform demo-loop --core-repo /Users/you/Projects/core --output-dir /tmp/builder-ii-core-demo --phase finalize
uv run builder-platform validate-demo-loop /tmp/builder-ii-core-demo/core-demo-loop-report.json
```

## R1.4 update

R1.4 leaves the governed setup apply and rollback slices intact and reconciles the remaining legacy bypass: `builder setup` now fails closed and prints the governed `builder-setup` sequence instead of writing Goose config, `.goosehints`, skills, or recipes. B1, B2, B3, runtime, model/provider, MCP/tool, Goose runtime, deepagents runtime, shell/subprocess execution in the setup path, patch, and autonomous write authority remain unpromoted.

## R1.5 update

R1.5 adds `builder-setup init`, `builder-setup wizard`, `builder onboarding`, and `builder-setup validate-onboarding-intent` to provide a governed onboarding UX over the R1 setup chain. It generates passive onboarding intent reports and prints deferred apply commands only. Setup mutation remains exclusively owned by existing `builder-setup apply --approve-digest`. B1, B2, B3, runtime, model/provider, MCP/tool, Goose runtime, deepagents runtime, shell/subprocess execution in the setup path, patch, and autonomous write authority remain unpromoted.

## R1.6 update

R1.6 completes R1 by introducing `builder-platform r1-closure` and `builder-platform validate-r1-closure`. These commands execute the entire passive config/setup/onboarding chain and emit a canonical, auditable `r1-closure-report.json` alongside the full evidence artifact chain (`config-schema.json`, `config-resolution.json`, `setup-plan.json`, `setup-overlay.json`, `setup-rollback-snapshot.json`, and `onboarding-intent.json`). This proves the R1 golden path while ensuring that setup apply/rollback execution remains explicit and B1/B2/runtime/model/tool/MCP/Goose/deepagents/patch authority remain unpromoted.

B1.1 adds `builder_ii.verification_execution_plan` plus `builder-verify plan` and `builder-verify validate-plan` as a passive verification execution planning surface. B1.2 adds `builder_ii.verification_execution_approval` plus `builder-verify approve-plan` and `builder-verify validate-approval` as a digest-bound HITL approval binding surface. Those planning and approval artifacts remain non-authoritative by themselves. B1.3A adds a receipt contract. B1.3B adds the first bounded approved verification runner for `platform_status`. B1.5 broadens the same fixed-profile, `shell=False`, HITL-bound runner to `docs_audit`, routes the lane through the central command authority gate, and emits a generated postflight sidecar bound to receipt/git preflight/postflight evidence. Arbitrary argv, broad shell execution, live read authority, patching, model/MCP/Goose/deepagents runtime, and B2 write authority remain disabled.

## B7 update

B7 implements `builder_ii.mcp_policy`, `builder_ii.tool_invocation_gateway`, and `builder-mcp` + `builder-tools invoke` to govern explicit low-risk MCP and tool execution. Invocation requires explicitly constructed JSON envelopes validated against a strictly constrained `MCPToolPolicy` (deny-by-default, fixed args, rollback classifications) before execution via the gateway. Receipts are written alongside operational event ledger entries `tool_call_executed`/`tool_call_denied`. Only safe stub operations (`echo`, `date`) are supported as a proof-of-capability. Shell execution, source writes, broader model automation, Goose runtime, deepagents orchestration, and patch application remain unpromoted and fully blocked.

## B8 update

B8 adds `builder_ii.artifact_memory`, `builder_ii.memory_cli`, and the `builder-memory` command group to convert explicit validated artifacts into governed memory atoms, deterministic indexes, lexical search results, and replay-stable reconstruction artifacts. This promotes `artifact memory` from `DESIGN_ONLY` to `PASSIVE_FOUNDATION`. The lane remains artifact-only: hidden memory, vector-store retrieval, autonomous memory writes, model authority, shell execution, runtime activation, and target-repo mutation remain disabled.

## B9 update

B9 completes the Operator Product Polish by introducing the governed local golden path via `builder-platform operator-status`, `builder-platform next`, and `builder-platform golden-path`. These primitives compose a coherent platform UX derived from existing truth boundaries (matrix, ledger, memory, authority) without claiming operational authority, shell access, model execution, or target repo writes. Golden path validation and next-step alignment operate exclusively via artifact generation, explicitly isolating builder-II from autonomous control planes and CORE Workbench coupling.

## CORE demo loop update

The CORE demo loop introduces `builder-platform demo-loop`, `builder-platform validate-demo-loop`, and the recording alias `builder-platform wow`. The loop targets a real AssetOverflow/core checkout by creating a detached temporary worktree from the current CORE `HEAD`, then walks through preflight, repo map, context pack, deterministic planner, HITL patch proposal, explicit approval, patch apply receipt, bounded verification receipt, rollback receipt, final postflight, artifact index, chain verification, and `DEMO_EVIDENCE.md`.

This is not a synthetic product tour. It uses real CORE repository structure and Git state, but the only approved mutation is a temporary documentation marker inside the detached worktree. The source CORE checkout is not mutated. The loop never commits, pushes, starts Goose, calls models, invokes MCP, writes hidden memory, or touches CORE Workbench/UI.


## B1.5 readiness pass update

B1.5 closes the smallest foundational authority gap without promoting ambient autonomy. `builder_ii.command_authority.enforce_command_authority()` is now a central fail-closed runtime gate that allows registered passive commands, denies unknown commands, denies unknown or over-authority effects, and requires HITL binding for HITL-gated lanes. `builder-verify run-approved` consults this gate before crossing subprocess/artifact-write authority. The approved verification runner now supports exactly two fixed profiles, `platform_status` and `docs_audit`; it still rejects arbitrary argv and shell strings. Real verification execution now produces a postflight record sidecar that links the receipt, plan, approval, preflight git fingerprint, postflight git fingerprint, and mutation verdict. This promotes the verification-runner postflight lane only; broad shell, broad Goose autonomy, broad MCP/live tool execution, hidden/autonomous memory, source CORE checkout mutation, commit/push automation, and model-driven file mutation remain unpromoted.
