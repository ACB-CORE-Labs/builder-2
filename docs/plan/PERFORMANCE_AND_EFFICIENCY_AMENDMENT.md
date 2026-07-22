# Performance and integration amendment

This amendment extends the builder-II master plan. It does not replace the roadmap, promote a runtime mode, or authorize new execution behavior.

builder-II remains a generic governed local agent/developer platform. CORE is one target profile, not the platform identity. CORE Workbench/UI remains outside builder-II. Goose is the preferred local runtime/operator when a runtime mode is eventually promoted. deepagents is an optional planning and subagent harness. Builder-II governance is the sovereign boundary around both.

## Purpose

The mature builder-II vision is larger than the current governed artifact foundation. The end state should coordinate:

- target repositories and target profiles;
- context packs and target bundles;
- prompt, agent, and verification profiles;
- model policy and governed hybrid local/frontier routing;
- Goose session manifests and runtime audit artifacts;
- optional deepagents planning and delegation;
- HITL approvals for command execution and source mutation;
- verification gates, rollback paths, and handoff artifacts.

This amendment identifies the highest-leverage integration and performance tracks needed to reach that mature state without weakening the current governance foundation.

## Current-state boundary

The source of truth for platform state is now the machine-readable capability matrix and docs audit surface in `builder_ii/core/platform_completion_audit.py`, exposed through `builder-platform status`, `builder-platform matrix`, and `builder-platform audit-docs`.

The Truth Report baseline has moved from plan prose into mechanically checkable state labels:

- R0 truth-machine work is represented by the platform completion matrix and docs audit commands.
- R1 config/onboarding work is represented by config source precedence, setup plans, overlay plans, setup apply receipts, rollback snapshots, rollback receipts, onboarding intent, and the `builder-setup init/wizard/apply/rollback/validate-*` surfaces.
- B1 verification-execution work is represented by passive verification plans, digest-bound HITL approvals, bounded `platform_status` execution, receipts, verification ledger indexing, receipt query, integrity, and reconstruction artifacts.

The platform remains denied-by-default. A valid artifact, approval, or receipt does not create authority outside its promoted command boundary.

Validated artifacts are evidence and review objects. They are not authority. They do not authorize:

- model execution outside the governed provider gateway;
- agent construction outside the governed deepagents runtime boundary;
- Goose runtime start outside readonly runtime receipts;
- deepagents construction outside promoted runtime receipts;
- command execution beyond the specific approved envelope;
- shell execution;
- source mutation beyond digest-approved setup or patch application boundaries;
- hidden memory mutation;
- commits or pushes;
- pull request creation;
- source collection, web search, or live MCP execution without separate promotion.

Any future capability must move through the promotion ladder with docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.

## Strategic priorities

| Priority | Track | Purpose | Current posture |
| --- | --- | --- | --- |
| 1 | Cross-layer integration contracts | Define artifact boundaries between builder-II governance, verification execution, patch authority, read authority, Goose runtime sessions, optional deepagents planning, model/provider calls, tool/MCP calls, memory, and operator UX. | Immediate spine; must track the capability matrix, not stale prose. |
| 2 | Model routing and hybrid execution policy | Govern when local MLX models, frontier models, or no model should be used. | Passive policy exists and B6 provider gateway is promoted; expansion remains artifact/receipt-first. |
| 3 | Governance usability | Keep HITL gates strong without making ordinary workflows unusable. | B9 must generate operator UX from truth matrix, command authority, receipts, and ledger evidence. |
| 4 | Artifact contracts and validation quality | Keep schemas precise, stable, replayable, and audit-friendly. | Continue current foundation; no schema rewrite without migration and parity evidence. |
| 5 | Context and memory management | Manage long sessions, subagent handoffs, and summarization without hiding provenance. | Artifact memory is `PASSIVE_FOUNDATION`; operational memory waits for B8 promotion. |
| 6 | Testing and reliability | Add cross-layer denial tests, artifact compatibility tests, and runtime audit validation. | Required before every authority promotion. |
| 7 | Operator documentation | Keep the platform usable and honest about what is implemented. | Must be generated or auditable against `builder-platform matrix/audit-docs`. |
| 8 | Performance and resource management | Improve throughput and Apple Silicon efficiency only where measurement proves value. | Candidate track, not an enabled capability. |

## PR ladder spine after the Truth Report baseline

