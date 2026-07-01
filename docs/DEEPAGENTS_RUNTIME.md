# Deepagents Runtime Harness

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the architectural and operator documentation for `deepagents_runtime.py` and its related command surfaces. 

## Capability Promotion State

The deepagents runtime operates strictly in the `operator_managed` promotion state. It is an interactive terminal helper for executing passive subagent plans under strict operator supervision, and it explicitly disables write authority.

## The Eight Promotion Gates

To maintain strict governance, this capability satisfies the following constraints:

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_deepagents_runtime.py`.
3. **Command surface**: Managed through `builder-deepagents run-plan` and `builder-deepagents collect-results`.
4. **Failure mode**: Fails closed if the runtime attempts to execute outside of a read-only or operator-managed envelope. Any exception during subagent execution aborts the harness without mutating system state.
5. **Human approval boundary**: Explicit operator invocation from the active terminal is required. The runtime does not start automatically or autonomously.
6. **Output artifact**: Emits a `deepagents_runtime_envelope` and subagent receipts.
7. **Rollback path**: As the capability does not grant write authority to the target repository, rollback consists of deleting the emitted JSON envelope and receipt artifacts.
8. **Verification path**: Output is verified by collecting the results via `builder-deepagents collect-results` to confirm the planned outcomes match the runtime outputs.

## Governance & Authority

* **Authority Boundary**: Operator-managed helper for deepagents planning. No autonomous source mutation or target repo writes are permitted.
* **Denied Behaviors**:
  - `builder-deepagents delegate` remains `forbidden_unpromoted`.
  - No active runtime initiation without operator command.
