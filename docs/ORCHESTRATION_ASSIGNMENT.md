# Orchestration Assignment

## Capability State
Capability state: artifact_only / validation_only

## Required Negative Space Guardrails
- No autonomous writes by default
- No shell execution
- No model execution unless routed through an approved model gateway / receipt path
- No MCP calls
- No Goose activation
- No CORE Workbench coupling

## The Eight Promotion Gates

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_orchestration_plan.py` and `tests/test_orchestration_dry_run.py`.
3. **Command surface**: Managed through `builder-orchestration render-assignment`, `builder-orchestration validate`, and `builder-orchestration dry-run`.
4. **Failure mode**: Fails closed upon encountering missing refs, unknown kinds, digest mismatches, invalid model recommendations, unsafe governance parameters, or authority escalation attempts.
5. **Human approval boundary**: The operator must explicitly review the deterministic bindings, denied capabilities, required promotions, and expected evidence before attempting any separate execution proposal.
6. **Output artifact**: Emits passive JSON ledgers such as `agent-assignment-plan.json`, `orchestration-assignment-plan.json`, `orchestration-assignment-dry-run.json`, and validation reports.
7. **Rollback path**: As the capability executes nothing, rollback simply requires deleting the emitted JSON artifact files.
8. **Verification path**: Integrity is verified via `builder-orchestration validate`.