This amendment intentionally keeps a PR-level execution spine tied to the state labels. The canonical state must be checked against `builder-platform matrix` before starting any slice.

```text
R0 -> R1 -> B1
-> B2 HITL patch apply + rollback
-> B3 governed read runtime
-> B4 Goose readonly runtime
-> B5 deepagents runtime harness
-> B6 model/provider gateway
-> B7 tool/MCP gateway
-> B8 defer operational memory promotion
-> B9 operator golden path
```

Current ladder interpretation:

| Slice | Promotion target | Current planning implication |
| --- | --- | --- |
| R0 | Truth machine and docs audit | Treat the matrix and audit-docs commands as the amendment's truth source. |
| R1 | Config/onboarding kernel | Treat setup schema, source precedence, apply receipts, rollback receipts, and onboarding intent as existing governed surfaces, not future design. |
| B1 | Verification execution chain | Use the verification plan -> approval -> bounded runner -> receipt -> ledger -> reconstruction chain as the immediate authority grammar for later slices. |
| B2 | HITL patch apply + rollback | Patch work must bind patch digest, clean git state, approval, rollback artifact, verification receipt, postflight diff, receipt, ledger, and rollback path. |
| B3 | Governed read runtime | Read authority must stay target-bound, budgeted, secret-aware, receipt-producing, and ledger-compatible. |
| B4 | Goose readonly runtime | Goose promotion begins readonly and receipt-bound; Goose must not inherit shell, write, or patch authority by implication. |
| B5 | deepagents runtime harness | deepagents remains optional; subagent work must produce proposal/result receipts and may not bypass builder-II governance. |
| B6 | Model/provider gateway | Model routing is no longer merely a future RFC; provider calls must flow through governed envelopes, prompt/context digests, budget controls, receipts, and replay declarations. |
| B7 | Tool/MCP gateway | Low-risk tool invocation and MCP policy must remain effect-classified; live MCP execution needs its own inventory, policy, envelope, receipt, and rollback/no-rollback proof. |
| B8 | Artifact memory operational promotion | Existing atoms, indexes, deterministic search, and reconstruction are passive; operational memory must preserve source refs, staleness, review state, and no hidden mutation. |
| B9 | Operator golden path | Operator UX must be generated from the truth matrix, setup state, command authority, receipts, ledger, memory artifacts, and denial proofs. |

## Performance track A: Rust artifact validation and processing

Rust-backed validation may become valuable once artifact contracts stabilize and Python validation or artifact processing becomes a measurable bottleneck.

The first Rust work should be a measured candidate track, not a rewrite.

Required sequence:

1. Confirm the relevant capability state from `builder-platform matrix`.
2. Define artifact validation hot paths.
3. Add timing and size benchmarks for existing Python validation.
4. Identify real bottlenecks.
5. Introduce a Rust crate only for stable schemas.
6. Keep Python validation as the reference implementation until parity is proven.
7. Require deterministic parity tests, malformed-artifact tests, and failure-mode tests.
8. Promote only after the capability promotion rule is satisfied.

Rust validation must not be promoted ahead of the authority spine it serves. Treat it as a candidate accelerator after B6 provider-gateway evidence exists and after the target schema family is stable enough to benchmark without changing semantics.

Allowed first surfaces:

- benchmark artifacts;
- validation parity reports;
- schema compatibility tests;
- optional local acceleration behind explicit commands.

Denied by default:

- replacing Python validation without parity evidence;
- adding Rust runtime authority;
- adding shell execution or source mutation authority;
- making Rust a required dependency before the measured value is clear.

## Performance track B: MLX context compression and summarization

MLX and Apple Silicon UMA are strategically aligned with builder-II's local-first posture. The first safe use is artifact-only context compression, not canonical memory.

Summaries are derived, lossy, and review-required. They must never masquerade as source truth.

Required artifact fields for any future context summary artifact:

- source paths;
- source hashes or git refs;
- selected target profile;
- model alias and backend;
- prompt or profile used;
- compression goal;
- known omissions;
- claim boundary;
- review-required flag;
- `artifact_is_authority: false`.

MLX compression must be sequenced after the B6 model/provider gateway is operational for the relevant model lane. Any memory-bearing use must also wait for B8 operational promotion and must preserve source refs, review state, staleness, reconstruction path, and denial of hidden durable memory writes.

