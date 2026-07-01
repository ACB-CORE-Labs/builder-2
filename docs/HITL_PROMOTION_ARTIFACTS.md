# HITL Promotion Bridge Artifacts

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the architectural and operator documentation for `hitl_promotion_artifacts.py` and its related command surfaces. 

## Capability Promotion State

The HITL promotion bridge operates strictly in the `artifact_only` / `validation_only` promotion states (Tier 1). It passively connects Goal 2/Goal 3 proposals to human review/decision records without executing any logic or granting authority.

## The Eight Promotion Gates

To maintain strict governance, this capability satisfies the following constraints:

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_hitl_promotion_artifacts.py`.
3. **Command surface**: Managed through `builder-hitl promotion-request`, `promotion-review`, `promotion-decision`, `approval-boundary`, `rejection-record`, and `validate-promotion`.
4. **Failure mode**: Fails closed on any active state claims or invalid digest mismatches. The validation ensures that the records strictly remain passive metadata ledgers.
5. **Human approval boundary**: The operator explicitly reviews promotion requests, review findings, decisions, and boundaries. No automation can force a promotion.
6. **Output artifact**: Emits passive JSON ledgers such as `promotion_request`, `promotion_review`, `promotion_decision`, `approval_boundary`, `rejection_record`, and validation reports.
7. **Rollback path**: As the capability executes nothing, rollback simply requires deleting the emitted JSON artifact files.
8. **Verification path**: Integrity is verified via `builder-hitl validate-promotion` to ensure valid digest connections.

## Governance & Authority

* **Authority Boundary**: Passive bridge for promotion records only. Does not grant execution authority.
* **Denied Behaviors**:
  - No active execution of the promoted capabilities by the artifact itself.
