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

## CLI

The `builder-records` command creates and validates approval record artifacts.

Example create command:

```text
builder-records record PROPOSAL_JSON --decision approved --decided-by operator --reason "ready for later gated handling" --output APPROVAL_RECORD_JSON
```

Example validate command:

```text
builder-records validate APPROVAL_RECORD_JSON
```

## Verification

```bash
uv run pytest tests/test_approval_records.py tests/test_approval_records_cli.py tests/test_approval_record_governance.py -q
uv run pytest -q
```
