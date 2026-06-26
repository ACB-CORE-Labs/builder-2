# State ledger

State ledger records collect promotion decision records into one metadata snapshot.

The ledger records capability names, target states, decision digests, and blocked or approved-for-followup status.

It is metadata-only. It does not enable any capability.

Validation preserves the ledger boundary by requiring:

- a ledger name;
- counts that match ledger entries;
- valid entry status shape;
- runtime execution disabled;
- model execution disabled;
- source writes disabled;
- memory mutation disabled;
- artifact authority disabled;
- CORE Workbench coupling none.

## CLI

```text
builder-state-index record promotion-decision.json --ledger-name main --output state-ledger.json
builder-state-index validate state-ledger.json
```

## Verification

```bash
uv run pytest tests/test_state_ledger_records.py tests/test_state_index_cli.py -q
uv run pytest -q
```
