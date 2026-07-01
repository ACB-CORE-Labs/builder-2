# Deepagents Work Artifacts

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the architectural and operator documentation for `deepagents_work_artifacts.py` and its related command surfaces. 

## Capability Promotion State

The deepagents work artifacts capability operates strictly in the `artifact_only` / `validation_only` promotion states. It is a passive capability for planning and delegating deepagents-style work, and generating validation boundaries.

## The Eight Promotion Gates

To maintain strict governance, this capability satisfies the following constraints:

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_deepagents_work_artifacts.py`.
3. **Command surface**: Managed through `builder-deepagents work-plan`, `assign-subagent`, `record-result`, `review-result`, `request-human-gate`, `record-blocked-action`, `proposal-result`, and `validate-work-artifact`.
4. **Failure mode**: Strict digest mismatch detection. Any attempt to escalate state to an active runtime or provide unverified cryptographic hashes fails closed immediately.
5. **Human approval boundary**: The operator must explicitly review all proposed subagent assignments, result summaries, reviews, and requested human gates before acting on them.
6. **Output artifact**: Emits passive JSON ledgers such as `deepagents_work_plan`, `subagent_assignment`, `subagent_result`, `subagent_review`, `human_gate_request`, `blocked_action_record`, `proposal_result`, and their respective validation reports.
7. **Rollback path**: Because the capability is `artifact_only` and does not mutate source code, network state, or active memory, rollback simply requires deleting the emitted JSON artifact files.
8. **Verification path**: Integrity is verified via `builder-deepagents validate-work-artifact`.

## Governance & Authority

* **Authority Boundary**: Passive work planning only. No subagent construction, no LLM calls, no shell execution, no memory mutation, and no authority grant.
* **Denied Behaviors**:
  - `builder-deepagents delegate` remains `forbidden_unpromoted`.
  - No automated runtime initiation.
  - No unauthorized artifact tampering.