Allowed first surfaces:

- `builder-context summarize` candidate design;
- context summary artifacts;
- provenance-preserving compression reports;
- benchmark reports for token, memory, and latency reduction.

Denied by default:

- durable memory mutation;
- replacing source files, git state, or validated artifacts as canonical truth;
- hidden model calls;
- summary-only verification claims;
- automatic frontier escalation.

## Model routing and hybrid execution phase

Model routing now has a passive policy surface and a governed provider gateway path. Future work should strengthen the policy/gateway contract rather than introduce a second router.

The governing artifact set should specify:

- task class;
- target profile;
- allowed model lanes;
- forbidden model lanes;
- local-first preference;
- privacy and cost boundary;
- frontier escalation rule;
- required human approval for nonlocal calls;
- expected evidence from each model lane;
- fallback behavior;
- audit artifact requirements;
- prompt/context digest;
- receipt schema;
- replay declaration;
- budget and rate-limit evidence.

Denied by default:

- hidden external model calls;
- silent cost-bearing execution;
- routing that bypasses target profiles, verification profiles, approvals, or audit artifacts;
- treating model output as authority without verification.

## Cross-layer integration contracts

The highest-risk integration boundary is not any single tool. It is the contract between:

```text
builder-II governance
-> target/context/model/agent/verification artifacts
-> HITL proposal and approval artifacts
-> verification execution receipts and ledger reconstruction
-> patch/read/Goose/deepagents/model/tool gateways
-> memory and handoff artifacts
-> operator golden-path UX
-> audit, verification, rollback, and replay artifacts
```

Each boundary should be validated independently before runtime behavior is promoted.

Required cross-layer checks:

- target profile compatibility;
- agent profile compatibility;
- verification profile compatibility;
- quality gate compatibility;
- command risk classification;
- approval artifact matching;
- audit artifact completeness;
- rollback path presence;
- receipt and ledger binding;
- replay declaration;
- denied-action tests;
- no hidden writes;
- no hidden shell;
- no hidden model/tool escalation.

## Artifact memory and CORE-inspired retrieval

Artifact memory is no longer design-only. The current governed surface includes explicit memory atoms, indexes, deterministic search, and replay-stable reconstruction artifacts.

Operational memory remains separate from passive artifact memory. Hidden memory, opaque vector stores, autonomous durable writes, and memory mutation by model output remain denied.

CORE-inspired reconstruction-over-storage and exact/persistent retrieval patterns may eventually inform experimental builder-II memory surfaces or CORE-specific target adapters.

Revisit those patterns only after:

- B6 model/provider gateway is operational for the relevant model lane;
- B8 defines an operational memory promotion boundary;
- runtime audit artifacts are stable;
- context summary artifacts are provenance-safe;
- no-runtime and HITL boundaries remain enforceable;
- an experiment can prove value without making builder-II a CORE runtime.

## Updated execution posture

Performance and efficiency are first-class, but they do not outrank governance.

Correct ordering:

1. Read the live capability matrix and docs audit output.
2. Preserve the R0/R1/B1 truth baseline and treat B2 through B9 as the authority spine.
3. Promote the next slice only through exact docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, verification path, command authority entry, and ledger/replay integration where operational.
4. Treat Rust validation and MLX compression as candidate tracks after the relevant gateway exists and measured bottlenecks justify them.
5. Keep operator documentation generated from or auditable against state labels, not hand-written completion claims.
6. Promote runtime behavior only through explicit HITL and verification gates.

## Non-goals

This amendment does not authorize:

- autonomous writes;
- arbitrary shell execution;
- hidden model execution;
- source collection or search execution;
- deepagents as a hard dependency;
- Goose runtime activation outside promoted readonly receipts;
- CORE Workbench/UI coupling;
- CORE-specific behavior outside the `core` target profile;
- Deephaven-related changes.

## Governing sentence

builder-II is a generic governed local agent/developer platform. Its mature form coordinates target profiles, context packs, model policy, artifact contracts, Goose runtime sessions, optional deepagents planning, HITL approvals, verification gates, audit trails, and handoff records. CORE is one target profile, not the platform identity. Performance tracks such as Rust validation, MLX context compression, and hybrid model routing are first-class only when introduced through the same promotion ladder: documented, tested, artifact-producing, rollback-aware, verification-bound, and unable to grant hidden runtime authority.
