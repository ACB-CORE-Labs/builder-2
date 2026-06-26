# Platform snapshot

Platform snapshot records connect an artifact index and a state ledger into one review checkpoint.

They store metadata and digests only.

## CLI

```text
builder-snapshot record artifact-index.json state-ledger.json --snapshot-name main --output platform-snapshot.json
builder-snapshot validate platform-snapshot.json
```

## Verification

```bash
uv run pytest tests/test_platform_checkpoint.py tests/test_platform_checkpoint_cli.py -q
uv run pytest -q
```
