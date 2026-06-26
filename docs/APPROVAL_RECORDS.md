# Approval records

Approval records capture an operator decision for a proposal artifact.

They are record-only artifacts. They preserve:

- `record_state = RECORDED_ONLY`
- `current_runtime_state = DISABLED`
- `grants_runtime_authority = false`
- `grants_action_authority = false`
- `artifact_is_authority = false`
- `core_workbench_coupling = NONE`

An approval record is evidence of human review. It is not standalone agent authority.

## Verification

```bash
uv run pytest tests/test_approval_records.py -q
uv run pytest -q
```
