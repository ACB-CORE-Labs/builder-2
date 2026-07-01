# Deepagents Work Artifacts

## Capability State
Capability state: artifact_only / validation_only

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
2. **Tests**: Validated via `pytest tests/test_deepagents_work_artifacts.py`.
3. **Command surface**: Managed through `builder-deepagents work-plan`, `assign-subagent`, `record-result`, `review-result`, `request-human-gate`, `record-blocked-action`, `proposal-result`, and `validate-work-artifact`.
4. **Failure mode**: Strict digest mismatch detection. Any attempt to escalate state to an active runtime or provide unverified cryptographic hashes fails closed immediately.
5. **Human approval boundary**: The operator must explicitly review all proposed subagent assignments, result summaries, reviews, and requested human gates before acting on them.
6. **Output artifact**: Emits passive JSON ledgers such as `deepagents_work_plan`, `subagent_assignment`, `subagent_result`, `subagent_review`, `human_gate_request`, `blocked_action_record`, `proposal_result`, and validation reports.
7. **Rollback path**: Because the capability is `artifact_only` and does not mutate source code, network state, or active memory, rollback simply requires deleting the emitted JSON artifact files.
8. **Verification path**: Integrity is verified via `builder-deepagents validate-work-artifact`.
