# Handoff bundles

Handoff bundle records package a handoff summary and artifact digests into one portable metadata record.

They store paths, hashes, target metadata, agent profile metadata, notes, and optional include references.

A complete bundle requires a valid complete handoff summary and a bundle name.

## CLI

```text
builder-handoff record SUMMARY_JSON --bundle-name HANDOFF_NAME --notes "handoff notes" --output HANDOFF_JSON
builder-handoff validate HANDOFF_JSON
```

## Verification

```bash
uv run pytest tests/test_handoff_bundle_records.py tests/test_handoff_bundle_cli.py -q
uv run pytest -q
```
