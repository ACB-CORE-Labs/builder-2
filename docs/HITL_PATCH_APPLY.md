# HITL Patch Apply

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the architectural and operator documentation for `hitl_patch_apply.py` and its related command surfaces. 

## Capability Promotion State

The HITL patch application capability operates in the `hitl_runtime_candidate` / `operator_managed` promotion states (Tier 3 / Tier 2). It provides controlled target repository patch application strictly gated by cryptographic human approvals.

## The Eight Promotion Gates

To maintain strict governance, this capability satisfies the following constraints:

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_hitl_patch_apply.py`.
3. **Command surface**: Managed through `builder-hitl apply-patch` and `builder-hitl rollback`.
4. **Failure mode**: Aborts closed without touching the target repository if the proposed patch lacks a corresponding cryptographically valid approval record or verification receipt.
5. **Human approval boundary**: The operator must supply explicit `approval` and `verification_receipt` JSON paths proving human sign-off before the patch applies.
6. **Output artifact**: Writes artifacts to the specified `output-dir` reflecting the applied patch status.
7. **Rollback path**: Provides `builder-hitl rollback`, which applies a reverse patch described in a `rollback-plan.json` explicitly verified by the operator.
8. **Verification path**: Verified by inspecting the target repository state post-application, and checking the resulting postflight JSON artifacts.

## Governance & Authority

* **Authority Boundary**: Target repository mutation requires cryptographically linked approval and verification receipt.
* **Denied Behaviors**:
  - Unprompted autonomous target source writes are disabled.
  - Automated pull request or commit creation is forbidden.
