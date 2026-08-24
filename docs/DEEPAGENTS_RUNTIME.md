# Deepagents Runtime Harness

## Capability State
Capability state: operator_managed

## Required Negative Space Guardrails
- No autonomous writes by default
- No shell execution
- No model execution unless routed through an approved model gateway / receipt path
- No MCP calls
- No Goose activation
- No CORE Workbench coupling
- Native deepagents construction remains out of scope and is not promoted; only the governed optional backend readiness gate exists.

## The Eight Promotion Gates

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_deepagents_runtime.py`.
3. **Command surface**: Managed through `builder-deepagents run-plan` and `builder-deepagents collect-results`.
4. **Failure mode**: Fails closed if the runtime attempts to execute outside of a read-only or operator-managed envelope. Any exception during subagent execution aborts the harness without mutating system state.
5. **Human approval boundary**: Explicit operator invocation from the active terminal is required. The runtime does not start automatically or autonomously.
6. **Output artifact**: Emits a `deepagents_runtime_envelope` and subagent receipts.
7. **Rollback path**: As the capability does not grant write authority to the target repository, rollback consists of deleting the emitted JSON envelope and receipt artifacts.
8. **Verification path**: `builder-deepagents replay-run` reconstructs run state from recorded events. It never reruns backend, model, or tool work; replay is not deterministic re-execution.
