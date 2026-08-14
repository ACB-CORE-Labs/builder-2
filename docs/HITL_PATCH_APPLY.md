# HITL Patch Apply

## Capability State
Capability state: hitl_runtime_candidate

## Required Negative Space Guardrails
- No autonomous writes by default
- No shell execution
- No model execution unless routed through an approved model gateway / receipt path
- No MCP calls
- No Goose activation
- No CORE Workbench coupling

## The Eight Promotion Gates

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_hitl_patch_apply.py`.
3. **Command surface**: Managed through `builder-hitl apply-patch` and `builder-hitl rollback`.
4. **Failure mode**: Aborts closed without touching the target repository if the proposed patch lacks a corresponding cryptographically valid approval record or verification receipt.
5. **Human approval boundary**: The operator must supply explicit `approval` and `verification_receipt` JSON paths proving human sign-off before the patch applies.
6. **Output artifact**: Writes artifacts to the specified `output-dir` reflecting the applied patch status.
7. **Rollback path**: Provides `builder-hitl rollback`, which applies a reverse patch described in a `rollback-plan.json` explicitly verified by the operator.
8. **Verification path**: Verified by inspecting the target repository state post-application, and checking the resulting postflight JSON artifacts.
