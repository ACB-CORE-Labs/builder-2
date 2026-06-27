# Bounded read-only inspection promotion

This is the design gate for a later bounded inspection candidate.

It does not add runtime behavior.

Required state:

- `DESIGN_ONLY`
- `DISABLED`
- `BLOCKED_UNTIL_APPROVED`

The future candidate must be target-bound, verification-bound, git-state-bound, and explicitly scoped by operator-provided paths and output artifacts.

The tests define the complete gate list and denied-action list.

## Verification

```bash
uv run pytest tests/test_readonly_inspection_promotion.py -q
uv run pytest -q
```
