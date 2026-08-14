# Receipt records

Receipt records capture an operator-observed outcome after a ready preflight record.

They are record-only artifacts. They preserve:

- `record_state = RECORDED_ONLY`
- `current_runtime_state = DISABLED`
- `grants_runtime_authority = false`
- `grants_action_authority = false`
- `artifact_is_authority = false`
- `core_workbench_coupling = NONE`

A receipt record requires:

- a valid ready preflight record;
- an operator identifier;
- at least one evidence reference;
- status of `passed`, `failed`, or `blocked`.

A passed receipt is accepted only when the preflight input is ready and there are no blockers.

## CLI

```text
builder-receipt record PREFLIGHT_JSON --status passed --recorded-by operator --evidence-ref RECEIPT_REF --output RECEIPT_JSON
builder-receipt validate RECEIPT_JSON
```

## Verification

```bash
uv run pytest tests/test_receipt_records.py tests/test_receipt_cli.py -q
uv run pytest -q
```
