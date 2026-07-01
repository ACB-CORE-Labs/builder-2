# Artifact Chain Verification

## Capability State
Capability state: validation_only

## Required Negative Space Guardrails
- No autonomous writes by default
- No shell execution
- No model execution unless routed through an approved model gateway / receipt path
- No MCP calls
- No Goose activation
- No CORE Workbench coupling

## The Eight Promotion Gates

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_artifact_chain_verification.py`.
3. **Command surface**: Managed through the `builder-chain` CLI entrypoint.
4. **Failure mode**: Fails closed if any broken links, invalid schemas, or missing cryptographic signatures are detected in the evidence sequence.
5. **Human approval boundary**: The operator runs `builder-chain` to explicitly audit the evidence trail integrity before any action relying on that chain is approved.
6. **Output artifact**: Emits a validation report JSON and/or stdout summary of the chain status.
7. **Rollback path**: Passive validation process; no rollback is required beyond deleting the invalid artifacts and correcting the chain generator process.
8. **Verification path**: Integrity of the verifier itself is checked via `pytest tests/test_artifact_chain_verification.py` and manual confirmation of the validation output.
