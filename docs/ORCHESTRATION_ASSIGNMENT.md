# Orchestration Assignment

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the architectural and operator documentation for `orchestration_assignment.py` and its related command surfaces. 

## Capability Promotion State

The orchestration assignment capability operates strictly in the `artifact_only` / `validation_only` promotion states (Tier 1). It passively binds targets, tasks, agents, and policies by SHA-256 for Goal 2 agent assignment.

## The Eight Promotion Gates

To maintain strict governance, this capability satisfies the following constraints:

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_orchestration_plan.py` and `tests/test_orchestration_dry_run.py`.
3. **Command surface**: Managed through `builder-orchestration render-assignment`, `builder-orchestration validate`, and `builder-orchestration dry-run`.
4. **Failure mode**: Fails closed upon encountering missing refs, unknown kinds, digest mismatches, invalid model recommendations, unsafe governance parameters, or authority escalation attempts.
5. **Human approval boundary**: The operator must explicitly review the deterministic bindings, denied capabilities, required promotions, and expected evidence before attempting any separate execution proposal.
6. **Output artifact**: Emits passive JSON ledgers such as `agent-assignment-plan.json`, `orchestration-assignment-plan.json`, `orchestration-assignment-dry-run.json`, and validation reports.
7. **Rollback path**: As the capability executes nothing, rollback simply requires deleting the emitted JSON artifact files.
8. **Verification path**: Integrity is verified via `builder-orchestration validate`.

## Governance & Authority

* **Authority Boundary**: Passive binding layer only. Cannot execute models/tools/shell, invoke Goose/deepagents/MCP, mutate target repositories, or grant authority.
* **Denied Behaviors**:
  - Unpromoted or Tier 2+ commands referenced in the assignment cause validation to fail closed.
