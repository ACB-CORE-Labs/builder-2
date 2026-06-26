# Performance and integration amendment

This amendment extends the builder-II master plan. It does not replace the roadmap, promote a runtime mode, or authorize new execution behavior.

builder-II remains a generic governed local agent/developer platform. CORE is one target profile, not the platform identity. CORE Workbench/UI remains outside builder-II. Goose is the preferred local runtime/operator when a runtime mode is eventually promoted. deepagents is an optional planning and subagent harness. Builder-II governance is the sovereign boundary around both.

## Purpose

The mature builder-II vision is larger than the current no-runtime foundation. The end state should coordinate:

- target repositories and target profiles;
- context packs and target bundles;
- prompt, agent, and verification profiles;
- model policy and eventual hybrid local/frontier routing;
- Goose session manifests and runtime audit artifacts;
- optional deepagents planning and delegation;
- HITL approvals for command execution and source mutation;
- verification gates, rollback paths, and handoff artifacts.

This amendment identifies the highest-leverage integration and performance tracks needed to reach that mature state without weakening the current governance foundation.

## Current-state boundary

The current platform remains no-runtime by default.

Validated artifacts are evidence and review objects. They are not authority. They do not authorize:

- model execution;
- agent construction;
- Goose runtime start;
- deepagents construction;
- command execution;
- shell execution;
- source mutation;
- memory mutation;
- commits or pushes;
- pull request creation;
- source collection, web search, or MCP execution.

Any future capability must move through the promotion ladder with docs, tests, command surface, failure mode, human approval boundary, output artifact, rollback path, and verification path.

## Strategic priorities

| Priority | Track | Purpose | Current posture |
| --- | --- | --- | --- |
| 1 | Cross-layer integration contracts | Define the artifact boundaries between builder-II governance, Goose runtime sessions, and optional deepagents planning. | First-class near-term work. |
| 2 | Model routing and hybrid execution policy | Define when local MLX models, frontier models, or no model should be used. | Policy/artifact surface first; no automatic calls. |
| 3 | Governance usability | Keep HITL gates strong without making ordinary workflows unusable. | Design and UX work before runtime enablement. |
| 4 | Artifact contracts and validation quality | Keep schemas precise, stable, replayable, and audit-friendly. | Continue current foundation. |
| 5 | Context and memory management | Manage long sessions, subagent handoffs, and summarization without hiding provenance. | Artifact-only compression first. |
| 6 | Testing and reliability | Add cross-layer denial tests, artifact compatibility tests, and runtime audit validation. | Required before promotion. |
| 7 | Operator documentation | Keep the platform usable and honest about what is implemented. | Immediate reconciliation work. |
| 8 | Performance and resource management | Improve throughput and Apple Silicon efficiency only where measurement proves value. | Candidate track, not an enabled capability. |

## Performance track A: Rust artifact validation and processing

Rust-backed validation may become valuable once artifact contracts stabilize and Python validation or artifact processing becomes a measurable bottleneck.

The first Rust work should be a measured candidate track, not a rewrite.

Required sequence:

1. Define artifact validation hot paths.
2. Add timing and size benchmarks for existing Python validation.
3. Identify real bottlenecks.
4. Introduce a Rust crate only for stable schemas.
5. Keep Python validation as the reference implementation until parity is proven.
6. Require deterministic parity tests, malformed-artifact tests, and failure-mode tests.
7. Promote only after the capability promotion rule is satisfied.

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

Model routing deserves its own phase because it will govern local MLX models and optional frontier models.

The first implementation should be a policy artifact, not an automatic router.

A future routing-policy artifact should specify:

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
- audit artifact requirements.

Denied by default:

- hidden external model calls;
- silent cost-bearing execution;
- routing that bypasses target profiles, verification profiles, approvals, or audit artifacts;
- treating model output as authority without verification.

## Cross-layer integration contracts

The highest-risk integration boundary is not any single tool. It is the contract between:

```text
builder-II governance
→ target/context/model/agent/verification artifacts
→ Goose session manifests
→ optional deepagents planning artifacts
→ approved runtime actions
→ audit, verification, rollback, and handoff artifacts
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
- denied-action tests;
- no hidden writes;
- no hidden shell;
- no hidden model/tool escalation.

## Future exploration: CORE-inspired memory and retrieval

CORE-inspired reconstruction-over-storage and exact/persistent retrieval patterns may eventually inform experimental builder-II memory surfaces or CORE-specific target adapters.

They are explicitly deferred.

Revisit only after:

- runtime audit artifacts are stable;
- context summary artifacts are provenance-safe;
- model routing policy exists;
- no-runtime and HITL boundaries remain enforceable;
- an experiment can prove value without making builder-II a CORE runtime.

## Updated execution posture

Performance and efficiency are first-class, but they do not outrank governance.

Correct ordering:

1. Reconcile platform identity and documentation.
2. Finish Goose session manifest alignment.
3. Add read-only runtime candidate design and audit artifact schema.
4. Add cross-layer compatibility and denied-action tests.
5. Introduce model routing as a policy/artifact surface.
6. Add measured Rust validation and MLX context-compression candidates where evidence supports them.
7. Promote runtime behavior only through explicit HITL and verification gates.

## Non-goals

This amendment does not authorize:

- autonomous writes;
- arbitrary shell execution;
- hidden model execution;
- source collection or search execution;
- deepagents as a hard dependency;
- Goose runtime activation;
- CORE Workbench/UI coupling;
- CORE-specific behavior outside the `core` target profile;
- Deephaven-related changes.

## Governing sentence

builder-II is a generic governed local agent/developer platform. Its mature form coordinates target profiles, context packs, model policy, artifact contracts, Goose runtime sessions, optional deepagents planning, HITL approvals, verification gates, audit trails, and handoff records. CORE is one target profile, not the platform identity. Performance tracks such as Rust validation, MLX context compression, and hybrid model routing are first-class only when introduced through the same promotion ladder: documented, tested, artifact-producing, rollback-aware, verification-bound, and unable to grant hidden runtime authority.
