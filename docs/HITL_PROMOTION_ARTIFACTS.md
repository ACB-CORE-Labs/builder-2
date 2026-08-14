# HITL Promotion Bridge Artifacts

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
2. **Tests**: Validated via `pytest tests/test_hitl_promotion_artifacts.py`.
3. **Command surface**: Managed through `builder-hitl promotion-request`, `promotion-review`, `promotion-decision`, `approval-boundary`, `rejection-record`, and `validate-promotion`.
4. **Failure mode**: Fails closed on any active state claims or invalid digest mismatches. The validation ensures that the records strictly remain passive metadata ledgers.
5. **Human approval boundary**: The operator explicitly reviews promotion requests, review findings, decisions, and boundaries. No automation can force a promotion.
6. **Output artifact**: Emits passive JSON ledgers such as `promotion_request`, `promotion_review`, `promotion_decision`, `approval_boundary`, `rejection_record`, and validation reports.
7. **Rollback path**: As the capability executes nothing, rollback simply requires deleting the emitted JSON artifact files.
8. **Verification path**: Integrity is verified via `builder-hitl validate-promotion` to ensure valid digest connections.
