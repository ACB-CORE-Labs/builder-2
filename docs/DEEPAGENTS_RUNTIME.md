# Deepagents Runtime Harness

## Capability state

`deepagents runtime/subagents` is `OPERATIONALLY_VERIFIED` with
`BOUNDED_EXECUTION_VERIFIED` assurance in the current platform matrix. This is a
capability-scoped claim, not ambient agent authority.

- `protocol_fake` is the deterministic structural/protocol lane.
- `optional_deepagents` is the bounded native lane through the official factory,
  readiness gate, two-key native acknowledgement, WRP children, governed model/tool
  gateways, mandatory HITL interrupt, and exact-digest persisted-state resume.
- Neither lane grants autonomous writes, generic shell, direct provider access, or
  general tool authority.

## Required Negative Space Guardrails
- No autonomous writes by default
- No shell execution
- No model execution unless routed through an approved model gateway / receipt path
- No MCP calls
- No Goose activation
- No CORE Workbench coupling
- Native construction exists only inside the bounded `optional_deepagents` path described above.

## The Eight Promotion Gates

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_deepagents_runtime.py`.
3. **Command surface**: The runtime trunk is `execution-candidate` →
   `approve-candidate` → `run-approved` → `replay-run` → `evidence-bundle`;
   `run-plan` remains a non-executing structural projection.
4. **Failure mode**: Fails closed if the runtime attempts to execute outside of a read-only or operator-managed envelope. Any exception during subagent execution aborts the harness without mutating system state.
5. **Human approval boundary**: `run-approved` requires the exact digest-bound candidate approval and the native path's separate readiness/two-key conditions. The runtime does not start automatically or autonomously.
6. **Output artifact**: Emits a `deepagents_runtime_envelope` and subagent receipts.
7. **Rollback path**: The runtime has no target-repository mutation authority, so no target rollback is claimed. Emitted proposals, receipts, and events remain evidence rather than being deleted as a substitute for rollback.
8. **Verification path**: `builder-deepagents replay-run` reconstructs run state from recorded events. It never reruns backend, model, or tool work; replay is not deterministic re-execution.
