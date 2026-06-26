# State ledger

State ledger records collect promotion decision records into one metadata snapshot.

The ledger records capability names, target states, decision digests, and blocked or approved-for-followup status.

It is metadata-only. It does not enable any capability.

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
