# Centralized glossary

## Artifact grammar

### Kind

The structural identifier in a builder-II artifact's `kind` field. A kind binds
data to an explicit schema and validator.

### Spine and chain integrity

The ordered governed artifacts for a session or capability lane. Digest references
bind predecessor bytes and let validators detect substitution or tampering.

### Digest-bound

Bound to byte identity relative to a recorded cryptographic digest. A digest does
not prove that a human reviewed the bytes.

### Human-in-the-loop (HITL)

An explicit operator decision required by a capability contract before a bounded
effect may execute. Approval binds the exact artifact digest; model output is not
approval.

## Three separate state vocabularies

Builder-II has no global active/passive mode that summarizes all authority. State
and authority are capability-scoped across three separate axes.

### Platform completion labels

The matrix uses eight lifecycle labels:

`NOT_STARTED`, `DESIGN_ONLY`, `ARTIFACT_ONLY`, `PASSIVE_FOUNDATION`,
`IMPLEMENTED_ON_BRANCH`, `PR_OPEN`, `MERGED_BUT_NOT_OPERATIONAL`, and
`OPERATIONALLY_VERIFIED`.

These labels describe implementation/completion truth. They are not command
promotion states and do not grant authority.

### Command/capability promotion states

The authority registry uses Tier 0 through Tier 4 plus promotion states defined in
`builder_ii/governance/authority/tier_definitions.py`, including `spec_only`,
`artifact_only`, `operator_managed`, `hitl_runtime_candidate`, and `enabled`.
Promotion state is command/capability metadata, not a matrix lifecycle label.

### Assurance states

Assurance semantics come from `builder_ii/governance/authority/assurance.py`.
They distinguish passive artifact evidence, local-state mutation, read-only
runtime, bounded execution, mutation with rollback, live-provider execution,
demo-only evidence, blocked evidence, and safety-critical prohibition.

`BOUNDED_EXECUTION_VERIFIED` attests the fixed approved invocation envelope; it
does not attest all behavior of code inside that envelope. The verification runner
executes target code with the operator's host privileges and is not containment.

`SAFETY_CRITICAL_PROHIBITED` currently applies to `allows_memory_mutation`, which
registry invariants reject regardless of evidence. It is not a general synonym for
Git push or arbitrary shell.

## Runtime and adapter terms

### Goose

The local operator runtime adapter. Its current manifest modes are `disabled` and
`read_only`; separately governed verification, model, patch, Deep Agents, MCP, and
delivery lanes do not become Goose modes.

### Deep Agents

An optional bounded delegation/runtime adapter. `protocol_fake` supplies
deterministic structural evidence; `optional_deepagents` is a separately gated
native path through the official factory, readiness checks, two-key acknowledgement,
governed gateways, HITL interrupt, and exact-digest resume. Neither grants ambient
write, shell, provider, or tool authority.

### MCP

An inventory-first, deny-by-default adapter seam. Admitted services delegate to
canonical builder-II implementations; MCP does not mint approval or acquire ambient
tool authority.

### WRP

The Workforce Reasoning Platform control plane for digest-bound model routing,
budgeting, assignments, obligations, and governed execution inputs.

### STRATUM

The operator TUI for observing current projections and composing governed command
lines. It does not convert display or composition into execution authority.

## Core doctrine

Planned is not executed. Executed is not verified. Verified is not promoted.
Artifact is not authority. Replay reconstruction is not re-execution. Verification
records the outcome of an exact approved path; it does not prove general program
correctness.
