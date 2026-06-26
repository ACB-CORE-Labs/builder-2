# Handoff summaries

Handoff summaries connect four artifact files by path and digest.

They are for review and transfer notes.

## CLI

```text
builder-chain record PROPOSAL_JSON APPROVAL_JSON PREFLIGHT_JSON RECEIPT_JSON --summary handoff --output CHAIN_JSON
builder-chain validate CHAIN_JSON
```

## Verification

```bash
uv run pytest tests/test_chain_summary_records.py tests/test_chain_cli.py -q
uv run pytest -q
```
