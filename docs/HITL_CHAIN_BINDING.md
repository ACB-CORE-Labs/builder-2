# HITL Chain Binding

`builder_ii.hitl_chain_binding` is passive chain metadata for HITL governance artifacts and grants no execution authority.

It binds the canonical evidence slots:

- proposal
- approval
- preflight
- request
- receipt
- postflight
- verification
- optional evidence bundle

The artifact is design-only:

- it does not grant execution authority;
- it does not execute commands;
- it does not start Goose;
- it does not start deepagents;
- it does not mutate source;
- it does not mutate memory.

Validation is fail-closed. Every required slot must be present, the slot kind must match the declared artifact kind, the path must be a safe relative path, and each digest must be a valid SHA-256 hex string. The disk verification helper resolves paths inside an explicit base directory and rejects path traversal and symlink escapes.

## Verification

```bash
uv run pytest tests/test_hitl_chain_binding.py -q
```
