# Artifact Chain Verification

## Platform Identity & Scope

builder-II is a generic governed local agent/developer platform. It is not CORE, not CORE Workbench/UI/UX, and not a second CORE runtime. CORE is only a target profile.

This document serves as the architectural and operator documentation for `artifact_chain_verification.py` and its related command surfaces. 

## Capability Promotion State

The artifact chain verification capability operates strictly in the `validation_only` promotion state (Tier 1). It traces hash and cryptographic linkage across evidence sequences to prove integrity, without granting runtime permissions.

## The Eight Promotion Gates

To maintain strict governance, this capability satisfies the following constraints:

1. **Docs**: This document serves as the formal boundary specification.
2. **Tests**: Validated via `pytest tests/test_artifact_chain_verification.py`.
3. **Command surface**: Managed through the `builder-chain` CLI entrypoint.
4. **Failure mode**: Fails closed if any broken links, invalid schemas, or missing cryptographic signatures are detected in the evidence sequence.
5. **Human approval boundary**: The operator runs `builder-chain` to explicitly audit the evidence trail integrity before any action relying on that chain is approved.
6. **Output artifact**: Emits a validation report JSON and/or stdout summary of the chain status.
7. **Rollback path**: Passive validation process; no rollback is required beyond deleting the invalid artifacts and correcting the chain generator process.
8. **Verification path**: Integrity of the verifier itself is checked via `pytest tests/test_artifact_chain_verification.py` and manual confirmation of the validation output.

## Governance & Authority

* **Authority Boundary**: Validates cryptographic and hash linkages only. Does not grant authority.
* **Denied Behaviors**:
  - A valid artifact chain verification report does not authorize model execution, agent construction, shell execution, source mutation, or any active runtime behavior.
