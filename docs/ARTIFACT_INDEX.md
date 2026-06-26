# Artifact index

Artifact index records scan a directory of JSON artifact files and record metadata for each known governed artifact.

The index records:

- relative path;
- SHA-256 digest;
- byte count;
- artifact kind;
- schema version;
- known/valid flags;
- validation errors.

It is metadata-only and does not activate artifact authority.

## CLI

```text
builder-index record .builder/artifacts --output .builder/artifacts/artifact-index.json
builder-index record .builder/artifacts --recursive --output .builder/artifacts/artifact-index.json
builder-index validate .builder/artifacts/artifact-index.json
```

## Verification

```bash
uv run pytest tests/test_artifact_index_records.py tests/test_artifact_index_cli.py -q
uv run pytest -q
```
